"""Review selected Model A candidates locally using Gemini with cached round-robin keys."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from data_utils import clean_text, read_jsonl  # noqa: E402
from phase3_utils import ProgressReporter, log_event  # noqa: E402


DECISIONS = {"KEEP", "EDIT", "REJECT"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def completed_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    result: set[str] = set()
    for row in read_jsonl(path):
        if row.get("parse_status") == "valid" and isinstance(row.get("id"), str):
            result.add(row["id"])
    return result


def parse_response(text: str, candidate: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("invalid_json") from error
    # The frozen contract returns {"results": [{...}]} while an earlier
    # single-record pilot contract returned the object directly.
    if isinstance(payload, dict) and isinstance(payload.get("results"), list) and len(payload["results"]) == 1:
        payload = payload["results"][0]
    if not isinstance(payload, dict) or payload.get("decision") not in DECISIONS:
        raise ValueError("invalid_decision")
    decision = payload["decision"]
    corrected = payload.get("corrected_text")
    reason = payload.get("reason_code")
    if corrected is not None:
        corrected = clean_text(corrected)
    if decision == "EDIT" and not corrected:
        raise ValueError("edit_without_corrected_text")
    if decision == "REJECT" and corrected is not None:
        raise ValueError("reject_with_corrected_text")
    if decision == "KEEP" and corrected not in (None, candidate):
        raise ValueError("keep_with_changed_text")
    return {"llm_decision": decision, "llm_corrected_text": corrected, "reason_code": reason}


def main() -> None:
    parser = argparse.ArgumentParser(description="Review ViSoLex candidates with local Gemini API access.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, default=Path("prompts/lexical_norm_review_v1.txt"))
    parser.add_argument("--config", type=Path, default=Path("configs/weak_label_config.json"))
    parser.add_argument("--cache", type=Path, default=Path("data/intermediate/gemini_review_cache.jsonl"))
    parser.add_argument("--errors", type=Path, default=Path("data/intermediate/gemini_review_errors.jsonl"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, help="Process only a deterministic prefix for pilot/smoke runs")
    parser.add_argument("--quiet", action="store_true", help="Suppress operational progress logs")
    parser.add_argument("--max-items", type=int, help="Hard cap on records processed this invocation; useful with --resume")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types
    except ImportError as error:
        raise SystemExit("Run `pip install -r requirements.txt` before local Gemini review.") from error

    load_dotenv()
    keys = [key.strip() for key in os.getenv("GEMINI_API_KEYS", "").split(",") if key.strip()]
    model_name = os.getenv("GEMINI_MODEL", "").strip()
    if not keys or not model_name:
        raise SystemExit("Set GEMINI_API_KEYS and GEMINI_MODEL in your local .env file.")
    config = load_json(args.config)
    prompt = args.prompt.read_text(encoding="utf-8")
    candidates = {row["id"]: row for row in read_jsonl(args.candidates)}
    manifest = read_jsonl(args.manifest)
    ids = [row.get("id") for row in manifest]
    if len(ids) != len(set(ids)) or any(sample_id not in candidates for sample_id in ids):
        raise ValueError("Manifest IDs are invalid or absent from candidates")
    done = completed_ids(args.cache) if args.resume else set()
    if args.cache.exists() and not args.resume:
        raise FileExistsError(f"{args.cache} exists; pass --resume to preserve its completed reviews")
    pending = [row for row in manifest if row["id"] not in done]
    if args.limit is not None:
        pending = pending[: args.limit]
    if args.max_items is not None:
        pending = pending[: args.max_items]
    reporter = ProgressReporter("Legacy Gemini review", len(manifest), len(done), quiet=args.quiet)
    log_event("START", f"Legacy Gemini review: total={len(manifest)} cached={len(done)} pending={len(pending)} model={model_name}", quiet=args.quiet)
    if done:
        log_event("RESUME", f"Reusing {len(done)} IDs from JSONL cache", quiet=args.quiet)

    key_index = 0
    attempts = int(config["max_retries_per_request"])
    base_wait = float(config["retry_base_seconds"])
    for number, manifest_row in enumerate(pending, 1):
        candidate = candidates[manifest_row["id"]]
        samples_payload = json.dumps(
            [{"id": candidate["id"], "source": candidate["input_text"], "candidate": candidate["candidate_text"]}],
            ensure_ascii=False,
        )
        # The current reviewer contract is batch-shaped (`{samples_json}`); retain
        # compatibility with the original single-record placeholders for old prompts.
        request_prompt = (
            prompt.replace("{samples_json}", samples_payload)
            .replace("{source}", candidate["input_text"])
            .replace("{candidate}", candidate["candidate_text"])
        )
        last_error = "unknown"
        for attempt in range(attempts):
            key = keys[key_index % len(keys)]
            key_index += 1
            try:
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=request_prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
                )
                parsed = parse_response(response.text or "", candidate["candidate_text"])
                append_jsonl(
                    args.cache,
                    {
                        **candidate,
                        **manifest_row,
                        **parsed,
                        "llm_model": model_name,
                        "prompt_version": config["prompt_version"],
                        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
                        "parse_status": "valid",
                    },
                )
                last_error = ""
                break
            except Exception as error:  # API/network/structured-output failures are retried and audited.
                last_error = f"{type(error).__name__}: {error}"[:500]
                if attempt + 1 < attempts:
                    wait = base_wait * (2**attempt) + random.uniform(0, 0.5)
                    log_event("RETRY", f"Legacy Gemini review: item={number}/{len(pending)} attempt={attempt + 1}/{attempts} wait={wait:.1f}s error={type(error).__name__}", quiet=args.quiet)
                    time.sleep(wait)
        if last_error:
            append_jsonl(
                args.errors,
                {
                    "id": candidate["id"],
                    "error": last_error,
                    "attempts": attempts,
                    "llm_model": model_name,
                    "prompt_version": config["prompt_version"],
                    "logged_at_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
        reporter.advance(1, f"pending_item={number}/{len(pending)} cache={'ok' if not last_error else 'error'}")
    reporter.done(f"cache={args.cache} errors={args.errors}")


if __name__ == "__main__":
    main()