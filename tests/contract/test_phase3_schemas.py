from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).parents[2]
CONTRACTS = ROOT / "specs/003-weak-labeling-llm-review/contracts"
FIXTURES = ROOT / "tests/fixtures/phase3"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("schema_name", "fixture_name"),
    [
        ("candidate.schema.json", "candidate.json"),
        ("review-response.schema.json", "review-response.json"),
        ("weak-label.schema.json", "weak-label.json"),
    ],
)
def test_valid_fixtures_match_contracts(schema_name: str, fixture_name: str) -> None:
    Draft202012Validator(load(CONTRACTS / schema_name)).validate(load(FIXTURES / fixture_name))


def test_edit_requires_corrected_text() -> None:
    record = load(FIXTURES / "weak-label.json")
    record["llm_corrected_text"] = None
    with pytest.raises(ValidationError):
        Draft202012Validator(load(CONTRACTS / "weak-label.schema.json")).validate(record)


def test_keep_requires_null_corrected_text() -> None:
    record = load(FIXTURES / "weak-label.json")
    record["llm_decision"] = "KEEP"
    with pytest.raises(ValidationError):
        Draft202012Validator(load(CONTRACTS / "weak-label.schema.json")).validate(record)


def test_empty_candidate_requires_explicit_empty_generation_status() -> None:
    record = load(FIXTURES / "candidate.json")
    record["candidate_text"] = ""
    with pytest.raises(ValidationError):
        Draft202012Validator(load(CONTRACTS / "candidate.schema.json")).validate(record)
    record["generation_status"] = "empty_after_special_token_decode"
    Draft202012Validator(load(CONTRACTS / "candidate.schema.json")).validate(record)


def test_weak_label_allows_audited_empty_model_candidate_but_not_empty_target() -> None:
    record = load(FIXTURES / "weak-label.json")
    record["candidate_text"] = ""
    record["generation_status"] = "empty_after_special_token_decode"
    Draft202012Validator(load(CONTRACTS / "weak-label.schema.json")).validate(record)
    record["target_text"] = ""
    with pytest.raises(ValidationError):
        Draft202012Validator(load(CONTRACTS / "weak-label.schema.json")).validate(record)