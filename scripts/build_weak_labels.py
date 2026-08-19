"""Build validated weak labels from the frozen SQLite review namespace."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).parent))
from data_utils import clean_text, read_jsonl  # noqa: E402
from phase3_utils import atomic_write_jsonl, load_json, sha256_text  # noqa: E402
from review_cache import ReviewCache  # noqa: E402
from review_candidates import validate_frozen_prompt  # noqa: E402


ROOT = Path(__file__).parents[1]
WEAK_VALIDATOR = Draft202012Validator(load_json(
    ROOT / "specs/003-weak-labeling-llm-review/contracts/weak-label.schema.json"
))


def is_artifact(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith(("{", "[", "```")) or '"decision"' in stripped


def normalized_input_hash(text: str) -> str:
    cleaned = clean_text(text)
    if cleaned is None:
        raise ValueError("Cannot hash empty text")
    return sha256_text(cleaned)


def build_records(manifest, reviews, protected_hashes, config, model, prompt_version):
    decisions = Counter()
    drops = Counter()
    generation_statuses = Counter()
    by_source = defaultdict(Counter)
    by_confidence = defaultdict(Counter)
    accepted = []
    seen_inputs = set()
    for item in manifest:
        review = reviews.get(item["id"])
        if review is None:
            drops["missing_valid_review"] += 1
            continue
        decision = review["decision"]
        generation_statuses[item["generation_status"]] += 1
        decisions[decision] += 1
        by_source[item["original_source"]][decision] += 1
        by_confidence[item["confidence_band"]][decision] += 1
        if decision == "REJECT":
            drops["llm_reject"] += 1
            continue
        target = item["candidate_text"] if decision == "KEEP" else review["corrected_text"]
        target = clean_text(target)
        reason = None
        if target is None:
            reason = "empty_target"
        elif is_artifact(target):
            reason = "response_artifact"
        elif normalized_input_hash(item["input_text"]) in protected_hashes:
            reason = "protected_overlap"
        elif item["input_text"] in seen_inputs:
            reason = "duplicate_input"
        else:
            length_ratio = len(target) / max(1, len(item["input_text"]))
            edit_ratio = 1 - SequenceMatcher(None, item["input_text"], target).ratio()
            if not float(config["min_length_ratio"]) <= length_ratio <= float(config["max_length_ratio"]):
                reason = "length_ratio"
            elif edit_ratio > float(config["max_edit_ratio"]):
                reason = "edit_ratio"
        if reason:
            drops[reason] += 1
            continue
        record = {
            "id": item["id"], "dataset": "ViSoLex", "original_source": item["original_source"],
            "input_text": item["input_text"], "candidate_text": item["candidate_text"],
            "model_a_confidence": item["model_a_confidence"], "confidence_band": item["confidence_band"],
            "generation_status": item["generation_status"],
            "llm_decision": decision, "llm_corrected_text": review["corrected_text"],
            "target_text": target, "label_source": "model_a+llm_review", "llm_model": model,
            "prompt_version": prompt_version, "accepted": True,
        }
        WEAK_VALIDATOR.validate(record)
        accepted.append(record)
        seen_inputs.add(item["input_text"])
        by_source[item["original_source"]]["accepted"] += 1
        by_confidence[item["confidence_band"]]["accepted"] += 1
    stats = {
        "manifest_review_count": len(manifest), "valid_llm_review_count": len(reviews),
        "keep_count": decisions["KEEP"], "edit_count": decisions["EDIT"],
        "reject_count": decisions["REJECT"],
        "keep_rate": decisions["KEEP"] / len(reviews) if reviews else 0.0,
        "edit_rate": decisions["EDIT"] / len(reviews) if reviews else 0.0,
        "reject_rate": decisions["REJECT"] / len(reviews) if reviews else 0.0,
        "validation_drop_count": sum(value for key, value in drops.items() if key != "llm_reject"),
        "drop_counts": dict(sorted(drops.items())), "final_accepted_count": len(accepted),
        "counts_by_generation_status": dict(sorted(generation_statuses.items())),
        "counts_by_original_source": {key: dict(value) for key, value in sorted(by_source.items())},
        "counts_by_confidence_band": {key: dict(value) for key, value in sorted(by_confidence.items())},
        "prompt_version": prompt_version, "llm_model": model,
    }
    return accepted, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Build strict Phase 3 weak labels.")
    parser.add_argument("--manifest", type=Path, default=Path("data/intermediate/visolex_review_manifest.jsonl"))
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--protected-hashes", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/visolex_weak_labeled.jsonl"))
    parser.add_argument("--stats", type=Path, default=Path("outputs/weak_label_stats.json"))
    args = parser.parse_args()
    config = load_json(args.config)
    prompt_hash = validate_frozen_prompt(config, Path(config["frozen_prompt_path"]))
    manifest = read_jsonl(args.manifest)
    protected_hashes = {line.strip() for line in args.protected_hashes.read_text(encoding="utf-8").splitlines() if line.strip()}
    cache = ReviewCache(args.cache or Path(config["cache_path"]))
    try:
        ids = [row["id"] for row in manifest]
        version = config["frozen_prompt_version"]
        reviews = cache.results_for_ids(ids, version, prompt_hash, args.model)
        if cache.failed_count(version, prompt_hash, args.model):
            raise RuntimeError("Review cache still contains failed batches")
    finally:
        cache.close()
    accepted, stats = build_records(
        manifest, reviews, protected_hashes, config, args.model, version
    )
    atomic_write_jsonl(accepted, args.output)
    args.stats.parent.mkdir(parents=True, exist_ok=True)
    args.stats.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(accepted)} weak labels -> {args.output}")


if __name__ == "__main__":
    main()