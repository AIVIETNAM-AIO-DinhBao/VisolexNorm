"""Verify the post-training research closure without modifying release v1.0.0."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
from visolexnorm.app.selection import load_selection
from visolexnorm.training.reports import checkpoint_inventory
SEGMENT = re.compile(r"^[a-f0-9]{16}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory_sha256(path: Path, kind: str) -> str:
    if kind == "file":
        return sha256_file(path)
    if kind == "directory":
        return checkpoint_inventory(path)[1]
    raise ValueError(f"Unsupported artifact kind: {kind}")


def join_segments(value: object) -> str:
    if not isinstance(value, list) or len(value) != 4 or not all(isinstance(part, str) and SEGMENT.fullmatch(part) for part in value):
        raise ValueError("sha256_segments must contain exactly four lowercase 16-hex segments")
    return "".join(value)


def load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Training closure must be a JSON object")
    return value


def verify(manifest: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1 or manifest.get("closure_id") != "training-closed-v1":
        errors.append("Invalid closure identity")
    application = manifest.get("application", {})
    if application.get("default_artifact_id") != "APP-DEFAULT" or application.get("fallback_artifact_id") != "APP-FALLBACK":
        errors.append("Closure application roles are invalid")
    if application.get("cmax20_promotion_eligible") is not False or application.get("test_metrics_used_for_closure_selection") is not False:
        errors.append("Closure must keep C-max20 exploratory and selection Dev-only")
    artifacts = manifest.get("artifacts", [])
    by_id = {item.get("id"): item for item in artifacts if isinstance(item, dict)}
    required = {"APP-DEFAULT", "APP-FALLBACK", "APP-SELECTION", "FCT-PROTOCOL", "FCT-SUMMARY", "FCT-CONCLUSION", "FCT-ARCHIVE", "OPT-CMAX20", "OPT-CMAX20-ANALYSIS"}
    if set(by_id) != required:
        errors.append("Closure artifact IDs are incomplete or duplicated")
        return errors
    for identifier, item in by_id.items():
        relative = item.get("path")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            errors.append(f"{identifier}: unsafe relative path")
            continue
        path = root / relative
        if not path.exists():
            errors.append(f"{identifier}: missing artifact")
            continue
        try:
            expected = join_segments(item.get("sha256_segments"))
        except ValueError as error:
            errors.append(f"{identifier}: {error}")
            continue
        actual = inventory_sha256(path, item.get("kind"))
        if actual != expected:
            errors.append(f"{identifier}: checksum mismatch")
    try:
        selection = load_selection(root / by_id["APP-SELECTION"]["path"])
        if selection.get("selected_model") != "model_c" or selection.get("fallback_model") != "model_b":
            errors.append("APP-SELECTION must retain Model C default and Model B fallback")
        if selection.get("test_metrics_used_for_selection") is not False:
            errors.append("APP-SELECTION must remain Dev-only")
        for identifier, key in (("APP-DEFAULT", "selected_checkpoint_inventory_sha256"), ("APP-FALLBACK", "fallback_checkpoint_inventory_sha256")):
            expected = join_segments(by_id[identifier]["sha256_segments"])
            if selection.get(key) != expected:
                errors.append(f"{identifier}: selection inventory does not match closure")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"Cannot verify APP-SELECTION: {error}")
    try:
        conclusion = json.loads((root / by_id["FCT-CONCLUSION"]["path"]).read_text(encoding="utf-8"))
        if conclusion.get("status") != "frozen_before_c_max20_es":
            errors.append("FCT-CONCLUSION is not frozen")
        if "C-max20-ES is exploratory" not in " ".join(conclusion.get("scope_limitations", [])):
            errors.append("FCT-CONCLUSION does not preserve C-max20 exploratory scope")
        for identifier, key in (("FCT-PROTOCOL", "protocol"), ("FCT-SUMMARY", "summary"), ("FCT-ARCHIVE", "run_artifacts")):
            expected = join_segments(by_id[identifier]["sha256_segments"])
            referenced = conclusion.get("artifacts", {}).get(key, {}).get("sha256_segments")
            if join_segments(referenced) != expected:
                errors.append(f"FCT-CONCLUSION does not match {identifier}")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"Cannot verify FCT-CONCLUSION: {error}")
    try:
        cmax = json.loads((root / by_id["OPT-CMAX20-ANALYSIS"]["path"]).read_text(encoding="utf-8"))
        if cmax.get("scope", {}).get("promotion_eligible") is not False or cmax.get("scope", {}).get("factorial_conclusion_revisable") is not False:
            errors.append("OPT-CMAX20-ANALYSIS must remain non-promotional")
        if join_segments(cmax.get("archive", {}).get("sha256_segments")) != join_segments(by_id["OPT-CMAX20"]["sha256_segments"]):
            errors.append("OPT-CMAX20-ANALYSIS archive does not match OPT-CMAX20")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"Cannot verify OPT-CMAX20-ANALYSIS: {error}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("release/training-closure.json"))
    args = parser.parse_args()
    manifest = load_manifest(args.manifest.resolve())
    errors = verify(manifest, ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("PASS: training closure verified (APP-DEFAULT=model_c, APP-FALLBACK=model_b)")


if __name__ == "__main__":
    main()