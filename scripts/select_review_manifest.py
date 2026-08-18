"""Select a deterministic, source/confidence-stratified Gemini review manifest."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).parent))
from data_utils import read_jsonl, write_jsonl  # noqa: E402


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def confidence_bin(value: float, low: float, high: float) -> str:
    return "low" if value <= low else "high" if value >= high else "medium"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a reproducible ViSoLex review manifest.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/intermediate/visolex_review_manifest.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("configs/weak_label_config.json"))
    parser.add_argument("--budget", type=int, help="Overrides review_budget in config")
    args = parser.parse_args()

    config = load_config(args.config)
    budget = int(args.budget or config["review_budget"])
    candidates = read_jsonl(args.candidates)
    if budget < 1 or not candidates:
        raise ValueError("Candidates and review budget must both be non-empty")
    ids = [row.get("id") for row in candidates]
    if len(ids) != len(set(ids)) or any(not isinstance(value, str) for value in ids):
        raise ValueError("Candidate artifact has invalid or duplicate IDs")
    for row in candidates:
        if not isinstance(row.get("model_a_confidence"), (int, float)) or not row.get("original_source"):
            raise ValueError(f"Candidate missing confidence/source: {row.get('id')}")

    scores = sorted(float(row["model_a_confidence"]) for row in candidates)
    low = scores[max(0, int((len(scores) - 1) * 1 / 3))]
    high = scores[max(0, int((len(scores) - 1) * 2 / 3))]
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        strata[(str(row["original_source"]), confidence_bin(float(row["model_a_confidence"]), low, high))].append(row)

    rng = random.Random(int(config["seed"]))
    # Allocate one rotating sample at a time to preserve every non-empty stratum
    # as far as the fixed API budget permits.
    selected: list[dict[str, Any]] = []
    pools: list[list[dict[str, Any]]] = []
    for key in sorted(strata):
        pool = sorted(strata[key], key=lambda row: str(row["id"]))
        rng.shuffle(pool)
        pools.append(pool)
    while len(selected) < min(budget, len(candidates)) and any(pools):
        for pool in pools:
            if pool and len(selected) < min(budget, len(candidates)):
                selected.append(pool.pop())
        pools = [pool for pool in pools if pool]

    selected_ids = {row["id"] for row in selected}
    if len(selected_ids) != len(selected):
        raise RuntimeError("Selection produced duplicate IDs")
    manifest = []
    for row in candidates:
        if row["id"] in selected_ids:
            manifest.append(
                {
                    "id": row["id"],
                    "dataset": "ViSoLex",
                    "original_source": row["original_source"],
                    "model_a_confidence": row["model_a_confidence"],
                    "confidence_bin": confidence_bin(float(row["model_a_confidence"]), low, high),
                    "selection_rule_version": "source_confidence_round_robin_v1",
                }
            )
    write_jsonl(manifest, args.output)
    print(f"Saved {len(manifest)} / {len(candidates)} selected IDs -> {args.output}")


if __name__ == "__main__":
    main()