"""Export one-way Dev/Test input fingerprints for downstream leakage checks."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from visolexnorm.common.artifacts import sha256_text
from visolexnorm.common.io import read_jsonl
from visolexnorm.common.progress import log_event


def main() -> None:
    parser = argparse.ArgumentParser(description="Export sorted protected input SHA-256 fingerprints.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/vilexnorm_protected_input_hashes.txt"))
    parser.add_argument("--quiet", action="store_true", help="Suppress operational progress logs")
    args = parser.parse_args()
    hashes = set()
    log_event("START", f"Protected-hash export: data_dir={args.data_dir}", quiet=args.quiet)
    for split in ("dev", "test"):
        path = args.data_dir / f"vilexnorm_{split}.jsonl"
        if not path.is_file():
            raise FileNotFoundError(path)
        rows = read_jsonl(path)
        hashes.update(sha256_text(row["input_text"]) for row in rows)
        log_event("PROGRESS", f"Protected-hash export: split={split} records={len(rows)} unique_hashes={len(hashes)}", quiet=args.quiet)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(sorted(hashes)) + "\n", encoding="utf-8")
    log_event("DONE", f"Protected-hash export: fingerprints={len(hashes)} output={args.output}", quiet=args.quiet)


if __name__ == "__main__":
    main()