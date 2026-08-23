import json
from pathlib import Path

import pytest

from scripts.evaluation_metrics import evaluate_records

ROOT = Path(__file__).parents[2]


def test_frozen_metric_parity_fixture() -> None:
    fixture = json.loads((ROOT / "tests/fixtures/phase5/metric_parity.json").read_text(encoding="utf-8"))
    actual = evaluate_records(fixture["records"])
    for key, expected in fixture["expected"].items():
        assert actual[key] == pytest.approx(expected) if isinstance(expected, float) else actual[key] == expected


def test_generator_records_are_counted_once() -> None:
    rows = ({"input_text": "ko", "target_text": "không", "prediction_text": "không"} for _ in range(2))
    assert evaluate_records(rows)["sample_count"] == 2