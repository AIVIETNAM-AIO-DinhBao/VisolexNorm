"""Validation and leakage-protection helpers for processed data artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from visolexnorm.common.artifacts import sha256_text
from visolexnorm.common.io import clean_text, read_jsonl
from visolexnorm.data.preparation import ALLOWED_SOURCES


@dataclass(frozen=True)
class DataValidationReport:
    """Counts returned after validating all Phase 1 processed artifacts."""

    split_counts: dict[str, int]
    source_counts: dict[str, int]
    total_ids: int


def validate_processed_data(data_dir: Path) -> DataValidationReport:
    """Fail closed on schema, normalization, duplicate IDs, and Dev/Test overlap."""
    all_ids: set[str] = set()
    splits: dict[str, list[dict[str, str]]] = {}
    split_counts: dict[str, int] = {}
    for split in ("train", "dev", "test"):
        path = data_dir / f"vilexnorm_{split}.jsonl"
        if not path.is_file():
            raise ValueError(f"Missing file: {path}")
        records = read_jsonl(path)
        for record in records:
            required = {"id", "dataset", "split", "input_text", "target_text", "label_source"}
            if not required <= record.keys():
                raise ValueError(f"{path}: missing required field in {record}")
            if record["dataset"] != "ViLexNorm" or record["split"] != split or record["label_source"] != "human":
                raise ValueError(f"{path}: invalid constants in {record}")
            if clean_text(record["input_text"]) != record["input_text"] or clean_text(record["target_text"]) != record["target_text"]:
                raise ValueError(f"{path}: text is empty or not whitespace-normalized")
            if record["id"] in all_ids:
                raise ValueError(f"Duplicate id: {record['id']}")
            all_ids.add(record["id"])
        splits[split] = records
        split_counts[split] = len(records)

    visolex_path = data_dir / "visolex_unlabeled.jsonl"
    if not visolex_path.is_file():
        raise ValueError(f"Missing file: {visolex_path}")
    visolex = read_jsonl(visolex_path)
    inputs: set[str] = set()
    source_counts = {source: 0 for source in sorted(ALLOWED_SOURCES)}
    for record in visolex:
        required = {"id", "dataset", "original_source", "input_text"}
        if not required <= record.keys():
            raise ValueError(f"{visolex_path}: missing required field in {record}")
        if record["dataset"] != "ViSoLex" or record["original_source"] not in ALLOWED_SOURCES:
            raise ValueError(f"{visolex_path}: invalid dataset/source in {record}")
        text = record["input_text"]
        if clean_text(text) != text:
            raise ValueError(f"{visolex_path}: text is empty or not whitespace-normalized")
        if text in inputs:
            raise ValueError(f"{visolex_path}: duplicate input_text: {text!r}")
        if record["id"] in all_ids:
            raise ValueError(f"Duplicate id: {record['id']}")
        inputs.add(text)
        all_ids.add(record["id"])
        source_counts[record["original_source"]] += 1
    protected = {record["input_text"] for split in ("dev", "test") for record in splits[split]}
    overlaps = inputs & protected
    if overlaps:
        raise ValueError(f"ViSoLex still overlaps ViLexNorm Dev/Test ({len(overlaps)} exact input matches).")
    return DataValidationReport(split_counts, source_counts, len(all_ids))


def build_protected_hashes(data_dir: Path) -> list[str]:
    """Return sorted SHA-256 fingerprints for exact Dev/Test input leakage checks."""
    hashes: set[str] = set()
    for split in ("dev", "test"):
        path = data_dir / f"vilexnorm_{split}.jsonl"
        if not path.is_file():
            raise FileNotFoundError(path)
        hashes.update(sha256_text(row["input_text"]) for row in read_jsonl(path))
    return sorted(hashes)