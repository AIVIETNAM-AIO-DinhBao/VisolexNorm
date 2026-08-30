"""Freeze an audited Phase 3 prompt and record its SHA-256 in config."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from visolexnorm.common.io import load_json, read_jsonl
from visolexnorm.review.policy import load_policy, review_identity_hash


def freeze_prompt(config_path: Path, pilot_report_path: Path, pilot_manifest_path: Path, *, replace_existing: bool = False) -> tuple[dict, int]:
    """Freeze an approved draft prompt and update a temporary/configured JSON file."""
    config = load_json(config_path)
    draft = Path(config["draft_prompt_path"])
    frozen = Path(config["frozen_prompt_path"])
    if frozen.exists() and not replace_existing:
        raise FileExistsError(f"Frozen prompt already exists: {frozen}")
    report = load_json(pilot_report_path)
    pilot_ids = [row["id"] for row in read_jsonl(pilot_manifest_path)]
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
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return config, expected_count