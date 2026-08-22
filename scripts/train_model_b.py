"""Train Model B from Model A with a deterministic per-epoch gold/pseudo mixture.

This Kaggle-oriented command never accepts or reads a ViLexNorm Test path.
"""
from __future__ import annotations

import argparse, hashlib, json, math, platform, shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    from .data_utils import read_jsonl, write_jsonl
except ImportError:
    from data_utils import read_jsonl, write_jsonl


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def checkpoint_inventory(checkpoint: Path) -> tuple[list[dict], str]:
    if not checkpoint.is_dir(): raise FileNotFoundError(checkpoint)
    files = [{"path": p.relative_to(checkpoint).as_posix(), "bytes": p.stat().st_size, "sha256": sha256_file(p)} for p in sorted(checkpoint.rglob("*")) if p.is_file()]
    names = {item["path"] for item in files}
    if "config.json" not in names or not any(x.endswith((".safetensors", ".bin")) for x in names) or not any("tokenizer" in x or x.endswith("sentencepiece.bpe.model") for x in names):
        raise ValueError("Model A checkpoint is missing model/tokenizer files")
    payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return files, hashlib.sha256(payload).hexdigest()


def validate_mixture_manifest(manifest: dict, config: dict) -> None:
    epochs = manifest.get("epochs", [])
    if manifest.get("gold_count") != config["expected_gold_count"] or manifest.get("dev_count") != config["expected_dev_count"] or manifest.get("weak_label_count") != config["expected_weak_label_count"]:
        raise ValueError("Mixture manifest counts do not match the frozen contract")
    if manifest.get("completion_status") != config["expected_phase3_completion_status"] or len(epochs) != config["num_train_epochs"]:
        raise ValueError("Mixture manifest status or epoch count is invalid")
    covered = set()
    for index, epoch in enumerate(epochs):
        gold_ids, pseudo_ids = epoch.get("gold_ids", []), epoch.get("pseudo_ids", [])
        if epoch.get("epoch_seed") != config["seed"] + index or len(gold_ids) != config["gold_per_epoch"] or len(pseudo_ids) != config["pseudo_per_epoch"]:
            raise ValueError(f"Invalid membership contract in epoch {index}")
        if len(set(gold_ids)) != len(gold_ids) or (not epoch.get("replacement_used") and len(set(pseudo_ids)) != len(pseudo_ids)):
            raise ValueError(f"Duplicate membership in epoch {index}")
        expected = {(x, "human") for x in gold_ids} | {(x, "model_a+llm_review") for x in pseudo_ids}
        actual = {(x.get("id"), x.get("label_source")) for x in epoch.get("ordered_ids", [])}
        if actual != expected or len(epoch.get("ordered_ids", [])) != len(gold_ids) + len(pseudo_ids):
            raise ValueError(f"ordered_ids mismatch in epoch {index}")
        covered.update(pseudo_ids)
    if len(covered) != config["expected_weak_label_count"]: raise ValueError("Mixture manifest does not cover the frozen pseudo pool")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Model B from a verified Model A checkpoint")
    parser.add_argument("--model-a-checkpoint", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True, help="Contains train, dev and frozen weak-label JSONL only")
    parser.add_argument("--mixture-manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/model_b_config.json"))
    parser.add_argument("--work-dir", type=Path, default=Path("."))
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    try:
        import torch, transformers
        from datasets import Dataset
        from torch.utils.data import DataLoader
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, DataCollatorForSeq2Seq, get_linear_schedule_with_warmup, set_seed
    except ImportError as error:
        raise SystemExit("Install requirements-kaggle.txt before training") from error

    config = json.loads(args.config.read_text()); manifest = json.loads(args.mixture_manifest.read_text())
    validate_mixture_manifest(manifest, config)
    inventory, inventory_sha = checkpoint_inventory(args.model_a_checkpoint)
    paths = {"gold": args.data_dir / "vilexnorm_train.jsonl", "dev": args.data_dir / "vilexnorm_dev.jsonl", "pseudo": args.data_dir / "visolex_weak_labeled.jsonl"}
    for key, path in paths.items():
        if sha256_file(path) != manifest["checksums"][key]: raise ValueError(f"Input changed since mixture build: {key}")
    gold, dev, pseudo = (read_jsonl(paths[x]) for x in ("gold", "dev", "pseudo"))
    by_id = {r["id"]: r for r in gold + pseudo}
    set_seed(config["seed"]); device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(args.model_a_checkpoint); model = AutoModelForSeq2SeqLM.from_pretrained(args.model_a_checkpoint).to(device)

    def tokenize(records: list[dict]):
        dataset = Dataset.from_list(records)
        def encode(batch):
            encoded = tokenizer(batch["input_text"], max_length=config["max_source_length"], truncation=True)
            encoded["labels"] = tokenizer(text_target=batch["target_text"], max_length=config["max_target_length"], truncation=True)["input_ids"]
            return encoded
        return dataset.map(encode, batched=True, remove_columns=dataset.column_names)

    collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)
    dev_records = dev[:50] if args.smoke_test else dev; dev_loader = DataLoader(tokenize(dev_records), batch_size=config["per_device_eval_batch_size"], collate_fn=collator)

    def evaluate_loss() -> float:
        model.eval()
        losses = []
        with torch.no_grad():
            for batch in dev_loader:
                batch = {key: value.to(device) for key, value in batch.items()}
                losses.append(model(**batch).loss.item())
        return sum(losses) / len(losses)

    initial_dev_loss = evaluate_loss()
    epoch_specs = manifest["epochs"][:1] if args.smoke_test else manifest["epochs"]
    if args.smoke_test:
        # Explicitly preserve the acceptance contract: 200 gold + 200 pseudo.
        spec = epoch_specs[0]; ordered = ([{"id": x, "label_source": "human"} for x in spec["gold_ids"][:200]] + [{"id": x, "label_source": "model_a+llm_review"} for x in spec["pseudo_ids"][:200]])
        epoch_specs = [{**spec, "ordered_ids": ordered}]
    steps_per_epoch = math.ceil(len(epoch_specs[0]["ordered_ids"]) / config["per_device_train_batch_size"] / config["gradient_accumulation_steps"])
    total_steps = steps_per_epoch * len(epoch_specs)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    scheduler = get_linear_schedule_with_warmup(optimizer, int(total_steps * config["warmup_ratio"]), total_steps)
    output = args.work_dir / "outputs/model_b"; checkpoint = args.work_dir / "checkpoints/model_b"; output.mkdir(parents=True, exist_ok=True); checkpoint.mkdir(parents=True, exist_ok=True)
    exported_mixture = output / "training_mixture_manifest.json"; shutil.copy2(args.mixture_manifest, exported_mixture)
    history, best_loss = [], float("inf")
    for spec in epoch_specs:
        records = [by_id[item["id"]] for item in spec["ordered_ids"]]
        loader = DataLoader(tokenize(records), batch_size=config["per_device_train_batch_size"], collate_fn=collator)
        model.train(); optimizer.zero_grad(); losses = []
        for step, batch in enumerate(loader):
            batch = {k: v.to(device) for k, v in batch.items()}; loss = model(**batch).loss / config["gradient_accumulation_steps"]; loss.backward(); losses.append(loss.item() * config["gradient_accumulation_steps"])
            if (step + 1) % config["gradient_accumulation_steps"] == 0 or step + 1 == len(loader): optimizer.step(); scheduler.step(); optimizer.zero_grad()
        dev_loss = evaluate_loss()
        window = max(1, len(losses) // 4)
        history.append({"epoch": spec["epoch_index"] + 1, "train_loss": sum(losses) / len(losses), "initial_train_loss": sum(losses[:window]) / window, "final_train_loss": sum(losses[-window:]) / window, "dev_loss": dev_loss})
        if dev_loss < best_loss:
            best_loss = dev_loss; model.save_pretrained(checkpoint); tokenizer.save_pretrained(checkpoint)
    best = AutoModelForSeq2SeqLM.from_pretrained(checkpoint).to(device); best.eval(); predictions = []
    with torch.no_grad():
        for start in range(0, len(dev_records), config["per_device_eval_batch_size"]):
            rows = dev_records[start:start + config["per_device_eval_batch_size"]]; encoded = tokenizer([r["input_text"] for r in rows], return_tensors="pt", padding=True, truncation=True, max_length=config["max_source_length"]).to(device)
            generated = best.generate(**encoded, num_beams=config["generation_num_beams"], max_length=config["generation_max_length"])
            predictions.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
    write_jsonl([{"id": r["id"], "input_text": r["input_text"], "target_text": r["target_text"], "prediction": p.strip()} for r, p in zip(dev_records, predictions)], output / "dev_predictions.jsonl")
    metrics = {"history": history, "initial_dev_loss": initial_dev_loss, "best_dev_loss": best_loss, "dev_examples": len(dev_records), "exact_sentence_match": sum(p.strip() == r["target_text"] for p, r in zip(predictions, dev_records)) / len(dev_records)}
    (output / "dev_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    run_config = {"run_type": "smoke_test" if args.smoke_test else "full", "initial_checkpoint": str(args.model_a_checkpoint), "checkpoint_inventory": inventory, "checkpoint_inventory_sha256": inventory_sha, "phase3_manifest_sha256": manifest["phase3_manifest_sha256"], "training_mixture_manifest_sha256": sha256_file(exported_mixture), "gold_checksum": manifest["checksums"]["gold"], "dev_checksum": manifest["checksums"]["dev"], "weak_label_checksum": manifest["checksums"]["pseudo"], "seed": config["seed"], "gold_count": manifest["gold_count"], "dev_count": manifest["dev_count"], "weak_label_count": manifest["weak_label_count"], "pseudo_per_epoch": manifest["pseudo_per_epoch"], "gold_pseudo_ratio": "1:1", "completion_status": manifest["completion_status"], "prompt_version": manifest["prompt_version"], "decision_distribution": manifest["decision_distribution"], "source_distribution": manifest["source_distribution"], "epoch_seeds": [e["epoch_seed"] for e in manifest["epochs"]], "replacement_used": manifest["replacement_used"], "hyperparameters": config, "runtime": {"python_version": platform.python_version(), "torch_version": torch.__version__, "transformers_version": transformers.__version__, "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"}, "best_checkpoint": str(checkpoint), "best_dev_loss": best_loss, "created_at_utc": datetime.now(timezone.utc).isoformat()}
    (output / "train_config.json").write_text(json.dumps(run_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    loss_decreased = best_loss < initial_dev_loss
    smoke = {
        "passed": bool(predictions) and any(prediction.strip() for prediction in predictions),
        "composition": {"gold": 200, "pseudo": 200} if args.smoke_test else None,
        "generation_nonempty": bool(predictions) and any(prediction.strip() for prediction in predictions),
        "checkpoint_reload": True,
        "initial_dev_loss": initial_dev_loss,
        "best_dev_loss": best_loss,
        "loss_decreased": loss_decreased,
        "loss_check": "informational_for_smoke_test; investigate before full training if false",
        "history": history,
    }
    if args.smoke_test: (output / "smoke_test.json").write_text(json.dumps(smoke, indent=2) + "\n")
    artifacts = []
    for base in (checkpoint, output):
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.name != "artifact_manifest.json":
                artifacts.append({"path": path.relative_to(args.work_dir).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    artifact_manifest = {"phase": 4, "run_type": run_config["run_type"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "artifacts": artifacts}
    (output / "artifact_manifest.json").write_text(json.dumps(artifact_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checkpoint": str(checkpoint), "best_dev_loss": best_loss, "smoke": args.smoke_test}))


if __name__ == "__main__": main()