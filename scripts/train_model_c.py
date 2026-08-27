"""Train exploratory Model C from Model A without reading Phase 5 Test artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .train_model_b import run_training
except ImportError:
    from train_model_b import run_training


def validate_model_c_manifest(manifest: dict[str, Any], config: dict[str, Any]) -> None:
    epochs = manifest.get("epochs", [])
    expected_epochs = manifest.get("num_train_epochs")
    if manifest.get("phase") != 8 or not epochs or len(epochs) != expected_epochs:
        raise ValueError("Model C mixture phase or epoch count is invalid")
    if manifest.get("model_a_inventory_sha256") != config["expected_initial_checkpoint_inventory_sha256"]:
        raise ValueError("Model C mixture does not reference the frozen Model A inventory")
    if (manifest.get("gold_count"), manifest.get("dev_count")) != (config["expected_gold_count"], config["expected_dev_count"]):
        raise ValueError("Model C mixture Train/Dev counts are invalid")
    covered: set[str] = set()
    for index, epoch in enumerate(epochs):
        gold_ids, pseudo_ids = epoch.get("gold_ids", []), epoch.get("pseudo_ids", [])
        if epoch.get("epoch_seed") != config["seed"] + index:
            raise ValueError(f"Invalid epoch seed at {index}")
        if len(gold_ids) != config["gold_per_epoch"] or len(pseudo_ids) != config["pseudo_per_epoch"]:
            raise ValueError(f"Invalid 1:1 membership at epoch {index}")
        if len(set(gold_ids)) != len(gold_ids) or len(set(pseudo_ids)) != len(pseudo_ids):
            raise ValueError(f"Duplicate membership at epoch {index}")
        if epoch.get("replacement_used") != (index == len(epochs) - 1 and len(covered) + len(pseudo_ids) > manifest["weak_label_count"]):
            raise ValueError(f"Invalid final-epoch wrap flag at epoch {index}")
        expected = {(sample_id, "human") for sample_id in gold_ids} | {(sample_id, "model_a+llm_review") for sample_id in pseudo_ids}
        actual = {(row.get("id"), row.get("label_source")) for row in epoch.get("ordered_ids", [])}
        if actual != expected or len(epoch.get("ordered_ids", [])) != len(gold_ids) + len(pseudo_ids):
            raise ValueError(f"ordered_ids mismatch in epoch {index}")
        covered.update(pseudo_ids)
    if len(covered) != manifest.get("weak_label_count") or manifest.get("pseudo_union_count") != len(covered):
        raise ValueError("Model C mixture does not cover the frozen pseudo pool")


def reject_prohibited_inputs(args: argparse.Namespace, config: dict[str, Any]) -> None:
    declared = [args.model_a_checkpoint, args.data_dir, args.mixture_manifest, args.config]
    normalized = [str(path).replace("\\", "/").lower() for path in declared]
    prohibited = [value.replace("\\", "/").lower().rstrip("/") for value in config["prohibited_input_paths"]]
    if any(blocked in path for path in normalized for blocked in prohibited):
        raise ValueError("Model C received a prohibited Test/evaluation input path")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-a-checkpoint", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True, help="Contains Train, Dev and expanded weak labels; never Test")
    parser.add_argument("--mixture-manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/model_c_config.json"))
    parser.add_argument("--work-dir", type=Path, default=Path("."))
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--smoke-report", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    reject_prohibited_inputs(args, config)
    run_training(
        args, model_name="model_c", pseudo_filename="visolex_weak_labeled_expanded.jsonl",
        phase=8, manifest_validator=validate_model_c_manifest,
    )


if __name__ == "__main__":
    main()