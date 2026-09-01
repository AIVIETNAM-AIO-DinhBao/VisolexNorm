"""Tests for application-model selection from common Dev metrics."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from visolexnorm.app.selection import build_dev_selection
from visolexnorm.evaluation.freeze import inventory


def _checkpoint(path: Path, value: str) -> str:
    path.mkdir(parents=True)
    (path / "config.json").write_text('{"model_type":"bart"}', encoding="utf-8")
    (path / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (path / "model.safetensors").write_text(value, encoding="utf-8")
    return inventory(path)["sha256"]


def _metrics(path: Path, reports: dict[str, dict[str, float]]) -> None:
    path.write_text(json.dumps({
        "schema_version": 1,
        "split": "dev",
        "selection_metric": "ERR",
        "selection_rule": ["higher_ERR", "higher_f1", "higher_exact_sentence_match", "model_a"],
        "models": reports,
    }), encoding="utf-8")


def _args(tmp_path: Path, reports: dict[str, dict[str, float]]) -> Namespace:
    metrics = tmp_path / "dev_metrics.json"
    _metrics(metrics, reports)
    hashes = {name: _checkpoint(tmp_path / f"checkpoints/{name}", name) for name in ("model_a", "model_b", "model_c")}
    return Namespace(
        dev_metrics=metrics,
        model_a_checkpoint=tmp_path / "checkpoints/model_a",
        model_b_checkpoint=tmp_path / "checkpoints/model_b",
        model_c_checkpoint=tmp_path / "checkpoints/model_c",
        expected_hashes=hashes,
    )


def test_dev_selection_chooses_highest_err_and_records_no_test_use(tmp_path: Path) -> None:
    args = _args(tmp_path, {
        "model_a": {"ERR": 0.60, "f1": 0.71, "exact_sentence_match": 0.52},
        "model_b": {"ERR": 0.66, "f1": 0.75, "exact_sentence_match": 0.55},
        "model_c": {"ERR": 0.67, "f1": 0.76, "exact_sentence_match": 0.56},
    })
    selection = build_dev_selection(args)
    assert selection["selected_model"] == "model_c"
    assert selection["fallback_model"] == "model_b"
    assert selection["selection_split"] == "dev"
    assert selection["test_metrics_used_for_selection"] is False


def test_dev_selection_is_not_hard_coded_to_model_c(tmp_path: Path) -> None:
    args = _args(tmp_path, {
        "model_a": {"ERR": 0.60, "f1": 0.71, "exact_sentence_match": 0.52},
        "model_b": {"ERR": 0.70, "f1": 0.75, "exact_sentence_match": 0.55},
        "model_c": {"ERR": 0.67, "f1": 0.76, "exact_sentence_match": 0.56},
    })
    assert build_dev_selection(args)["selected_model"] == "model_b"


def test_dev_selection_uses_f1_then_exact_match_as_tie_breaks(tmp_path: Path) -> None:
    args = _args(tmp_path, {
        "model_a": {"ERR": 0.70, "f1": 0.71, "exact_sentence_match": 0.52},
        "model_b": {"ERR": 0.70, "f1": 0.76, "exact_sentence_match": 0.55},
        "model_c": {"ERR": 0.70, "f1": 0.76, "exact_sentence_match": 0.56},
    })
    assert build_dev_selection(args)["selected_model"] == "model_c"