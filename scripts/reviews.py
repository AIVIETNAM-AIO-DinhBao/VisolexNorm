"""Run Gemini review, export pilot worksheets, and freeze approved prompts."""

from __future__ import annotations

import argparse
import csv
import os
from collections import Counter
from pathlib import Path

from visolexnorm.common.io import load_json, read_jsonl
from visolexnorm.common.progress import log_event
from visolexnorm.review.cache import ReviewCache
from visolexnorm.review.freeze import freeze_prompt
from visolexnorm.review.pilot import FIELDS, export_rows
from visolexnorm.review.pipeline import export_review_stats, load_approved_exclusions, run_batches, validate_frozen_prompt, validate_manifest_scope
from visolexnorm.review.policy import load_policy, review_identity_hash
from visolexnorm.review.provider import GeminiKeyPool, GeminiRequester


def add_run_parser(subparsers) -> None:
    parser = subparsers.add_parser("run", help="Run strict batched Gemini review")
    parser.add_argument("--mode", choices=("pilot", "full"), required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/intermediate/visolex_review_manifest.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--excluded-ids-file", type=Path)
    parser.add_argument("--stats", type=Path)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=run_review)


def add_export_parser(subparsers) -> None:
    parser = subparsers.add_parser("export-pilot", help="Export a reviewed pilot CSV worksheet")
    parser.add_argument("--pilot-manifest", type=Path, default=Path("data/intermediate/visolex_pilot_manifest.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--output", type=Path, default=Path("outputs/pilot_review_audit.csv"))
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=export_pilot)


def add_freeze_parser(subparsers) -> None:
    parser = subparsers.add_parser("freeze-prompt", help="Freeze a manually approved review prompt")
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--pilot-report", type=Path, required=True)
    parser.add_argument("--pilot-manifest", type=Path, default=Path("data/intermediate/visolex_pilot_manifest.jsonl"))
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=freeze)


def load_runtime_model(model: str | None = None) -> str:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError("Install requirements.txt before Gemini review.") from error
    load_dotenv()
    value = model or os.getenv("GEMINI_MODEL", "").strip()
    if not value:
        raise RuntimeError("Set GEMINI_MODEL in .env or pass --model")
    return value


def run_review(args: argparse.Namespace) -> None:
    try:
        from dotenv import load_dotenv
        import google.genai  # noqa: F401
    except ImportError as error:
        raise RuntimeError("Install requirements.txt before Gemini review.") from error
    load_dotenv()
    keys = [key.strip() for key in os.getenv("GEMINI_API_KEYS", "").split(",") if key.strip()]
    model = os.getenv("GEMINI_MODEL", "").strip()
    if not keys or not model:
        raise RuntimeError("Set GEMINI_API_KEYS and GEMINI_MODEL in .env")
    config = load_json(args.config)
    if args.batch_size is not None:
        if args.batch_size < 1:
            raise ValueError("--batch-size must be at least 1")
        config["batch_size"] = args.batch_size
    policy = load_policy(Path(config["lexical_policy_path"]))
    rows = read_jsonl(args.manifest)
    validate_manifest_scope(rows, config)
    if args.mode == "pilot":
        rows = [row for row in rows if row.get("is_pilot")]
        prompt_path, version = Path(config["draft_prompt_path"]), config["draft_prompt_version"]
        prompt_hash = review_identity_hash(prompt_path.read_text(encoding="utf-8"), policy)
    else:
        prompt_path, version = Path(config["frozen_prompt_path"]), config["frozen_prompt_version"]
        prompt_hash = validate_frozen_prompt(config, prompt_path)
    cache = ReviewCache(args.cache or Path(config["cache_path"]))
    requester = GeminiRequester()
    try:
        exclusion_path = args.excluded_ids_file or (Path(config["approved_exclusions_path"]) if config.get("approved_exclusions_path") else None)
        excluded_ids: set[str] = set()
        exclusions: list[dict] = []
        if exclusion_path is not None:
            excluded_ids, exclusions = load_approved_exclusions(exclusion_path, rows, prompt_hash, version, model, cache)
        run_batches(rows, prompt_path.read_text(encoding="utf-8"), prompt_hash, version, model, config, cache, GeminiKeyPool(keys, float(config["quota_cooldown_seconds"])), requester, quiet=args.quiet, policy=policy, excluded_ids=excluded_ids)
        missing = {row["id"] for row in rows} - cache.completed_ids(version, prompt_hash, model)
        if missing != excluded_ids:
            raise RuntimeError(f"Review incomplete: unresolved={len(missing - excluded_ids)} exclusions_with_reviews={len(excluded_ids - missing)}; rerun to resume")
        superseded = cache.reconcile_superseded_failures(version, prompt_hash, model, excluded_ids)
        if superseded:
            log_event("RECONCILE", f"Marked {superseded} failed batches as superseded by committed reviews or approved exclusions", quiet=args.quiet)
        if cache.failed_count(version, prompt_hash, model):
            raise RuntimeError("Review incomplete: unresolved failed batches remain")
        stats_path = args.stats or (Path(config["review_stats_path"]) if config.get("review_stats_path") else None)
        if stats_path is not None:
            export_review_stats(stats_path, rows, prompt_hash, version, model, cache, exclusions, exclusion_path)
        log_event("DONE", f"Gemini {args.mode} review completed: committed={len(rows) - len(excluded_ids)} excluded={len(excluded_ids)} cache={cache.path}", quiet=args.quiet)
    finally:
        requester.close()
        cache.close()


def export_pilot(args: argparse.Namespace) -> None:
    model = load_runtime_model(args.model)
    config = load_json(args.config)
    prompt_path = Path(config["draft_prompt_path"])
    prompt_hash = review_identity_hash(prompt_path.read_text(encoding="utf-8"), load_policy(Path(config["lexical_policy_path"])))
    version = config["draft_prompt_version"]
    manifest = read_jsonl(args.pilot_manifest)
    expected = int(config["pilot_per_stratum"]) * 4 * len(config["confidence_bands"])
    if len(manifest) != expected or not all(row.get("is_pilot") for row in manifest):
        raise ValueError(f"Pilot manifest must contain exactly {expected} pilot rows")
    log_event("START", f"Pilot audit export: manifest={len(manifest)} model={model} prompt={version}@{prompt_hash[:12]}", quiet=args.quiet)
    cache = ReviewCache.open_reader(args.cache or Path(config["cache_path"]))
    try:
        ids = [row["id"] for row in manifest]
        if cache.failed_count(version, prompt_hash, model):
            raise RuntimeError("Pilot cache contains failed batches; rerun pilot review before audit export")
        rows = export_rows(manifest, cache.results_for_ids(ids, version, prompt_hash, model))
    finally:
        cache.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    log_event("DONE", f"Pilot audit export: rows={len(rows)} decisions={dict(Counter(row['llm_decision'] for row in rows))} output={args.output}", quiet=args.quiet)


def freeze(args: argparse.Namespace) -> None:
    if not args.approved:
        raise RuntimeError("Pass --approved only after manually auditing all 240 pilot samples")
    config, count = freeze_prompt(args.config, args.pilot_report, args.pilot_manifest, replace_existing=args.replace_existing)
    log_event("DONE", f"Prompt freeze: prompt_version={config['frozen_prompt_version']} audited_ids={count} review_identity_sha256={config['frozen_prompt_sha256']} policy={config['frozen_policy_version']} config={args.config}", quiet=args.quiet)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_run_parser(subparsers)
    add_export_parser(subparsers)
    add_freeze_parser(subparsers)
    args = parser.parse_args()
    try:
        args.handler(args)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()