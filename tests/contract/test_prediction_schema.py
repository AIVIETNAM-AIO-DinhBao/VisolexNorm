import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).parents[2]
SCHEMA = json.loads((ROOT / "specs/005-experiment-evaluation/contracts/prediction.schema.json").read_text())


def valid_prediction() -> dict:
    digest = "a" * 64
    return {"id": "vilexnorm_test_000001", "input_text": "ko", "target_text": "không", "prediction_text": "không", "model": "model_a", "checkpoint_checksum": digest, "generation_config_hash": digest}


def test_complete_prediction_is_valid() -> None:
    Draft202012Validator(SCHEMA).validate(valid_prediction())


@pytest.mark.parametrize("field,value", [("model", "model_c"), ("checkpoint_checksum", "bad"), ("id", "")])
def test_invalid_prediction_field_is_rejected(field: str, value: str) -> None:
    prediction = valid_prediction()
    prediction[field] = value
    with pytest.raises(ValidationError):
        Draft202012Validator(SCHEMA).validate(prediction)


def test_missing_or_extra_field_is_rejected() -> None:
    prediction = valid_prediction()
    prediction.pop("generation_config_hash")
    with pytest.raises(ValidationError):
        Draft202012Validator(SCHEMA).validate(prediction)
    prediction = valid_prediction()
    prediction["unexpected"] = True
    with pytest.raises(ValidationError):
        Draft202012Validator(SCHEMA).validate(prediction)