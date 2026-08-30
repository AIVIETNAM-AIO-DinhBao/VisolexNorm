import json
from pathlib import Path
import pytest
from visolexnorm.training.mixtures import build_model_b_manifest, validate_model_b_manifest
from visolexnorm.training.reports import checkpoint_inventory

ROOT = Path(__file__).parents[2]

def test_checkpoint_inventory_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    (tmp_path / "tokenizer_config.json").write_text("{}")
    assert checkpoint_inventory(tmp_path) == checkpoint_inventory(tmp_path)

def test_manifest_validation_rejects_membership_tampering() -> None:
    manifest = build_model_b_manifest(ROOT, ROOT/"configs/model_b_config.json", ROOT/"outputs/phase3_manifest.json")
    config = json.loads((ROOT/"configs/model_b_config.json").read_text())
    manifest["epochs"][0]["ordered_ids"].pop()
    with pytest.raises(ValueError, match="ordered_ids mismatch"):
        validate_model_b_manifest(manifest, config)