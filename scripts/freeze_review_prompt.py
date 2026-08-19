"""Freeze an audited Phase 3 prompt and record its SHA-256 in config."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from data_utils import read_jsonl
from phase3_utils import load_json, sha256_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze the manually approved reviewer prompt.")
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--pilot-report", type=Path, required=True, help="JSON audit report bound to prompt hash and IDs")
    parser.add_argument("--pilot-manifest", type=Path, default=Path("data/intermediate/visolex_pilot_manifest.jsonl"))
    parser.add_argument("--approved", action="store_true", help="Confirms that all 240 pilot samples were audited")
    args = parser.parse_args()
    if not args.approved:
        raise SystemExit("Pass --approved only after manually auditing all 240 pilot samples")
    config = load_json(args.config)
    draft = Path(config["draft_prompt_path"])
    frozen = Path(config["frozen_prompt_path"])
    if frozen.exists():
        raise FileExistsError(f"Frozen prompt already exists: {frozen}")
    report = load_json(args.pilot_report)
    pilot_ids = [row["id"] for row in read_jsonl(args.pilot_manifest)]
    expected_count = int(config["pilot_per_stratum"]) * 4 * len(config["confidence_bands"])
    draft_hash = sha256_text(draft.read_text(encoding="utf-8"))
    if report.get("approved") is not True or report.get("prompt_sha256") != draft_hash:
        raise ValueError("Pilot report is not approved for the current draft prompt")
    audited_ids = report.get("audited_ids")
    if not isinstance(audited_ids, list) or len(audited_ids) != expected_count:
        raise ValueError(f"Pilot report must contain exactly {expected_count} audited IDs")
    if len(set(audited_ids)) != expected_count or set(audited_ids) != set(pilot_ids):
        raise ValueError("Pilot report IDs do not exactly match the pilot manifest")
    frozen.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(draft, frozen)
    config["prompt_frozen"] = True
    config["frozen_prompt_sha256"] = draft_hash
    args.config.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Frozen prompt SHA-256: {config['frozen_prompt_sha256']}")


if __name__ == "__main__":
    main()