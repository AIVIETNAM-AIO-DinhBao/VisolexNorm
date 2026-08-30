import pytest

from visolexnorm.review.pilot import export_rows


def manifest(sample_id: str) -> dict:
    return {
        "id": sample_id, "original_source": "ViHSD", "confidence_band": "low",
        "generation_status": "generated_text", "model_a_confidence": -0.2,
        "input_text": "mik ko bt", "candidate_text": "mình không biết", "is_pilot": True,
    }


def test_export_rows_prefills_machine_fields_and_human_columns() -> None:
    result = export_rows([manifest("a")], {"a": {"decision": "KEEP", "corrected_text": None, "reason_code": None}})
    assert result == [{
        "id": "a", "original_source": "ViHSD", "confidence_band": "low", "generation_status": "generated_text",
        "model_a_confidence": -0.2, "input_text": "mik ko bt", "candidate_text": "mình không biết",
        "llm_decision": "KEEP", "llm_corrected_text": "", "reason_code": "", "human_verdict": "",
        "issue_tags": "", "human_expected_target": "", "reviewer_note": "",
    }]


def test_export_rows_rejects_incomplete_cache() -> None:
    with pytest.raises(ValueError, match="missing=1"):
        export_rows([manifest("a")], {})