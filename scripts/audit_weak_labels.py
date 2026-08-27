"""Audit weak labels and freeze Phase 3 or Phase 8 artifact inventories."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from visolexnorm.common.artifacts import sha256_file
from visolexnorm.common.io import atomic_write_jsonl, load_json, read_jsonl
from visolexnorm.common.progress import log_event


ROOT = Path(__file__).parents[1]
WEAK_VALIDATOR = Draft202012Validator(load_json(
    ROOT / "specs/003-weak-labeling-llm-review/contracts/weak-label.schema.json"
))


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
    paths = [
        Path(config["phase3_weak_label_path"]), Path(config["remaining_manifest_path"]),
        Path(config["remaining_manifest_report_path"]), Path(config["cache_path"]),
        Path(config["approved_exclusions_path"]), Path(config["review_stats_path"]),
        Path(config["protected_hashes_path"]), Path(config["lexical_policy_path"]),
        Path(config["frozen_prompt_path"]), weak_labels, audit,
    ]
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
        "counts": {"phase3": len(prior_ids), "phase8": len(rows) - len(prior_ids),
                   "expanded": len(rows), "unique_ids": len({row["id"] for row in rows})},
        "decision_distribution": dict(sorted(decisions.items())),
        "source_distribution": dict(sorted(sources.items())),
        "confidence_distribution": dict(sorted(confidence.items())),
        "artifacts": [artifact(path) for path in paths],
    }


def write_frozen_manifest(manifest: dict[str, Any], path: Path) -> None:
    if path.is_file():
        if load_json(path) != manifest:
            raise ValueError(f"Refusing to overwrite changed frozen manifest: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def phase3_artifacts(args: argparse.Namespace, config: dict[str, Any]) -> list[Path]:
    paths = [
        Path("data/processed/vilexnorm_train.jsonl"), Path("data/processed/vilexnorm_dev.jsonl"),
        Path("data/processed/vilexnorm_test.jsonl"), Path("data/processed/visolex_unlabeled.jsonl"),
        Path("data/processed/vilexnorm_protected_input_hashes.txt"), Path("model_a_artifacts.zip"),
        Path("outputs/model_a/dev_predictions.jsonl"), Path("outputs/model_a/dev_metrics.json"),
        Path("outputs/model_a/train_config.json"), Path("outputs/model_a/candidate_full_run_integrity.json"),
        Path("visolex_model_a_candidates.zip"), Path("data/intermediate/visolex_model_a_candidates.jsonl"),
        Path("data/intermediate/visolex_review_manifest.jsonl"), Path("data/intermediate/visolex_review_cache.sqlite3"),
        Path("outputs/pilot_review_report_v6.json"), Path("outputs/pilot_review_audit_v6.csv"),
        Path("configs/candidate_generation_config.json"), args.config,
        Path(config["lexical_policy_path"]), Path(config["frozen_prompt_path"]),
        args.weak_labels, args.stats, args.audit,
    ]
    if args.approved_exclusions:
        paths.append(args.approved_exclusions)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weak-labels", type=Path)
    parser.add_argument("--stats", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--phase-manifest", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--approved-exclusions", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    config = load_json(args.config)
    phase8 = config.get("phase") == 8
    args.weak_labels = args.weak_labels or Path(config["expanded_weak_label_path"] if phase8 else "data/processed/visolex_weak_labeled.jsonl")
    args.audit = args.audit or Path(config["expanded_audit_path"] if phase8 else "outputs/weak_label_audit.jsonl")
    args.phase_manifest = args.phase_manifest or Path(config["expanded_artifact_manifest_path"] if phase8 else "outputs/phase3_manifest.json")
    if not phase8 and args.stats is None:
        parser.error("--stats is required for Phase 3 audit")
    rows = read_jsonl(args.weak_labels)
    validate_rows(rows)
    log_event("START", f"Weak-label audit: phase={config.get('phase', 3)} records={len(rows)}", quiet=args.quiet)
    selected = select_audit_rows(rows, int(config["seed"]), int(config["audit_samples_per_stratum"]))
    atomic_write_jsonl(selected, args.audit)
    if phase8:
        write_frozen_manifest(build_phase8_manifest(config, args.weak_labels, args.audit), args.phase_manifest)
    else:
        artifacts = phase3_artifacts(args, config)
        missing = [path.as_posix() for path in artifacts if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Phase 3 manifest inputs missing: {missing}")
        manifest = {"phase": 3, "completion_status": "completed_with_approved_provider_exclusions" if args.approved_exclusions else "completed", "artifacts": [artifact(path) for path in artifacts]}
        args.phase_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.phase_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_event("DONE", f"Weak-label audit: selected={len(selected)} manifest={args.phase_manifest}", quiet=args.quiet)


if __name__ == "__main__":
    main()