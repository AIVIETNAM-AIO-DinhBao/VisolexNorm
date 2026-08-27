from __future__ import annotations

import math
from pathlib import Path

import pytest

from visolexnorm.common.artifacts import (
    canonical_json,
    ensure_finite_number,
    sha256_bytes,
    sha256_file,
    sha256_json,
    sha256_text,
)
from visolexnorm.common.io import (
    atomic_write_jsonl,
    clean_text,
    load_json,
    read_jsonl,
    read_rows,
    write_jsonl,
)
from visolexnorm.common.progress import ProgressReporter, format_duration, log_event


def test_common_io_preserves_text_cleaning_and_atomic_jsonl_contract(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    assert clean_text("  tie\tViệt\n") == "tie Việt"
    assert clean_text(1) is None
    assert atomic_write_jsonl([{"id": "one"}, {"id": "two"}], path) == 2
    assert read_jsonl(path) == [{"id": "one"}, {"id": "two"}]
    assert not list(tmp_path.glob(".*.tmp"))


def test_common_artifact_helpers_preserve_deterministic_hashes(tmp_path: Path) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"artifact")
    assert canonical_json({"b": 1, "a": "x"}) == '{"a":"x","b":1}'
    assert sha256_bytes(b"artifact") == sha256_text("artifact")
    assert sha256_json({"b": 1, "a": "x"}) == sha256_text('{"a":"x","b":1}')
    assert sha256_file(path) == sha256_text("artifact")
    assert ensure_finite_number(1, "score") == 1.0
    with pytest.raises(ValueError, match="score"):
        ensure_finite_number(math.nan, "score")
    with pytest.raises(ValueError, match="score"):
        ensure_finite_number(True, "score")


def test_load_json_requires_an_object_and_progress_format_is_stable(tmp_path: Path) -> None:
    object_path = tmp_path / "object.json"
    array_path = tmp_path / "array.json"
    object_path.write_text('{"ok": true}', encoding="utf-8")
    array_path.write_text('[]', encoding="utf-8")
    assert load_json(object_path) == {"ok": True}
    with pytest.raises(ValueError, match="Expected a JSON object"):
        load_json(array_path)
    assert format_duration(65) == "1:05"
    reporter = ProgressReporter("work", 2, quiet=True, clock=lambda: 10.0)
    reporter.advance(1)
    reporter.done()


def test_read_rows_supports_delimited_files_and_json_wrappers(tmp_path: Path) -> None:
    csv_path = tmp_path / "records.csv"
    tsv_path = tmp_path / "records.tsv"
    json_path = tmp_path / "records.json"
    csv_path.write_text("id,text\n1,hello\n", encoding="utf-8")
    tsv_path.write_text("id\ttext\n2\tworld\n", encoding="utf-8")
    json_path.write_text('{"items": [{"id": "3"}]}', encoding="utf-8")
    assert read_rows(csv_path) == [{"id": "1", "text": "hello"}]
    assert read_rows(tsv_path) == [{"id": "2", "text": "world"}]
    assert read_rows(json_path) == [{"id": "3"}]


def test_jsonl_writers_preserve_utf8_and_atomic_failures_leave_no_partial_file(tmp_path: Path) -> None:
    regular = tmp_path / "regular.jsonl"
    atomic = tmp_path / "atomic.jsonl"
    assert write_jsonl([{"text": "tiếng Việt"}], regular) == 1
    assert regular.read_bytes() == '{"text": "tiếng Việt"}\n'.encode()
    atomic.write_text("original\n", encoding="utf-8")
    with pytest.raises(TypeError):
        atomic_write_jsonl([{"ok": 1}, {"invalid": object()}], atomic)
    assert atomic.read_text(encoding="utf-8") == "original\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_progress_and_quiet_logging_output_is_stable(capsys) -> None:
    ticks = iter((0.0, 2.0, 3.0))
    reporter = ProgressReporter("work", 2, clock=lambda: next(ticks))
    reporter.advance(1, "item=1")
    reporter.done("saved")
    log_event("SECRET", "hidden", quiet=True)
    assert capsys.readouterr().out.splitlines() == [
        "[PROGRESS] work: 1/2 (50.0%) elapsed=0:02 eta=0:02 | item=1",
        "[DONE] work: 1/2 elapsed=0:03 | saved",
    ]