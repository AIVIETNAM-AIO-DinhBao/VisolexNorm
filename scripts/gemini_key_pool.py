"""Deterministic Gemini key rotation with quota cooldown and auth disabling."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


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