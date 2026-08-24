"""Build the Phase 8 manifest from candidates not reviewed in Phase 3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from data_utils import read_jsonl  # noqa: E402
from phase3_utils import atomic_write_jsonl, load_json, sha256_file  # noqa: E402
from select_review_manifest import validate_candidates  # noqa: E402


def unique_ids(rows: list[dict[str, Any]], label: str) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        sample_id = row.get("id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in ids:
            raise ValueError(f"Invalid or duplicate {label} ID: {sample_id!r}")
        ids.add(sample_id)
    return ids


def select_remaining(
    candidates: list[dict[str, Any]], prior_manifest: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return the candidate-order-preserving Phase 8 complement of the Phase 3 manifest."""
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


def build_report(
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/expanded_review_config.json"))
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--prior-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    config = load_json(args.config)
    candidates_path = args.candidates or Path(config["candidate_path"])
    prior_manifest_path = args.prior_manifest or Path(config["prior_manifest_path"])
    output_path = args.output or Path(config["remaining_manifest_path"])
    report_path = args.report or Path(config["remaining_manifest_report_path"])
    candidates = read_jsonl(candidates_path)
    prior_manifest = read_jsonl(prior_manifest_path)
    remaining = select_remaining(candidates, prior_manifest, config)
    atomic_write_jsonl(remaining, output_path)
    report = build_report(candidates_path, prior_manifest_path, output_path, candidates, prior_manifest, remaining)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"remaining_count": len(remaining), "output": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()