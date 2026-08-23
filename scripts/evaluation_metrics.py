"""Deterministic ViLexNorm-style lexical-normalization metrics.

Reference: Nguyen, Le and Nguyen (EACL 2024), ViLexNorm, which reports the
van der Goot (2019) Error Reduction Rate (ERR) against Leave-As-Is (LAI).
The corpus repository at ngxtnhi/ViLexNorm commit
1070c6b9b00830fad278f48d9797df9ae1c942ac distributes data only, not an
evaluator.  This dependency-free port therefore defines the complete protocol
used by this project and is protected by a frozen parity fixture.
"""
from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
from typing import Iterable

OFFICIAL_REFERENCE = {
    "repository": "https://github.com/ngxtnhi/ViLexNorm",
    "commit": "1070c6b9b00830fad278f48d9797df9ae1c942ac",
    "paper": "https://aclanthology.org/2024.eacl-long.85",
    "protocol": "van der Goot (2019) ERR against Leave-As-Is; project token-edit port v1",
}


def _edits(source: str, normalized: str) -> Counter[tuple[tuple[str, ...], tuple[str, ...]]]:
    """Return whitespace-token replacement edits, preserving 1:n and n:1 edits."""
    source_tokens, target_tokens = source.split(), normalized.split()
    edits: Counter[tuple[tuple[str, ...], tuple[str, ...]]] = Counter()
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=source_tokens, b=target_tokens, autojunk=False).get_opcodes():
        if tag != "equal":
            edits[(tuple(source_tokens[i1:i2]), tuple(target_tokens[j1:j2]))] += 1
    return edits


def evaluate_records(records: Iterable[dict]) -> dict[str, float | int]:
    """Compute micro P/R/F1 and ERR over lexical normalization edit operations."""
    records = list(records)
    gold_total = predicted_total = correct_total = 0
    for row in records:
        source, gold, prediction = row["input_text"], row["target_text"], row["prediction_text"]
        gold_edits, predicted_edits = _edits(source, gold), _edits(source, prediction)
        gold_total += sum(gold_edits.values())
        predicted_total += sum(predicted_edits.values())
        correct_total += sum((gold_edits & predicted_edits).values())
    precision = correct_total / predicted_total if predicted_total else 0.0
    recall = correct_total / gold_total if gold_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    # LAI leaves every gold edit unresolved; remaining errors are gold edits not corrected.
    err = correct_total / gold_total if gold_total else 0.0
    return {
        "sample_count": len(records),
        "gold_edits": gold_total,
        "predicted_edits": predicted_total,
        "correct_edits": correct_total,
        "ERR": err,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }