"""Byte-level characterization tests for frozen training artifacts."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from visolexnorm.training.mixtures import build_model_b_manifest, build_model_c_manifest
from visolexnorm.training.reports import build_model_c_exit_report


ROOT = Path(__file__).parents[2]


def serialized_json(value: dict, *, newline: str = "\n") -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").replace("\n", newline).encode("utf-8")


def test_model_b_reconstruction_is_byte_equivalent() -> None:
    manifest = build_model_b_manifest(ROOT, ROOT / "configs/model_b_config.json", ROOT / "outputs/phase3_manifest.json")
    frozen = ROOT / "outputs/model_b/training_mixture_manifest.json"
    assert serialized_json(manifest) == frozen.read_bytes()
    assert manifest["manifest_content_sha256"] == "9e197fc2bd7261645c527b872d4505425578d0d342e119d713f377fdabb32895"
    assert [epoch["epoch_seed"] for epoch in manifest["epochs"]] == [2026, 2027, 2028]


def test_model_c_reconstruction_is_byte_equivalent() -> None:
    manifest = build_model_c_manifest(ROOT, ROOT / "configs/model_c_config.json")
    frozen = ROOT / "outputs/model_c/training_mixture_manifest.json"
    assert serialized_json(manifest) == frozen.read_bytes()
    assert manifest["manifest_content_sha256"] == "c49567c2a7f470eb0101fa61b20bc02f095f6ddd5eac5848448f7290ee7504ad"
    assert [epoch["epoch_seed"] for epoch in manifest["epochs"]] == list(range(2026, 2034))
    usage = Counter(sample_id for epoch in manifest["epochs"] for sample_id in epoch["pseudo_ids"])
    assert len(usage) == 64813
    assert Counter(usage.values()) == {1: 62650, 2: 2163}
    assert not any(epoch["replacement_used"] for epoch in manifest["epochs"][:-1])
    assert manifest["epochs"][-1]["replacement_used"]


def test_model_c_exit_report_reconstruction_is_byte_equivalent() -> None:
    report = build_model_c_exit_report(ROOT)
    frozen = ROOT / "outputs/model_c/phase8_exit_report.json"
    assert serialized_json(report, newline="\r\n") == frozen.read_bytes()
    assert report["promotion_status"] == "blocked_pending_independent_frozen_holdout"
    assert report["app_checkpoint_changed"] is False
    assert report["test_inputs_loaded"] is False