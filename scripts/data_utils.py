"""Small standard-library helpers shared by Phase 1 data scripts."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


def clean_text(value: Any) -> str | None:
    """Keep lexical noise while making text safe for JSONL processing."""
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFC", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def read_rows(path: Path) -> list[dict[str, Any]]:
    """Read a CSV, TSV, JSON list/object, or JSONL file into dict rows."""
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle, delimiter=delimiter))

    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number} is not a JSON object")
                rows.append(value)
        return rows

    if suffix == ".json":
        with path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
        if isinstance(value, list) and all(isinstance(row, dict) for row in value):
            return value
        if isinstance(value, dict):
            # Supports a common wrapper such as {"data": [...]}.
            for key in ("data", "records", "items"):
                rows = value.get(key)
                if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                    return rows
        raise ValueError(
            f"{path} must be a JSON list of objects or an object with data/records/items."
        )

    raise ValueError(f"Unsupported file type: {path}. Use .csv, .tsv, .json, or .jsonl.")


def write_jsonl(records: Iterable[dict[str, Any]], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_rows(path)
