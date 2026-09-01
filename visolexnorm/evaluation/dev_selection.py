"""Common Dev scoring for model selection without Test metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from visolexnorm.common.artifacts import sha256_file
from visolexnorm.common.io import read_jsonl


MODELS = ("model_a", "model_b", "model_c")
SELECTION_RULE = ("higher_ERR", "higher_f1", "higher_exact_sentence_match", "model_a")


def _canonical_dev_rows(path: Path) -> list[dict[str, str]]:
    rows = read_jsonl(path)
    result: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        prediction = row.get("prediction_text", row.get("prediction"))
        required = (row.get("id"), row.get("input_text"), row.get("target_text"), prediction)
        if not all(isinstance(value, str) for value in required):
            raise ValueError(f"Invalid Dev prediction at {path}:{index}")
        result.append({
            "id": row["id"],
            "input_text": row["input_text"],
            "target_text": row["target_text"],
            "prediction_text": prediction,
        })
    if not result or len({row["id"] for row in result}) != len(result):
        raise ValueError(f"Dev predictions are empty or contain duplicate IDs: {path}")
    return result


def score_dev_predictions(
    prediction_paths: dict[str, Path],
    *,
    evaluate_records: Callable[[list[dict[str, str]]], dict[str, Any]],
) -> dict[str, Any]:
    """Score aligned A/B/C Dev predictions under one metric implementation."""
    if set(prediction_paths) != set(MODELS):
        raise ValueError("Dev scoring requires exactly Model A, Model B, and Model C")
    rows = {model: _canonical_dev_rows(prediction_paths[model]) for model in MODELS}
    reference = [(row["id"], row["input_text"], row["target_text"]) for row in rows["model_a"]]
    for model in MODELS[1:]:
        aligned = [(row["id"], row["input_text"], row["target_text"]) for row in rows[model]]
        if aligned != reference:
            raise ValueError(f"{model} Dev predictions do not align with Model A")
    reports: dict[str, dict[str, Any]] = {}
    for model in MODELS:
        report = evaluate_records(rows[model])
        report["exact_sentence_match"] = sum(
            row["prediction_text"] == row["target_text"] for row in rows[model]
        ) / len(rows[model])
        report["prediction_sha256"] = sha256_file(prediction_paths[model])
        reports[model] = report
    ranking = sorted(
        MODELS,
        key=lambda model: (
            reports[model]["ERR"],
            reports[model]["f1"],
            reports[model]["exact_sentence_match"],
            model == "model_a",
        ),
        reverse=True,
    )
    return {
        "schema_version": 1,
        "split": "dev",
        "example_count": len(reference),
        "selection_metric": "ERR",
        "selection_rule": list(SELECTION_RULE),
        "models": reports,
        "ranking": ranking,
        "selected_model": ranking[0],
        "test_metrics_used_for_selection": False,
    }


def write_dev_metrics(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")