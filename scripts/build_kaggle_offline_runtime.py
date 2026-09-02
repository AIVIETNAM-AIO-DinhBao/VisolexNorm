"""Build an upload-ready offline Kaggle source bundle and Linux wheelhouse.

Run this command from a clean, committed checkout with Internet access. The
resulting directory is uploaded as an unpacked private Kaggle Dataset. PyTorch,
CUDA, NVIDIA, and Triton wheels are intentionally forbidden because the Kaggle
GPU image supplies the driver-compatible PyTorch runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


FORBIDDEN_WHEEL_PREFIXES = ("torch-", "nvidia_", "triton-")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments], text=True, stderr=subprocess.STDOUT
    ).strip()


def require_clean_commit(root: Path) -> str:
    try:
        revision = git_output(root, "rev-parse", "HEAD")
        dirty = git_output(root, "status", "--porcelain")
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("Offline runtime build requires a Git checkout") from error
    if dirty:
        raise RuntimeError("Commit all source changes before building the offline runtime")
    return revision


def build_runtime(
    root: Path,
    output: Path,
    requirements: Path,
    *,
    python_version: str,
    platform: str,
) -> Path:
    """Create an unpacked Kaggle Dataset directory and integrity manifest."""
    revision = require_clean_commit(root)
    if output.exists():
        shutil.rmtree(output)
    source_dir, wheelhouse = output / "source", output / "wheelhouse"
    source_dir.mkdir(parents=True)
    wheelhouse.mkdir(parents=True)
    bundle = source_dir / "visolexnorm.bundle"
    subprocess.run(
        ["git", "-C", str(root), "bundle", "create", str(bundle), "HEAD", "main"],
        check=True,
    )
    locked_requirements = output / "requirements-kaggle-offline.txt"
    shutil.copy2(requirements, locked_requirements)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--dest",
            str(wheelhouse),
            "--requirement",
            str(requirements),
            "--platform",
            platform,
            "--python-version",
            python_version.replace(".", ""),
            "--implementation",
            "cp",
            "--abi",
            "cp" + python_version.replace(".", ""),
            "--only-binary=:all:",
            "--disable-pip-version-check",
        ],
        check=True,
    )
    wheels = sorted(wheelhouse.glob("*.whl"))
    if not wheels:
        raise RuntimeError("pip download produced an empty wheelhouse")
    forbidden = [path.name for path in wheels if path.name.lower().startswith(FORBIDDEN_WHEEL_PREFIXES)]
    if forbidden:
        raise RuntimeError(
            "Offline runtime must use Kaggle's CUDA PyTorch; forbidden wheels found: "
            + ", ".join(forbidden)
        )
    files = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        files.append(
            {
                "path": path.relative_to(output).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "schema_version": 1,
        "runtime": "visolexnorm_controlled_kaggle_offline",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": revision,
        "target": {
            "os": "linux",
            "architecture": "x86_64",
            "python": python_version,
            "platform_tag": platform,
            "torch_source": "preinstalled_kaggle_gpu_image",
        },
        "requirements_path": locked_requirements.relative_to(output).as_posix(),
        "files": files,
        "forbidden_wheel_prefixes": list(FORBIDDEN_WHEEL_PREFIXES),
    }
    manifest_path = output / "offline-runtime-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path(".tmp/kaggle_offline_runtime"))
    parser.add_argument(
        "--requirements", type=Path, default=Path("requirements-kaggle-offline.txt")
    )
    parser.add_argument("--python-version", default="3.12")
    parser.add_argument("--platform", default="manylinux2014_x86_64")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    requirements = args.requirements if args.requirements.is_absolute() else root / args.requirements
    manifest = build_runtime(
        root,
        args.output.resolve(),
        requirements.resolve(),
        python_version=args.python_version,
        platform=args.platform,
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "output": str(manifest.parent),
                "source_commit": payload["source_commit"],
                "files": len(payload["files"]),
                "bytes": sum(item["bytes"] for item in payload["files"]),
                "upload_mode": "unpacked_private_kaggle_dataset",
            }
        )
    )


if __name__ == "__main__":
    main()