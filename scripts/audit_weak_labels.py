"""Export deterministic stratified Phase 3 audit samples and artifact checksums."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from data_utils import read_jsonl
from phase3_utils import atomic_write_jsonl, load_json, sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit weak labels and write Phase 3 checksums.")
    parser.add_argument("--weak-labels", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--audit", type=Path, default=Path("outputs/weak_label_audit.jsonl"))
    parser.add_argument("--phase-manifest", type=Path, default=Path("outputs/phase3_manifest.json"))
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    args = parser.parse_args()
    config = load_json(args.config)
    rows = read_jsonl(args.weak_labels)
    strata = defaultdict(list)
    for row in rows:
        strata[(row["llm_decision"], row["original_source"], row["confidence_band"])].append(row)
    selected = []
    count = int(config["audit_samples_per_stratum"])
    for key in sorted(strata):
        pool = sorted(strata[key], key=lambda row: row["id"])
        random.Random(f"{config['seed']}:{key}").shuffle(pool)
        selected.extend(pool[:count])
    atomic_write_jsonl(selected, args.audit)
    artifacts = [args.weak_labels, args.stats, args.audit, args.config, Path(config["frozen_prompt_path"])]
    manifest = {"artifacts": [
        {"path": path.as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in artifacts
    ]}
    args.phase_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.phase_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(selected)} audit rows and {len(artifacts)} checksums")


if __name__ == "__main__":
    main()