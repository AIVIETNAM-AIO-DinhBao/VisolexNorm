"""Review Phase 3 manifest batches with Gemini and an atomic SQLite cache."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from scripts.gemini_key_pool import GeminiKeyPool, classify_error
from scripts.lexical_policy import apply_policy, load_policy, review_identity_hash
from scripts.review_cache import ReviewCache
from visolexnorm.common.artifacts import sha256_json, sha256_text
from visolexnorm.common.io import load_json, read_jsonl
from visolexnorm.common.progress import ProgressReporter, log_event


@dataclass
class GeminiResponse:
    """Text plus secret-safe provider diagnostics needed to explain parse failures."""

    text: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


class GeminiResponseError(RuntimeError):
    """A response completed but cannot be reviewed safely or parsed."""

    def __init__(
        self, code: str, *, metadata: dict[str, Any] | None = None,
        raw_response: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.metadata = metadata or {}
        self.raw_response = raw_response


def chunks(rows: list[dict[str, Any]], size: int):
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def render_prompt(template: str, rows: list[dict[str, Any]]) -> str:
    samples = [{"id": row["id"], "source": row["input_text"], "candidate": row["candidate_text"]} for row in rows]
    return template.replace("{samples_json}", json.dumps(samples, ensure_ascii=False, indent=2))


def parse_response(text: str, expected_ids: list[str], validator: Draft202012Validator) -> list[dict[str, Any]]:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].strip().lower() in {"```", "```json"} and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    # Gemini may prepend a short sentence despite response_mime_type. Accept
    # exactly one balanced top-level object, then retain schema/ID validation.
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("Gemini response is not valid JSON") from error
    for result in payload.get("results", []):
        # A few Gemini responses serialize a JSON null as the literal string
        # "null". Coerce only this exact, schema-equivalent representation.
        for field in ("corrected_text", "reason_code"):
            if result.get(field) == "null":
                result[field] = None
    validator.validate(payload)
    results = payload["results"]
    actual = [result["id"] for result in results]
    if len(actual) != len(set(actual)) or set(actual) != set(expected_ids) or len(actual) != len(expected_ids):
        raise ValueError("Gemini response IDs do not exactly match the request batch")
    by_id = {result["id"]: result for result in results}
    return [by_id[sample_id] for sample_id in expected_ids]


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


def safe_error_detail(error: Exception) -> str:
    """Return an actionable terminal code without exposing API/request content."""
    if isinstance(error, GeminiResponseError):
        return error.code
    text = str(error).lower()
    if "client has been closed" in text:
        return "client_closed"
    if "not found" in text or "404" in text:
        return "model_or_endpoint_not_found"
    if "invalid argument" in text or "400" in text:
        return "invalid_request"
    if "response is not valid json" in text:
        return "invalid_json_response"
    if "does not exactly match" in text:
        return "response_id_mismatch"
    if "validationerror" in type(error).__name__.lower():
        return "response_schema_invalid"
    return "api_or_transport_error"


def enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def response_diagnostics(response: Any) -> dict[str, Any]:
    """Extract provider status without retaining prompts, API keys, or generated text."""
    metadata: dict[str, Any] = {"candidate_count": len(response.candidates or [])}
    feedback = response.prompt_feedback
    if feedback is not None:
        metadata["prompt_block_reason"] = enum_value(feedback.block_reason)
        metadata["prompt_safety"] = [
            {
                "category": enum_value(rating.category),
                "probability": enum_value(rating.probability),
                "blocked": rating.blocked,
            }
            for rating in (feedback.safety_ratings or [])
        ]
    if response.candidates:
        candidate = response.candidates[0]
        metadata.update({
            "finish_reason": enum_value(candidate.finish_reason),
            "candidate_token_count": candidate.token_count,
            "candidate_safety": [
                {
                    "category": enum_value(rating.category),
                    "probability": enum_value(rating.probability),
                    "blocked": rating.blocked,
                }
                for rating in (candidate.safety_ratings or [])
            ],
        })
    usage = response.usage_metadata
    if usage is not None:
        metadata["usage"] = {
            "prompt_tokens": usage.prompt_token_count,
            "candidate_tokens": usage.candidates_token_count,
            "thought_tokens": usage.thoughts_token_count,
            "total_tokens": usage.total_token_count,
        }
    return metadata


def response_text(result: str | GeminiResponse) -> tuple[str, dict[str, Any]]:
    """Reject blocked, truncated, or textless responses before JSON parsing."""
    if isinstance(result, str):
        return result, {}
    metadata = result.metadata
    prompt_block = metadata.get("prompt_block_reason")
    if prompt_block and prompt_block != "BLOCKED_REASON_UNSPECIFIED":
        raise GeminiResponseError("prompt_blocked", metadata=metadata, raw_response=result.text)
    if metadata.get("candidate_count") == 0:
        raise GeminiResponseError("no_candidates", metadata=metadata, raw_response=result.text)
    finish_reason = metadata.get("finish_reason")
    if finish_reason and finish_reason not in {"STOP", "FINISH_REASON_UNSPECIFIED"}:
        raise GeminiResponseError(
            f"finish_{finish_reason.lower()}", metadata=metadata, raw_response=result.text,
        )
    if result.text is None or not result.text.strip():
        raise GeminiResponseError("empty_response_text", metadata=metadata, raw_response=result.text)
    return result.text, metadata


class GeminiRequester:
    """Keep each synchronous SDK client alive for the complete review run."""

    def __init__(self) -> None:
        self.clients: dict[str, Any] = {}

    def __call__(self, key: str, model: str, prompt: str) -> GeminiResponse:
        from google import genai
        from google.genai import types

        # Do not create the Client in a temporary expression: its finalizer can
        # close the underlying HTTP client while a request is still in flight.
        client = self.clients.setdefault(key, genai.Client(api_key=key))
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=PROVIDER_RESPONSE_SCHEMA,
                temperature=0,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        return GeminiResponse(response.text, response_diagnostics(response))

    def close(self) -> None:
        for client in self.clients.values():
            close = getattr(client, "close", None)
            if callable(close):
                close()


def run_batches(
    rows: list[dict[str, Any]], template: str, prompt_hash: str, prompt_version: str,
    model: str, config: dict[str, Any], cache: ReviewCache, key_pool: GeminiKeyPool,
    request: Callable[[str, str, str], str | GeminiResponse], sleep: Callable[[float], None] = time.sleep,
    quiet: bool = False, policy: dict[str, Any] | None = None,
    excluded_ids: set[str] | None = None,
) -> None:
    excluded = (excluded_ids or set()) & {row["id"] for row in rows}
    completed = cache.completed_ids(prompt_version, prompt_hash, model)
    completed &= {row["id"] for row in rows}
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
        last_error = "unknown"
        last_code = "api_or_transport_error"
        attempts_made = 0
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
                last_error = f"{type(error).__name__}: {error}"
                last_code = safe_error_detail(error)
                if isinstance(error, GeminiResponseError):
                    metadata = error.metadata
                    raw = error.raw_response
                cache.complete_attempt(
                    attempt_id, "failed", error_code=last_code, error_detail=last_error,
                    response_metadata=metadata, raw_response=raw,
                )
                category = classify_error(error)
                if category == "quota":
                    key_pool.cooldown(key)
                    action = "key cooled down"
                elif category == "auth":
                    key_pool.disable(key)
                    action = "key disabled"
                else:
                    action = "will retry"
                deterministic_block = last_code in {
                    "prompt_blocked", "no_candidates", "finish_safety",
                    "finish_prohibited_content", "finish_blocklist", "finish_spii", "finish_max_tokens",
                }
                if deterministic_block:
                    action = "will isolate samples" if len(batch) > 1 else "will not retry blocked sample"
                    log_event("RETRY", f"Gemini batch {batch_number}/{batch_total}: attempt={attempt + 1}/{max_retries} category=response action={action} error={last_code}", quiet=quiet)
                    break
                if depth and last_code in RECOVERABLE_RESPONSE_ERRORS:
                    action = "will continue isolation" if len(batch) > 1 else "will not repeat isolated sample"
                    log_event("RETRY", f"Gemini batch {batch_number}/{batch_total}: attempt={attempt + 1}/{max_retries} category=response action={action} error={last_code}", quiet=quiet)
                    break
                if attempt + 1 < max_retries:
                    wait = float(waits[min(attempt, len(waits) - 1)]) + random.uniform(
                        0, float(config["retry_jitter_max_seconds"])
                    )
                    log_event("RETRY", f"Gemini batch {batch_number}/{batch_total}: attempt={attempt + 1}/{max_retries} category={category} action={action} wait={wait:.1f}s error={last_code}", quiet=quiet)
                    sleep(wait)
        if last_error:
            cache.mark_failed(batch_id, prompt_version, prompt_hash, model, last_error)
            if len(batch) > 1 and last_code in RECOVERABLE_RESPONSE_ERRORS:
                midpoint = len(batch) // 2
                log_event(
                    "RECOVERY",
                    f"Gemini batch {batch_number}/{batch_total}: splitting samples={len(batch)} into {midpoint}+{len(batch) - midpoint} after error={last_code}",
                    quiet=quiet,
                )
                left = review_batch(batch[:midpoint], batch_number, depth + 1)
                right = review_batch(batch[midpoint:], batch_number, depth + 1)
                return left and right
            log_event("WARNING", f"Gemini batch {batch_number}/{batch_total}: failed; rerun resumes it. attempts={attempts_made} samples={len(batch)} error={last_code}", quiet=quiet)
            return False
        return True

    for batch_number, batch in enumerate(chunks(pending, size), start=1):
        review_batch(batch, batch_number)
    reporter.done(f"pending_batches={batch_total}")


ROOT = Path(__file__).parents[1]
RESPONSE_SCHEMA = load_json(ROOT / "specs/003-weak-labeling-llm-review/contracts/review-response.schema.json")
RESPONSE_VALIDATOR = Draft202012Validator(RESPONSE_SCHEMA)
PROVIDER_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "minItems": 1,
            "maxItems": 15,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "decision", "corrected_text", "reason_code"],
                "properties": {
                    "id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["KEEP", "EDIT", "REJECT"]},
                    "corrected_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "reason_code": {
                        "anyOf": [
                            {
                                "type": "string",
                                "enum": ["AMBIGUOUS", "MEANING_UNCERTAIN", "CANDIDATE_UNUSABLE", "NOT_LEXICAL_NORMALIZATION", "OTHER"],
                            },
                            {"type": "null"},
                        ]
                    },
                },
            },
        }
    },
}
RECOVERABLE_RESPONSE_ERRORS = {
    "prompt_blocked", "no_candidates", "empty_response_text", "invalid_json_response",
    "response_schema_invalid", "response_id_mismatch", "finish_max_tokens", "finish_safety",
    "finish_prohibited_content", "finish_blocklist", "finish_spii", "finish_recitation",
    "finish_language", "finish_other",
}


def load_approved_exclusions(
    path: Path, rows: list[dict[str, Any]], prompt_hash: str, prompt_version: str, model: str,
    cache: ReviewCache,
) -> tuple[set[str], list[dict[str, Any]]]:
    """Validate owner-approved exclusions against singleton provider-block evidence."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Approved exclusions must be a non-empty JSON array")
    manifest_ids = {row["id"] for row in rows}
    completed = cache.completed_ids(prompt_version, prompt_hash, model)
    seen: set[str] = set()
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
        expected = {
            "status": "approved_provider_exclusion",
            "reason_code": "GEMINI_PROHIBITED_CONTENT_PRE_INFERENCE",
            "review_identity_sha256": prompt_hash,
            "llm_model": model,
            "singleton_recovery": True,
            "provider_block_reason": "PROHIBITED_CONTENT",
            "candidate_count": 0,
            "approved_by": "project_owner",
        }
        for field_name, expected_value in expected.items():
            if exclusion.get(field_name) != expected_value:
                raise ValueError(f"Invalid approved exclusion field {field_name} for {sample_id}")
        if not isinstance(exclusion.get("recovery_attempts"), int) or exclusion["recovery_attempts"] < 1:
            raise ValueError(f"Invalid recovery_attempts for {sample_id}")
        if not isinstance(exclusion.get("approved_at"), str) or not exclusion["approved_at"]:
            raise ValueError(f"Missing approved_at for {sample_id}")
        attempts = cache.connection.execute(
            """SELECT response_metadata_json FROM review_attempts
               WHERE prompt_version=? AND prompt_hash=? AND llm_model=? AND error_code='prompt_blocked'
               AND json_array_length(sample_ids_json)=1
               AND EXISTS (SELECT 1 FROM json_each(sample_ids_json) WHERE value=?)
               ORDER BY attempt_id DESC""",
            (prompt_version, prompt_hash, model, sample_id),
        ).fetchall()
        evidence = [json.loads(attempt[0]) for attempt in attempts if attempt[0]]
        if not any(
            item.get("prompt_block_reason") == "PROHIBITED_CONTENT"
            and item.get("candidate_count") == 0
            for item in evidence
        ):
            raise ValueError(f"No singleton PROHIBITED_CONTENT evidence for {sample_id}")
    return seen, payload


