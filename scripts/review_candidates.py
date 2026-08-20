"""Review Phase 3 manifest batches with Gemini and an atomic SQLite cache."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).parent))
from data_utils import read_jsonl  # noqa: E402
from gemini_key_pool import GeminiKeyPool, classify_error  # noqa: E402
from phase3_utils import ProgressReporter, load_json, log_event, sha256_json, sha256_text  # noqa: E402
from review_cache import ReviewCache  # noqa: E402


def chunks(rows: list[dict[str, Any]], size: int):
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def render_prompt(template: str, rows: list[dict[str, Any]]) -> str:
    samples = [{"id": row["id"], "source": row["input_text"], "candidate": row["candidate_text"]} for row in rows]
    return template.replace("{samples_json}", json.dumps(samples, ensure_ascii=False, indent=2))


def parse_response(text: str, expected_ids: list[str], validator: Draft202012Validator) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("Gemini response is not valid JSON") from error
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
    digest = sha256_text(prompt_path.read_text(encoding="utf-8"))
    if digest != config.get("frozen_prompt_sha256"):
        raise ValueError("Frozen prompt SHA-256 does not match the config")
    return digest


def run_batches(
    rows: list[dict[str, Any]], template: str, prompt_hash: str, prompt_version: str,
    model: str, config: dict[str, Any], cache: ReviewCache, key_pool: GeminiKeyPool,
    request: Callable[[str, str, str], str], sleep: Callable[[float], None] = time.sleep,
    quiet: bool = False,
) -> None:
    completed = cache.completed_ids(prompt_version, prompt_hash, model)
    completed &= {row["id"] for row in rows}
    pending = [row for row in rows if row["id"] not in completed]
    size = int(config["batch_size"])
    waits = list(config["retry_backoff_seconds"])
    max_retries = int(config["max_retries"])
    batch_total = math.ceil(len(pending) / size) if pending else 0
    reporter = ProgressReporter("Gemini review", len(rows), len(completed), quiet=quiet)
    log_event("START", f"Gemini review: total={len(rows)} cached={len(completed)} pending={len(pending)} batches={batch_total} batch_size={size} model={model} prompt={prompt_version}@{prompt_hash[:12]}", quiet=quiet)
    if completed:
        log_event("RESUME", f"Reusing {len(completed)} committed reviews from SQLite cache", quiet=quiet)
    for batch_number, batch in enumerate(chunks(pending, size), start=1):
        ids = [row["id"] for row in batch]
        batch_id = sha256_json({"prompt_hash": prompt_hash, "ids": ids})[:24]
        rendered = render_prompt(template, batch)
        last_error = "unknown"
        for attempt in range(max_retries):
            try:
                key = key_pool.acquire()
            except RuntimeError:
                log_event("WAIT", f"Gemini batch {batch_number}/{batch_total}: all keys cooling down; waiting {config['quota_cooldown_seconds']}s", quiet=quiet)
                sleep(float(config["quota_cooldown_seconds"]))
                key = key_pool.acquire()
            cache.mark_attempt(batch_id, prompt_hash, prompt_version, model, ids)
            try:
                log_event("REQUEST", f"Gemini batch {batch_number}/{batch_total}: samples={len(ids)} attempt={attempt + 1}/{max_retries}", quiet=quiet)
                raw = request(key, model, rendered)
                results = parse_response(raw, ids, RESPONSE_VALIDATOR)
                cache.commit_success(batch_id, prompt_hash, prompt_version, model, results, raw)
                last_error = ""
                reporter.advance(len(batch), f"batch={batch_number}/{batch_total} committed")
                break
            except Exception as error:
                last_error = f"{type(error).__name__}: {error}"
                category = classify_error(error)
                if category == "quota":
                    key_pool.cooldown(key)
                    action = "key cooled down"
                elif category == "auth":
                    key_pool.disable(key)
                    action = "key disabled"
                else:
                    action = "will retry"
                if attempt + 1 < max_retries:
                    wait = float(waits[min(attempt, len(waits) - 1)]) + random.uniform(
                        0, float(config["retry_jitter_max_seconds"])
                    )
                    log_event("RETRY", f"Gemini batch {batch_number}/{batch_total}: attempt={attempt + 1}/{max_retries} category={category} action={action} wait={wait:.1f}s error={type(error).__name__}", quiet=quiet)
                    sleep(wait)
        if last_error:
            cache.mark_failed(batch_id, prompt_version, prompt_hash, model, last_error)
            log_event("WARNING", f"Gemini batch {batch_number}/{batch_total}: failed after {max_retries} attempts; rerun resumes it. error_type={last_error.split(':', 1)[0]}", quiet=quiet)
    reporter.done(f"pending_batches={batch_total}")


def gemini_request(key: str, model: str, prompt: str) -> str:
    from google import genai
    from google.genai import types

    response = genai.Client(api_key=key).models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    return response.text or ""


ROOT = Path(__file__).parents[1]
RESPONSE_SCHEMA = load_json(ROOT / "specs/003-weak-labeling-llm-review/contracts/review-response.schema.json")
RESPONSE_VALIDATOR = Draft202012Validator(RESPONSE_SCHEMA)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strict batched Gemini review.")
    parser.add_argument("--mode", choices=("pilot", "full"), required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/intermediate/visolex_review_manifest.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--cache", type=Path)
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
    rows = read_jsonl(args.manifest)
    if args.mode == "pilot":
        rows = [row for row in rows if row.get("is_pilot")]
        prompt_path = Path(config["draft_prompt_path"])
        version = config["draft_prompt_version"]
        prompt_hash = sha256_text(prompt_path.read_text(encoding="utf-8"))
    else:
        prompt_path = Path(config["frozen_prompt_path"])
        version = config["frozen_prompt_version"]
        prompt_hash = validate_frozen_prompt(config, prompt_path)
    template = prompt_path.read_text(encoding="utf-8")
    cache = ReviewCache(args.cache or Path(config["cache_path"]))
    try:
        run_batches(
            rows, template, prompt_hash, version, model, config, cache,
            GeminiKeyPool(keys, float(config["quota_cooldown_seconds"])), gemini_request, quiet=args.quiet,
        )
        missing = {row["id"] for row in rows} - cache.completed_ids(version, prompt_hash, model)
        if missing:
            raise SystemExit(f"Review incomplete: {len(missing)} IDs missing; rerun to resume")
        log_event("DONE", f"Gemini {args.mode} review completed: {len(rows)} IDs committed in cache={cache.path}", quiet=args.quiet)
    finally:
        cache.close()


if __name__ == "__main__":
    main()