"""Weak-label validation, audit sampling, and artifact inventory generation."""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from visolexnorm.common.artifacts import sha256_file
from visolexnorm.common.io import atomic_write_jsonl, load_json, read_jsonl


ROOT = Path(__file__).parents[2]
WEAK_VALIDATOR = Draft202012Validator(load_json(ROOT / "specs/003-weak-labeling-llm-review/contracts/weak-label.schema.json"))


def select_audit_rows(rows: list[dict[str, Any]], seed: int, per_stratum: int) -> list[dict[str, Any]]:
    strata: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[(row["llm_decision"], row["original_source"], row["confidence_band"])].append(row)
    selected: list[dict[str, Any]] = []
    for key in sorted(strata):
        pool = sorted(strata[key], key=lambda row: row["id"])
        random.Random(f"{seed}:{key}").shuffle(pool)
        selected.extend(pool[:per_stratum])
    return selected


def artifact(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def validate_rows(rows: list[dict[str, Any]]) -> None:
    ids: set[str] = set()
    for row in rows:
        WEAK_VALIDATOR.validate(row)
        if row["id"] in ids:
            raise ValueError(f"Duplicate weak-label ID: {row['id']}")
        ids.add(row["id"])


def build_phase8_manifest(config: dict[str, Any], weak_labels: Path, audit: Path) -> dict[str, Any]:
    paths = [Path(config[key]) for key in (
        "phase3_weak_label_path", "remaining_manifest_path", "remaining_manifest_report_path", "cache_path",
        "approved_exclusions_path", "review_stats_path", "protected_hashes_path", "lexical_policy_path", "frozen_prompt_path",
    )] + [weak_labels, audit]
    missing = [path.as_posix() for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Phase 8 manifest inputs missing: {missing}")
    rows = read_jsonl(weak_labels)
    validate_rows(rows)
    decisions = Counter(row["llm_decision"] for row in rows)
    sources = Counter(row["original_source"] for row in rows)
    confidence = Counter(row["confidence_band"] for row in rows)
    prior_ids = {row["id"] for row in read_jsonl(Path(config["phase3_weak_label_path"]))}
    review_stats = load_json(Path(config["review_stats_path"]))
    return {
        "schema_version": 1, "phase": 8, "status": "frozen",
        "completion_status": review_stats["completion_status"],
        "review_identity_sha256": review_stats["review_identity_sha256"],
        "prompt_version": review_stats["prompt_version"], "llm_model": review_stats["llm_model"],
        "counts": {"phase3": len(prior_ids), "phase8": len(rows) - len(prior_ids), "expanded": len(rows), "unique_ids": len({row["id"] for row in rows})},
        "decision_distribution": dict(sorted(decisions.items())),
        "source_distribution": dict(sorted(sources.items())),
        "confidence_distribution": dict(sorted(confidence.items())),
        "artifacts": [artifact(path) for path in paths],
    }


def write_frozen_manifest(manifest: dict[str, Any], path: Path) -> None:
    if path.is_file():
        if load_json(path) != manifest:
            raise FileExistsError(f"Frozen manifest differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def phase3_artifacts(config_path: Path, weak_labels: Path, stats: Path, audit: Path, config: dict[str, Any], approved_exclusions: Path | None = None) -> list[Path]:
    paths = [
        Path("data/processed/vilexnorm_train.jsonl"), Path("data/processed/vilexnorm_dev.jsonl"), Path("data/processed/vilexnorm_test.jsonl"), Path("data/processed/visolex_unlabeled.jsonl"),
        Path("data/processed/vilexnorm_protected_input_hashes.txt"), Path("model_a_artifacts.zip"),
        Path("outputs/model_a/dev_predictions.jsonl"), Path("outputs/model_a/dev_metrics.json"), Path("outputs/model_a/train_config.json"), Path("outputs/model_a/candidate_full_run_integrity.json"),
        Path("visolex_model_a_candidates.zip"), Path("data/intermediate/visolex_model_a_candidates.jsonl"), Path("data/intermediate/visolex_review_manifest.jsonl"), Path("data/intermediate/visolex_review_cache.sqlite3"),
        Path("outputs/pilot_review_report_v6.json"), Path("outputs/pilot_review_audit_v6.csv"), Path("configs/candidate_generation_config.json"), config_path,
        Path(config["lexical_policy_path"]), Path(config["frozen_prompt_path"]), weak_labels, stats, audit,
    ]
    if approved_exclusions:
        paths.append(approved_exclusions)
    return paths


def audit_weak_labels(config: dict[str, Any], *, config_path: Path, weak_labels: Path, stats: Path | None, audit: Path, phase_manifest: Path, approved_exclusions: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Write deterministic audit rows and a phase inventory without CLI concerns."""
    phase8 = config.get("phase") == 8
    if not phase8 and stats is None:
        raise ValueError("--stats is required for Phase 3 audit")
    rows = read_jsonl(weak_labels)
    validate_rows(rows)
    selected = select_audit_rows(rows, int(config["seed"]), int(config["audit_samples_per_stratum"]))
    atomic_write_jsonl(selected, audit)
    if phase8:
        manifest = build_phase8_manifest(config, weak_labels, audit)
        write_frozen_manifest(manifest, phase_manifest)
    else:
        assert stats is not None
        paths = phase3_artifacts(config_path, weak_labels, stats, audit, config, approved_exclusions)
        missing = [path.as_posix() for path in paths if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Phase 3 manifest inputs missing: {missing}")
        manifest = {"phase": 3, "completion_status": "completed_with_approved_provider_exclusions" if approved_exclusions else "completed", "artifacts": [artifact(path) for path in paths]}
        phase_manifest.parent.mkdir(parents=True, exist_ok=True)
        phase_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return selected, manifest