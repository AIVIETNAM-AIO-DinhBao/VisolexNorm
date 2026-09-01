"""Deterministic lexical-normalization metrics used by ViSoLexNorm.

Reference: Nguyen, Le and Nguyen (EACL 2024), ViLexNorm, which reports the
van der Goot (2019) Error Reduction Rate (ERR) against Leave-As-Is (LAI).
ERR follows ViLexNorm's token-accuracy reduction over the Leave-As-Is (LAI)
baseline. Token accuracy differences are computed equivalently from aggregate
whitespace-token Levenshtein error counts. The edit P/R/F1 protocol is reported
separately and remains protected by a deterministic parity fixture.
"""
from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
from typing import Iterable

OFFICIAL_REFERENCE = {
    "repository": "https://github.com/ngxtnhi/ViLexNorm",
    "commit": "1070c6b9b00830fad278f48d9797df9ae1c942ac",
    "paper": "https://aclanthology.org/2024.eacl-long.85",
    "protocol": "ViLexNorm token-accuracy ERR against Leave-As-Is plus project edit P/R/F1 v2",
}


def _edits(source: str, normalized: str) -> Counter[tuple[tuple[str, ...], tuple[str, ...]]]:
    """Return whitespace-token replacement edits, preserving 1:n and n:1 edits."""
    source_tokens, target_tokens = source.split(), normalized.split()
    edits: Counter[tuple[tuple[str, ...], tuple[str, ...]]] = Counter()
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=source_tokens, b=target_tokens, autojunk=False).get_opcodes():
        if tag != "equal":
            edits[(tuple(source_tokens[i1:i2]), tuple(target_tokens[j1:j2]))] += 1
    return edits


def token_levenshtein_distance(source: str, target: str) -> int:
    """Return Levenshtein distance between whitespace-token sequences."""
    source_tokens, target_tokens = source.split(), target.split()
    previous = list(range(len(target_tokens) + 1))
    for source_index, source_token in enumerate(source_tokens, start=1):
        current = [source_index]
        for target_index, target_token in enumerate(target_tokens, start=1):
            current.append(min(
                current[-1] + 1,
                previous[target_index] + 1,
                previous[target_index - 1] + (source_token != target_token),
            ))
        previous = current
    return previous[-1]


def evaluate_records(records: Iterable[dict]) -> dict[str, float | int]:
    """Compute edit P/R/F1 and token-accuracy ERR against Leave-As-Is."""
    records = list(records)
    gold_total = predicted_total = correct_total = 0
    lai_token_errors = system_token_errors = 0
    for row in records:
        source, gold, prediction = row["input_text"], row["target_text"], row["prediction_text"]
        gold_edits, predicted_edits = _edits(source, gold), _edits(source, prediction)
        gold_total += sum(gold_edits.values())
        predicted_total += sum(predicted_edits.values())
        correct_total += sum((gold_edits & predicted_edits).values())
        lai_token_errors += token_levenshtein_distance(source, gold)
        system_token_errors += token_levenshtein_distance(prediction, gold)
    precision = correct_total / predicted_total if predicted_total else 0.0
    recall = correct_total / gold_total if gold_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    # ERR is undefined for a corpus containing no LAI errors. Return 0.0 for
    # that degenerate subset so per-record sufficient statistics remain usable
    # by paired bootstrap; non-degenerate corpus reports use the standard ratio.
    err = (lai_token_errors - system_token_errors) / lai_token_errors if lai_token_errors else 0.0
    return {
        "sample_count": len(records),
        "gold_edits": gold_total,
        "predicted_edits": predicted_total,
        "correct_edits": correct_total,
        "lai_token_errors": lai_token_errors,
        "system_token_errors": system_token_errors,
        "ERR": err,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }