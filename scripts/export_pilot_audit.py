"""Export a complete, deterministic CSV worksheet for manual pilot review."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from scripts.lexical_policy import load_policy, review_identity_hash
from scripts.review_cache import ReviewCache
from visolexnorm.common.io import load_json, read_jsonl
from visolexnorm.common.progress import log_event


FIELDS = [
    "id", "original_source", "confidence_band", "generation_status", "model_a_confidence",
    "input_text", "candidate_text", "llm_decision", "llm_corrected_text", "reason_code",
    "human_verdict", "issue_tags", "human_expected_target", "reviewer_note",
]


def export_rows(manifest: list[dict], reviews: dict[str, dict]) -> list[dict]:
    ids = [row["id"] for row in manifest]
    if len(ids) != len(set(ids)):
        raise ValueError("Pilot manifest contains duplicate IDs")
    missing = [sample_id for sample_id in ids if sample_id not in reviews]
    extra = sorted(set(reviews) - set(ids))
    if missing or extra:
        raise ValueError(f"Pilot cache mismatch: missing={len(missing)} extra={len(extra)}")
    rows = []
    for item in sorted(manifest, key=lambda row: (row["original_source"], row["confidence_band"], row["id"])):
        review = reviews[item["id"]]
        rows.append({
            "id": item["id"],
            "original_source": item["original_source"],
            "confidence_band": item["confidence_band"],
            "generation_status": item["generation_status"],
            "model_a_confidence": item["model_a_confidence"],
            "input_text": item["input_text"],
            "candidate_text": item["candidate_text"],
            "llm_decision": review["decision"],
            "llm_corrected_text": review["corrected_text"] or "",
            "reason_code": review["reason_code"] or "",
            "human_verdict": "",
            "issue_tags": "",
            "human_expected_target": "",
            "reviewer_note": "",
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the reviewed pilot as a human-auditable CSV worksheet.")
    parser.add_argument("--pilot-manifest", type=Path, default=Path("data/intermediate/visolex_pilot_manifest.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--model", help="Defaults to GEMINI_MODEL from the environment")
    parser.add_argument("--output", type=Path, default=Path("outputs/pilot_review_audit.csv"))
    parser.add_argument("--quiet", action="store_true", help="Suppress operational logs")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise SystemExit("Install requirements.txt before exporting the pilot audit") from error
    load_dotenv()
    config = load_json(args.config)
    model = args.model or __import__("os").environ.get("GEMINI_MODEL", "").strip()
    if not model:
        raise SystemExit("Set GEMINI_MODEL in .env or pass --model")
    prompt_path = Path(config["draft_prompt_path"])
    policy = load_policy(Path(config["lexical_policy_path"]))
    prompt_hash = review_identity_hash(prompt_path.read_text(encoding="utf-8"), policy)
    version = config["draft_prompt_version"]
    manifest = read_jsonl(args.pilot_manifest)
    expected = int(config["pilot_per_stratum"]) * 4 * len(config["confidence_bands"])
    if len(manifest) != expected or not all(row.get("is_pilot") for row in manifest):
        raise ValueError(f"Pilot manifest must contain exactly {expected} pilot rows")
    log_event("START", f"Pilot audit export: manifest={len(manifest)} model={model} prompt={version}@{prompt_hash[:12]}", quiet=args.quiet)
    cache = ReviewCache(args.cache or Path(config["cache_path"]))
    try:
        ids = [row["id"] for row in manifest]
        if cache.failed_count(version, prompt_hash, model):
            raise RuntimeError("Pilot cache contains failed batches; rerun pilot review before audit export")
        reviews = cache.results_for_ids(ids, version, prompt_hash, model)
    finally:
        cache.close()
    rows = export_rows(manifest, reviews)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    decisions = Counter(row["llm_decision"] for row in rows)
    by_source = Counter(row["original_source"] for row in rows)
    empty = sum(row["generation_status"] == "empty_after_special_token_decode" for row in rows)
    log_event("DONE", f"Pilot audit export: rows={len(rows)} decisions={dict(decisions)} sources={dict(by_source)} empty_candidates={empty} output={args.output}", quiet=args.quiet)


if __name__ == "__main__":
    main()