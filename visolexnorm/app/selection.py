"""Verified Dev-based application checkpoint selection with fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from visolexnorm.common.artifacts import canonical_json, sha256_file, sha256_text
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


def build_dev_selection(args: Any) -> dict[str, Any]:
    """Build application selection exclusively from common Dev metrics."""
    metrics = _load_json(args.dev_metrics)
    if metrics.get("split") != "dev" or metrics.get("test_metrics_used_for_selection") not in {None, False}:
        raise ValueError("Application selection requires Dev-only metrics")
    reports = metrics.get("models", {})
    models = ("model_a", "model_b", "model_c")
    if set(reports) != set(models):
        raise ValueError("Dev metrics must contain exactly Model A, Model B, and Model C")
    rule = metrics.get("selection_rule")
    expected_rule = ["higher_ERR", "higher_f1", "higher_exact_sentence_match", "model_a"]
    if rule != expected_rule:
        raise ValueError("Dev selection rule is missing or changed")
    ranking = sorted(
        models,
        key=lambda model: (
            reports[model]["ERR"], reports[model]["f1"],
            reports[model]["exact_sentence_match"], model == "model_a",
        ),
        reverse=True,
    )
    checkpoint_paths = {
        model: getattr(args, f"{model}_checkpoint") for model in models
    }
    hashes = {model: _checkpoint_hash(path) for model, path in checkpoint_paths.items()}
    expected_hashes = getattr(args, "expected_hashes", None)
    if expected_hashes is not None and hashes != expected_hashes:
        raise ValueError("Checkpoint inventory differs from the expected Dev-selection inventory")
    selected, fallback = ranking[:2]
    selected_metrics = {
        key: reports[selected][key] for key in ("ERR", "f1", "exact_sentence_match")
    }
    return {
        "schema_version": 2,
        "selected_model": selected,
        "selected_checkpoint": f"checkpoints/{selected}",
        "selected_checkpoint_inventory_sha256": hashes[selected],
        "fallback_model": fallback,
        "fallback_checkpoint": f"checkpoints/{fallback}",
        "fallback_checkpoint_inventory_sha256": hashes[fallback],
        "selection_split": "dev",
        "selection_metric": "ERR",
        "selection_rule": expected_rule,
        "selected_dev_metrics": selected_metrics,
        "dev_metrics_sha256": sha256_file(args.dev_metrics),
        "test_metrics_used_for_selection": False,
        "selection_approved": True,
        "ranking": ranking,
    }


def load_selection(path: Path) -> dict[str, Any]:
    """Load and validate the current application selection artifact."""
    selection = _load_json(path)
    common = {
        "selected_model",
        "selected_checkpoint",
        "selected_checkpoint_inventory_sha256",
    }
    if not common <= selection.keys():
        raise ValueError("Application model selection is incomplete")
    if "fallback_model" in selection:
        required = {"fallback_model", "fallback_checkpoint", "fallback_checkpoint_inventory_sha256"}
        if not required <= selection.keys() or selection.get("selection_approved") is not True:
            raise ValueError("Dev-based application selection is incomplete or unapproved")
        if selection.get("selection_split") != "dev" or selection.get("test_metrics_used_for_selection") is not False:
            raise ValueError("Application selection is not based exclusively on Dev")
    else:
        required = {"rollback_model", "rollback_checkpoint", "rollback_checkpoint_inventory_sha256"}
        if not required <= selection.keys() or selection.get("promotion_approved") is not True or selection.get("rollback_available") is not True:
            raise ValueError("Legacy application selection is incomplete or unapproved")
    return selection


def resolve_checkpoint(selection_path: Path, root: Path = Path(".")) -> ResolvedCheckpoint:
    """Resolve the selected checkpoint, with verified fallback on mismatch."""
    selection = load_selection(selection_path)
    selected_path = root / selection["selected_checkpoint"]
    try:
        if _checkpoint_hash(selected_path) != selection["selected_checkpoint_inventory_sha256"]:
            raise ValueError("selected checkpoint inventory mismatch")
        return ResolvedCheckpoint(selection["selected_model"], selected_path, False, None, selection)
    except (FileNotFoundError, ValueError) as error:
        fallback_path_key = "fallback_checkpoint" if "fallback_checkpoint" in selection else "rollback_checkpoint"
        fallback_hash_key = "fallback_checkpoint_inventory_sha256" if "fallback_model" in selection else "rollback_checkpoint_inventory_sha256"
        fallback_model_key = "fallback_model" if "fallback_model" in selection else "rollback_model"
        fallback_path = root / selection[fallback_path_key]
        if _checkpoint_hash(fallback_path) != selection[fallback_hash_key]:
            raise ValueError("rollback checkpoint inventory mismatch") from error
        return ResolvedCheckpoint(selection[fallback_model_key], fallback_path, True, str(error), selection)


def selection_sha256(selection: dict[str, Any]) -> str:
    """Return a canonical selection content digest for smoke reports."""
    return sha256_text(canonical_json(selection))