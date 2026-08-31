"""Validate the tracked Phase 10 application-selection evidence."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_model_c_application_selection_preserves_phase5_and_rollback() -> None:
    selection = json.loads((ROOT / "outputs/app/model_selection.json").read_text(encoding="utf-8"))
    phase5 = json.loads((ROOT / "outputs/evaluation/best_model.json").read_text(encoding="utf-8"))

    assert selection["selected_model"] == "model_c"
    assert selection["rollback_model"] == phase5["selected_model"] == "model_b"
    assert selection["benchmark_manifest_sha256"] == "b29cf856c61f4f190d6c4607f79b6a9b13b6d05be72f58d3eb8c0276610c240e"
    assert selection["model_c_f1"] > selection["model_b_f1"]
    assert selection["f1_delta_bootstrap_ci95"][0] > 0


def test_phase6_smoke_records_verified_local_runtime_and_gradio_acceptance() -> None:
    smoke = json.loads((ROOT / "outputs/app/model_c_promotion_smoke_test.json").read_text(encoding="utf-8"))

    assert smoke["preflight_passed"] is True
    assert smoke["selected_model"] == "model_c"
    assert smoke["rollback_model"] == "model_b"
    assert smoke["checkpoint_inventory_verified"] is True
    assert smoke["runtime_model_loaded"] is True
    assert smoke["tokenizer_loaded"] is True
    assert smoke["nonempty_inference_verified"] is True
    assert smoke["runtime_reused_on_second_call"] is True
    assert smoke["gradio_http_status"] == 200
    assert smoke["gradio_loopback_host"] == "127.0.0.1"
    assert smoke["gradio_public_share_enabled"] is False
    assert smoke["gradio_callback_verified"] is True
    assert smoke["runtime_limitation"] is None