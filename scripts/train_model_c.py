"""Train exploratory Model C from Model A without reading Phase 5 Test artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from scripts.train_model_b import run_training
from visolexnorm.common.artifacts import sha256_file, sha256_text
from visolexnorm.common.io import load_json, read_jsonl


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


def verify_model_c_artifacts(root: Path, manifest: dict[str, Any]) -> None:
    if manifest.get("phase") != 8 or manifest.get("model") != "model_c" or manifest.get("run_type") != "full":
        raise ValueError("Model C artifact manifest is not a Phase 8 full run")
    for item in manifest.get("artifacts", []):
        path = root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Model C artifact mismatch: {item['path']}")


def assert_dev_only_report(report: dict[str, Any]) -> None:
    forbidden = {"test_metrics", "test_predictions", "test_f1", "test_err", "test_precision", "test_recall"}
    pending: list[Any] = [report]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            keys = {str(key).lower() for key in value}
            if keys & forbidden:
                raise ValueError("Phase 8 exit report contains forbidden Test results")
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    if report.get("test_inputs_loaded") is not False or report.get("evaluation_scope") != "dev_only_exploratory":
        raise ValueError("Phase 8 exit report must remain Dev-only")


def build_exit_report(root: Path) -> dict[str, Any]:
    output = root / "outputs/model_c"
    artifact_manifest_path = output / "artifact_manifest.json"
    artifact_manifest = load_json(artifact_manifest_path)
    verify_model_c_artifacts(root, artifact_manifest)

    smoke = load_json(output / "smoke_test.json")
    train_config = load_json(output / "train_config.json")
    metrics = load_json(output / "dev_metrics.json")
    mixture = load_json(output / "training_mixture_manifest.json")
    expanded = load_json(root / "outputs/expanded_review/artifact_manifest.json")
    review = load_json(root / "outputs/expanded_review/review_stats.json")
    model_b_metrics = load_json(root / "outputs/model_b/dev_metrics.json")
    predictions = read_jsonl(output / "dev_predictions.jsonl")

    if not smoke.get("passed") or smoke.get("test_inputs_loaded") is not False:
        raise ValueError("Model C smoke gate did not pass")
    if train_config.get("run_type") != "full" or train_config.get("test_inputs_loaded") is not False:
        raise ValueError("Model C full run is missing its no-Test guarantee")
    if len(predictions) != len({row.get("id") for row in predictions}) or len(predictions) != metrics.get("dev_examples"):
        raise ValueError("Model C Dev predictions are missing or duplicated")
    if any(not str(row.get("id", "")).startswith("vilexnorm_dev_") or not str(row.get("prediction", "")).strip() for row in predictions):
        raise ValueError("Model C predictions are not complete ViLexNorm Dev outputs")

    usage = Counter(sample_id for epoch in mixture.get("epochs", []) for sample_id in epoch.get("pseudo_ids", []))
    pool_count = expanded.get("counts", {}).get("expanded")
    if len(usage) != pool_count or mixture.get("pseudo_union_count") != pool_count:
        raise ValueError("Model C mixture does not cover the frozen expanded pool")
    history = metrics.get("history", [])
    if len(history) != mixture.get("num_train_epochs") or not history:
        raise ValueError("Model C training history does not match the frozen epoch count")
    best = min(history, key=lambda row: row["dev_loss"])
    if best["dev_loss"] != metrics.get("best_dev_loss") or best["dev_loss"] != train_config.get("best_dev_loss"):
        raise ValueError("Model C best checkpoint selection is inconsistent")

    checkpoint_entries = [
        item for item in artifact_manifest["artifacts"]
        if item["path"].startswith("checkpoints/model_c/")
    ]
    checkpoint_inventory_sha256 = sha256_text(
        json.dumps(checkpoint_entries, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    report = {
        "schema_version": 1,
        "phase": 8,
        "status": "completed",
        "evaluation_scope": "dev_only_exploratory",
        "source_revision": train_config["source_revision"],
        "review": {
            "manifest_count": review["manifest_review_count"],
            "valid_llm_review_count": review["valid_llm_review_count"],
            "provider_exclusion_count": review["provider_exclusion_count"],
            "reconciled_count": review["reconciled_count"],
            "decision_counts": review["decision_counts"],
        },
        "weak_label_pool": {
            "phase3_count": expanded["counts"]["phase3"],
            "phase8_count": expanded["counts"]["phase8"],
            "expanded_count": pool_count,
            "sha256": mixture["checksums"]["pseudo"],
        },
        "training": {
            "epochs": len(history),
            "gold_per_epoch": mixture["gold_count"],
            "pseudo_per_epoch": mixture["pseudo_per_epoch"],
            "pseudo_union_count": len(usage),
            "pseudo_usage_distribution": {str(key): value for key, value in sorted(Counter(usage.values()).items())},
            "best_epoch": best["epoch"],
        },
        "dev_evaluation": {
            "examples": metrics["dev_examples"],
            "best_dev_loss": metrics["best_dev_loss"],
            "exact_sentence_match": metrics["exact_sentence_match"],
            "model_b_dev_loss": model_b_metrics["best_dev_loss"],
            "model_b_exact_sentence_match": model_b_metrics["exact_sentence_match"],
            "dev_loss_delta_model_c_minus_b": metrics["best_dev_loss"] - model_b_metrics["best_dev_loss"],
            "exact_match_delta_model_c_minus_b": metrics["exact_sentence_match"] - model_b_metrics["exact_sentence_match"],
            "final_comparison_available": False,
            "final_comparison_blocker": "Model C requires a new independently frozen holdout; ViLexNorm Test Phase 5 is already observed.",
        },
        "provenance": {
            "model_a_inventory_sha256": train_config["checkpoint_inventory_sha256"],
            "model_c_checkpoint_inventory_sha256": checkpoint_inventory_sha256,
            "model_c_weights_sha256": next(item["sha256"] for item in checkpoint_entries if item["path"].endswith("model.safetensors")),
            "expanded_artifact_manifest_sha256": sha256_file(root / "outputs/expanded_review/artifact_manifest.json"),
            "training_mixture_manifest_sha256": sha256_file(output / "training_mixture_manifest.json"),
            "artifact_manifest_sha256": sha256_file(artifact_manifest_path),
        },
        "acceptance": {
            "smoke_test_passed": True,
            "checkpoint_reload": smoke["checkpoint_reload"],
            "dev_predictions": len(predictions),
            "unique_dev_ids": len({row["id"] for row in predictions}),
            "artifact_checksums_verified": True,
        },
        "test_inputs_loaded": False,
        "app_checkpoint_changed": False,
        "promotion_status": "blocked_pending_independent_frozen_holdout",
    }
    assert_dev_only_report(report)
    return report


def finalize_phase8(root: Path, output: Path | None = None) -> Path:
    report = build_exit_report(root)
    destination = output or root / "outputs/model_c/phase8_exit_report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-a-checkpoint", type=Path)
    parser.add_argument("--data-dir", type=Path, help="Contains Train, Dev and expanded weak labels; never Test")
    parser.add_argument("--mixture-manifest", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/model_c_config.json"))
    parser.add_argument("--work-dir", type=Path, default=Path("."))
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--smoke-report", type=Path)
    parser.add_argument("--finalize", action="store_true", help="Verify downloaded artifacts and write the Dev-only Phase 8 exit report")
    parser.add_argument("--exit-report", type=Path)
    args = parser.parse_args()
    if args.finalize:
        destination = finalize_phase8(args.work_dir.resolve(), args.exit_report)
        print(json.dumps({"exit_report": str(destination), "status": "completed"}))
        return
    if not args.model_a_checkpoint or not args.data_dir or not args.mixture_manifest:
        parser.error("training requires --model-a-checkpoint, --data-dir and --mixture-manifest")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    reject_prohibited_inputs(args, config)
    run_training(
        args, model_name="model_c", pseudo_filename="visolex_weak_labeled_expanded.jsonl",
        phase=8, manifest_validator=validate_model_c_manifest,
    )


if __name__ == "__main__":
    main()