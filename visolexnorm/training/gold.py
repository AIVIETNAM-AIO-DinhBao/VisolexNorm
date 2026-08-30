"""Fine-tune BARTpho-syllable on ViLexNorm gold Train and evaluate on Dev.

Designed for Kaggle GPU. It deliberately never reads the ViLexNorm Test split.

Example:
python -m scripts.training train --model model_a \
  --data-dir /kaggle/input/visolexnorm-processed \
  --config configs/model_a_config.json \
  --work-dir /kaggle/working
"""

from __future__ import annotations

import json
import platform
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from visolexnorm.common.io import read_jsonl, write_jsonl
from visolexnorm.common.progress import log_event

if TYPE_CHECKING:
    from datasets import Dataset


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def require_gold_records(records: list[dict[str, Any]], split: str) -> None:
    required = {"id", "input_text", "target_text", "dataset", "split", "label_source"}
    for index, record in enumerate(records, start=1):
        if not required <= record.keys():
            raise ValueError(f"{split} record {index} is missing required fields")
        if record["dataset"] != "ViLexNorm" or record["split"] != split:
            raise ValueError(f"{split} record {index} has incorrect dataset/split")
        if record["label_source"] != "human" or not record["input_text"] or not record["target_text"]:
            raise ValueError(f"{split} record {index} is not a valid gold pair")


def run_gold_training(args: Namespace) -> None:
    try:
        import numpy as np
        import torch
        import transformers
        from datasets import Dataset
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            DataCollatorForSeq2Seq,
            EarlyStoppingCallback,
            Seq2SeqTrainer,
            Seq2SeqTrainingArguments,
            set_seed,
        )
    except ImportError as error:
        raise SystemExit(
            "Missing training dependencies. On Kaggle run `pip install -r requirements-kaggle.txt`."
        ) from error

    config = load_config(args.config)
    train_path = args.data_dir / "vilexnorm_train.jsonl"
    dev_path = args.data_dir / "vilexnorm_dev.jsonl"
    if not train_path.is_file() or not dev_path.is_file():
        raise FileNotFoundError("data-dir must contain vilexnorm_train.jsonl and vilexnorm_dev.jsonl")

    train_records = read_jsonl(train_path)
    dev_records = read_jsonl(dev_path)
    require_gold_records(train_records, "train")
    require_gold_records(dev_records, "dev")
    if args.smoke_test:
        train_records, dev_records = train_records[:200], dev_records[:50]
    log_event("START", f"Model A training: train={len(train_records)} dev={len(dev_records)} smoke_test={args.smoke_test} checkpoint_path={args.checkpoint_path or 'base model'}", quiet=args.quiet)

    set_seed(config["seed"])
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
    if args.checkpoint_path:
        if not args.checkpoint_path.is_dir():
            raise FileNotFoundError(f"Checkpoint directory does not exist: {args.checkpoint_path}")
        model = AutoModelForSeq2SeqLM.from_pretrained(args.checkpoint_path)
    else:
        model = AutoModelForSeq2SeqLM.from_pretrained(config["model_name"])

    def tokenize(batch: dict[str, list[str]]) -> dict[str, list[list[int]]]:
        encoded = tokenizer(
            batch["input_text"], max_length=config["max_source_length"], truncation=True
        )
        labels = tokenizer(
            text_target=batch["target_text"],
            max_length=config["max_target_length"],
            truncation=True,
        )
        encoded["labels"] = labels["input_ids"]
        return encoded

    train_dataset = Dataset.from_list(train_records)
    dev_dataset = Dataset.from_list(dev_records)
    train_tokenized = train_dataset.map(tokenize, batched=True, remove_columns=train_dataset.column_names)
    dev_tokenized = dev_dataset.map(tokenize, batched=True, remove_columns=dev_dataset.column_names)

    work_dir = args.work_dir
    trainer_dir = work_dir / "trainer_model_a"
    checkpoint_dir = work_dir / "checkpoints" / "model_a"
    output_dir = work_dir / "outputs" / "model_a"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = Seq2SeqTrainingArguments(
        output_dir=str(trainer_dir),
        learning_rate=config["learning_rate"],
        per_device_train_batch_size=config["per_device_train_batch_size"],
        per_device_eval_batch_size=config["per_device_eval_batch_size"],
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        num_train_epochs=1 if args.smoke_test else config["num_train_epochs"],
        weight_decay=config["weight_decay"],
        warmup_ratio=config["warmup_ratio"],
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="steps",
        logging_steps=25,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        predict_with_generate=True,
        generation_num_beams=config["generation_num_beams"],
        generation_max_length=config["generation_max_length"],
        save_total_limit=2,
        report_to="none",
        fp16=torch.cuda.is_available(),
        seed=config["seed"],
    )
    callbacks = [] if args.smoke_test else [EarlyStoppingCallback(config["early_stopping_patience"])]
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=dev_tokenized,
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model),
        processing_class=tokenizer,
        callbacks=callbacks,
    )
    if not args.checkpoint_path:
        log_event("PROGRESS", "Model A training: Trainer started; see Transformers training logs for epoch/step progress", quiet=args.quiet)
        trainer.train()
    log_event("PROGRESS", "Model A training: generating Dev predictions", quiet=args.quiet)
    dev_result = trainer.predict(dev_tokenized, metric_key_prefix="dev")
    # Trainer uses -100 to pad generated predictions in distributed/padded
    # batches. -100 is a loss ignore index, not a valid BARTpho token ID.
    prediction_ids = np.where(dev_result.predictions == -100, tokenizer.pad_token_id, dev_result.predictions)
    predictions = tokenizer.batch_decode(prediction_ids, skip_special_tokens=True)
    predictions = [prediction.strip() for prediction in predictions]
    exact_matches = sum(pred == record["target_text"] for pred, record in zip(predictions, dev_records))

    prediction_records = [
        {
            "id": record["id"],
            "input_text": record["input_text"],
            "target_text": record["target_text"],
            "prediction": prediction,
        }
        for record, prediction in zip(dev_records, predictions)
    ]
    write_jsonl(prediction_records, output_dir / "dev_predictions.jsonl")
    metrics = {
        **{key: float(value) for key, value in dev_result.metrics.items()},
        "exact_sentence_match": exact_matches / len(dev_records),
        "dev_examples": len(dev_records),
        "generation_config": {
            "num_beams": config["generation_num_beams"],
            "max_length": config["generation_max_length"],
        },
    }
    with (output_dir / "dev_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)

    trainer.save_model(str(checkpoint_dir))
    tokenizer.save_pretrained(str(checkpoint_dir))
    run_config = {
        **config,
        "run_type": "smoke_test" if args.smoke_test else "full",
        "train_examples": len(train_records),
        "dev_examples": len(dev_records),
        "best_checkpoint": str(args.checkpoint_path) if args.checkpoint_path else trainer.state.best_model_checkpoint,
        "best_metric": None if args.checkpoint_path else trainer.state.best_metric,
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "python_version": platform.python_version(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with (output_dir / "train_config.json").open("w", encoding="utf-8") as handle:
        json.dump(run_config, handle, ensure_ascii=False, indent=2)
    log_event("DONE", f"Model A training: checkpoint={checkpoint_dir} outputs={output_dir} dev_loss={metrics.get('dev_loss')} exact_sentence_match={metrics['exact_sentence_match']:.4f}", quiet=args.quiet)
