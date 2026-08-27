"""Freeze an audited Phase 3 prompt and record its SHA-256 in config."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from scripts.lexical_policy import load_policy, review_identity_hash
from visolexnorm.common.io import load_json, read_jsonl
from visolexnorm.common.progress import log_event


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze the manually approved reviewer prompt.")
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--pilot-report", type=Path, required=True, help="JSON audit report bound to prompt hash and IDs")
    parser.add_argument("--pilot-manifest", type=Path, default=Path("data/intermediate/visolex_pilot_manifest.jsonl"))
    parser.add_argument("--approved", action="store_true", help="Confirms that all 240 pilot samples were audited")
    parser.add_argument("--replace-existing", action="store_true", help="Replace a stale, never-frozen v1 prompt during approved migration")
    parser.add_argument("--quiet", action="store_true", help="Suppress operational progress logs")
    args = parser.parse_args()
    if not args.approved:
        raise SystemExit("Pass --approved only after manually auditing all 240 pilot samples")
    config = load_json(args.config)
    draft = Path(config["draft_prompt_path"])
    frozen = Path(config["frozen_prompt_path"])
    if frozen.exists() and not args.replace_existing:
        raise FileExistsError(f"Frozen prompt already exists: {frozen}")
    log_event("START", f"Prompt freeze: draft={draft} pilot_manifest={args.pilot_manifest}", quiet=args.quiet)
    report = load_json(args.pilot_report)
    pilot_ids = [row["id"] for row in read_jsonl(args.pilot_manifest)]
    expected_count = int(config["pilot_per_stratum"]) * 4 * len(config["confidence_bands"])
    policy = load_policy(Path(config["lexical_policy_path"]))
    review_hash = review_identity_hash(draft.read_text(encoding="utf-8"), policy)
    report_hash = report.get("review_identity_sha256") or report.get("prompt_sha256")
    if report.get("approved") is not True or report_hash != review_hash:
        raise ValueError("Pilot report is not approved for the current draft prompt and lexical policy")
    audited_ids = report.get("audited_ids")
    if not isinstance(audited_ids, list) or len(audited_ids) != expected_count:
        raise ValueError(f"Pilot report must contain exactly {expected_count} audited IDs")
    if len(set(audited_ids)) != expected_count or set(audited_ids) != set(pilot_ids):
        raise ValueError("Pilot report IDs do not exactly match the pilot manifest")
    frozen.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(draft, frozen)
    config["prompt_frozen"] = True
    config["frozen_prompt_sha256"] = review_hash
    config["frozen_policy_version"] = policy["version"]
    args.config.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_event("DONE", f"Prompt freeze: prompt_version={config['frozen_prompt_version']} audited_ids={expected_count} review_identity_sha256={config['frozen_prompt_sha256']} policy={policy['version']} config={args.config}", quiet=args.quiet)


if __name__ == "__main__":
    main()