def export_review_stats(
    path: Path, rows: list[dict[str, Any]], prompt_hash: str, prompt_version: str,
    model: str, cache: ReviewCache, exclusions: list[dict[str, Any]],
    exclusion_path: Path | None,
) -> dict[str, Any]:
    """Export deterministic completion counts without retaining review text or secrets."""
    ids = [row["id"] for row in rows]
    reviews = cache.results_for_ids(ids, prompt_version, prompt_hash, model)
    decisions = Counter(review["decision"] for review in reviews.values())
    reasons = Counter(
        review["reason_code"] for review in reviews.values()
        if review["decision"] == "REJECT"
    )
    batch_statuses = Counter(
        row[0] for row in cache.connection.execute(
            """SELECT status FROM review_batches WHERE prompt_version=?
               AND prompt_hash=? AND llm_model=?""",
            (prompt_version, prompt_hash, model),
        )
    )
    attempt_outcomes = Counter(
        (row[0], row[1] or "success") for row in cache.connection.execute(
            """SELECT status, error_code FROM review_attempts WHERE prompt_version=?
               AND prompt_hash=? AND llm_model=?""",
            (prompt_version, prompt_hash, model),
        )
    )
    report = {
        "phase": 8,
        "completion_status": "completed_with_approved_provider_exclusions" if exclusions else "completed",
        "manifest_review_count": len(rows),
        "valid_llm_review_count": len(reviews),
        "provider_exclusion_count": len(exclusions),
        "reconciled_count": len(reviews) + len(exclusions),
        "decision_counts": {key: decisions.get(key, 0) for key in ("KEEP", "EDIT", "REJECT")},
        "reject_reason_counts": {str(key): value for key, value in sorted(reasons.items())},
        "batch_status_counts": dict(sorted(batch_statuses.items())),
        "attempt_outcome_counts": {
            f"{status}:{code}": count
            for (status, code), count in sorted(attempt_outcomes.items())
        },
        "prompt_version": prompt_version,
        "review_identity_sha256": prompt_hash,
        "llm_model": model,
        "cache_path": cache.path.as_posix(),
        "approved_exclusions_path": exclusion_path.as_posix() if exclusion_path else None,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if report["reconciled_count"] != len(rows) or batch_statuses.get("failed", 0):
        raise RuntimeError("Review stats cannot be exported before all IDs and failed batches are reconciled")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strict batched Gemini review.")
    parser.add_argument("--mode", choices=("pilot", "full"), required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/intermediate/visolex_review_manifest.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--excluded-ids-file", type=Path, help="Approved provider exclusions with singleton cache evidence")
    parser.add_argument("--stats", type=Path, help="Write final review statistics after reconciliation")
    parser.add_argument("--batch-size", type=int, help="Override request batch size for a resume/recovery run")
    parser.add_argument("--quiet", action="store_true", help="Suppress operational progress logs")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        import google.genai  # noqa: F401
    except ImportError as error:
        raise SystemExit("Install requirements.txt before Gemini review.") from error
    load_dotenv()
    keys = [key.strip() for key in os.getenv("GEMINI_API_KEYS", "").split(",") if key.strip()]
    model = os.getenv("GEMINI_MODEL", "").strip()
    if not keys or not model:
        raise SystemExit("Set GEMINI_API_KEYS and GEMINI_MODEL in .env")

    config = load_json(args.config)
    if args.batch_size is not None:
        if args.batch_size < 1:
            raise SystemExit("--batch-size must be at least 1")
        config["batch_size"] = args.batch_size
    policy = load_policy(Path(config["lexical_policy_path"]))
    rows = read_jsonl(args.manifest)
    validate_manifest_scope(rows, config)
    if args.mode == "pilot":
        rows = [row for row in rows if row.get("is_pilot")]
        prompt_path = Path(config["draft_prompt_path"])
        version = config["draft_prompt_version"]
        prompt_hash = review_identity_hash(prompt_path.read_text(encoding="utf-8"), policy)
    else:
        prompt_path = Path(config["frozen_prompt_path"])
        version = config["frozen_prompt_version"]
        prompt_hash = validate_frozen_prompt(config, prompt_path)
    template = prompt_path.read_text(encoding="utf-8")
    cache = ReviewCache(args.cache or Path(config["cache_path"]))
    requester = GeminiRequester()
    try:
        exclusion_path = args.excluded_ids_file
        if exclusion_path is None and config.get("approved_exclusions_path"):
            exclusion_path = Path(config["approved_exclusions_path"])
        excluded_ids: set[str] = set()
        exclusions: list[dict[str, Any]] = []
        if exclusion_path is not None:
            excluded_ids, exclusions = load_approved_exclusions(
                exclusion_path, rows, prompt_hash, version, model, cache,
            )
        run_batches(
            rows, template, prompt_hash, version, model, config, cache,
            GeminiKeyPool(keys, float(config["quota_cooldown_seconds"])), requester,
            quiet=args.quiet, policy=policy, excluded_ids=excluded_ids,
        )
        missing = {row["id"] for row in rows} - cache.completed_ids(version, prompt_hash, model)
        if missing != excluded_ids:
            unresolved = missing - excluded_ids
            unexpected = excluded_ids - missing
            raise SystemExit(
                f"Review incomplete: unresolved={len(unresolved)} exclusions_with_reviews={len(unexpected)}; rerun to resume"
            )
        superseded = cache.reconcile_superseded_failures(version, prompt_hash, model, excluded_ids)
        if superseded:
            log_event("RECONCILE", f"Marked {superseded} failed batches as superseded by committed reviews or approved exclusions", quiet=args.quiet)
        if cache.failed_count(version, prompt_hash, model):
            raise SystemExit("Review incomplete: unresolved failed batches remain")
        stats_path = args.stats
        if stats_path is None and config.get("review_stats_path"):
            stats_path = Path(config["review_stats_path"])
        if stats_path is not None:
            export_review_stats(
                stats_path, rows, prompt_hash, version, model, cache,
                exclusions, exclusion_path,
            )
        log_event("DONE", f"Gemini {args.mode} review completed: committed={len(rows) - len(excluded_ids)} excluded={len(excluded_ids)} cache={cache.path}", quiet=args.quiet)
    finally:
        requester.close()
        cache.close()


if __name__ == "__main__":
    main()