from __future__ import annotations

import pytest

from scripts.select_remaining_review_manifest import select_remaining


def candidate(index: int) -> dict:
    return {
        "id": f"visolex_{index:06d}",
        "dataset": "ViSoLex",
        "original_source": "ViHSD",
        "input_text": f"source {index}",
        "candidate_text": f"candidate {index}",
        "model_a_confidence": -float(index),
        "candidate_checkpoint": "model_a",
        "generation_config_hash": "a" * 64,
        "sequence_token_count": 2,
        "generation_status": "generated_text",
    }


def config(candidate_count: int, prior_count: int) -> dict:
    return {
        "seed": 2026,
        "expected_candidate_count": candidate_count,
        "expected_prior_manifest_count": prior_count,
        "expected_remaining_count": candidate_count - prior_count,
    }


def test_selection_is_deterministic_and_preserves_candidate_order() -> None:
    candidates = [candidate(index) for index in range(1, 6)]
    prior = [candidates[1], candidates[3]]
    first = select_remaining(candidates, prior, config(5, 2))
    second = select_remaining(candidates, prior, config(5, 2))

    assert first == second
    assert [row["id"] for row in first] == ["visolex_000001", "visolex_000003", "visolex_000005"]
    assert [row["selection_rank"] for row in first] == [1, 2, 3]
    assert all(row["review_scope"] == "phase8_remaining" and not row["prior_manifest"] for row in first)


def test_selection_rejects_duplicate_or_unknown_prior_ids() -> None:
    candidates = [candidate(index) for index in range(1, 4)]
    with pytest.raises(ValueError, match="duplicate prior manifest ID"):
        select_remaining(candidates, [candidates[0], candidates[0]], config(3, 2))

    unknown = {**candidate(9), "id": "visolex_unknown"}
    with pytest.raises(ValueError, match="absent from candidates"):
        select_remaining(candidates, [unknown], config(3, 1))


def test_selection_rejects_candidate_without_required_provenance() -> None:
    invalid = candidate(1)
    invalid.pop("candidate_checkpoint")
    with pytest.raises(ValueError, match="Candidate fields do not match contract"):
        select_remaining([invalid], [], config(1, 0))