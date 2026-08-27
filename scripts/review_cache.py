"""SQLite WAL repository for atomic Phase 3 review batches."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS review_batches (
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
            CREATE TABLE IF NOT EXISTS review_results (
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
            CREATE TABLE IF NOT EXISTS review_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                llm_model TEXT NOT NULL,
                sample_ids_json TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                status TEXT NOT NULL,
                error_code TEXT,
                error_detail TEXT,
                response_metadata_json TEXT,
                raw_response TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS review_attempts_identity_idx
                ON review_attempts (batch_id, prompt_version, prompt_hash, llm_model);
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def completed_ids(self, prompt_version: str, prompt_hash: str, model: str) -> set[str]:
        rows = self.connection.execute(
            """SELECT sample_id FROM review_results
               WHERE prompt_version = ? AND prompt_hash = ? AND llm_model = ?""",
            (prompt_version, prompt_hash, model),
        )
        return {row[0] for row in rows}

    def mark_attempt(self, batch_id: str, prompt_hash: str, version: str, model: str, ids: list[str]) -> int:
        now = utc_now()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO review_batches (
                    batch_id, prompt_hash, prompt_version, llm_model, sample_ids_json,
                    attempt_count, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 1, 'in_flight', ?)
                ON CONFLICT(batch_id, prompt_version, prompt_hash, llm_model) DO UPDATE SET
                    attempt_count = attempt_count + 1, status = 'in_flight', last_error = NULL
                """,
                (batch_id, prompt_hash, version, model, json.dumps(ids), now),
            )
            attempt_number = int(self.connection.execute(
                """SELECT attempt_count FROM review_batches WHERE batch_id=? AND prompt_version=?
                   AND prompt_hash=? AND llm_model=?""",
                (batch_id, version, prompt_hash, model),
            ).fetchone()[0])
            cursor = self.connection.execute(
                """INSERT INTO review_attempts (
                       batch_id, prompt_hash, prompt_version, llm_model, sample_ids_json,
                       attempt_number, status, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, 'in_flight', ?)""",
                (batch_id, prompt_hash, version, model, json.dumps(ids), attempt_number, now),
            )
        return int(cursor.lastrowid)

    def complete_attempt(
        self, attempt_id: int, status: str, *, error_code: str | None = None,
        error_detail: str | None = None, response_metadata: dict[str, Any] | None = None,
        raw_response: str | None = None,
    ) -> None:
        """Persist one request outcome without losing earlier retry diagnostics."""
        with self.connection:
            self.connection.execute(
                """UPDATE review_attempts SET status=?, error_code=?, error_detail=?,
                   response_metadata_json=?, raw_response=?, completed_at=? WHERE attempt_id=?""",
                (
                    status, error_code, error_detail[:1000] if error_detail else None,
                    json.dumps(response_metadata, ensure_ascii=False, sort_keys=True) if response_metadata else None,
                    raw_response, utc_now(), attempt_id,
                ),
            )

    def commit_success(
        self, batch_id: str, prompt_hash: str, version: str, model: str,
        results: list[dict[str, Any]], raw_response: str,
    ) -> None:
        now = utc_now()
        with self.connection:
            for result in results:
                self.connection.execute(
                    """
                    INSERT INTO review_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sample_id, prompt_version, prompt_hash, llm_model) DO UPDATE SET
                        batch_id=excluded.batch_id, decision=excluded.decision,
                        corrected_text=excluded.corrected_text, reason_code=excluded.reason_code,
                        reviewed_at=excluded.reviewed_at
                    """,
                    (result["id"], prompt_hash, version, model, batch_id, result["decision"],
                     result["corrected_text"], result["reason_code"], now),
                )
            self.connection.execute(
                """UPDATE review_batches SET status='succeeded', raw_response=?, completed_at=?,
                   last_error=NULL WHERE batch_id=? AND prompt_version=? AND prompt_hash=? AND llm_model=?""",
                (raw_response, now, batch_id, version, prompt_hash, model),
            )

    def mark_failed(self, batch_id: str, version: str, prompt_hash: str, model: str, error: str) -> None:
        with self.connection:
            self.connection.execute(
                """UPDATE review_batches SET status='failed', last_error=?, completed_at=?
                   WHERE batch_id=? AND prompt_version=? AND prompt_hash=? AND llm_model=?""",
                (error[:1000], utc_now(), batch_id, version, prompt_hash, model),
            )

    def results_for_ids(self, ids: list[str], version: str, prompt_hash: str, model: str) -> dict[str, dict[str, Any]]:
        if not ids:
            return {}
        results: dict[str, dict[str, Any]] = {}
        # Keep well below SQLite's build-dependent host-parameter limit. Phase 8
        # requests 48,411 IDs here, so one monolithic IN clause is not portable.
        for start in range(0, len(ids), 900):
            chunk = ids[start : start + 900]
            placeholders = ",".join("?" for _ in chunk)
            rows = self.connection.execute(
                f"""SELECT * FROM review_results WHERE prompt_version=? AND prompt_hash=? AND llm_model=?
                    AND sample_id IN ({placeholders})""",
                (version, prompt_hash, model, *chunk),
            )
            results.update({row["sample_id"]: dict(row) for row in rows})
        return results

    def failed_count(self, version: str, prompt_hash: str, model: str) -> int:
        return int(self.connection.execute(
            """SELECT COUNT(*) FROM review_batches WHERE prompt_version=?
               AND prompt_hash=? AND llm_model=? AND status='failed'""",
            (version, prompt_hash, model),
        ).fetchone()[0])

    def reconcile_superseded_failures(
        self, version: str, prompt_hash: str, model: str, resolved_without_review: set[str] | None = None,
    ) -> int:
        """Mark failed attempts superseded once every referenced sample has a committed result."""
        resolved = self.completed_ids(version, prompt_hash, model) | (resolved_without_review or set())
        rows = self.connection.execute(
            """SELECT batch_id, sample_ids_json FROM review_batches WHERE prompt_version=?
               AND prompt_hash=? AND llm_model=? AND status='failed'""",
            (version, prompt_hash, model),
        ).fetchall()
        superseded = [row["batch_id"] for row in rows if set(json.loads(row["sample_ids_json"])) <= resolved]
        if not superseded:
            return 0
        now = utc_now()
        with self.connection:
            for batch_id in superseded:
                self.connection.execute(
                    """UPDATE review_batches SET status='superseded', completed_at=?
                       WHERE batch_id=? AND prompt_version=? AND prompt_hash=? AND llm_model=?
                       AND status='failed'""",
                    (now, batch_id, version, prompt_hash, model),
                )
        return len(superseded)