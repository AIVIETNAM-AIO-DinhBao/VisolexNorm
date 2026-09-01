"""Validate the tracked Dev-based application-selection evidence."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_model_c_application_selection_uses_dev_and_preserves_fallback() -> None:
    selection = json.loads((ROOT / "outputs/app/model_selection.json").read_text(encoding="utf-8"))
    dev = json.loads((ROOT / "outputs/evaluation_dev/model_metrics.json").read_text(encoding="utf-8"))

    assert selection["selected_model"] == dev["selected_model"] == "model_c"
    assert selection["fallback_model"] == dev["ranking"][1] == "model_b"
    assert selection["selection_split"] == "dev"
    assert selection["selection_metric"] == "ERR"
    assert selection["test_metrics_used_for_selection"] is False
    assert selection["selected_dev_metrics"]["ERR"] == dev["models"]["model_c"]["ERR"]


def test_phase6_smoke_records_verified_local_runtime_and_gradio_acceptance() -> None:
    smoke = json.loads((ROOT / "outputs/app/model_c_promotion_smoke_test.json").read_text(encoding="utf-8"))

    assert smoke["preflight_passed"] is True
    assert smoke["selected_model"] == "model_c"
    assert smoke["fallback_model"] == "model_b"
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