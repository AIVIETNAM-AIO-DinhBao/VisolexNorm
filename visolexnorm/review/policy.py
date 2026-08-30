"""Versioned deterministic safeguards for Phase 3 LLM review output."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from visolexnorm.common.artifacts import sha256_json
from visolexnorm.common.io import load_json


WORD_BOUNDARY = re.compile(r"(?<!\w){}(?!\w)", re.IGNORECASE)
EMOJI_OR_SYMBOL = re.compile(r"[^\w\s.,;:!?()\[\]{}'\"/@&*+=%#-]", re.UNICODE)
REPEATED = re.compile(r"(.)\1{4,}", re.UNICODE)
ALPHA_TOKEN = re.compile(r"[A-Za-zÀ-ỹ]+", re.UNICODE)
VOWEL = re.compile(r"[aeiouyàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]", re.IGNORECASE)


def load_policy(path: Path) -> dict[str, Any]:
    policy = load_json(path)
    if not isinstance(policy.get("version"), str) or not policy["version"]:
        raise ValueError("Lexical policy requires a version")
    for field in ("canonical_replacements", "unambiguous_abbreviations"):
        if not isinstance(policy.get(field), dict):
            raise ValueError(f"Lexical policy requires {field}")
    if not isinstance(policy.get("ambiguous_source_phrases", []), list):
        raise ValueError("Lexical policy ambiguous_source_phrases must be a list")
    return policy


def policy_fingerprint(policy: dict[str, Any]) -> dict[str, Any]:
    """Return the complete versioned policy payload for cache namespacing."""
    return policy


def review_identity_hash(prompt_text: str, policy: dict[str, Any]) -> str:
    """Hash the exact reviewer instructions and the deterministic policy together."""
    return sha256_json({"prompt": prompt_text, "lexical_policy": policy_fingerprint(policy)})


def canonicalize(text: str, policy: dict[str, Any]) -> str:
    """Apply only explicit, versioned lexical replacements."""
    merged = {**policy["unambiguous_abbreviations"], **policy["canonical_replacements"]}
    result = text
    for source in sorted(merged, key=len, reverse=True):
        replacement = str(merged[source])
        result = re.sub(WORD_BOUNDARY.pattern.format(re.escape(source)), replacement, result, flags=re.IGNORECASE)
    return result


def is_fully_opaque(text: str, policy: dict[str, Any]) -> bool:
    """Reject only clearly unusable all-gibberish inputs, not mixed social text."""
    tokens = ALPHA_TOKEN.findall(text)
    minimum = int(policy["opaque_token_min_length"])
    if len(tokens) != 1 or len(tokens[0]) < minimum:
        return False
    token = tokens[0]
    return not VOWEL.search(token)


def preservation_errors(source: str, target: str, policy: dict[str, Any]) -> list[str]:
    """Detect high-confidence loss of non-lexical information in a final target."""
    errors: list[str] = []
    for value in EMOJI_OR_SYMBOL.findall(source):
        if value not in target:
            errors.append("source_symbol_removed")
            break
    for sequence in REPEATED.findall(source):
        # Regex returns only the repeated character; inspect full runs separately below.
        _ = sequence
    for match in REPEATED.finditer(source):
        if match.group(0) not in target:
            errors.append("expressive_elongation_removed")
            break
    for number in re.findall(r"\d+(?:[.,]\d+)?", source):
        if number not in target:
            errors.append("number_removed")
            break
    return errors


def apply_policy(rows: list[dict[str, Any]], results: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Canonicalize safe lexical forms and reject unreviewable or lossy outputs."""
    by_id = {row["id"]: row for row in rows}
    adjusted: list[dict[str, Any]] = []
    for result in results:
        row = by_id[result["id"]]
        if any(phrase.casefold() in row["input_text"].casefold() for phrase in policy["ambiguous_source_phrases"]):
            adjusted.append({"id": result["id"], "decision": "REJECT", "corrected_text": None, "reason_code": "AMBIGUOUS"})
            continue
        if is_fully_opaque(row["input_text"], policy):
            adjusted.append({"id": result["id"], "decision": "REJECT", "corrected_text": None, "reason_code": "NOT_LEXICAL_NORMALIZATION"})
            continue
        final_text = row["candidate_text"] if result["decision"] == "KEEP" else result["corrected_text"]
        if result["decision"] != "REJECT":
            canonical = canonicalize(final_text, policy)
            errors = preservation_errors(row["input_text"], canonical, policy)
            if errors:
                adjusted.append({"id": result["id"], "decision": "REJECT", "corrected_text": None, "reason_code": "OTHER"})
                continue
            if result["decision"] == "KEEP" and canonical != final_text:
                adjusted.append({"id": result["id"], "decision": "EDIT", "corrected_text": canonical, "reason_code": None})
            elif result["decision"] == "EDIT":
                adjusted.append({**result, "corrected_text": canonical})
            else:
                adjusted.append(result)
        else:
            adjusted.append(result)
    return adjusted