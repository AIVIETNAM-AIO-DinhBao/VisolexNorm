"""Verified application checkpoint selection with Model B rollback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from visolexnorm.common.artifacts import canonical_json, sha256_file, sha256_text
from visolexnorm.evaluation.benchmark import BENCHMARK_SCOPE, verify_manifest as verify_benchmark_manifest
from visolexnorm.evaluation.freeze import inventory


@dataclass(frozen=True)
class ResolvedCheckpoint:
    """A verified selected or rollback application checkpoint."""

    model: str
    checkpoint: Path
    fallback_applied: bool
    fallback_reason: str | None
    selection: dict[str, Any]


def _checkpoint_hash(path: Path) -> str:
    value = inventory(path)
    if value.get("kind") != "directory":
        raise ValueError(f"Checkpoint is not a directory: {path}")
    return value["sha256"]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _verify_posthoc_metrics(metrics: dict[str, Any], deltas: dict[str, Any], report: dict[str, Any]) -> None:
    if metrics.get("evaluation_scope") != BENCHMARK_SCOPE:
        raise ValueError("Post-hoc metrics have an invalid evaluation scope")
    if metrics.get("promotion_eligible") is not False or metrics.get("changes_phase5_selection") is not False:
        raise ValueError("Post-hoc metrics do not preserve Phase 5 history")
    if report.get("descriptive_leader") != "model_c":
        raise ValueError("Model C is not the descriptive benchmark leader")
    model_c = metrics.get("models", {}).get("model_c", {})
    model_b = metrics.get("models", {}).get("model_b", {})
    if model_c.get("f1", 0.0) <= model_b.get("f1", 0.0):
        raise ValueError("Model C F1 does not exceed Model B")
    f1_ci = deltas.get("deltas", {}).get("model_c_minus_model_b", {}).get("bootstrap", {}).get("f1", {})
    if f1_ci.get("ci95_low", 0.0) <= 0.0:
        raise ValueError("Model C F1 bootstrap confidence interval is not positive")


def build_model_c_selection(args: Any) -> dict[str, Any]:
    """Build the current app selection from verified Phase 9 benchmark evidence."""
    manifest = _load_json(args.benchmark_manifest)
    verify_benchmark_manifest(manifest, args)
    metrics = _load_json(args.benchmark_metrics)
    deltas = _load_json(args.benchmark_deltas)
    report = _load_json(args.benchmark_report)
    _verify_posthoc_metrics(metrics, deltas, report)
    phase5_best = _load_json(args.phase5_best_model)
    if phase5_best.get("selected_model") != "model_b":
        raise ValueError("Historical Phase 5 selection must remain Model B")

    model_c = metrics["models"]["model_c"]
    model_b = metrics["models"]["model_b"]
    model_c_hash = _checkpoint_hash(args.model_c_checkpoint)
    model_b_hash = _checkpoint_hash(args.model_b_checkpoint)
    if model_c_hash != model_c["checkpoint_checksum"]:
        raise ValueError("Model C checkpoint differs from the post-hoc benchmark")
    if model_b_hash != model_b["checkpoint_checksum"]:
        raise ValueError("Model B rollback checkpoint differs from Phase 5")

    f1_bootstrap = deltas["deltas"]["model_c_minus_model_b"]["bootstrap"]["f1"]
    return {
        "schema_version": 1,
        "phase": 10,
        "selected_model": "model_c",
        "selected_checkpoint": "checkpoints/model_c",
        "selected_checkpoint_inventory_sha256": model_c_hash,
        "rollback_model": "model_b",
        "rollback_checkpoint": "checkpoints/model_b",
        "rollback_checkpoint_inventory_sha256": model_b_hash,
        "selection_scope": "production_candidate_posthoc_abc_benchmark",
        "promotion_approved": True,
        "rollback_available": True,
        "phase5_historical_selected_model": "model_b",
        "benchmark_manifest_sha256": sha256_file(args.benchmark_manifest),
        "benchmark_metrics_sha256": sha256_file(args.benchmark_metrics),
        "benchmark_deltas_sha256": sha256_file(args.benchmark_deltas),
        "benchmark_report_sha256": sha256_file(args.benchmark_report),
        "model_c_prediction_sha256": model_c["prediction_sha256"],
        "model_c_f1": model_c["f1"],
        "model_b_f1": model_b["f1"],
        "f1_delta_c_minus_b": deltas["deltas"]["model_c_minus_model_b"]["f1"],
        "f1_delta_bootstrap_ci95": [f1_bootstrap["ci95_low"], f1_bootstrap["ci95_high"]],
        "scientific_caveat": (
            "Selected for application use from a post-hoc A/B/C benchmark on a previously observed test; "
            "an independently frozen holdout remains desirable for final scientific confirmation."
        ),
    }


def load_selection(path: Path) -> dict[str, Any]:
    """Load and validate the current application selection artifact."""
    selection = _load_json(path)
    required = {
        "selected_model",
        "selected_checkpoint",
        "selected_checkpoint_inventory_sha256",
        "rollback_model",
        "rollback_checkpoint",
        "rollback_checkpoint_inventory_sha256",
        "promotion_approved",
        "rollback_available",
    }
    if not required <= selection.keys():
        raise ValueError("Application model selection is incomplete")
    if selection["selected_model"] != "model_c" or selection["rollback_model"] != "model_b":
        raise ValueError("Application selection must select Model C with Model B rollback")
    if selection["promotion_approved"] is not True or selection["rollback_available"] is not True:
        raise ValueError("Application selection is not approved with rollback")
    return selection


def resolve_checkpoint(selection_path: Path, root: Path = Path(".")) -> ResolvedCheckpoint:
    """Resolve Model C, falling back to verified Model B on missing/mismatched C."""
    selection = load_selection(selection_path)
    selected_path = root / selection["selected_checkpoint"]
    try:
        if _checkpoint_hash(selected_path) != selection["selected_checkpoint_inventory_sha256"]:
            raise ValueError("selected checkpoint inventory mismatch")
        return ResolvedCheckpoint("model_c", selected_path, False, None, selection)
    except (FileNotFoundError, ValueError) as error:
        rollback_path = root / selection["rollback_checkpoint"]
        if _checkpoint_hash(rollback_path) != selection["rollback_checkpoint_inventory_sha256"]:
            raise ValueError("rollback checkpoint inventory mismatch") from error
        return ResolvedCheckpoint("model_b", rollback_path, True, str(error), selection)


def selection_sha256(selection: dict[str, Any]) -> str:
    """Return a canonical selection content digest for smoke reports."""
    return sha256_text(canonical_json(selection))