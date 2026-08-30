import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).parents[2]
SCHEMA = json.loads(
    (ROOT / "specs/009-posthoc-abc-benchmark/contracts/prediction.schema.json").read_text()
)


def prediction(model: str = "model_c") -> dict:
    digest = "a" * 64
    return {
        "id": "vilexnorm_test_000001",
        "input_text": "ko",
        "target_text": "không",
        "prediction_text": "không",
        "model": model,
        "checkpoint_checksum": digest,
        "generation_config_hash": digest,
    }


@pytest.mark.parametrize("model", ("model_a", "model_b", "model_c"))
def test_posthoc_schema_accepts_all_three_models(model: str) -> None:
    Draft202012Validator(SCHEMA).validate(prediction(model))


def test_posthoc_schema_rejects_unknown_model_and_empty_prediction() -> None:
    validator = Draft202012Validator(SCHEMA)
    invalid = prediction("model_d")
    with pytest.raises(ValidationError):
        validator.validate(invalid)
    invalid = prediction()
    invalid["prediction_text"] = ""
    with pytest.raises(ValidationError):
        validator.validate(invalid)