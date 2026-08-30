"""Structured Gemini response contracts and strict response parsing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from visolexnorm.common.io import load_json


ROOT = Path(__file__).parents[2]
RESPONSE_SCHEMA = load_json(ROOT / "specs/003-weak-labeling-llm-review/contracts/review-response.schema.json")
RESPONSE_VALIDATOR = Draft202012Validator(RESPONSE_SCHEMA)
PROVIDER_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "minItems": 1,
            "maxItems": 15,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "decision", "corrected_text", "reason_code"],
                "properties": {
                    "id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["KEEP", "EDIT", "REJECT"]},
                    "corrected_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "reason_code": {
                        "anyOf": [
                            {"type": "string", "enum": ["AMBIGUOUS", "MEANING_UNCERTAIN", "CANDIDATE_UNUSABLE", "NOT_LEXICAL_NORMALIZATION", "OTHER"]},
                            {"type": "null"},
                        ]
                    },
                },
            },
        }
    },
}


def parse_response(text: str, expected_ids: list[str], validator: Draft202012Validator = RESPONSE_VALIDATOR) -> list[dict[str, Any]]:
    """Parse, validate, and reorder one provider response to request ID order."""
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].strip().lower() in {"```", "```json"} and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("Gemini response is not valid JSON") from error
    for result in payload.get("results", []):
        for field in ("corrected_text", "reason_code"):
            if result.get(field) == "null":
                result[field] = None
    validator.validate(payload)
    results = payload["results"]
    actual = [result["id"] for result in results]
    if len(actual) != len(set(actual)) or set(actual) != set(expected_ids) or len(actual) != len(expected_ids):
        raise ValueError("Gemini response IDs do not exactly match the request batch")
    by_id = {result["id"]: result for result in results}
    return [by_id[sample_id] for sample_id in expected_ids]