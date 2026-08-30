"""Validate frozen Phase 5 predictions, calculate metrics, and select Model A/B.

The historical freeze manifest remains authoritative for the Test run. A future
freeze uses ``higher_ERR`` because this project's ERR is error reduction rate;
if a historical manifest reaches that tie-break, its recorded rule is used.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


from visolexnorm.evaluation.freeze import inventory, verify_manifest
from visolexnorm.common.artifacts import sha256_file, sha256_json
from visolexnorm.common.io import read_jsonl


ROOT = Path(__file__).parents[2]
PREDICTION_FIELDS = {"id", "input_text", "target_text", "prediction_text", "model", "checkpoint_checksum", "generation_config_hash"}


def git_commit(root: Path) -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def validate_prediction_rows(rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], *, model: str, checkpoint_checksum: str, generation_config_hash: str, validator: Draft202012Validator) -> None:
    """Fail closed on schema, count, order, alignment, or frozen metadata drift."""
    if len(rows) != len(test_rows):
        raise ValueError(f"{model}: expected {len(test_rows)} predictions, got {len(rows)}")
    seen: set[str] = set()
    for index, (row, test) in enumerate(zip(rows, test_rows), start=1):
        errors = sorted(validator.iter_errors(row), key=lambda error: list(error.path))
        if errors:
            raise ValueError(f"{model}: prediction {index} fails schema: {errors[0].message}")
        if row["id"] in seen:
            raise ValueError(f"{model}: duplicate prediction ID {row['id']!r}")
        seen.add(row["id"])
        if set(row) != PREDICTION_FIELDS:
            raise ValueError(f"{model}: prediction {index} does not have exactly seven fields")
        if any(row[field] != test[field] for field in ("id", "input_text", "target_text")):
            raise ValueError(f"{model}: prediction {index} does not align with frozen Test")
        if row["model"] != model or row["checkpoint_checksum"] != checkpoint_checksum or row["generation_config_hash"] != generation_config_hash:
            raise ValueError(f"{model}: prediction {index} does not match frozen model/config")


def select_best_model(metrics: dict[str, dict[str, Any]], rule: list[str]) -> tuple[str, str]:
    """Apply the frozen selection rule and return (winner, deciding criterion)."""
    a, b = metrics["model_a"], metrics["model_b"]
    if a["f1"] != b["f1"]:
        return ("model_a" if a["f1"] > b["f1"] else "model_b", "higher_f1")
    err_rule = rule[1] if len(rule) > 1 else "higher_ERR"
    if a["ERR"] != b["ERR"]:
        if err_rule == "higher_ERR":
            return ("model_a" if a["ERR"] > b["ERR"] else "model_b", "higher_ERR")
        if err_rule == "lower_ERR":
            return ("model_a" if a["ERR"] < b["ERR"] else "model_b", "lower_ERR")
        raise ValueError(f"Unsupported frozen ERR tie-break rule: {err_rule}")
    return "model_a", "model_a"


def render_comparison(metrics: dict[str, dict[str, Any]], best: dict[str, Any]) -> str:
    lines = ["# Phase 5 Test Comparison", "", "| Model | Samples | ERR (error reduction) | Precision | Recall | F1 |", "|---|---:|---:|---:|---:|---:|"]
    lines.extend(f"| {model} | {report['sample_count']} | {report['ERR']:.6f} | {report['precision']:.6f} | {report['recall']:.6f} | {report['f1']:.6f} |" for model, report in metrics.items())
    lines.extend(["", f"**Selected model:** `{best['selected_model']}` by `{best['deciding_criterion']}`.", "", f"Frozen historical rule: `{', '.join(best['frozen_selection_rule'])}`. ERR tie-break was not used when F1 selected a winner.", ""])
    return "\n".join(lines)


def evaluate(args: Any, *, evaluate_records: Any, metric_reference: dict[str, Any]) -> dict[str, Any]:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    paths = {"model_a_checkpoint": args.model_a_checkpoint, "model_b_checkpoint": args.model_b_checkpoint, "test": args.test, "generation_config": args.generation_config, "metric_code": args.metric_code, "phase3_manifest": args.phase3_manifest, "phase4_exit_report": args.phase4_exit_report}
    verify_manifest(manifest, paths)
    test_rows = read_jsonl(args.test)
    config_hash = sha256_json(json.loads(args.generation_config.read_text(encoding="utf-8")))
    validator = Draft202012Validator(json.loads(args.schema.read_text(encoding="utf-8")))
    reports: dict[str, dict[str, Any]] = {}
    for model, prediction_path in (("model_a", args.model_a_prediction), ("model_b", args.model_b_prediction)):
        rows = read_jsonl(prediction_path)
        checkpoint_hash = manifest["inputs"][f"{model}_checkpoint"]["inventory"]["sha256"]
        validate_prediction_rows(rows, test_rows, model=model, checkpoint_checksum=checkpoint_hash, generation_config_hash=config_hash, validator=validator)
        reports[model] = {**evaluate_records(rows), "prediction_sha256": sha256_file(prediction_path), "checkpoint_checksum": checkpoint_hash, "generation_config_hash": config_hash}
    winner, criterion = select_best_model(reports, manifest["model_selection_rule"])
    evaluated_at = datetime.now(timezone.utc).isoformat()
    common = {"schema_version": 1, "phase": 5, "evaluated_at_utc": evaluated_at, "freeze_manifest_sha256": sha256_file(args.manifest), "metric_code_inventory": inventory(args.metric_code, normalize_text=True), "metric_reference": metric_reference, "source_commit": git_commit(ROOT), "models": reports}
    best = {"schema_version": 1, "phase": 5, "selected_model": winner, "deciding_criterion": criterion, "frozen_selection_rule": manifest["model_selection_rule"], "selected_checkpoint_checksum": reports[winner]["checkpoint_checksum"], "selected_prediction_sha256": reports[winner]["prediction_sha256"], "freeze_manifest_sha256": common["freeze_manifest_sha256"], "evaluated_at_utc": evaluated_at}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "test_metrics.json").write_text(json.dumps(common, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "best_model.json").write_text(json.dumps(best, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "comparison.md").write_text(render_comparison(reports, best), encoding="utf-8", newline="\n")
    return {"metrics": common, "best_model": best}
