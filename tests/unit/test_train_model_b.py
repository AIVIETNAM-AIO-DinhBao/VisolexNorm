import json
from pathlib import Path
import pytest
from scripts.train_model_b import checkpoint_inventory, validate_mixture_manifest

ROOT = Path(__file__).parents[2]

def test_checkpoint_inventory_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    (tmp_path / "tokenizer_config.json").write_text("{}")
    assert checkpoint_inventory(tmp_path) == checkpoint_inventory(tmp_path)

def test_manifest_validation_rejects_membership_tampering() -> None:
    from scripts.build_model_b_mixture import build_manifest
    manifest = build_manifest(ROOT, ROOT/"configs/model_b_config.json", ROOT/"outputs/phase3_manifest.json")
    config = json.loads((ROOT/"configs/model_b_config.json").read_text())
    manifest["epochs"][0]["ordered_ids"].pop()
    with pytest.raises(ValueError, match="ordered_ids mismatch"):
        validate_mixture_manifest(manifest, config)