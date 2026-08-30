"""Build validated weak labels from the frozen SQLite review namespace."""

from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from visolexnorm.common.artifacts import sha256_text
from visolexnorm.common.io import clean_text, load_json
from visolexnorm.common.progress import ProgressReporter


ROOT = Path(__file__).parents[2]
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


def build_records(manifest, reviews, protected_hashes, config, model, prompt_version, quiet=False, excluded_ids=None):
    excluded_ids = excluded_ids or set()
    decisions = Counter()
    drops = Counter()
    generation_statuses = Counter()
    by_source = defaultdict(Counter)
    by_confidence = defaultdict(Counter)
    accepted = []
    seen_inputs = set()
    reporter = ProgressReporter("Weak-label validation", len(manifest), quiet=quiet)
    for index, item in enumerate(manifest, start=1):
        review = reviews.get(item["id"])
        if review is None:
            drops["llm_unreviewable_invalid_json" if item["id"] in excluded_ids else "missing_valid_review"] += 1
            if index % 1000 == 0 or index == len(manifest):
                reporter.advance(1000 if index % 1000 == 0 else index % 1000)
            continue
        decision = review["decision"]
        generation_statuses[item["generation_status"]] += 1
        decisions[decision] += 1
        by_source[item["original_source"]][decision] += 1
        by_confidence[item["confidence_band"]][decision] += 1
        if decision == "REJECT":
            drops["llm_reject"] += 1
            if index % 1000 == 0 or index == len(manifest):
                reporter.advance(1000 if index % 1000 == 0 else index % 1000)
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
            if index % 1000 == 0 or index == len(manifest):
                reporter.advance(1000 if index % 1000 == 0 else index % 1000)
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
        if index % 1000 == 0 or index == len(manifest):
            reporter.advance(1000 if index % 1000 == 0 else index % 1000)
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
