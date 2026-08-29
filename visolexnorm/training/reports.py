"""Checkpoint inventories and Phase 8 Dev-only report handling."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from visolexnorm.common.artifacts import sha256_file, sha256_text
from visolexnorm.common.io import load_json, read_jsonl


def checkpoint_inventory(checkpoint: Path) -> tuple[list[dict[str, Any]], str]:
    """Return the deterministic inventory required for Model A provenance."""
    if not checkpoint.is_dir():
        raise FileNotFoundError(checkpoint)
    files = [
        {"path": path.relative_to(checkpoint).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(checkpoint.rglob("*")) if path.is_file()
    ]
    names = {item["path"] for item in files}
    if "config.json" not in names or not any(name.endswith((".safetensors", ".bin")) for name in names) or not any("tokenizer" in name or name.endswith("sentencepiece.bpe.model") for name in names):
        raise ValueError("Model A checkpoint is missing model/tokenizer files")
    return files, sha256_text(json.dumps(files, sort_keys=True, separators=(",", ":")))


def source_revision() -> str | None:
    """Read the Git revision where available without making it a hard dependency."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def reject_prohibited_inputs(options: Any, config: dict[str, Any]) -> None:
    """Prevent Model C from receiving Test or Phase 5 evaluation paths."""
    declared = [options.model_a_checkpoint, options.data_dir, options.mixture_manifest, options.config]
    normalized = [str(path).replace("\\", "/").lower() for path in declared]
    prohibited = [value.replace("\\", "/").lower().rstrip("/") for value in config["prohibited_input_paths"]]
    if any(blocked in path for path in normalized for blocked in prohibited):
        raise ValueError("Model C received a prohibited Test/evaluation input path")


def verify_model_c_artifacts(root: Path, manifest: dict[str, Any]) -> None:
    """Verify a completed Model C artifact manifest without reading Test data."""
    if manifest.get("phase") != 8 or manifest.get("model") != "model_c" or manifest.get("run_type") != "full":
        raise ValueError("Model C artifact manifest is not a Phase 8 full run")
    for item in manifest.get("artifacts", []):
        path = root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Model C artifact mismatch: {item['path']}")


def assert_dev_only_report(report: dict[str, Any]) -> None:
    """Reject recursively any Test results from the Model C exit report."""
    forbidden = {"test_metrics", "test_predictions", "test_f1", "test_err", "test_precision", "test_recall"}
    pending: list[Any] = [report]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if {str(key).lower() for key in value} & forbidden:
                raise ValueError("Phase 8 exit report contains forbidden Test results")
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    if report.get("test_inputs_loaded") is not False or report.get("evaluation_scope") != "dev_only_exploratory":
        raise ValueError("Phase 8 exit report must remain Dev-only")


def build_model_c_exit_report(root: Path) -> dict[str, Any]:
    """Rebuild the frozen Phase 8 exit report from existing artifacts only."""
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
    checkpoint_entries = [item for item in artifact_manifest["artifacts"] if item["path"].startswith("checkpoints/model_c/")]
    checkpoint_inventory_sha256 = sha256_text(json.dumps(checkpoint_entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    report = {
        "schema_version": 1, "phase": 8, "status": "completed", "evaluation_scope": "dev_only_exploratory", "source_revision": train_config["source_revision"],
        "review": {"manifest_count": review["manifest_review_count"], "valid_llm_review_count": review["valid_llm_review_count"], "provider_exclusion_count": review["provider_exclusion_count"], "reconciled_count": review["reconciled_count"], "decision_counts": review["decision_counts"]},
        "weak_label_pool": {"phase3_count": expanded["counts"]["phase3"], "phase8_count": expanded["counts"]["phase8"], "expanded_count": pool_count, "sha256": mixture["checksums"]["pseudo"]},
        "training": {"epochs": len(history), "gold_per_epoch": mixture["gold_count"], "pseudo_per_epoch": mixture["pseudo_per_epoch"], "pseudo_union_count": len(usage), "pseudo_usage_distribution": {str(key): value for key, value in sorted(Counter(usage.values()).items())}, "best_epoch": best["epoch"]},
        "dev_evaluation": {"examples": metrics["dev_examples"], "best_dev_loss": metrics["best_dev_loss"], "exact_sentence_match": metrics["exact_sentence_match"], "model_b_dev_loss": model_b_metrics["best_dev_loss"], "model_b_exact_sentence_match": model_b_metrics["exact_sentence_match"], "dev_loss_delta_model_c_minus_b": metrics["best_dev_loss"] - model_b_metrics["best_dev_loss"], "exact_match_delta_model_c_minus_b": metrics["exact_sentence_match"] - model_b_metrics["exact_sentence_match"], "final_comparison_available": False, "final_comparison_blocker": "Model C requires a new independently frozen holdout; ViLexNorm Test Phase 5 is already observed."},
        "provenance": {"model_a_inventory_sha256": train_config["checkpoint_inventory_sha256"], "model_c_checkpoint_inventory_sha256": checkpoint_inventory_sha256, "model_c_weights_sha256": next(item["sha256"] for item in checkpoint_entries if item["path"].endswith("model.safetensors")), "expanded_artifact_manifest_sha256": sha256_file(root / "outputs/expanded_review/artifact_manifest.json"), "training_mixture_manifest_sha256": sha256_file(output / "training_mixture_manifest.json"), "artifact_manifest_sha256": sha256_file(artifact_manifest_path)},
        "acceptance": {"smoke_test_passed": True, "checkpoint_reload": smoke["checkpoint_reload"], "dev_predictions": len(predictions), "unique_dev_ids": len({row["id"] for row in predictions}), "artifact_checksums_verified": True},
        "test_inputs_loaded": False, "app_checkpoint_changed": False, "promotion_status": "blocked_pending_independent_frozen_holdout",
    }
    assert_dev_only_report(report)
    return report


def finalize_model_c(root: Path, output: Path | None = None) -> Path:
    """Write the verified Dev-only exit report without regenerating artifacts."""
    destination = output or root / "outputs/model_c/phase8_exit_report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(build_model_c_exit_report(root), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


# Names retained for the Phase 8 finalization contract.
build_exit_report = build_model_c_exit_report
finalize_phase8 = finalize_model_c