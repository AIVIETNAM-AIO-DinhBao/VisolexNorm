"""Deterministic Phase 3 and Phase 8 review manifest selection."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from visolexnorm.candidates.contracts import validate_candidates
from visolexnorm.common.artifacts import sha256_file


def unique_ids(rows: list[dict[str, Any]], label: str) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        sample_id = row.get("id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in ids:
            raise ValueError(f"Invalid or duplicate {label} ID: {sample_id!r}")
        ids.add(sample_id)
    return ids


def largest_remainder_quotas(counts: dict[str, int], budget: int, source_order: list[str]) -> dict[str, int]:
    total = sum(counts.values())
    if budget < 1 or budget > total:
        raise ValueError("Review budget must be between 1 and the candidate count")
    exact = {source: budget * counts.get(source, 0) / total for source in source_order}
    quotas = {source: min(counts.get(source, 0), math.floor(exact[source])) for source in source_order}
    remaining = budget - sum(quotas.values())
    priority = sorted(
        source_order,
        key=lambda source: (-(exact[source] - math.floor(exact[source])), source_order.index(source)),
    )
    while remaining:
        progressed = False
        for source in priority:
            if quotas[source] < counts.get(source, 0) and remaining:
                quotas[source] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            raise RuntimeError("Unable to allocate the complete review budget")
    return quotas


def split_quota(total: int, bands: list[str]) -> dict[str, int]:
    base, remainder = divmod(total, len(bands))
    return {band: base + (1 if index < remainder else 0) for index, band in enumerate(bands)}


def assign_confidence_bands(rows: list[dict[str, Any]], bands: list[str]) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda row: (float(row["model_a_confidence"]), str(row["id"])))
    result = {band: [] for band in bands}
    for index, row in enumerate(ordered):
        band_index = min(len(bands) - 1, index * len(bands) // len(ordered))
        result[bands[band_index]].append(row)
    return result


def select_stratified_review_manifest(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Select the frozen Phase 3 source-by-confidence review manifest."""
    validate_candidates(rows)
    source_order = list(config["source_order"])
    bands = list(config["confidence_bands"])
    budget = int(config["review_budget"])
    seed = int(config["seed"])
    pilot_per_stratum = int(config["pilot_per_stratum"])
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source = str(row["original_source"])
        if source not in source_order:
            raise ValueError(f"Unexpected source: {source}")
        by_source[source].append(row)
    source_quotas = largest_remainder_quotas(
        {source: len(by_source[source]) for source in source_order}, budget, source_order
    )
    selected: list[dict[str, Any]] = []
    for source in source_order:
        if not by_source[source]:
            continue
        band_rows = assign_confidence_bands(by_source[source], bands)
        band_quotas = split_quota(source_quotas[source], bands)
        for band_index, band in enumerate(bands):
            pool = list(band_rows[band])
            if band_quotas[band] > len(pool):
                raise ValueError(f"Insufficient candidates in {source}/{band}")
            random.Random(f"{seed}:{source}:{band_index}").shuffle(pool)
            for rank, candidate in enumerate(pool[:band_quotas[band]], start=1):
                selected.append({
                    **candidate,
                    "confidence_band": band,
                    "source_quota": source_quotas[source],
                    "selection_rank": rank,
                    "selection_seed": seed,
                    "is_pilot": rank <= pilot_per_stratum,
                })
    if len(selected) != budget or len({row["id"] for row in selected}) != budget:
        raise RuntimeError("Manifest does not contain the expected number of unique IDs")
    return selected


def select_remaining_review_manifest(
    candidates: list[dict[str, Any]], prior_manifest: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return the candidate-order-preserving Phase 8 complement of Phase 3 IDs."""
    validate_candidates(candidates)
    candidate_ids = {row["id"] for row in candidates}
    prior_ids = unique_ids(prior_manifest, "prior manifest")
    unexpected = prior_ids - candidate_ids
    if unexpected:
        raise ValueError(f"Prior manifest contains {len(unexpected)} IDs absent from candidates")
    expected = (
        ("candidate", len(candidates), int(config["expected_candidate_count"])),
        ("prior manifest", len(prior_manifest), int(config["expected_prior_manifest_count"])),
    )
    for label, actual, required in expected:
        if actual != required:
            raise ValueError(f"Unexpected {label} count: {actual} != {required}")
    seed = int(config["seed"])
    remaining = [
        {
            **row,
            "review_scope": "phase8_remaining",
            "prior_manifest": False,
            "selection_seed": seed,
            "selection_rank": index,
        }
        for index, row in enumerate((row for row in candidates if row["id"] not in prior_ids), start=1)
    ]
    if len(remaining) != int(config["expected_remaining_count"]):
        raise ValueError(f"Unexpected remaining count: {len(remaining)} != {config['expected_remaining_count']}")
    return remaining


def build_remaining_report(
    candidates_path: Path,
    prior_manifest_path: Path,
    remaining_path: Path,
    candidates: list[dict[str, Any]],
    prior_manifest: list[dict[str, Any]],
    remaining: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "phase": 8,
        "candidate_count": len(candidates),
        "prior_manifest_count": len(prior_manifest),
        "remaining_count": len(remaining),
        "candidate_path": candidates_path.as_posix(),
        "candidate_sha256": sha256_file(candidates_path),
        "prior_manifest_path": prior_manifest_path.as_posix(),
        "prior_manifest_sha256": sha256_file(prior_manifest_path),
        "remaining_manifest_path": remaining_path.as_posix(),
        "candidate_order_preserved": True,
        "prior_manifest_is_candidate_subset": True,
        "prior_remaining_intersection_count": 0,
    }