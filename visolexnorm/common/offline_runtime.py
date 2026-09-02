"""Verify and install the checksum-bound offline Kaggle wheelhouse."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_runtime(runtime_root: Path) -> dict[str, Any]:
    """Verify target ABI, every listed file, and forbidden CUDA wheels."""
    manifest_path = runtime_root / "offline-runtime-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = manifest.get("target", {})
    actual_python = f"{sys.version_info.major}.{sys.version_info.minor}"
    if target.get("os") != "linux" or target.get("architecture") != "x86_64":
        raise RuntimeError("Offline runtime does not target Kaggle Linux x86_64")
    if target.get("python") != actual_python:
        raise RuntimeError(
            f"Offline runtime requires Python {target.get('python')}, got {actual_python}"
        )
    files = manifest.get("files", [])
    if not files:
        raise RuntimeError("Offline runtime manifest has no files")
    for item in files:
        path = runtime_root / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256(path) != item["sha256"]
        ):
            raise RuntimeError(f"Offline runtime artifact mismatch: {item['path']}")
    wheel_names = [path.name.lower() for path in (runtime_root / "wheelhouse").glob("*.whl")]
    forbidden = [
        name
        for name in wheel_names
        if name.startswith(tuple(manifest.get("forbidden_wheel_prefixes", [])))
    ]
    if forbidden:
        raise RuntimeError("Offline runtime contains forbidden CUDA/PyTorch wheels")
    return manifest


def _activate_target(target: Path) -> None:
    value = str(target)
    if value not in sys.path:
        sys.path.insert(0, value)
    current = os.environ.get("PYTHONPATH", "")
    entries = [entry for entry in current.split(os.pathsep) if entry]
    if value not in entries:
        os.environ["PYTHONPATH"] = os.pathsep.join([value, *entries])


def install_runtime(runtime_root: Path, target: Path) -> dict[str, Any]:
    """Install only from the verified wheelhouse into an isolated target."""
    manifest = verify_runtime(runtime_root)
    manifest_sha256 = _sha256(runtime_root / "offline-runtime-manifest.json")
    marker = target / ".visolexnorm-offline-runtime.json"
    if marker.is_file():
        installed = json.loads(marker.read_text(encoding="utf-8"))
        if installed.get("manifest_sha256") == manifest_sha256:
            _activate_target(target)
            return manifest
    if target.exists():
        shutil.rmtree(target)
    environment = os.environ.copy()
    environment.update(
        {
            "PIP_NO_INDEX": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-cache-dir",
            "--find-links",
            str(runtime_root / "wheelhouse"),
            "--target",
            str(target),
            "--upgrade",
            "--requirement",
            str(runtime_root / manifest["requirements_path"]),
        ],
        check=True,
        env=environment,
    )
    marker.write_text(
        json.dumps(
            {
                "manifest_sha256": manifest_sha256,
                "source_commit": manifest["source_commit"],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _activate_target(target)
    return manifest