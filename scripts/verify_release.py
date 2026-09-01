"""Verify a ViSoLexNorm release manifest, local artifacts, and secret policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SECRET_PATTERNS = (
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_-]{20,}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)
REQUIRED_ARTIFACT_FIELDS = {
    "path",
    "phase",
    "artifact_type",
    "kind",
    "location",
    "sha256",
    "size_bytes",
    "required",
    "distribution_url",
    "contains_sensitive_data",
}
ALLOWED_ARTIFACT_TYPES = {"code", "config", "prompt", "data", "checkpoint", "metrics", "predictions", "docs"}
ALLOWED_KINDS = {"file", "directory"}
ALLOWED_LOCATIONS = {"repository", "local-handoff", "external"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(path: Path) -> tuple[str, int, str]:
    """Return kind, byte count, and deterministic SHA-256 for a file or directory."""
    if path.is_file():
        return "file", path.stat().st_size, sha256_file(path)
    if not path.is_dir():
        raise FileNotFoundError(path)
    entries = []
    total_size = 0
    for item in sorted(path.rglob("*")):
        if item.is_file():
            size = item.stat().st_size
            total_size += size
            entries.append({"path": item.relative_to(path).as_posix(), "bytes": size, "sha256": sha256_file(item)})
    if not entries:
        raise ValueError(f"Artifact directory is empty: {path}")
    return "directory", total_size, hashlib.sha256(canonical_json(entries).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def is_safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or re.match(r"^[A-Za-z]:", value):
        return False
    return all(part not in {"", ".", ".."} for part in Path(value).parts)


def is_fixed_kaggle_version_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "www.kaggle.com"
        and bool(re.fullmatch(r"/datasets/[^/]+/[^/]+/versions/[1-9][0-9]*", parsed.path))
    )


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"project", "version", "created_at", "source_revision", "release_status", "artifacts"}
    if set(manifest) != required:
        errors.append("Manifest fields do not match the release contract")
    if manifest.get("project") != "ViSoLexNorm":
        errors.append("project must be ViSoLexNorm")
    if not isinstance(manifest.get("version"), str) or not SEMVER_PATTERN.fullmatch(manifest["version"]):
        errors.append("version must use semantic versioning")
    if not isinstance(manifest.get("source_revision"), str) or not re.fullmatch(r"[a-f0-9]{40}", manifest["source_revision"]):
        errors.append("source_revision must be a 40-character Git SHA")
    if manifest.get("release_status") not in {"candidate_pending_checkpoint_distribution", "released"}:
        errors.append("release_status is invalid")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return errors + ["artifacts must be a non-empty array"]
    seen_paths: set[str] = set()
    for index, artifact in enumerate(artifacts):
        prefix = f"artifacts[{index}]"
        if not isinstance(artifact, dict) or set(artifact) != REQUIRED_ARTIFACT_FIELDS:
            errors.append(f"{prefix} fields do not match the release contract")
            continue
        path = artifact["path"]
        if not is_safe_relative_path(path):
            errors.append(f"{prefix}.path is not a safe relative path")
        elif path in seen_paths:
            errors.append(f"{prefix}.path is duplicated: {path}")
        else:
            seen_paths.add(path)
        if not isinstance(artifact["phase"], int) or not 1 <= artifact["phase"] <= 10:
            errors.append(f"{prefix}.phase must be between 1 and 10")
        if artifact["artifact_type"] not in ALLOWED_ARTIFACT_TYPES:
            errors.append(f"{prefix}.artifact_type is invalid")
        if artifact["kind"] not in ALLOWED_KINDS:
            errors.append(f"{prefix}.kind is invalid")
        if artifact["location"] not in ALLOWED_LOCATIONS:
            errors.append(f"{prefix}.location is invalid")
        if not isinstance(artifact["size_bytes"], int) or artifact["size_bytes"] < 0:
            errors.append(f"{prefix}.size_bytes is invalid")
        if not isinstance(artifact["required"], bool) or artifact["contains_sensitive_data"] is not False:
            errors.append(f"{prefix} required/sensitive flags are invalid")
        if not isinstance(artifact["sha256"], str) or not SHA256_PATTERN.fullmatch(artifact["sha256"]):
            errors.append(f"{prefix}.sha256 is invalid")
        url = artifact["distribution_url"]
        if url is not None and not (isinstance(url, str) and urlparse(url).scheme == "https"):
            errors.append(f"{prefix}.distribution_url must be an HTTPS URL or null")
        if artifact["location"] == "repository" and url is not None:
            errors.append(f"{prefix} repository artifact must not have distribution_url")
    return errors


def verify_artifacts(manifest: dict[str, Any], root: Path) -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    warnings: list[str] = []
    passed = 0
    for artifact in manifest["artifacts"]:
        path = root / artifact["path"]
        if not path.exists():
            message = f"Missing artifact: {artifact['path']}"
            (errors if artifact["required"] else warnings).append(message)
            continue
        try:
            kind, size_bytes, digest = inventory(path)
        except (FileNotFoundError, ValueError) as error:
            errors.append(str(error))
            continue
        mismatches = []
        if kind != artifact["kind"]:
            mismatches.append(f"kind expected={artifact['kind']} actual={kind}")
        if size_bytes != artifact["size_bytes"]:
            mismatches.append(f"size expected={artifact['size_bytes']} actual={size_bytes}")
        if digest != artifact["sha256"]:
            mismatches.append("sha256 mismatch")
        if mismatches:
            errors.append(f"Artifact mismatch {artifact['path']}: {', '.join(mismatches)}")
        else:
            passed += 1
    return errors, warnings, passed


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
    return [root / value.decode("utf-8") for value in result.stdout.split(b"\0") if value]


def scan_secrets(root: Path, additional_files: list[Path] | None = None) -> list[str]:
    errors: list[str] = []
    try:
        files = tracked_files(root)
    except (OSError, subprocess.CalledProcessError) as error:
        return [f"Cannot enumerate tracked files for secret scan: {error}"]
    files = list(dict.fromkeys(files + (additional_files or [])))
    if (root / ".env") in files:
        errors.append(".env must never be tracked")
    for path in files:
        if path.suffix.lower() not in {".env", ".py", ".md", ".json", ".ipynb", ".txt", ".yml", ".yaml", ".csv"} and path.name not in {".env", ".env.example"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"Cannot UTF-8 scan tracked text file: {path.relative_to(root)}")
            continue
        relative = path.relative_to(root).as_posix()
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"Potential {name} in {relative}")
        if path.name == ".env.example":
            values = re.findall(r"^GEMINI_API_KEYS=(.*)$", text, flags=re.MULTILINE)
            if len(values) != 1 or any(value.strip() and not re.fullmatch(r"key_[0-9]+(?:,key_[0-9]+)*", value.strip()) for value in values):
                errors.append(".env.example must contain only comma-separated key_N placeholders")
    return errors


def verify_policy(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        app = load_json(root / "outputs/app/model_selection.json")
        dev = load_json(root / "outputs/evaluation_dev/model_metrics.json")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        return [f"Cannot verify model-selection policy: {error}"]
    if app.get("selected_model") != dev.get("selected_model") or app.get("fallback_model") != dev.get("ranking", [None, None])[1]:
        errors.append("Application selection must match the common Dev ranking")
    if app.get("selection_split") != "dev" or app.get("test_metrics_used_for_selection") is not False:
        errors.append("Application selection must be Dev-only and exclude Test metrics")
    if app.get("selection_metric") != "ERR" or dev.get("selection_metric") != "ERR":
        errors.append("Application selection must use corrected Dev ERR")
    return errors


def distribution_errors(manifest: dict[str, Any], strict_distribution: bool) -> list[str]:
    errors: list[str] = []
    checkpoints = [item for item in manifest["artifacts"] if item["artifact_type"] == "checkpoint"]
    for checkpoint in checkpoints:
        url = checkpoint["distribution_url"]
        if strict_distribution and not is_fixed_kaggle_version_url(url):
            errors.append(f"Checkpoint requires a fixed Kaggle Dataset version URL: {checkpoint['path']}")
    if strict_distribution and manifest["release_status"] != "released":
        errors.append("Strict distribution verification requires release_status=released")
    return errors


def write_report(path: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str], passed: int) -> None:
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    report = {
        "schema_version": 1,
        "project": "ViSoLexNorm",
        "release_version": manifest.get("version"),
        "manifest_sha256": sha256_file(path.parent / "manifest.json") if (path.parent / "manifest.json").is_file() else None,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "git_revision": revision,
        "artifacts_passed": passed,
        "errors": errors,
        "warnings": warnings,
        "secret_scan_passed": not any("Potential" in error or ".env" in error for error in errors),
        "exit_code": 0 if not errors else 1,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("release/manifest.json"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--strict-distribution", action="store_true")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    try:
        manifest = load_json(manifest_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: Cannot load manifest: {error}", file=sys.stderr)
        raise SystemExit(2)
    errors = validate_manifest(manifest)
    warnings: list[str] = []
    passed = 0
    if not errors:
        artifact_errors, artifact_warnings, passed = verify_artifacts(manifest, ROOT)
        errors.extend(artifact_errors)
        warnings.extend(artifact_warnings)
        declared_files = [ROOT / item["path"] for item in manifest["artifacts"] if item["location"] == "repository"]
        errors.extend(scan_secrets(ROOT, declared_files))
        errors.extend(verify_policy(ROOT))
        errors.extend(distribution_errors(manifest, args.strict_distribution))
        if manifest["release_status"] != "released":
            warnings.append("Release candidate is not taggable until Kaggle checkpoint URLs are frozen and strict verification passes")
    for message in warnings:
        print(f"WARNING: {message}")
    for message in errors:
        print(f"ERROR: {message}", file=sys.stderr)
    if args.report:
        write_report(args.report.resolve(), manifest, errors, warnings, passed)
    if errors:
        raise SystemExit(1)
    print(f"PASS: {passed}/{len(manifest['artifacts'])} artifacts verified")


if __name__ == "__main__":
    main()