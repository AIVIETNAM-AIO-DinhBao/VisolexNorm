"""Candidate record contracts shared by generation, manifests, and audits."""

from __future__ import annotations

from typing import Any

from visolexnorm.common.artifacts import ensure_finite_number


REQUIRED_INPUT = {"id", "dataset", "original_source", "input_text"}
REQUIRED_CANDIDATE = {
    "id", "dataset", "original_source", "input_text", "candidate_text",
    "model_a_confidence", "candidate_checkpoint", "generation_config_hash",
    "sequence_token_count", "generation_status",
}
GENERATION_STATUSES = {"generated_text", "empty_after_special_token_decode"}


def validate_inputs(records: list[dict[str, Any]]) -> None:
    """Validate canonical ViSoLex inputs before Model A generation."""
    seen: set[str] = set()
    for line_number, record in enumerate(records, start=1):
        if not REQUIRED_INPUT <= record.keys() or record.get("dataset") != "ViSoLex":
            raise ValueError(f"Invalid ViSoLex input at line {line_number}")
        if not isinstance(record.get("input_text"), str) or not record["input_text"]:
            raise ValueError(f"Empty input_text at line {line_number}")
        sample_id = record.get("id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen:
            raise ValueError(f"Invalid or duplicate ID at line {line_number}: {sample_id!r}")
        seen.add(sample_id)


def validate_candidate(record: dict[str, Any], expected: dict[str, Any], config_hash: str) -> None:
    """Validate a candidate against its exact source row and frozen config hash."""
    if set(record) != REQUIRED_CANDIDATE:
        raise ValueError(f"Candidate fields do not match contract for {expected['id']}")
    for field in ("id", "dataset", "original_source", "input_text"):
        if record[field] != expected[field]:
            raise ValueError(f"Candidate {expected['id']} changed field {field}")
    if not isinstance(record["candidate_text"], str):
        raise ValueError(f"Candidate text is not a string for {expected['id']}")
    if record.get("generation_status") not in GENERATION_STATUSES:
        raise ValueError(f"Invalid generation_status for {expected['id']}")
    if bool(record["candidate_text"]) != (record["generation_status"] == "generated_text"):
        raise ValueError(f"Candidate text/status mismatch for {expected['id']}")
    ensure_finite_number(record["model_a_confidence"], "model_a_confidence")
    if record["generation_config_hash"] != config_hash:
        raise ValueError(f"Candidate config hash mismatch for {expected['id']}")
    if not isinstance(record["sequence_token_count"], int) or record["sequence_token_count"] < 1:
        raise ValueError(f"Invalid sequence_token_count for {expected['id']}")


def validate_candidates(rows: list[dict[str, Any]]) -> None:
    """Validate the field contract and unique IDs for a candidate corpus."""
    seen: set[str] = set()
    for row in rows:
        if set(row) != REQUIRED_CANDIDATE:
            raise ValueError(f"Candidate fields do not match contract: {row.get('id')}")
        sample_id = row.get("id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen:
            raise ValueError(f"Invalid or duplicate candidate ID: {sample_id!r}")
        ensure_finite_number(row.get("model_a_confidence"), "model_a_confidence")
        seen.add(sample_id)