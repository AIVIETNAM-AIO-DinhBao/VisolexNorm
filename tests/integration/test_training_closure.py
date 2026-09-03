"""Tests for the post-training closure without altering release v1.0.0."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import verify_training_closure


ROOT = Path(__file__).parents[2]


def test_join_segments_requires_four_safe_parts() -> None:
    assert verify_training_closure.join_segments(["a" * 16] * 4) == "a" * 64
    for invalid in ([], ["a" * 16] * 3, ["A" * 16] * 4, ["a" * 15] * 4):
        try:
            verify_training_closure.join_segments(invalid)
        except ValueError:
            pass
        else:  # pragma: no cover - explicit failure detail
            raise AssertionError(f"Expected invalid segments: {invalid}")


def test_training_closure_preserves_app_boundary_and_segmented_format() -> None:
    closure = json.loads((ROOT / "release/training-closure.json").read_text(encoding="utf-8"))
    assert closure["application"]["default_artifact_id"] == "APP-DEFAULT"
    assert closure["application"]["fallback_artifact_id"] == "APP-FALLBACK"
    assert closure["application"]["cmax20_promotion_eligible"] is False
    assert closure["application"]["test_metrics_used_for_closure_selection"] is False
    for artifact in closure["artifacts"]:
        segments = artifact["sha256_segments"]
        if segments:
            assert len(segments) == 4
            assert all(len(segment) == 16 for segment in segments)
            assert "sha256" not in artifact
    assert "OPT-CMAX20-ANALYSIS" in {artifact["id"] for artifact in closure["artifacts"]}


def test_frontend_handoff_protects_model_selection_and_closure() -> None:
    handoff = (ROOT / "docs/frontend-handoff.md").read_text(encoding="utf-8")
    assert "Model C" in handoff and "Model B" in handoff
    assert "outputs/app/model_selection.json" in handoff
    assert "release/training-closure.json" in handoff
    assert "C-max20" in handoff


def test_report_and_closure_document_non_promotional_cmax_scope() -> None:
    report = (ROOT / "report/main.tex").read_text(encoding="utf-8")
    closure = (ROOT / "release/TRAINING_CLOSURE.md").read_text(encoding="utf-8")
    assert "Controlled factorial follow-up" in report
    assert "Exploratory maximum-20-epoch optimization" in report
    assert "not promotion eligible" in report
    assert "OPT-CMAX20 is exploratory" in closure