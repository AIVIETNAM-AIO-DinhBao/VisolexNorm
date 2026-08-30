"""Tests for the Phase 10 application checkpoint resolver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from visolexnorm.app.selection import resolve_checkpoint
from visolexnorm.evaluation.freeze import inventory


def write_checkpoint(path: Path, payload: str) -> str:
    path.mkdir(parents=True)
    (path / "config.json").write_text('{"model_type":"bart"}', encoding="utf-8")
    (path / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (path / "model.safetensors").write_text(payload, encoding="utf-8")
    return inventory(path)["sha256"]


def write_selection(path: Path, c_hash: str, b_hash: str) -> None:
    path.write_text(json.dumps({
        "selected_model": "model_c",
        "selected_checkpoint": "checkpoints/model_c",
        "selected_checkpoint_inventory_sha256": c_hash,
        "rollback_model": "model_b",
        "rollback_checkpoint": "checkpoints/model_b",
        "rollback_checkpoint_inventory_sha256": b_hash,
        "promotion_approved": True,
        "rollback_available": True,
    }), encoding="utf-8")


def test_resolve_uses_verified_model_c(tmp_path: Path) -> None:
    c_hash = write_checkpoint(tmp_path / "checkpoints/model_c", "model-c")
    b_hash = write_checkpoint(tmp_path / "checkpoints/model_b", "model-b")
    selection = tmp_path / "model_selection.json"
    write_selection(selection, c_hash, b_hash)

    resolved = resolve_checkpoint(selection, tmp_path)

    assert resolved.model == "model_c"
    assert resolved.fallback_applied is False
    assert resolved.checkpoint == tmp_path / "checkpoints/model_c"


def test_resolve_falls_back_to_verified_model_b_on_model_c_mismatch(tmp_path: Path) -> None:
    c_path = tmp_path / "checkpoints/model_c"
    c_hash = write_checkpoint(c_path, "model-c")
    b_hash = write_checkpoint(tmp_path / "checkpoints/model_b", "model-b")
    selection = tmp_path / "model_selection.json"
    write_selection(selection, c_hash, b_hash)
    (c_path / "model.safetensors").write_text("tampered", encoding="utf-8")

    resolved = resolve_checkpoint(selection, tmp_path)

    assert resolved.model == "model_b"
    assert resolved.fallback_applied is True
    assert "mismatch" in resolved.fallback_reason


def test_resolve_rejects_unverified_rollback(tmp_path: Path) -> None:
    c_path = tmp_path / "checkpoints/model_c"
    c_hash = write_checkpoint(c_path, "model-c")
    b_path = tmp_path / "checkpoints/model_b"
    b_hash = write_checkpoint(b_path, "model-b")
    selection = tmp_path / "model_selection.json"
    write_selection(selection, c_hash, b_hash)
    (c_path / "model.safetensors").write_text("tampered", encoding="utf-8")
    (b_path / "model.safetensors").write_text("tampered-too", encoding="utf-8")

    with pytest.raises(ValueError, match="rollback checkpoint inventory mismatch"):
        resolve_checkpoint(selection, tmp_path)