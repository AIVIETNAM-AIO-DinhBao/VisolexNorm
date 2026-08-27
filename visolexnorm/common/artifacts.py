"""Deterministic hashing and scalar validation helpers for artifacts."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize JSON deterministically for content hashing."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    """Return the SHA-256 digest for an in-memory byte sequence."""
    return hashlib.sha256(value).hexdigest()


def sha256_text(text: str) -> str:
    """Return the SHA-256 digest for UTF-8 text."""
    return sha256_bytes(text.encode("utf-8"))


def sha256_json(value: Any) -> str:
    """Return the SHA-256 digest for canonical JSON."""
    return sha256_text(canonical_json(value))


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for file bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_finite_number(value: Any, field: str) -> float:
    """Validate and normalize a finite numeric field without accepting booleans."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)