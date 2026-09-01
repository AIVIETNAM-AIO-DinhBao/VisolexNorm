import json
from pathlib import Path

import pytest

from scripts.evaluation_metrics import evaluate_records, token_levenshtein_distance

ROOT = Path(__file__).parents[2]


def test_frozen_metric_parity_fixture() -> None:
    fixture = json.loads((ROOT / "tests/fixtures/phase5/metric_parity.json").read_text(encoding="utf-8"))
    actual = evaluate_records(fixture["records"])
    for key, expected in fixture["expected"].items():
        assert actual[key] == pytest.approx(expected) if isinstance(expected, float) else actual[key] == expected


def test_generator_records_are_counted_once() -> None:
    rows = ({"input_text": "ko", "target_text": "không", "prediction_text": "không"} for _ in range(2))
    assert evaluate_records(rows)["sample_count"] == 2


def test_token_levenshtein_preserves_one_to_many_and_many_to_one_costs() -> None:
    assert token_levenshtein_distance("mng", "mọi người") == 2
    assert token_levenshtein_distance("mọi người", "mng") == 2


def test_err_is_one_for_perfect_normalization_and_zero_for_leave_as_is() -> None:
    perfect = evaluate_records([
        {"input_text": "ko đi học", "target_text": "không đi học", "prediction_text": "không đi học"}
    ])
    unchanged = evaluate_records([
        {"input_text": "ko đi học", "target_text": "không đi học", "prediction_text": "ko đi học"}
    ])
    assert perfect["ERR"] == pytest.approx(1.0)
    assert unchanged["ERR"] == pytest.approx(0.0)


def test_err_penalizes_wrong_edits_and_can_be_negative() -> None:
    report = evaluate_records([
        {"input_text": "ko đi học", "target_text": "không đi học", "prediction_text": "ko về chơi"}
    ])
    assert report["system_token_errors"] > report["lai_token_errors"]
    assert report["ERR"] < 0.0


def test_err_penalizes_over_normalization_and_is_not_recall() -> None:
    report = evaluate_records([
        {"input_text": "ko đi học", "target_text": "không đi học", "prediction_text": "không đi học"},
        {"input_text": "hôm nay đi học", "target_text": "hôm nay đi học", "prediction_text": "hôm qua nghỉ học"},
    ])
    assert report["recall"] == pytest.approx(1.0)
    assert report["ERR"] < report["recall"]


def test_degenerate_all_canonical_subset_retains_error_counts_for_bootstrap() -> None:
    report = evaluate_records([
        {"input_text": "hôm nay đi học", "target_text": "hôm nay đi học", "prediction_text": "hôm qua nghỉ học"}
    ])
    assert report["lai_token_errors"] == 0
    assert report["system_token_errors"] > 0
    assert report["ERR"] == 0.0