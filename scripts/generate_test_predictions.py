"""Generate frozen Phase 5 Test predictions on Kaggle GPU.

The command verifies every frozen input before opening ViLexNorm Test. It is
intended to run once per model from `evaluate_models_kaggle.ipynb`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from scripts.freeze_experiment import inventory, verify_manifest
from visolexnorm.common.artifacts import sha256_file, sha256_json
from visolexnorm.common.io import read_jsonl


def validate_predictions(rows: list[dict], test_rows: list[dict], model_name: str, checkpoint_sha: str, config_sha: str) -> None:
    if len(rows) != len(test_rows):
        raise ValueError("Prediction count does not match Test")
    for index, (row, test) in enumerate(zip(rows, test_rows), start=1):
        required = {"id", "input_text", "target_text", "prediction_text", "model", "checkpoint_checksum", "generation_config_hash"}
        if set(row) != required:
            raise ValueError(f"Prediction {index} does not match the 7-field contract")
        if row["id"] != test["id"] or row["input_text"] != test["input_text"] or row["target_text"] != test["target_text"]:
            raise ValueError(f"Prediction {index} is not aligned with frozen Test")
        if row["model"] != model_name or row["checkpoint_checksum"] != checkpoint_sha or row["generation_config_hash"] != config_sha:
            raise ValueError(f"Prediction {index} does not match frozen model/config")
        if not isinstance(row["prediction_text"], str) or not row["prediction_text"].strip():
            raise ValueError(f"Prediction {index} is empty")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", choices=("model_a", "model_b"), required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--generation-config", type=Path, required=True)
    parser.add_argument("--model-a-checkpoint", type=Path, required=True)
    parser.add_argument("--model-b-checkpoint", type=Path, required=True)
    parser.add_argument("--phase3-manifest", type=Path, required=True)
    parser.add_argument("--phase4-exit-report", type=Path, required=True)
    parser.add_argument("--metric-code", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, set_seed
    except ImportError as error:
        raise SystemExit("Install requirements-kaggle.txt before generation") from error

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    verify_manifest(manifest, {
        "model_a_checkpoint": args.model_a_checkpoint,
        "model_b_checkpoint": args.model_b_checkpoint,
        "test": args.test,
        "generation_config": args.generation_config,
        "metric_code": args.metric_code,
        "phase3_manifest": args.phase3_manifest,
        "phase4_exit_report": args.phase4_exit_report,
    })
    config = json.loads(args.generation_config.read_text(encoding="utf-8"))
    config_sha = sha256_json(config)
    checkpoint_sha = manifest["inputs"][f"{args.model}_checkpoint"]["inventory"]["sha256"]
    if inventory(args.generation_config, normalize_text=True) != manifest["inputs"]["generation_config"]["inventory"]:
        raise ValueError("Frozen generation config mismatch")
    if args.checkpoint != (args.model_a_checkpoint if args.model == "model_a" else args.model_b_checkpoint):
        raise ValueError("The selected model/checkpoint does not match the frozen input")

    set_seed(int(config["seed"]))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        raise RuntimeError("Phase 5 Test generation must run on a Kaggle GPU")
    test_rows = read_jsonl(args.test)
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.checkpoint).to(device)
    model.eval()
    predictions: list[dict] = []
    batch_size = int(config["batch_size"])
    for start in range(0, len(test_rows), batch_size):
        batch = test_rows[start:start + batch_size]
        encoded = tokenizer([row["input_text"] for row in batch], return_tensors="pt", padding=True, truncation=True, max_length=int(config["max_source_length"])).to(device)
        with torch.no_grad():
            generated = model.generate(**encoded, num_beams=int(config["num_beams"]), max_new_tokens=int(config["max_new_tokens"]), early_stopping=bool(config["early_stopping"]))
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        predictions.extend({"id": row["id"], "input_text": row["input_text"], "target_text": row["target_text"], "prediction_text": text.strip(), "model": args.model, "checkpoint_checksum": checkpoint_sha, "generation_config_hash": config_sha} for row, text in zip(batch, decoded))
    validate_predictions(predictions, test_rows, args.model, checkpoint_sha, config_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions), encoding="utf-8")
    print(json.dumps({"model": args.model, "records": len(predictions), "output": str(args.output)}))


if __name__ == "__main__":
    main()