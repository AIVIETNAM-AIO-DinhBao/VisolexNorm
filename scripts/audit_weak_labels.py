"""Export deterministic stratified Phase 3 audit samples and artifact checksums."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from data_utils import read_jsonl
from phase3_utils import atomic_write_jsonl, load_json, log_event, sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit weak labels and write Phase 3 checksums.")
    parser.add_argument("--weak-labels", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--audit", type=Path, default=Path("outputs/weak_label_audit.jsonl"))
    parser.add_argument("--phase-manifest", type=Path, default=Path("outputs/phase3_manifest.json"))
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--approved-exclusions", type=Path)
    parser.add_argument("--quiet", action="store_true", help="Suppress operational progress logs")
    args = parser.parse_args()
    config = load_json(args.config)
    rows = read_jsonl(args.weak_labels)
    log_event("START", f"Weak-label audit: records={len(rows)} sample_per_stratum={config['audit_samples_per_stratum']}", quiet=args.quiet)
    strata = defaultdict(list)
    for row in rows:
        strata[(row["llm_decision"], row["original_source"], row["confidence_band"])].append(row)
    selected = []
    count = int(config["audit_samples_per_stratum"])
    for key in sorted(strata):
        pool = sorted(strata[key], key=lambda row: row["id"])
        random.Random(f"{config['seed']}:{key}").shuffle(pool)
        selected.extend(pool[:count])
    log_event("PROGRESS", f"Weak-label audit: strata={len(strata)} selected={len(selected)}", quiet=args.quiet)
    atomic_write_jsonl(selected, args.audit)
    artifacts = [
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
        artifacts.append(args.approved_exclusions)
    missing = [path.as_posix() for path in artifacts if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Phase 3 manifest inputs missing: {missing}")
    manifest = {
        "phase": 3,
        "completion_status": "completed_with_approved_provider_exclusions" if args.approved_exclusions else "completed",
        "artifacts": [
        {"path": path.as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in artifacts
        ],
    }
    args.phase_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.phase_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_event("DONE", f"Weak-label audit: audit_rows={len(selected)} checksums={len(artifacts)} audit={args.audit} manifest={args.phase_manifest}", quiet=args.quiet)


if __name__ == "__main__":
    main()