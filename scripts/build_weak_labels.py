"""Build validated ViSoLex weak labels from cached Gemini decisions, locally."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).parent))
from data_utils import clean_text, read_jsonl, write_jsonl  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def is_artifact(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith(("{", "[", "```")) or '"decision"' in stripped


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and build reviewed ViSoLex weak labels.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, default=Path("data/intermediate/gemini_review_cache.jsonl"))
    parser.add_argument("--vilexnorm-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/visolex_weak_labeled.jsonl"))
    parser.add_argument("--stats", type=Path, default=Path("outputs/weak_label_stats.json"))
    parser.add_argument("--config", type=Path, default=Path("configs/weak_label_config.json"))
    args = parser.parse_args()

    config = load_json(args.config)
    candidates = {row["id"]: row for row in read_jsonl(args.candidates)}
    manifest = read_jsonl(args.manifest)
    manifest_ids = {row.get("id") for row in manifest}
    if len(manifest_ids) != len(manifest) or not manifest_ids <= set(candidates):
        raise ValueError("Manifest must contain unique IDs found in candidate artifact")

    reviews: dict[str, dict[str, Any]] = {}
    for review in read_jsonl(args.reviews):
        sample_id = review.get("id")
        if review.get("parse_status") == "valid" and sample_id in manifest_ids:
            if sample_id in reviews:
                raise ValueError(f"Duplicate valid review for ID: {sample_id}")
            reviews[sample_id] = review

    protected: set[str] = set()
    for split in ("dev", "test"):
        path = args.vilexnorm_dir / f"vilexnorm_{split}.jsonl"
        if not path.is_file():
            raise FileNotFoundError(f"Required leakage-protection file is missing: {path}")
        protected.update(row["input_text"] for row in read_jsonl(path))

    decisions: Counter[str] = Counter()
    drops: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    by_confidence: dict[str, Counter[str]] = defaultdict(Counter)
    accepted: list[dict[str, Any]] = []
    for manifest_row in manifest:
        sample_id = manifest_row["id"]
        review = reviews.get(sample_id)
        if review is None:
            drops["missing_valid_review"] += 1
            continue
        candidate = candidates[sample_id]
        decision = review.get("llm_decision")
        decisions[str(decision)] += 1
        by_source[candidate["original_source"]][str(decision)] += 1
        confidence_group = str(manifest_row.get("confidence_bin", "unknown"))
        by_confidence[confidence_group][str(decision)] += 1
        if decision == "REJECT":
            drops["llm_reject"] += 1
            continue
        target = candidate["candidate_text"] if decision == "KEEP" else review.get("llm_corrected_text")
        target = clean_text(target)
        drop_reason: str | None = None
        if decision not in {"KEEP", "EDIT"}:
            drop_reason = "invalid_decision"
        elif target is None:
            drop_reason = "empty_target"
        elif is_artifact(target):
            drop_reason = "response_artifact"
        elif target in protected or candidate["input_text"] in protected:
            drop_reason = "dev_test_overlap"
        else:
            length_ratio = len(target) / max(1, len(candidate["input_text"]))
            edit_ratio = 1 - SequenceMatcher(None, candidate["input_text"], target).ratio()
            if not float(config["min_length_ratio"]) <= length_ratio <= float(config["max_length_ratio"]):
                drop_reason = "length_ratio"
            elif edit_ratio > float(config["max_edit_ratio"]):
                drop_reason = "edit_ratio"
        if drop_reason:
            drops[drop_reason] += 1
            continue
        record = {
            "id": candidate["id"],
            "dataset": "ViSoLex",
            "original_source": candidate["original_source"],
            "input_text": candidate["input_text"],
            "candidate_text": candidate["candidate_text"],
            "model_a_confidence": candidate["model_a_confidence"],
            "llm_decision": decision,
            "llm_corrected_text": review.get("llm_corrected_text"),
            "target_text": target,
            "label_source": "model_a+llm_review",
            "llm_model": review.get("llm_model"),
            "prompt_version": review.get("prompt_version"),
            "accepted": True,
        }
        accepted.append(record)
        by_source[candidate["original_source"]]["accepted"] += 1
        by_confidence[confidence_group]["accepted"] += 1

    # Inputs were globally deduplicated in Phase 1; retain this defensive check.
    if len({row["input_text"] for row in accepted}) != len(accepted):
        raise ValueError("Accepted weak labels have duplicate input_text values")
    write_jsonl(accepted, args.output)
    stats = {
        "model_a_candidate_count": len(candidates),
        "manifest_review_count": len(manifest),
        "valid_llm_review_count": len(reviews),
        "keep_count": decisions["KEEP"],
        "edit_count": decisions["EDIT"],
        "reject_count": decisions["REJECT"],
        "keep_rate": decisions["KEEP"] / len(reviews) if reviews else 0.0,
        "edit_rate": decisions["EDIT"] / len(reviews) if reviews else 0.0,
        "reject_rate": decisions["REJECT"] / len(reviews) if reviews else 0.0,
        "validation_drop_count": sum(value for key, value in drops.items() if key != "llm_reject"),
        "drop_counts": dict(sorted(drops.items())),
        "final_accepted_count": len(accepted),
        "counts_by_original_source": {key: dict(value) for key, value in sorted(by_source.items())},
        "counts_by_confidence_bin": {key: dict(value) for key, value in sorted(by_confidence.items())},
        "prompt_version": config["prompt_version"],
    }
    args.stats.parent.mkdir(parents=True, exist_ok=True)
    with args.stats.open("w", encoding="utf-8") as handle:
        json.dump(stats, handle, ensure_ascii=False, indent=2)
    print(f"Saved {len(accepted)} accepted weak labels -> {args.output}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()