"""Build deterministic compact report assets from frozen evaluation outputs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


SOURCE = Path("outputs/evaluation_abc_posthoc/pairwise_error_analysis.jsonl")
OUTPUT = Path("report/data/error_analysis_summary.json")
MODELS = ("model_a", "model_b", "model_c")
EXAMPLE_IDS = (
    "vilexnorm_test_000003",
    "vilexnorm_test_000054",
    "vilexnorm_test_000654",
    "vilexnorm_test_000021",
    "vilexnorm_test_000033",
)


def main() -> None:
    rows = [json.loads(line) for line in SOURCE.open(encoding="utf-8")]
    by_id = {row["id"]: row for row in rows}
    payload = {
        "schema_version": 1,
        "source": SOURCE.as_posix(),
        "sample_count": len(rows),
        "category_counts": {
            model: dict(sorted(Counter(row[f"{model}_category"] for row in rows).items()))
            for model in MODELS
        },
        "pairwise_exact": {
            "model_c_vs_model_a": dict(sorted(Counter(row["model_c_vs_a"] for row in rows).items())),
            "model_c_vs_model_b": dict(sorted(Counter(row["model_c_vs_b"] for row in rows).items())),
        },
        "selected_examples": [by_id[identifier] for identifier in EXAMPLE_IDS],
        "note": (
            "Primary categories are deterministic heuristics; zero over-normalization "
            "categories do not imply zero false-positive edits."
        ),
    }
    if any(sum(payload["category_counts"][model].values()) != len(rows) for model in MODELS):
        raise ValueError("Error categories do not cover every record exactly once")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()