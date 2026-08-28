from __future__ import annotations

import json
from pathlib import Path

import pytest

from visolexnorm.review.policy import apply_policy, load_policy


ROOT = Path(__file__).parents[2]
POLICY = load_policy(ROOT / "configs/lexical_normalization_policy_v1.json")
CASES = json.loads((ROOT / "tests/fixtures/phase3/lexical_policy_calibration.json").read_text(encoding="utf-8"))


def result(case: dict) -> dict:
    return {"id": case["id"], "decision": case["decision"], "corrected_text": case["corrected_text"], "reason_code": None}


def row(case: dict) -> dict:
    return {"id": case["id"], "input_text": case["source"], "candidate_text": case["candidate"]}


def test_policy_canonicalizes_keep_and_prevents_target_regression() -> None:
    first, second = CASES[:2]
    adjusted = apply_policy([row(first), row(second)], [result(first), result(second)], POLICY)
    assert adjusted[0] == {"id": "canonical-keep", "decision": "EDIT", "corrected_text": "Giao hàng nhanh, sản phẩm tốt", "reason_code": None}
    assert adjusted[1]["corrected_text"] == "nhưng mà điện thoại tốt"


def test_policy_rejects_fully_opaque_input() -> None:
    case = CASES[2]
    adjusted = apply_policy([row(case)], [result(case)], POLICY)
    assert adjusted[0]["decision"] == "REJECT"
    assert adjusted[0]["reason_code"] == "NOT_LEXICAL_NORMALIZATION"


def test_policy_rejects_explicitly_ambiguous_source_phrase() -> None:
    case = CASES[3]
    adjusted = apply_policy([row(case)], [result(case)], POLICY)
    assert adjusted[0]["decision"] == "REJECT"
    assert adjusted[0]["reason_code"] == "AMBIGUOUS"


def test_policy_rejects_when_source_symbol_is_removed() -> None:
    case = CASES[4]
    adjusted = apply_policy([row(case)], [result(case)], POLICY)
    assert adjusted[0]["decision"] == "REJECT"
    assert adjusted[0]["reason_code"] == "OTHER"