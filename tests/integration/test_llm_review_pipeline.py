from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.gemini_key_pool import GeminiKeyPool
from scripts.review_cache import ReviewCache
from scripts.review_candidates import parse_response, run_batches, safe_error_detail, validate_frozen_prompt, RESPONSE_VALIDATOR


def row(index: int) -> dict:
    return {"id": f"id-{index}", "input_text": f"source {index}", "candidate_text": f"candidate {index}"}


def config() -> dict:
    return {
        "batch_size": 15, "max_retries": 5, "retry_backoff_seconds": [0, 0, 0, 0, 0],
        "retry_jitter_max_seconds": 0, "quota_cooldown_seconds": 0,
    }


def successful_response(prompt: str) -> str:
    samples = json.loads(prompt.split("SAMPLES:\n", 1)[1])
    return json.dumps({"results": [
        {"id": sample["id"], "decision": "KEEP", "corrected_text": None, "reason_code": None}
        for sample in samples
    ]})


def test_batch_size_resume_and_atomic_sqlite(tmp_path: Path) -> None:
    cache = ReviewCache(tmp_path / "cache.sqlite3")
    calls = []

    def request(key, model, prompt):
        calls.append(key)
        return successful_response(prompt)

    rows = [row(index) for index in range(31)]
    pool = GeminiKeyPool(["key-a", "key-b"], cooldown_seconds=0)
    run_batches(rows, "SAMPLES:\n{samples_json}", "a" * 64, "draft", "model", config(), cache, pool, request, lambda _: None)
    assert len(calls) == 3
    assert calls == ["key-a", "key-b", "key-a"]
    run_batches(rows, "SAMPLES:\n{samples_json}", "a" * 64, "draft", "model", config(), cache, pool, request, lambda _: None)
    assert len(calls) == 3
    assert len(cache.completed_ids("draft", "a" * 64, "model")) == 31
    cache.close()


def test_progress_logs_are_secret_safe_and_show_resume(tmp_path: Path, capsys) -> None:
    cache = ReviewCache(tmp_path / "cache.sqlite3")
    rows = [row(index) for index in range(2)]

    def request(key, model, prompt):
        assert key == "super-secret-key"
        return successful_response(prompt)

    pool = GeminiKeyPool(["super-secret-key"], cooldown_seconds=0)
    run_batches(rows, "SAMPLES:\n{samples_json}", "a" * 64, "draft", "model", config(), cache, pool, request, lambda _: None)
    run_batches(rows, "SAMPLES:\n{samples_json}", "a" * 64, "draft", "model", config(), cache, pool, request, lambda _: None)
    output = capsys.readouterr().out
    assert "[START]" in output and "[PROGRESS]" in output and "[RESUME]" in output
    assert "super-secret-key" not in output and "source 0" not in output
    cache.close()


def test_safe_error_detail_is_actionable_without_request_content() -> None:
    assert safe_error_detail(RuntimeError("Cannot send a request, as the client has been closed.")) == "client_closed"
    assert safe_error_detail(RuntimeError("404 model not found")) == "model_or_endpoint_not_found"
    assert safe_error_detail(ValueError("source text must not leak")) == "api_or_transport_error"


def test_response_rejects_missing_or_duplicate_ids() -> None:
    payload = {"results": [{"id": "a", "decision": "KEEP", "corrected_text": None, "reason_code": None}]}
    with pytest.raises(ValueError):
        parse_response(json.dumps(payload), ["a", "b"], RESPONSE_VALIDATOR)


def test_response_accepts_a_single_json_code_fence() -> None:
    payload = {"results": [{"id": "a", "decision": "KEEP", "corrected_text": None, "reason_code": None}]}
    assert parse_response(f"```json\n{json.dumps(payload)}\n```", ["a"], RESPONSE_VALIDATOR) == payload["results"]


def test_response_recovers_one_json_object_and_literal_nulls() -> None:
    payload = {"results": [{"id": "a", "decision": "KEEP", "corrected_text": "null", "reason_code": "null"}]}
    parsed = parse_response(f"Here is the result:\n{json.dumps(payload)}\n", ["a"], RESPONSE_VALIDATOR)
    assert parsed == [{"id": "a", "decision": "KEEP", "corrected_text": None, "reason_code": None}]


