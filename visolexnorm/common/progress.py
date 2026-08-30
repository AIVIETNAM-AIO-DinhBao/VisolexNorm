"""Dependency-free, secret-safe operational progress reporting."""

from __future__ import annotations

import time
from typing import Callable


def format_duration(seconds: float) -> str:
    """Format an elapsed or estimated duration for durable terminal logs."""
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:d}:{seconds:02d}"


def log_event(event: str, message: str, *, quiet: bool = False) -> None:
    """Emit one flushed, secret-safe operational log line."""
    if not quiet:
        print(f"[{event}] {message}", flush=True)


class ProgressReporter:
    """Small progress reporter suitable for terminal and Kaggle logs."""

    def __init__(
        self,
        label: str,
        total: int,
        completed: int = 0,
        *,
        quiet: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if total < 0 or not 0 <= completed <= total:
            raise ValueError("Progress bounds are invalid")
        self.label = label
        self.total = total
        self.completed = completed
        self.initial_completed = completed
        self.quiet = quiet
        self.clock = clock
        self.started_at = clock()

    def advance(self, count: int, detail: str = "") -> None:
        self.completed = min(self.total, self.completed + count)
        elapsed = self.clock() - self.started_at
        newly_completed = self.completed - self.initial_completed
        rate = newly_completed / elapsed if elapsed and newly_completed else 0.0
        remaining = self.total - self.completed
        eta = format_duration(remaining / rate) if rate else "unknown"
        suffix = f" | {detail}" if detail else ""
        percentage = self.completed / self.total * 100 if self.total else 100
        log_event(
            "PROGRESS",
            f"{self.label}: {self.completed}/{self.total} ({percentage:.1f}%) "
            f"elapsed={format_duration(elapsed)} eta={eta}{suffix}",
            quiet=self.quiet,
        )

    def done(self, detail: str = "") -> None:
        suffix = f" | {detail}" if detail else ""
        log_event(
            "DONE",
            f"{self.label}: {self.completed}/{self.total} "
            f"elapsed={format_duration(self.clock() - self.started_at)}{suffix}",
            quiet=self.quiet,
        )