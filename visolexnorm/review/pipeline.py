"""Review orchestration, scope guards, exclusions, and completion statistics."""

from __future__ import annotations

import json
import math
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from visolexnorm.common.artifacts import sha256_json
from visolexnorm.common.progress import ProgressReporter, log_event
from visolexnorm.review.cache import ReviewCache
from visolexnorm.review.contracts import RESPONSE_VALIDATOR, parse_response
from visolexnorm.review.policy import apply_policy, load_policy, review_identity_hash
from visolexnorm.review.provider import GeminiKeyPool, GeminiResponse, GeminiResponseError, classify_error, response_text, safe_error_detail


RECOVERABLE_RESPONSE_ERRORS = {
    "prompt_blocked", "no_candidates", "empty_response_text", "invalid_json_response",
    "response_schema_invalid", "response_id_mismatch", "finish_max_tokens", "finish_safety",
    "finish_prohibited_content", "finish_blocklist", "finish_spii", "finish_recitation",
    "finish_language", "finish_other",
}


def chunks(rows: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def render_prompt(template: str, rows: list[dict[str, Any]]) -> str:
    samples = [{"id": row["id"], "source": row["input_text"], "candidate": row["candidate_text"]} for row in rows]
    return template.replace("{samples_json}", json.dumps(samples, ensure_ascii=False, indent=2))


def validate_frozen_prompt(config: dict[str, Any], prompt_path: Path) -> str:
    if not config.get("prompt_frozen"):
        raise ValueError("Full review is blocked until prompt_frozen=true")
    policy = load_policy(Path(config["lexical_policy_path"]))
    digest = review_identity_hash(prompt_path.read_text(encoding="utf-8"), policy)
    if digest != config.get("frozen_prompt_sha256"):
        raise ValueError("Frozen prompt SHA-256 does not match the config")
    return digest


def validate_manifest_scope(rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    """Apply optional config guards for a review manifest namespace."""
    required_scope = config.get("required_review_scope")
    if required_scope is None:
        return
    if not isinstance(required_scope, str) or not required_scope:
        raise ValueError("required_review_scope must be a non-empty string")
    expected_count = config.get("expected_remaining_count")
    if expected_count is not None and len(rows) != int(expected_count):
        raise ValueError(f"Unexpected review manifest count: {len(rows)} != {expected_count}")
    ids = [row.get("id") for row in rows]
    if any(not isinstance(sample_id, str) or not sample_id for sample_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("Review manifest contains an invalid or duplicate ID")
    if any(row.get("review_scope") != required_scope for row in rows):
        raise ValueError(f"Review manifest must use review_scope={required_scope!r}")
    if config.get("require_prior_manifest_false") and any(row.get("prior_manifest") is not False for row in rows):
        raise ValueError("Review manifest contains an ID from a prior manifest")


def run_batches(
    rows: list[dict[str, Any]], template: str, prompt_hash: str, prompt_version: str,
    model: str, config: dict[str, Any], cache: ReviewCache, key_pool: GeminiKeyPool,
    request: Callable[[str, str, str], str | GeminiResponse], sleep: Callable[[float], None] = time.sleep,
    quiet: bool = False, policy: dict[str, Any] | None = None,
    excluded_ids: set[str] | None = None,
) -> None:
    """Run resumable batches while preserving retry, isolation, and cache semantics."""
    excluded = (excluded_ids or set()) & {row["id"] for row in rows}
    completed = cache.completed_ids(prompt_version, prompt_hash, model) & {row["id"] for row in rows}
    pending = [row for row in rows if row["id"] not in completed and row["id"] not in excluded]
    size = int(config["batch_size"])
    waits = list(config["retry_backoff_seconds"])
    max_retries = int(config["max_retries"])
    batch_total = math.ceil(len(pending) / size) if pending else 0
    reporter = ProgressReporter("Gemini review", len(rows), len(completed) + len(excluded), quiet=quiet)
    log_event("START", f"Gemini review: total={len(rows)} cached={len(completed)} excluded={len(excluded)} pending={len(pending)} batches={batch_total} batch_size={size} model={model} prompt={prompt_version}@{prompt_hash[:12]}", quiet=quiet)
    if completed or excluded:
        log_event("RESUME", f"Reusing {len(completed)} committed reviews and {len(excluded)} approved provider exclusions", quiet=quiet)

    def review_batch(batch: list[dict[str, Any]], batch_number: int, depth: int = 0) -> bool:
        ids = [row["id"] for row in batch]
        batch_id = sha256_json({"prompt_hash": prompt_hash, "ids": ids})[:24]
        rendered = render_prompt(template, batch)
        last_error, last_code, attempts_made = "unknown", "api_or_transport_error", 0
        for attempt in range(max_retries):
            try:
                key = key_pool.acquire()
            except RuntimeError:
                log_event("WAIT", f"Gemini batch {batch_number}/{batch_total}: all keys cooling down; waiting {config['quota_cooldown_seconds']}s", quiet=quiet)
                sleep(float(config["quota_cooldown_seconds"]))
                key = key_pool.acquire()
            attempt_id = cache.mark_attempt(batch_id, prompt_hash, prompt_version, model, ids)
            attempts_made += 1
            raw: str | None = None
            metadata: dict[str, Any] = {}
            try:
                recovery = f" recovery_depth={depth}" if depth else ""
                log_event("REQUEST", f"Gemini batch {batch_number}/{batch_total}: samples={len(ids)} attempt={attempt + 1}/{max_retries}{recovery}", quiet=quiet)
                raw, metadata = response_text(request(key, model, rendered))
                results = parse_response(raw, ids, RESPONSE_VALIDATOR)
                if policy is not None:
                    results = apply_policy(batch, results, policy)
                cache.commit_success(batch_id, prompt_hash, prompt_version, model, results, raw)
                cache.complete_attempt(attempt_id, "succeeded", response_metadata=metadata)
                last_error = ""
                reporter.advance(len(batch), f"batch={batch_number}/{batch_total} committed")
                return True
            except Exception as error:
                last_error, last_code = f"{type(error).__name__}: {error}", safe_error_detail(error)
                if isinstance(error, GeminiResponseError):
                    metadata, raw = error.metadata, error.raw_response
                cache.complete_attempt(attempt_id, "failed", error_code=last_code, error_detail=last_error, response_metadata=metadata, raw_response=raw)
                category = classify_error(error)
                if category == "quota":
                    key_pool.cooldown(key)
                    action = "key cooled down"
                elif category == "auth":
                    key_pool.disable(key)
                    action = "key disabled"
                else:
                    action = "will retry"
                deterministic_block = last_code in {"prompt_blocked", "no_candidates", "finish_safety", "finish_prohibited_content", "finish_blocklist", "finish_spii", "finish_max_tokens"}
                if deterministic_block:
                    action = "will isolate samples" if len(batch) > 1 else "will not retry blocked sample"
                    log_event("RETRY", f"Gemini batch {batch_number}/{batch_total}: attempt={attempt + 1}/{max_retries} category=response action={action} error={last_code}", quiet=quiet)
                    break
                if depth and last_code in RECOVERABLE_RESPONSE_ERRORS:
                    action = "will continue isolation" if len(batch) > 1 else "will not repeat isolated sample"
                    log_event("RETRY", f"Gemini batch {batch_number}/{batch_total}: attempt={attempt + 1}/{max_retries} category=response action={action} error={last_code}", quiet=quiet)
                    break
                if attempt + 1 < max_retries:
                    wait = float(waits[min(attempt, len(waits) - 1)]) + random.uniform(0, float(config["retry_jitter_max_seconds"]))
                    log_event("RETRY", f"Gemini batch {batch_number}/{batch_total}: attempt={attempt + 1}/{max_retries} category={category} action={action} wait={wait:.1f}s error={last_code}", quiet=quiet)
                    sleep(wait)
        if last_error:
            cache.mark_failed(batch_id, prompt_version, prompt_hash, model, last_error)
            if len(batch) > 1 and last_code in RECOVERABLE_RESPONSE_ERRORS:
                midpoint = len(batch) // 2
                log_event("RECOVERY", f"Gemini batch {batch_number}/{batch_total}: splitting samples={len(batch)} into {midpoint}+{len(batch) - midpoint} after error={last_code}", quiet=quiet)
                left = review_batch(batch[:midpoint], batch_number, depth + 1)
                right = review_batch(batch[midpoint:], batch_number, depth + 1)
                return left and right
            log_event("WARNING", f"Gemini batch {batch_number}/{batch_total}: failed; rerun resumes it. attempts={attempts_made} samples={len(batch)} error={last_code}", quiet=quiet)
            return False
        return True

    for batch_number, batch in enumerate(chunks(pending, size), start=1):
        review_batch(batch, batch_number)
    reporter.done(f"pending_batches={batch_total}")


def load_approved_exclusions(path: Path, rows: list[dict[str, Any]], prompt_hash: str, prompt_version: str, model: str, cache: ReviewCache) -> tuple[set[str], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Approved exclusions must be a non-empty JSON array")
    manifest_ids, completed, seen = {row["id"] for row in rows}, cache.completed_ids(prompt_version, prompt_hash, model), set()
    for exclusion in payload:
        if not isinstance(exclusion, dict) or not isinstance(exclusion.get("id"), str):
            raise ValueError("Each approved exclusion must be an object containing id")
        sample_id = exclusion["id"]
        if sample_id in seen:
            raise ValueError(f"Duplicate approved exclusion ID: {sample_id}")
        seen.add(sample_id)
        if sample_id not in manifest_ids:
            raise ValueError(f"Approved exclusion is outside the review manifest: {sample_id}")
        if sample_id in completed:
            raise ValueError(f"Approved exclusion already has a committed review: {sample_id}")
        expected = {"status": "approved_provider_exclusion", "reason_code": "GEMINI_PROHIBITED_CONTENT_PRE_INFERENCE", "review_identity_sha256": prompt_hash, "llm_model": model, "singleton_recovery": True, "provider_block_reason": "PROHIBITED_CONTENT", "candidate_count": 0, "approved_by": "project_owner"}
        for field_name, expected_value in expected.items():
            if exclusion.get(field_name) != expected_value:
                raise ValueError(f"Invalid approved exclusion field {field_name} for {sample_id}")
        if not isinstance(exclusion.get("recovery_attempts"), int) or exclusion["recovery_attempts"] < 1:
            raise ValueError(f"Invalid recovery_attempts for {sample_id}")
        if not isinstance(exclusion.get("approved_at"), str) or not exclusion["approved_at"]:
            raise ValueError(f"Missing approved_at for {sample_id}")
        evidence = cache.blocked_singleton_metadata(prompt_version, prompt_hash, model, sample_id)
        if not any(item.get("prompt_block_reason") == "PROHIBITED_CONTENT" and item.get("candidate_count") == 0 for item in evidence):
            raise ValueError(f"No singleton PROHIBITED_CONTENT evidence for {sample_id}")
    return seen, payload


def export_review_stats(path: Path, rows: list[dict[str, Any]], prompt_hash: str, prompt_version: str, model: str, cache: ReviewCache, exclusions: list[dict[str, Any]], exclusion_path: Path | None) -> dict[str, Any]:
    ids = [row["id"] for row in rows]
    reviews = cache.results_for_ids(ids, prompt_version, prompt_hash, model)
    decisions = Counter(review["decision"] for review in reviews.values())
    reasons = Counter(review["reason_code"] for review in reviews.values() if review["decision"] == "REJECT")
    batch_statuses = Counter(cache.batch_status_counts(prompt_version, prompt_hash, model))
    attempt_outcomes = Counter(cache.attempt_outcome_counts(prompt_version, prompt_hash, model))
    report = {
        "phase": 8,
        "completion_status": "completed_with_approved_provider_exclusions" if exclusions else "completed",
        "manifest_review_count": len(rows), "valid_llm_review_count": len(reviews),
        "provider_exclusion_count": len(exclusions), "reconciled_count": len(reviews) + len(exclusions),
        "decision_counts": {key: decisions.get(key, 0) for key in ("KEEP", "EDIT", "REJECT")},
        "reject_reason_counts": {str(key): value for key, value in sorted(reasons.items())},
        "batch_status_counts": dict(sorted(batch_statuses.items())),
        "attempt_outcome_counts": {f"{status}:{code}": count for (status, code), count in sorted(attempt_outcomes.items())},
        "prompt_version": prompt_version, "review_identity_sha256": prompt_hash, "llm_model": model,
        "cache_path": cache.path.as_posix(),
        "approved_exclusions_path": exclusion_path.as_posix() if exclusion_path else None,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if report["reconciled_count"] != len(rows) or batch_statuses.get("failed", 0):
        raise RuntimeError("Review stats cannot be exported before all IDs and failed batches are reconciled")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report