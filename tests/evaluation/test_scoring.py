import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from visolexnorm.evaluation.scoring import select_best_model, validate_prediction_rows


ROOT = Path(__file__).parents[2]
SCHEMA = Draft202012Validator(json.loads((ROOT / "specs/005-experiment-evaluation/contracts/prediction.schema.json").read_text(encoding="utf-8")))
DIGEST = "a" * 64


def _row(identifier: str = "test-1") -> dict:
    return {"id": identifier, "input_text": "ko", "target_text": "không", "prediction_text": "không", "model": "model_a", "checkpoint_checksum": DIGEST, "generation_config_hash": DIGEST}


def test_prediction_validation_requires_frozen_alignment() -> None:
    row = _row()
    validate_prediction_rows([row], [{"id": "test-1", "input_text": "ko", "target_text": "không"}], model="model_a", checkpoint_checksum=DIGEST, generation_config_hash=DIGEST, validator=SCHEMA)
    row["target_text"] = "khum"
    with pytest.raises(ValueError, match="align"):
        validate_prediction_rows([row], [{"id": "test-1", "input_text": "ko", "target_text": "không"}], model="model_a", checkpoint_checksum=DIGEST, generation_config_hash=DIGEST, validator=SCHEMA)


def test_selection_uses_frozen_err_direction_only_after_f1_tie() -> None:
    metrics = {"model_a": {"f1": 0.7, "ERR": 0.6}, "model_b": {"f1": 0.8, "ERR": 0.1}}
    assert select_best_model(metrics, ["higher_f1", "higher_ERR", "model_a"]) == ("model_b", "higher_f1")
    metrics["model_b"] = {"f1": 0.7, "ERR": 0.5}
    assert select_best_model(metrics, ["higher_f1", "higher_ERR", "model_a"]) == ("model_a", "higher_ERR")
    assert select_best_model(metrics, ["higher_f1", "lower_ERR", "model_a"]) == ("model_b", "lower_ERR")