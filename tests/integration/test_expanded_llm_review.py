from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.gemini_key_pool import GeminiKeyPool
from scripts.review_cache import ReviewCache
from scripts.review_candidates import run_batches, validate_manifest_scope


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