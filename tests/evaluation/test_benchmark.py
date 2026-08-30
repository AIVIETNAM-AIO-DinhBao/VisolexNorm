from __future__ import annotations

from pathlib import Path

from visolexnorm.evaluation.benchmark import (
    BENCHMARK_SCOPE,
    _bootstrap_delta,
    _bootstrap_pairwise_metrics,
    _pairwise,
    _verify_model_c_artifacts,
    render_comparison,
)


def rows(predictions: list[str]) -> list[dict]:
    targets = ["a", "b", "c"]
    return [
        {
            "id": f"test-{index}",
            "input_text": target,
            "target_text": target,
            "prediction_text": prediction,
        }
        for index, (target, prediction) in enumerate(zip(targets, predictions), start=1)
    ]


def evaluator(records: list[dict]) -> dict[str, float]:
    return {"f1": sum(row["prediction_text"] == row["target_text"] for row in records) / len(records), "ERR": 0.0}


def test_bootstrap_delta_is_deterministic() -> None:
    left = rows(["a", "b", "c"])
    right = rows(["a", "x", "x"])
    first = _bootstrap_delta(left, right, evaluator, seed=2026, samples=40, metric="f1")
    second = _bootstrap_delta(left, right, evaluator, seed=2026, samples=40, metric="f1")
    assert first == second
    assert first["mean"] > 0


def test_precomputed_bootstrap_is_deterministic() -> None:
    def count_evaluator(records: list[dict]) -> dict[str, int]:
        correct = sum(row["prediction_text"] == row["target_text"] for row in records)
        return {"gold_edits": len(records), "predicted_edits": len(records), "correct_edits": correct}

    left = rows(["a", "b", "c"])
    right = rows(["a", "x", "x"])
    first = _bootstrap_pairwise_metrics(left, right, count_evaluator, seed=2026, samples=40)
    second = _bootstrap_pairwise_metrics(left, right, count_evaluator, seed=2026, samples=40)
    assert first == second
    assert first["f1"]["mean"] > 0


def test_pairwise_counts_and_comparison_disclaimer() -> None:
    model_c = rows(["a", "b", "x"])
    model_b = rows(["x", "b", "c"])
    assert _pairwise(model_c, model_b) == {
        "left_correct_right_wrong": 1,
        "right_correct_left_wrong": 1,
        "both_correct": 1,
        "both_wrong": 0,
    }
    reports = {
        "model_a": {"sample_count": 3, "ERR": 0.1, "precision": 0.1, "recall": 0.1, "f1": 0.1, "exact_sentence_match": 0.1},
        "model_b": {"sample_count": 3, "ERR": 0.2, "precision": 0.2, "recall": 0.2, "f1": 0.2, "exact_sentence_match": 0.2},
        "model_c": {"sample_count": 3, "ERR": 0.3, "precision": 0.3, "recall": 0.3, "f1": 0.3, "exact_sentence_match": 0.3},
    }
    text = render_comparison(reports, "model_c", {"phase5_manifest_sha256": "a" * 64})
    assert "post-hoc" in text.lower()
    assert "cannot promote Model C" in text
    assert BENCHMARK_SCOPE == "posthoc_previously_observed_vilexnorm_test"


def test_phase8_model_c_checkpoint_matches_its_artifact_manifest() -> None:
    root = Path(__file__).parents[2]
    _verify_model_c_artifacts(
        root / "checkpoints/model_c",
        root / "outputs/model_c/artifact_manifest.json",
        root / "outputs/model_c/phase8_exit_report.json",
    )