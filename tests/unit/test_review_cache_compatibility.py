from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from visolexnorm.review.cache import ReviewCache


def create_legacy_cache(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE review_batches (
            batch_id TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            llm_model TEXT NOT NULL,
            sample_ids_json TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            last_error TEXT,
            raw_response TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            PRIMARY KEY (batch_id, prompt_version, prompt_hash, llm_model)
        );
        CREATE TABLE review_results (
            sample_id TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            llm_model TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            corrected_text TEXT,
            reason_code TEXT,
            reviewed_at TEXT NOT NULL,
            PRIMARY KEY (sample_id, prompt_version, prompt_hash, llm_model)
        );
        """
    )
    connection.execute(
        "INSERT INTO review_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("sample", "a" * 64, "v1", "model", "batch", "KEEP", None, None, "now"),
    )
    connection.commit()
    connection.close()


def test_reader_opens_legacy_two_table_cache_without_schema_mutation(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    create_legacy_cache(path)
    before = path.read_bytes()
    cache = ReviewCache.open_reader(path)
    try:
        assert cache.readonly is True
        assert cache.has_attempts_table() is False
        assert cache.completed_ids("v1", "a" * 64, "model") == {"sample"}
        assert cache.attempt_outcome_counts("v1", "a" * 64, "model") == {}
        with pytest.raises(RuntimeError, match="read-only"):
            cache.mark_attempt("batch", "a" * 64, "v1", "model", ["sample"])
    finally:
        cache.close()
    assert path.read_bytes() == before


def test_writer_creates_the_full_phase8_schema(tmp_path: Path) -> None:
    cache = ReviewCache(tmp_path / "writer.sqlite3")
    try:
        assert cache.has_attempts_table() is True
        tables = {
            row[0] for row in cache.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"review_batches", "review_results", "review_attempts"} <= tables
    finally:
        cache.close()