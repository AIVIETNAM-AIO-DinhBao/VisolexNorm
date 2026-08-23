"""Read a Phase 5 prediction JSONL and calculate the frozen metric protocol.

This narrow command is intentionally limited to one model.  Phase 5 Chặng 3
will extend it with cross-model comparison, artifact exports and model choice.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .data_utils import read_jsonl
    from .evaluation_metrics import OFFICIAL_REFERENCE, evaluate_records
except ImportError:
    from data_utils import read_jsonl
    from evaluation_metrics import OFFICIAL_REFERENCE, evaluate_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction", type=Path, required=True)
    args = parser.parse_args()
    rows = read_jsonl(args.prediction)
    print(json.dumps({"metric_reference": OFFICIAL_REFERENCE, "metrics": evaluate_records(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()