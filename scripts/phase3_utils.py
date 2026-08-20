"""Shared deterministic helpers for the Phase 3 weak-labeling pipeline."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Iterable


def format_duration(seconds: float) -> str:
    """Format an elapsed/estimated duration for durable terminal logs."""
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:d}:{seconds:02d}"


def log_event(event: str, message: str, *, quiet: bool = False) -> None:
    """Emit one flushed, secret-safe operational log line."""
    if not quiet:
        print(f"[{event}] {message}", flush=True)


class ProgressReporter:
    """Small dependency-free progress reporter suitable for terminal/Kaggle logs."""

    def __init__(self, label: str, total: int, completed: int = 0, *, quiet: bool = False, clock=time.monotonic):
        if total < 0 or not 0 <= completed <= total:
            raise ValueError("Progress bounds are invalid")
        self.label, self.total, self.completed = label, total, completed
        self.initial_completed = completed
        self.quiet, self.clock, self.started_at = quiet, clock, clock()

    def advance(self, count: int, detail: str = "") -> None:
        self.completed = min(self.total, self.completed + count)
        elapsed = self.clock() - self.started_at
        newly_completed = self.completed - self.initial_completed
        rate = (newly_completed / elapsed) if elapsed and newly_completed else 0.0
        remaining = self.total - self.completed
        eta = format_duration(remaining / rate) if rate else "unknown"
        suffix = f" | {detail}" if detail else ""
        log_event(
            "PROGRESS",
            f"{self.label}: {self.completed}/{self.total} ({self.completed / self.total * 100 if self.total else 100:.1f}%) "
            f"elapsed={format_duration(elapsed)} eta={eta}{suffix}",
            quiet=self.quiet,
        )

    def done(self, detail: str = "") -> None:
        suffix = f" | {detail}" if detail else ""
        log_event(
            "DONE", f"{self.label}: {self.completed}/{self.total} elapsed={format_duration(self.clock() - self.started_at)}{suffix}",
            quiet=self.quiet,
        )


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_finite_number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def atomic_write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    count = 0
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return count