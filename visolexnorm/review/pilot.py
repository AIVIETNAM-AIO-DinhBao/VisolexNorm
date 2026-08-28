"""Export a complete, deterministic CSV worksheet for manual pilot review."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

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
