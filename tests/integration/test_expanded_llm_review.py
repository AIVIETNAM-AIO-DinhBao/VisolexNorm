from __future__ import annotations

import json
from pathlib import Path

import pytest

from visolexnorm.review.cache import ReviewCache
from visolexnorm.review.pipeline import (
    export_review_stats,
    load_approved_exclusions,
    run_batches,
    validate_manifest_scope,
)
from visolexnorm.review.provider import GeminiKeyPool


def row(index: int) -> dict:
    return {
        "id": f"phase8-{index}",
        "input_text": f"source {index}",
        "candidate_text": f"candidate {index}",
        "review_scope": "phase8_remaining",
        "prior_manifest": False,
    }


def config(count: int) -> dict:
    return {
        "expected_remaining_count": count,
        "required_review_scope": "phase8_remaining",
        "require_prior_manifest_false": True,
        "batch_size": 15,
        "max_retries": 2,
        "retry_backoff_seconds": [0, 0],
        "retry_jitter_max_seconds": 0,
        "quota_cooldown_seconds": 0,
    }


def successful_response(prompt: str) -> str:
    samples = json.loads(prompt.split("SAMPLES:\n", 1)[1])
    return json.dumps({"results": [
        {"id": sample["id"], "decision": "KEEP", "corrected_text": None, "reason_code": None}
        for sample in samples
    ]})


def test_phase8_scope_guard_and_resume_use_only_remaining_manifest(tmp_path: Path) -> None:
    rows = [row(index) for index in range(31)]
    review_config = config(len(rows))
    validate_manifest_scope(rows, review_config)
    cache = ReviewCache(tmp_path / "phase8.sqlite3")
    calls: list[str] = []

    def request(key: str, model: str, prompt: str) -> str:
        calls.append(key)
        return successful_response(prompt)

    pool = GeminiKeyPool(["key-a", "key-b"], cooldown_seconds=0)
    try:
        run_batches(rows, "SAMPLES:\n{samples_json}", "a" * 64, "lexical_norm_review_v1", "gemini-test", review_config, cache, pool, request, lambda _: None)
        assert calls == ["key-a", "key-b", "key-a"]
        run_batches(rows, "SAMPLES:\n{samples_json}", "a" * 64, "lexical_norm_review_v1", "gemini-test", review_config, cache, pool, request, lambda _: None)
        assert len(calls) == 3
        assert cache.completed_ids("lexical_norm_review_v1", "a" * 64, "gemini-test") == {row["id"] for row in rows}
    finally:
        cache.close()


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda rows: rows.__setitem__(0, {**rows[0], "review_scope": "phase3"}), "review_scope"),
        (lambda rows: rows.__setitem__(0, {**rows[0], "prior_manifest": True}), "prior manifest"),
        (lambda rows: rows.__setitem__(1, {**rows[1], "id": rows[0]["id"]}), "duplicate ID"),
    ],
)
def test_phase8_scope_guard_rejects_non_remaining_records(mutate, message: str) -> None:
    rows = [row(index) for index in range(2)]
    mutate(rows)
    with pytest.raises(ValueError, match=message):
        validate_manifest_scope(rows, config(2))


def exclusion(sample_id: str, prompt_hash: str, model: str) -> dict:
    return {
        "id": sample_id,
        "status": "approved_provider_exclusion",
        "reason_code": "GEMINI_PROHIBITED_CONTENT_PRE_INFERENCE",
        "review_identity_sha256": prompt_hash,
        "llm_model": model,
        "recovery_attempts": 1,
        "singleton_recovery": True,
        "provider_block_reason": "PROHIBITED_CONTENT",
        "candidate_count": 0,
        "approved_by": "project_owner",
        "approved_at": "2026-08-27T00:00:00+07:00",
    }


def test_approved_provider_exclusion_skips_request_and_closes_review(tmp_path: Path) -> None:
    rows = [row(index) for index in range(3)]
    prompt_hash, version, model = "a" * 64, "lexical_norm_review_v1", "gemini-test"
    cache = ReviewCache(tmp_path / "phase8.sqlite3")
    blocked_id = rows[1]["id"]
    attempt_id = cache.mark_attempt("blocked", prompt_hash, version, model, [blocked_id])
    metadata = {"candidate_count": 0, "prompt_block_reason": "PROHIBITED_CONTENT"}
    cache.complete_attempt(
        attempt_id, "failed", error_code="prompt_blocked",
        error_detail="GeminiResponseError: prompt_blocked", response_metadata=metadata,
    )
    cache.mark_failed("blocked", version, prompt_hash, model, "GeminiResponseError: prompt_blocked")
    exclusion_path = tmp_path / "exclusions.json"
    exclusion_payload = [exclusion(blocked_id, prompt_hash, model)]
    exclusion_path.write_text(json.dumps(exclusion_payload), encoding="utf-8")
    excluded_ids, loaded = load_approved_exclusions(
        exclusion_path, rows, prompt_hash, version, model, cache,
    )
    calls: list[list[str]] = []

    def request(key: str, request_model: str, prompt: str) -> str:
        samples = json.loads(prompt.split("SAMPLES:\n", 1)[1])
        calls.append([sample["id"] for sample in samples])
        return successful_response(prompt)

    run_batches(
        rows, "SAMPLES:\n{samples_json}", prompt_hash, version, model, config(3), cache,
        GeminiKeyPool(["key"], cooldown_seconds=0), request, lambda _: None,
        excluded_ids=excluded_ids,
    )
    assert all(blocked_id not in requested for requested in calls)
    assert cache.reconcile_superseded_failures(version, prompt_hash, model, excluded_ids) == 1
    stats = export_review_stats(
        tmp_path / "stats.json", rows, prompt_hash, version, model, cache,
        loaded, exclusion_path,
    )
    assert stats["valid_llm_review_count"] == 2
    assert stats["provider_exclusion_count"] == 1
    assert stats["reconciled_count"] == 3
    assert stats["batch_status_counts"].get("failed", 0) == 0
    assert stats["batch_status_counts"]["superseded"] == 1
    assert cache.failed_count(version, prompt_hash, model) == 0
    cache.close()


def test_approved_provider_exclusion_requires_singleton_cache_evidence(tmp_path: Path) -> None:
    rows = [row(0)]
    prompt_hash, version, model = "a" * 64, "lexical_norm_review_v1", "gemini-test"
    cache = ReviewCache(tmp_path / "phase8.sqlite3")
    exclusion_path = tmp_path / "exclusions.json"
    exclusion_path.write_text(
        json.dumps([exclusion(rows[0]["id"], prompt_hash, model)]), encoding="utf-8",
    )
    with pytest.raises(ValueError, match="No singleton PROHIBITED_CONTENT evidence"):
        load_approved_exclusions(exclusion_path, rows, prompt_hash, version, model, cache)
    cache.close()