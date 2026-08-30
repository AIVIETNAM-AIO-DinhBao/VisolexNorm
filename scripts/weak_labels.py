"""Build and audit initial or expanded weak-label artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from visolexnorm.common.artifacts import sha256_file
from visolexnorm.common.io import atomic_write_jsonl, load_json, read_jsonl
from visolexnorm.common.progress import log_event
from visolexnorm.review.cache import ReviewCache
from visolexnorm.review.pipeline import validate_frozen_prompt
from visolexnorm.weak_labels.audit import audit_weak_labels
from visolexnorm.weak_labels.pipeline import build_expanded_pool, build_initial_pool, load_initial_exclusion_ids


def add_initial_parser(subparsers) -> None:
    parser = subparsers.add_parser("build-initial", help="Build strict Phase 3 weak labels")
    parser.add_argument("--manifest", type=Path, default=Path("data/intermediate/visolex_review_manifest.jsonl"))
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--protected-hashes", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/visolex_weak_labeled.jsonl"))
    parser.add_argument("--stats", type=Path, default=Path("outputs/weak_label_stats.json"))
    parser.add_argument("--excluded-ids-file", type=Path)
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=build_initial)


def add_expanded_parser(subparsers) -> None:
    parser = subparsers.add_parser("build-expanded", help="Build the Phase 8 weak-label union")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--config", type=Path, default=Path("configs/expanded_review_config.json"))
    parser.add_argument("--output", type=Path)
    parser.set_defaults(handler=build_expanded)


def add_audit_parser(subparsers) -> None:
    parser = subparsers.add_parser("audit", help="Audit weak labels and freeze artifact inventories")
    parser.add_argument("--weak-labels", type=Path)
    parser.add_argument("--stats", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--phase-manifest", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--approved-exclusions", type=Path)
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=run_audit)


def build_initial(args: argparse.Namespace) -> None:
    config = load_json(args.config)
    prompt_hash = validate_frozen_prompt(config, Path(config["frozen_prompt_path"]))
    manifest = read_jsonl(args.manifest)
    protected = {line.strip() for line in args.protected_hashes.read_text(encoding="utf-8").splitlines() if line.strip()}
    excluded = load_initial_exclusion_ids(args.excluded_ids_file)
    cache = ReviewCache.open_reader(args.cache or Path(config["cache_path"]))
    try:
        accepted, stats = build_initial_pool(manifest, protected, config, args.model, prompt_hash, cache, excluded)
    finally:
        cache.close()
    atomic_write_jsonl(accepted, args.output)
    args.stats.parent.mkdir(parents=True, exist_ok=True)
    args.stats.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_event("DONE", f"Weak-label build: accepted={len(accepted)} validation_drops={stats['validation_drop_count']} output={args.output} stats={args.stats}", quiet=args.quiet)


def build_expanded(args: argparse.Namespace) -> None:
    root = args.repo_root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    config = load_json(config_path)
    output = args.output or Path(config["expanded_weak_label_path"])
    output = output if output.is_absolute() else root / output
    rows, summary = build_expanded_pool(root, config_path)
    atomic_write_jsonl(rows, output)
    summary["expanded_weak_label_sha256"] = sha256_file(output)
    print(json.dumps(summary, ensure_ascii=False))


def run_audit(args: argparse.Namespace) -> None:
    config = load_json(args.config)
    phase8 = config.get("phase") == 8
    weak_labels = args.weak_labels or Path(config["expanded_weak_label_path"] if phase8 else "data/processed/visolex_weak_labeled.jsonl")
    audit = args.audit or Path(config["expanded_audit_path"] if phase8 else "outputs/weak_label_audit.jsonl")
    phase_manifest = args.phase_manifest or Path(config["expanded_artifact_manifest_path"] if phase8 else "outputs/phase3_manifest.json")
    log_event("START", f"Weak-label audit: phase={config.get('phase', 3)} records={len(read_jsonl(weak_labels))}", quiet=args.quiet)
    selected, _ = audit_weak_labels(config, config_path=args.config, weak_labels=weak_labels, stats=args.stats, audit=audit, phase_manifest=phase_manifest, approved_exclusions=args.approved_exclusions)
    log_event("DONE", f"Weak-label audit: selected={len(selected)} manifest={phase_manifest}", quiet=args.quiet)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_initial_parser(subparsers)
    add_expanded_parser(subparsers)
    add_audit_parser(subparsers)
    args = parser.parse_args()
    try:
        args.handler(args)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()