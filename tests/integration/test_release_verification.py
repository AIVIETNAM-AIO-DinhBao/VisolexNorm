"""Tests for release manifest verification without large production artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_release


ROOT = Path(__file__).parents[2]


def write_file(path: Path, content: str = "release artifact") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def artifact(path: Path, root: Path, *, phase: int = 7, location: str = "repository", url: str | None = None) -> dict:
    kind, size_bytes, digest = verify_release.inventory(path)
    return {
        "path": path.relative_to(root).as_posix(),
        "phase": phase,
        "artifact_type": "docs",
        "kind": kind,
        "location": location,
        "sha256": digest,
        "size_bytes": size_bytes,
        "required": True,
        "distribution_url": url,
        "contains_sensitive_data": False,
    }


def manifest(items: list[dict], *, status: str = "candidate_pending_checkpoint_distribution") -> dict:
    return {
        "project": "ViSoLexNorm",
        "version": "1.0.0",
        "created_at": "2026-08-31T00:00:00+00:00",
        "source_revision": "0" * 40,
        "release_status": status,
        "artifacts": items,
    }


def test_inventory_hashes_files_and_directories(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    write_file(file_path, "one")
    directory = tmp_path / "checkpoint"
    write_file(directory / "a.txt", "a")
    write_file(directory / "nested" / "b.txt", "b")

    assert verify_release.inventory(file_path)[0] == "file"
    first = verify_release.inventory(directory)
    assert first[0] == "directory"
    assert first == verify_release.inventory(directory)


def test_validate_manifest_rejects_path_traversal_and_duplicate(tmp_path: Path) -> None:
    file_path = tmp_path / "release.txt"
    write_file(file_path)
    item = artifact(file_path, tmp_path)
    unsafe = dict(item, path="../secret.txt")

    errors = verify_release.validate_manifest(manifest([item, unsafe]))

    assert any("safe relative path" in error for error in errors)
    assert not verify_release.validate_manifest(manifest([item]))


def test_verify_artifacts_detects_checksum_mismatch(tmp_path: Path) -> None:
    file_path = tmp_path / "release.txt"
    write_file(file_path, "original")
    release = manifest([artifact(file_path, tmp_path)])
    write_file(file_path, "tampered")

    errors, warnings, passed = verify_release.verify_artifacts(release, tmp_path)

    assert warnings == []
    assert passed == 0
    assert len(errors) == 1
    assert "sha256 mismatch" in errors[0]


def test_distribution_gate_requires_fixed_kaggle_version_url(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint"
    write_file(checkpoint / "model.txt")
    item = artifact(checkpoint, tmp_path, phase=10, location="external")
    item["artifact_type"] = "checkpoint"
    candidate = manifest([item])

    assert verify_release.distribution_errors(candidate, strict_distribution=False) == []
    assert verify_release.distribution_errors(candidate, strict_distribution=True)

    item["distribution_url"] = "https://www.kaggle.com/datasets/dinhbaobao/visolexnorm-app-checkpoints-v1/versions/1"
    released = manifest([item], status="released")
    assert verify_release.distribution_errors(released, strict_distribution=True) == []


def test_scan_secrets_detects_tracked_env_and_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_file(tmp_path / ".env", "GEMINI_API_KEYS=" + "AIza" + "123456789012345678901234567890\n")
    monkeypatch.setattr(verify_release, "tracked_files", lambda root: [root / ".env"])

    errors = verify_release.scan_secrets(tmp_path)

    assert any(".env" in error for error in errors)
    assert any("google_api_key" in error for error in errors)


def test_scan_secrets_includes_declared_untracked_release_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = tmp_path / "release-note.md"
    write_file(candidate, "AIza" + "123456789012345678901234567890")
    monkeypatch.setattr(verify_release, "tracked_files", lambda root: [])

    errors = verify_release.scan_secrets(tmp_path, [candidate])

    assert any("google_api_key" in error for error in errors)


def test_write_report_records_exit_code(tmp_path: Path) -> None:
    release = manifest([])
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(release), encoding="utf-8")
    report_path = tmp_path / "verification-report.json"

    verify_release.write_report(report_path, release, ["failure"], ["warning"], 2)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["exit_code"] == 1
    assert report["artifacts_passed"] == 2


def test_release_candidate_manifest_matches_current_phase7_policy() -> None:
    release = json.loads((ROOT / "release/manifest.json").read_text(encoding="utf-8"))

    assert verify_release.validate_manifest(release) == []
    assert release["release_status"] == "candidate_pending_checkpoint_distribution"
    checkpoint_items = [item for item in release["artifacts"] if item["artifact_type"] == "checkpoint"]
    assert {item["path"] for item in checkpoint_items} == {"checkpoints/model_c", "checkpoints/model_b"}
    assert all(item["distribution_url"] is None for item in checkpoint_items)
    assert verify_release.distribution_errors(release, strict_distribution=False) == []
    assert verify_release.distribution_errors(release, strict_distribution=True)