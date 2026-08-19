"""Export one-way Dev/Test input fingerprints for downstream leakage checks."""

from __future__ import annotations

import argparse
from pathlib import Path

from data_utils import read_jsonl
from phase3_utils import sha256_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Export sorted protected input SHA-256 fingerprints.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/vilexnorm_protected_input_hashes.txt"))
    args = parser.parse_args()
    hashes = set()
    for split in ("dev", "test"):
        path = args.data_dir / f"vilexnorm_{split}.jsonl"
        if not path.is_file():
            raise FileNotFoundError(path)
        hashes.update(sha256_text(row["input_text"]) for row in read_jsonl(path))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(sorted(hashes)) + "\n", encoding="utf-8")
    print(f"Saved {len(hashes)} protected fingerprints -> {args.output}")


if __name__ == "__main__":
    main()