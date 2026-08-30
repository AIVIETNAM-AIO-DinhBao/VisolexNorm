"""Create deterministic per-example Phase 5 error analysis and audit samples.

Category precedence: correct; over-normalization; missed; one-to-many;
many-to-one; suspected-weak-label-noise; wrong. Noise requires explicit,
frozen supplied Test IDs; without evidence, uncertain examples remain wrong.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from visolexnorm.common.io import read_jsonl, write_jsonl


def categorize(input_text: str, target_text: str, prediction_text: str, *, weak_label_noise: bool = False) -> str:
    if prediction_text == target_text:
        return "correct"
    if input_text == target_text:
        return "over-normalization"
    if prediction_text == input_text:
        return "missed"
    if len(input_text.split()) < len(target_text.split()):
        return "one-to-many"
    if len(input_text.split()) > len(target_text.split()):
        return "many-to-one"
    if weak_label_noise:
        return "suspected-weak-label-noise"
    return "wrong"


def analyze_rows(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]], noise_ids: set[str]) -> list[dict[str, Any]]:
    if len(rows_a) != len(rows_b):
        raise ValueError("Model A/B prediction count differs")
    result: list[dict[str, Any]] = []
    for a, b in zip(rows_a, rows_b):
        if any(a[field] != b[field] for field in ("id", "input_text", "target_text")):
            raise ValueError(f"Prediction pair is not aligned at ID {a.get('id')!r}")
        category_a = categorize(a["input_text"], a["target_text"], a["prediction_text"], weak_label_noise=a["id"] in noise_ids)
        category_b = categorize(b["input_text"], b["target_text"], b["prediction_text"], weak_label_noise=b["id"] in noise_ids)
        better = "model_a" if category_a == "correct" and category_b != "correct" else "model_b" if category_b == "correct" and category_a != "correct" else "tie"
        result.append({"id": a["id"], "input_text": a["input_text"], "target_text": a["target_text"], "model_a_prediction": a["prediction_text"], "model_b_prediction": b["prediction_text"], "model_a_category": category_a, "model_b_category": category_b, "better_model": better, "weak_label_evidence": a["id"] in noise_ids})
    return result


def write_error_analysis(args: Any) -> dict[str, int]:
    if args.audit_limit < 1:
        raise ValueError("audit-limit must be positive")
    noise_ids = set()
    if args.weak_label_evidence:
        value = json.loads(args.weak_label_evidence.read_text(encoding="utf-8"))
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("Weak-label evidence must be a JSON list of Test IDs")
        noise_ids = set(value)
    records = analyze_rows(read_jsonl(args.model_a_prediction), read_jsonl(args.model_b_prediction), noise_ids)
    write_jsonl(records, args.output)
    audits = {model: [record for record in records if record[f"{model}_category"] != "correct"][:args.audit_limit] for model in ("model_a", "model_b")}
    args.audit_output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_output.write_text(json.dumps(audits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"records": len(records), "model_a_audit_errors": len(audits["model_a"]), "model_b_audit_errors": len(audits["model_b"])}
