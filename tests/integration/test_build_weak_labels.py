from __future__ import annotations

import pytest

from scripts.build_expanded_weak_labels import validate_union
from scripts.build_weak_labels import build_records, normalized_input_hash


def item(sample_id, decision="KEEP"):
    return {
        "id": sample_id, "original_source": "ViHSD", "input_text": f"source {sample_id}",
        "candidate_text": f"candidate {sample_id}", "model_a_confidence": -0.1,
        "confidence_band": "medium", "generation_status": "generated_text",
    }


def review(decision, corrected=None):
    return {"decision": decision, "corrected_text": corrected}


def config():
    return {"min_length_ratio": 0.1, "max_length_ratio": 10, "max_edit_ratio": 1.0}


def test_decision_mapping_reject_and_protected_hash_filtering() -> None:
    manifest = [item("keep"), item("edit"), item("reject"), item("protected")]
    reviews = {
        "keep": review("KEEP"), "edit": review("EDIT", "edited target"),
        "reject": review("REJECT"), "protected": review("KEEP"),
    }
    protected = {normalized_input_hash("source protected")}
    accepted, stats = build_records(manifest, reviews, protected, config(), "model", "lexical_norm_review_v1")
    assert [row["id"] for row in accepted] == ["keep", "edit"]
    assert accepted[0]["target_text"] == "candidate keep"
    assert accepted[1]["target_text"] == "edited target"
    assert stats["reject_count"] == 1
    assert stats["drop_counts"]["protected_overlap"] == 1


def test_empty_model_candidate_is_not_accepted_through_keep() -> None:
    empty = item("icon")
    empty["input_text"] = "🥰🥰🥰"
    empty["candidate_text"] = ""
    empty["generation_status"] = "empty_after_special_token_decode"
    accepted, stats = build_records(
        [empty], {"icon": review("KEEP")}, set(), config(), "model", "lexical_norm_review_v1"
    )
    assert accepted == []
    assert stats["drop_counts"]["empty_target"] == 1
    assert stats["counts_by_generation_status"]["empty_after_special_token_decode"] == 1


def test_expanded_union_rejects_duplicate_ids() -> None:
    accepted, _ = build_records(
        [item("duplicate")], {"duplicate": review("KEEP")}, set(), config(),
        "model", "lexical_norm_review_v1",
    )
    with pytest.raises(ValueError, match="Duplicate weak-label ID"):
        validate_union(accepted, accepted + accepted, set())