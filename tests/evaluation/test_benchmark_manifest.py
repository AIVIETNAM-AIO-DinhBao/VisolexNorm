from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from visolexnorm.evaluation.benchmark import BENCHMARK_SCOPE, verify_manifest


ROOT = Path(__file__).parents[2]


def options() -> Namespace:
    return Namespace(
        config=ROOT / "configs/posthoc_abc_benchmark_config.json",
        phase5_manifest=ROOT / "outputs/evaluation/freeze_manifest.json",
        phase5_metrics=ROOT / "outputs/evaluation/test_metrics.json",
        model_a_prediction=ROOT / "outputs/evaluation/model_a_test_predictions.jsonl",
        model_b_prediction=ROOT / "outputs/evaluation/model_b_test_predictions.jsonl",
        model_a_checkpoint=ROOT / "checkpoints/model_a",
        model_b_checkpoint=ROOT / "checkpoints/model_b",
        model_c_checkpoint=ROOT / "checkpoints/model_c",
        model_c_artifact_manifest=ROOT / "outputs/model_c/artifact_manifest.json",
        model_c_exit_report=ROOT / "outputs/model_c/phase8_exit_report.json",
        test=ROOT / "data/processed/vilexnorm_test.jsonl",
        generation_config=ROOT / "configs/evaluation_generation_config.json",
        metric_code=ROOT / "scripts/evaluation_metrics.py",
        phase3_manifest=ROOT / "outputs/phase3_manifest.json",
        phase4_exit_report=ROOT / "outputs/model_b/phase4_exit_report.json",
        schema=ROOT / "specs/009-posthoc-abc-benchmark/contracts/prediction.schema.json",
    )


def test_frozen_posthoc_manifest_verifies_current_inputs() -> None:
    manifest = json.loads(
        (ROOT / "outputs/evaluation_abc_posthoc/benchmark_manifest.json").read_text(encoding="utf-8")
    )
    verify_manifest(manifest, options())
    assert manifest["evaluation_scope"] == BENCHMARK_SCOPE
    assert manifest["test_previously_observed"] is True
    assert manifest["promotion_eligible"] is False
    assert manifest["phase5_selected_model"] == "model_b"


def test_posthoc_manifest_rejects_promotion_flag() -> None:
    manifest = json.loads(
        (ROOT / "outputs/evaluation_abc_posthoc/benchmark_manifest.json").read_text(encoding="utf-8")
    )
    manifest["promotion_eligible"] = True
    with pytest.raises(ValueError, match="post-hoc restrictions"):
        verify_manifest(manifest, options())