def test_full_mode_requires_matching_frozen_hash(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("content", encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"version": "test", "canonical_replacements": {}, "unambiguous_abbreviations": {}}), encoding="utf-8")
    base = {"lexical_policy_path": str(policy)}
    with pytest.raises(ValueError):
        validate_frozen_prompt({**base, "prompt_frozen": False}, prompt)
    with pytest.raises(ValueError):
        validate_frozen_prompt({**base, "prompt_frozen": True, "frozen_prompt_sha256": "bad"}, prompt)


def test_quota_error_rotates_to_next_key_and_retries(tmp_path: Path) -> None:
    cache = ReviewCache(tmp_path / "quota.sqlite3")
    calls = []

    def request(key, model, prompt):
        calls.append(key)
        if len(calls) == 1:
            raise RuntimeError("429 quota exhausted")
        return successful_response(prompt)

    pool = GeminiKeyPool(["key-a", "key-b"], cooldown_seconds=60, clock=lambda: 0)
    run_batches([row(1)], "SAMPLES:\n{samples_json}", "a" * 64, "draft", "model", config(), cache, pool, request, lambda _: None)
    assert calls == ["key-a", "key-b"]
    assert cache.completed_ids("draft", "a" * 64, "model") == {"id-1"}
    cache.close()


def test_auth_error_disables_key_for_remaining_retries(tmp_path: Path) -> None:
    cache = ReviewCache(tmp_path / "auth.sqlite3")
    calls = []

    def request(key, model, prompt):
        calls.append(key)
        if key == "bad-key":
            raise RuntimeError("401 authentication failed")
        return successful_response(prompt)

    pool = GeminiKeyPool(["bad-key", "good-key"], cooldown_seconds=0)
    run_batches([row(1)], "SAMPLES:\n{samples_json}", "a" * 64, "draft", "model", config(), cache, pool, request, lambda _: None)
    assert calls == ["bad-key", "good-key"]
    assert pool.states[0].disabled is True
    cache.close()


def test_prompt_version_has_an_independent_cache_namespace(tmp_path: Path) -> None:
    cache = ReviewCache(tmp_path / "namespace.sqlite3")
    calls = []

    def request(key, model, prompt):
        calls.append(key)
        return successful_response(prompt)

    pool = GeminiKeyPool(["key"], cooldown_seconds=0)
    run_batches([row(1)], "SAMPLES:\n{samples_json}", "a" * 64, "draft", "model", config(), cache, pool, request, lambda _: None)
    run_batches([row(1)], "SAMPLES:\n{samples_json}", "a" * 64, "v1", "model", config(), cache, pool, request, lambda _: None)
    assert len(calls) == 2
    cache.close()


def test_failed_batch_is_reconciled_after_recovery_results(tmp_path: Path) -> None:
    cache = ReviewCache(tmp_path / "recovery.sqlite3")
    version, prompt_hash, model = "v1", "a" * 64, "gemini-test"
    ids = ["sample-1", "sample-2"]
    cache.mark_attempt("failed-batch", prompt_hash, version, model, ids)
    cache.mark_failed("failed-batch", version, prompt_hash, model, "invalid JSON")
    for sample_id in ids:
        batch_id = f"recovery-{sample_id}"
        cache.mark_attempt(batch_id, prompt_hash, version, model, [sample_id])
        cache.commit_success(batch_id, prompt_hash, version, model, [{
            "id": sample_id,
            "decision": "REJECT",
            "corrected_text": None,
            "reason_code": "AMBIGUOUS",
        }], '{"results": []}')
    assert cache.reconcile_superseded_failures(version, prompt_hash, model) == 1
    assert cache.failed_count(version, prompt_hash, model) == 0
    cache.close()


def test_failed_batch_is_reconciled_by_approved_exclusion(tmp_path: Path) -> None:
    cache = ReviewCache(tmp_path / "excluded.sqlite3")
    version, prompt_hash, model = "v1", "a" * 64, "gemini-test"
    cache.mark_attempt("blocked-batch", prompt_hash, version, model, ["blocked-sample"])
    cache.mark_failed("blocked-batch", version, prompt_hash, model, "provider prohibited content")
    assert cache.reconcile_superseded_failures(
        version, prompt_hash, model, {"blocked-sample"}
    ) == 1
    assert cache.failed_count(version, prompt_hash, model) == 0
    cache.close()