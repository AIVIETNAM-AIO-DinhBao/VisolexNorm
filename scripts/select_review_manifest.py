"""Select the deterministic 20k source × confidence review manifest and pilot."""

from __future__ import annotations

import argparse
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).parent))
from data_utils import read_jsonl  # noqa: E402
from generate_candidates import REQUIRED_CANDIDATE  # noqa: E402
from phase3_utils import atomic_write_jsonl, ensure_finite_number, load_json, log_event  # noqa: E402


def validate_candidates(rows: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for row in rows:
        if set(row) != REQUIRED_CANDIDATE:
            raise ValueError(f"Candidate fields do not match contract: {row.get('id')}")
        sample_id = row.get("id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen:
            raise ValueError(f"Invalid or duplicate candidate ID: {sample_id!r}")
        ensure_finite_number(row.get("model_a_confidence"), "model_a_confidence")
        seen.add(sample_id)


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


def create_manifest(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
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
            rng = random.Random(f"{seed}:{source}:{band_index}")
            rng.shuffle(pool)
            for rank, candidate in enumerate(pool[: band_quotas[band]], start=1):
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the deterministic Phase 3 review manifest.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/intermediate/visolex_review_manifest.jsonl"))
    parser.add_argument("--pilot-output", type=Path, default=Path("data/intermediate/visolex_pilot_manifest.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--quiet", action="store_true", help="Suppress operational progress logs")
    args = parser.parse_args()

    config = load_json(args.config)
    candidates = read_jsonl(args.candidates)
    log_event("START", f"Review-manifest selection: candidates={len(candidates)} budget={config['review_budget']} seed={config['seed']}", quiet=args.quiet)
    manifest = create_manifest(candidates, config)
    pilot = [row for row in manifest if row["is_pilot"]]
    active_sources = {row["original_source"] for row in manifest}
    expected_pilot = int(config["pilot_per_stratum"]) * len(active_sources) * len(config["confidence_bands"])
    if len(pilot) != expected_pilot:
        raise RuntimeError(f"Pilot count mismatch: expected {expected_pilot}, found {len(pilot)}")
    atomic_write_jsonl(manifest, args.output)
    atomic_write_jsonl(pilot, args.pilot_output)
    log_event("PROGRESS", f"Review-manifest quotas: {dict(Counter(row['original_source'] for row in manifest))}", quiet=args.quiet)
    log_event("DONE", f"Review-manifest selection: manifest={len(manifest)} pilot={len(pilot)} output={args.output} pilot_output={args.pilot_output}", quiet=args.quiet)


if __name__ == "__main__":
    main()