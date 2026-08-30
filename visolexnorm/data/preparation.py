"""Deterministic preparation of ViLexNorm and ViSoLex JSONL artifacts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from visolexnorm.common.io import clean_text, read_jsonl, read_rows


ALLOWED_SOURCES = {"ViHSD", "UIT-VSMEC", "ViHOS", "ViSpamReviews", "UIT-ViSFD"}
LogEvent = Callable[[str, str], None]


@dataclass(frozen=True)
class SourceSpec:
    """One raw ViSoLex source and the field that contains its text."""

    name: str
    path: Path
    text_field: str


@dataclass(frozen=True)
class SplitPreparation:
    """Prepared ViLexNorm records and the number excluded for empty text."""

    records: list[dict[str, str]]
    skipped_empty: int


@dataclass(frozen=True)
class ViSoLexPreparation:
    """Prepared canonical corpus plus source-level accounting."""

    records: list[dict[str, str]]
    raw_counts: Counter[str]
    empty_counts: Counter[str]
    duplicate_counts: Counter[str]
    overlap_counts: Counter[str]


def prepare_vilexnorm_split(
    raw_path: Path,
    split: str,
    input_field: str,
    target_field: str,
    *,
    log_every: int = 0,
    log: LogEvent | None = None,
) -> SplitPreparation:
    """Prepare one ViLexNorm split while preserving record order and lexical noise."""
    rows = read_rows(raw_path)
    records: list[dict[str, str]] = []
    skipped_empty = 0
    for position, row in enumerate(rows, start=1):
        source = clean_text(row.get(input_field))
        target = clean_text(row.get(target_field))
        if source is None or target is None:
            skipped_empty += 1
        else:
            records.append({
                "id": f"vilexnorm_{split}_{len(records) + 1:06d}",
                "dataset": "ViLexNorm",
                "split": split,
                "input_text": source,
                "target_text": target,
                "label_source": "human",
            })
        if log is not None and log_every > 0 and position % log_every == 0:
            log("PROGRESS", f"ViLexNorm preprocessing: split={split} raw={position}/{len(rows)} kept={len(records)}")
    return SplitPreparation(records, skipped_empty)


def validate_source_specs(sources: list[SourceSpec]) -> None:
    """Validate source names, uniqueness, and raw-file availability before processing."""
    names = [source.name for source in sources]
    invalid_names = set(names) - ALLOWED_SOURCES
    if invalid_names:
        raise ValueError(f"Unknown source name(s): {sorted(invalid_names)}")
    if len(set(names)) != len(names):
        raise ValueError("Each source may be supplied only once.")
    for source in sources:
        if not source.path.is_file():
            raise FileNotFoundError(f"Raw file for {source.name} does not exist: {source.path}")


def protected_texts(vilexnorm_dir: Path) -> set[str]:
    """Load exact Dev/Test inputs that must not occur in the unlabeled corpus."""
    paths = [vilexnorm_dir / "vilexnorm_dev.jsonl", vilexnorm_dir / "vilexnorm_test.jsonl"]
    if not all(path.is_file() for path in paths):
        raise FileNotFoundError("Prepare ViLexNorm dev/test first; both files are required for leakage removal.")
    return {
        record["input_text"]
        for path in paths
        for record in read_jsonl(path)
        if isinstance(record.get("input_text"), str)
    }


def prepare_visolex_corpus(
    sources: list[SourceSpec],
    protected: set[str],
    *,
    log_every: int = 0,
    log: LogEvent | None = None,
) -> ViSoLexPreparation:
    """Prepare canonical ViSoLex records with first-source provenance on duplicates."""
    validate_source_specs(sources)
    seen: set[str] = set()
    records: list[dict[str, str]] = []
    raw_counts: Counter[str] = Counter()
    empty_counts: Counter[str] = Counter()
    duplicate_counts: Counter[str] = Counter()
    overlap_counts: Counter[str] = Counter()
    for source in sources:
        source_rows = read_rows(source.path)
        if log is not None:
            log("START", f"ViSoLex preprocessing: source={source.name} raw_rows={len(source_rows)} input={source.path}")
        for position, row in enumerate(source_rows, start=1):
            raw_counts[source.name] += 1
            text = clean_text(row.get(source.text_field))
            if text is None:
                empty_counts[source.name] += 1
            elif text in protected:
                overlap_counts[source.name] += 1
            elif text in seen:
                duplicate_counts[source.name] += 1
            else:
                seen.add(text)
                records.append({
                    "id": f"visolex_{len(records) + 1:06d}",
                    "dataset": "ViSoLex",
                    "original_source": source.name,
                    "input_text": text,
                })
            if log is not None and log_every > 0 and position % log_every == 0:
                log("PROGRESS", f"ViSoLex preprocessing: source={source.name} raw={position}/{len(source_rows)} kept_total={len(records)}")
        if log is not None:
            kept = sum(record["original_source"] == source.name for record in records)
            log("DONE", f"ViSoLex preprocessing: source={source.name} raw={raw_counts[source.name]} kept={kept} empty={empty_counts[source.name]} duplicates={duplicate_counts[source.name]} protected_overlap={overlap_counts[source.name]}")
    return ViSoLexPreparation(records, raw_counts, empty_counts, duplicate_counts, overlap_counts)