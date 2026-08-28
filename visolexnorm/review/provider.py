"""Gemini key rotation, requester lifecycle, and secret-safe diagnostics."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from visolexnorm.review.contracts import PROVIDER_RESPONSE_SCHEMA


@dataclass
class KeyState:
    value: str
    cooldown_until: float = 0.0
    disabled: bool = False


class GeminiKeyPool:
    def __init__(self, keys: list[str], cooldown_seconds: float = 60, clock: Callable[[], float] = time.monotonic):
        if not keys or any(not key for key in keys):
            raise ValueError("At least one non-empty Gemini API key is required")
        self.states = [KeyState(key) for key in keys]
        self.cooldown_seconds = cooldown_seconds
        self.clock = clock
        self.index = 0

    def acquire(self) -> str:
        now = self.clock()
        for _ in range(len(self.states)):
            state = self.states[self.index % len(self.states)]
            self.index += 1
            if not state.disabled and state.cooldown_until <= now:
                return state.value
        raise RuntimeError("No Gemini API key is currently available")

    def cooldown(self, key: str) -> None:
        self._state(key).cooldown_until = self.clock() + self.cooldown_seconds

    def disable(self, key: str) -> None:
        self._state(key).disabled = True

    def _state(self, key: str) -> KeyState:
        return next(state for state in self.states if state.value == key)


def classify_error(error: Exception) -> str:
    text = f"{type(error).__name__}: {error}".lower()
    if any(token in text for token in ("429", "quota", "resource_exhausted")):
        return "quota"
    if any(token in text for token in ("401", "403", "api key", "authentication", "permission_denied")):
        return "auth"
    return "transient"


@dataclass
class GeminiResponse:
    """Text plus provider diagnostics that do not contain API keys or prompts."""

    text: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


class GeminiResponseError(RuntimeError):
    """A completed provider response that cannot be parsed or used safely."""

    def __init__(self, code: str, *, metadata: dict[str, Any] | None = None, raw_response: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.metadata = metadata or {}
        self.raw_response = raw_response


def safe_error_detail(error: Exception) -> str:
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
    return None if value is None else str(getattr(value, "value", value))


def response_diagnostics(response: Any) -> dict[str, Any]:
    """Extract safe provider metadata without retaining prompt or generated text."""
    metadata: dict[str, Any] = {"candidate_count": len(response.candidates or [])}
    feedback = response.prompt_feedback
    if feedback is not None:
        metadata["prompt_block_reason"] = enum_value(feedback.block_reason)
        metadata["prompt_safety"] = [{"category": enum_value(r.category), "probability": enum_value(r.probability), "blocked": r.blocked} for r in (feedback.safety_ratings or [])]
    if response.candidates:
        candidate = response.candidates[0]
        metadata.update({"finish_reason": enum_value(candidate.finish_reason), "candidate_token_count": candidate.token_count, "candidate_safety": [{"category": enum_value(r.category), "probability": enum_value(r.probability), "blocked": r.blocked} for r in (candidate.safety_ratings or [])]})
    usage = response.usage_metadata
    if usage is not None:
        metadata["usage"] = {"prompt_tokens": usage.prompt_token_count, "candidate_tokens": usage.candidates_token_count, "thought_tokens": usage.thoughts_token_count, "total_tokens": usage.total_token_count}
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
        raise GeminiResponseError(f"finish_{finish_reason.lower()}", metadata=metadata, raw_response=result.text)
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