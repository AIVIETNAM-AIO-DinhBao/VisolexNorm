from scripts.generate_test_predictions import validate_predictions


def _test_rows() -> list[dict]:
    return [{"id": "test-1", "input_text": "ko", "target_text": "không"}]


def _prediction() -> dict:
    digest = "a" * 64
    return {"id": "test-1", "input_text": "ko", "target_text": "không", "prediction_text": "không", "model": "model_a", "checkpoint_checksum": digest, "generation_config_hash": digest}


def test_prediction_validator_accepts_aligned_contract() -> None:
    validate_predictions([_prediction()], _test_rows(), "model_a", "a" * 64, "a" * 64)


def test_prediction_validator_rejects_misaligned_input() -> None:
    prediction = _prediction()
    prediction["input_text"] = "khum"
    try:
        validate_predictions([prediction], _test_rows(), "model_a", "a" * 64, "a" * 64)
    except ValueError as error:
        assert "aligned" in str(error)
    else:
        raise AssertionError("Expected alignment validation to fail")