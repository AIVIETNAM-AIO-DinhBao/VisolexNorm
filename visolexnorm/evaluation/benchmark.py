"""Post-hoc A/B/C benchmark on the previously observed ViLexNorm Test."""

from __future__ import annotations

import json
import random
import subprocess
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from visolexnorm.common.artifacts import canonical_json, sha256_file, sha256_json, sha256_text
from visolexnorm.common.io import read_jsonl, write_jsonl
from visolexnorm.evaluation.errors import categorize
from visolexnorm.evaluation.freeze import inventory, tokenizer_inventory, verify_manifest as verify_phase5_manifest
from visolexnorm.evaluation.scoring import validate_prediction_rows


BENCHMARK_SCOPE = "posthoc_previously_observed_vilexnorm_test"
MODELS = ("model_a", "model_b", "model_c")


def git_revision(root: Path) -> str | None:
    """Return the current source revision without making Git a runtime dependency."""
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def phase5_paths(args: Namespace) -> dict[str, Path]:
    """Return the inputs required to verify the immutable Phase 5 manifest."""
    return {
        "model_a_checkpoint": args.model_a_checkpoint,
        "model_b_checkpoint": args.model_b_checkpoint,
        "test": args.test,
        "generation_config": args.generation_config,
        "metric_code": args.metric_code,
        "phase3_manifest": args.phase3_manifest,
        "phase4_exit_report": args.phase4_exit_report,
    }


def _load_schema(path: Path) -> Draft202012Validator:
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


def _assert_posthoc_config(config: dict[str, Any]) -> None:
    if config.get("phase") != 9 or config.get("benchmark_type") != "posthoc_abc_vilexnorm_test":
        raise ValueError("Post-hoc benchmark config is invalid")
    if config.get("test_previously_observed") is not True:
        raise ValueError("Post-hoc benchmark must disclose the observed Test")
    if config.get("promotion_eligible") is not False:
        raise ValueError("Post-hoc benchmark must not be promotion eligible")
    if int(config.get("bootstrap_samples", 0)) < 1:
        raise ValueError("bootstrap_samples must be positive")
    if not isinstance(config.get("benchmark_code_path"), str):
        raise ValueError("benchmark_code_path is required")


def _assert_phase5_metrics(metrics: dict[str, Any], predictions: dict[str, Path]) -> None:
    models = metrics.get("models", {})
    if set(models) != {"model_a", "model_b"}:
        raise ValueError("Phase 5 metrics must contain exactly Model A and Model B")
    for model, path in predictions.items():
        if models[model].get("prediction_sha256") != sha256_file(path):
            raise ValueError(f"Phase 5 {model} prediction hash changed")


def _verify_model_c_artifacts(checkpoint: Path, artifact_manifest_path: Path, exit_report_path: Path) -> None:
    artifact_manifest = json.loads(artifact_manifest_path.read_text(encoding="utf-8"))
    exit_report = json.loads(exit_report_path.read_text(encoding="utf-8"))
    if artifact_manifest.get("phase") != 8 or artifact_manifest.get("model") != "model_c":
        raise ValueError("Model C artifact manifest is invalid")
    if exit_report.get("promotion_status") != "blocked_pending_independent_frozen_holdout":
        raise ValueError("Model C exit report has an invalid promotion status")
    if exit_report.get("test_inputs_loaded") is not False:
        raise ValueError("Model C exit report lost its Dev-only guarantee")
    expected = {
        item["path"].removeprefix("checkpoints/model_c/"): {
            "path": item["path"].removeprefix("checkpoints/model_c/"),
            "bytes": item["bytes"],
            "sha256": item["sha256"],
        }
        for item in artifact_manifest.get("artifacts", [])
        if item.get("path", "").startswith("checkpoints/model_c/")
    }
    actual = inventory(checkpoint)
    actual_files = {item["path"]: item for item in actual.get("files", [])}
    if expected != actual_files:
        raise ValueError("Model C checkpoint differs from its Phase 8 artifact manifest")
    if exit_report.get("provenance", {}).get("model_c_checkpoint_inventory_sha256") != sha256_text(
        canonical_json([item for item in artifact_manifest["artifacts"] if item["path"].startswith("checkpoints/model_c/")])
    ):
        raise ValueError("Model C exit report inventory provenance changed")


def build_manifest(args: Namespace) -> dict[str, Any]:
    """Freeze inputs for one non-promotional post-hoc Model C inference run."""
    config = json.loads(args.config.read_text(encoding="utf-8"))
    _assert_posthoc_config(config)
    phase5_manifest = json.loads(args.phase5_manifest.read_text(encoding="utf-8"))
    verify_phase5_manifest(phase5_manifest, phase5_paths(args))
    if int(config["expected_test_count"]) != phase5_manifest.get("expected_test_count"):
        raise ValueError("Post-hoc expected Test count differs from Phase 5")

    model_c_artifact = args.model_c_artifact_manifest
    model_c_exit = args.model_c_exit_report
    _verify_model_c_artifacts(args.model_c_checkpoint, model_c_artifact, model_c_exit)
    phase5_metrics = json.loads(args.phase5_metrics.read_text(encoding="utf-8"))
    ab_predictions = {"model_a": args.model_a_prediction, "model_b": args.model_b_prediction}
    _assert_phase5_metrics(phase5_metrics, ab_predictions)

    test_rows = read_jsonl(args.test)
    test_ids = [row["id"] for row in test_rows]
    schema = _load_schema(args.schema)
    generation_hash = sha256_json(json.loads(args.generation_config.read_text(encoding="utf-8")))
    for model, path in ab_predictions.items():
        rows = read_jsonl(path)
        checkpoint_hash = phase5_manifest["inputs"][f"{model}_checkpoint"]["inventory"]["sha256"]
        validate_prediction_rows(
            rows,
            test_rows,
            model=model,
            checkpoint_checksum=checkpoint_hash,
            generation_config_hash=generation_hash,
            validator=schema,
        )

    tokenizer_c = tokenizer_inventory(args.model_c_checkpoint)
    if tokenizer_c != phase5_manifest.get("tokenizer_contract"):
        raise ValueError("Model C tokenizer does not match the Phase 5 tokenizer contract")
    benchmark_code = Path(config["benchmark_code_path"])
    inputs = {
        "benchmark_config": inventory(args.config, normalize_text=True),
        "benchmark_code": inventory(benchmark_code, normalize_text=True),
        "phase5_manifest": inventory(args.phase5_manifest),
        "phase5_metrics": inventory(args.phase5_metrics),
        "phase5_model_a_prediction": inventory(args.model_a_prediction),
        "phase5_model_b_prediction": inventory(args.model_b_prediction),
        "model_c_checkpoint": inventory(args.model_c_checkpoint),
        "model_c_artifact_manifest": inventory(model_c_artifact),
        "model_c_exit_report": inventory(model_c_exit),
        "test": inventory(args.test),
        "generation_config": inventory(args.generation_config, normalize_text=True),
        "metric_code": inventory(args.metric_code, normalize_text=True),
        "prediction_schema": inventory(args.schema, normalize_text=True),
    }
    return {
        "schema_version": 1,
        "phase": 9,
        "benchmark_type": config["benchmark_type"],
        "status": "frozen",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_scope": BENCHMARK_SCOPE,
        "test_previously_observed": True,
        "promotion_eligible": False,
        "changes_phase5_selection": False,
        "expected_test_count": len(test_rows),
        "test_order_sha256": sha256_text(canonical_json(test_ids)),
        "generation_config_hash": generation_hash,
        "bootstrap_seed": int(config["bootstrap_seed"]),
        "bootstrap_samples": int(config["bootstrap_samples"]),
        "phase5_selected_model": "model_b",
        "phase5_manifest_sha256": sha256_file(args.phase5_manifest),
        "phase5_model_metrics": phase5_metrics["models"],
        "tokenizer_contract": tokenizer_c,
        "inputs": inputs,
    }


def verify_manifest(manifest: dict[str, Any], args: Namespace) -> None:
    """Verify all inputs before reading Test for post-hoc Model C generation."""
    if manifest.get("phase") != 9 or manifest.get("status") != "frozen":
        raise ValueError("Benchmark manifest is not frozen Phase 9 input")
    if manifest.get("evaluation_scope") != BENCHMARK_SCOPE or manifest.get("promotion_eligible") is not False:
        raise ValueError("Benchmark manifest does not preserve post-hoc restrictions")
    inventory_paths = {
        "benchmark_config": args.config,
        "benchmark_code": Path(json.loads(args.config.read_text(encoding="utf-8"))["benchmark_code_path"]),
        "phase5_manifest": args.phase5_manifest,
        "phase5_metrics": args.phase5_metrics,
        "phase5_model_a_prediction": args.model_a_prediction,
        "phase5_model_b_prediction": args.model_b_prediction,
        "model_c_checkpoint": args.model_c_checkpoint,
        "model_c_artifact_manifest": args.model_c_artifact_manifest,
        "model_c_exit_report": args.model_c_exit_report,
        "test": args.test,
        "generation_config": args.generation_config,
        "metric_code": args.metric_code,
        "prediction_schema": args.schema,
    }
    normalized = {"benchmark_config", "benchmark_code", "generation_config", "metric_code", "prediction_schema"}
    for name, path in inventory_paths.items():
        if inventory(path, normalize_text=name in normalized) != manifest.get("inputs", {}).get(name):
            raise ValueError(f"Post-hoc frozen artifact mismatch: {name}")

    phase5 = json.loads(args.phase5_manifest.read_text(encoding="utf-8"))
    verify_manifest_phase5 = phase5_paths(args)
    verify_phase5_manifest(phase5, verify_manifest_phase5)
    _verify_model_c_artifacts(args.model_c_checkpoint, args.model_c_artifact_manifest, args.model_c_exit_report)
    if tokenizer_inventory(args.model_c_checkpoint) != manifest.get("tokenizer_contract"):
        raise ValueError("Post-hoc tokenizer contract mismatch")
    rows = read_jsonl(args.test)
    if len(rows) != manifest.get("expected_test_count"):
        raise ValueError("Post-hoc Test count changed")
    if sha256_text(canonical_json([row["id"] for row in rows])) != manifest.get("test_order_sha256"):
        raise ValueError("Post-hoc Test order changed")


def generate_model_c_predictions(args: Namespace) -> None:
    """Generate exactly one Model C prediction file after frozen input verification."""
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, set_seed
    except ImportError as error:
        raise SystemExit("Install requirements-kaggle.txt before generation") from error

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    verify_manifest(manifest, args)
    if args.model != "model_c" or args.checkpoint != args.model_c_checkpoint:
        raise ValueError("Post-hoc generation only permits the frozen Model C checkpoint")
    config = json.loads(args.generation_config.read_text(encoding="utf-8"))
    checkpoint_hash = manifest["inputs"]["model_c_checkpoint"]["sha256"]
    generation_hash = manifest["generation_config_hash"]
    set_seed(int(config["seed"]))
    if not torch.cuda.is_available():
        raise RuntimeError("Post-hoc Test generation must run on a Kaggle GPU")

    device = "cuda"
    rows = read_jsonl(args.test)
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.checkpoint).to(device)
    model.eval()
    predictions: list[dict[str, Any]] = []
    for start in range(0, len(rows), int(config["batch_size"])):
        batch = rows[start : start + int(config["batch_size"])]
        encoded = tokenizer(
            [row["input_text"] for row in batch],
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=int(config["max_source_length"]),
        ).to(device)
        with torch.no_grad():
            generated = model.generate(
                **encoded,
                num_beams=int(config["num_beams"]),
                max_new_tokens=int(config["max_new_tokens"]),
                early_stopping=bool(config["early_stopping"]),
            )
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        predictions.extend(
            {
                "id": row["id"],
                "input_text": row["input_text"],
                "target_text": row["target_text"],
                "prediction_text": prediction.strip(),
                "model": "model_c",
                "checkpoint_checksum": checkpoint_hash,
                "generation_config_hash": generation_hash,
            }
            for row, prediction in zip(batch, decoded)
        )
    validator = _load_schema(args.schema)
    validate_prediction_rows(
        predictions,
        rows,
        model="model_c",
        checkpoint_checksum=checkpoint_hash,
        generation_config_hash=generation_hash,
        validator=validator,
    )
    write_jsonl(predictions, args.output)
    print(json.dumps({"model": "model_c", "records": len(predictions), "output": str(args.output)}))


def _report_rows(
    rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    *,
    model: str,
    checkpoint_hash: str,
    generation_hash: str,
    validator: Draft202012Validator,
    evaluate_records: Callable[[list[dict[str, Any]]], dict[str, Any]],
) -> dict[str, Any]:
    validate_prediction_rows(
        rows,
        test_rows,
        model=model,
        checkpoint_checksum=checkpoint_hash,
        generation_config_hash=generation_hash,
        validator=validator,
    )
    exact_sentence_match = sum(
        row["prediction_text"] == row["target_text"] for row in rows
    ) / len(rows)
    return {
        **evaluate_records(rows),
        "exact_sentence_match": exact_sentence_match,
        "prediction_sha256": "",
        "checkpoint_checksum": checkpoint_hash,
        "generation_config_hash": generation_hash,
    }


def _bootstrap_delta(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    evaluate_records: Callable[[list[dict[str, Any]]], dict[str, Any]],
    *,
    seed: int,
    samples: int,
    metric: str,
) -> dict[str, float]:
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(samples):
        indices = [rng.randrange(len(left)) for _ in range(len(left))]
        deltas.append(evaluate_records([left[index] for index in indices])[metric] - evaluate_records([right[index] for index in indices])[metric])
    deltas.sort()
    return {
        "mean": sum(deltas) / len(deltas),
        "ci95_low": deltas[int(0.025 * (len(deltas) - 1))],
        "ci95_high": deltas[int(0.975 * (len(deltas) - 1))],
    }


def _metrics_from_counts(counts: dict[str, int]) -> dict[str, float]:
    precision = counts["correct_edits"] / counts["predicted_edits"] if counts["predicted_edits"] else 0.0
    recall = counts["correct_edits"] / counts["gold_edits"] if counts["gold_edits"] else 0.0
    return {
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "ERR": recall,
    }


def _bootstrap_pairwise_metrics(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    evaluate_records: Callable[[list[dict[str, Any]]], dict[str, Any]],
    *,
    seed: int,
    samples: int,
) -> dict[str, dict[str, float]]:
    """Bootstrap F1/ERR deltas from precomputed single-record edit counts."""
    fields = ("gold_edits", "predicted_edits", "correct_edits")
    left_counts = [evaluate_records([row]) for row in left]
    right_counts = [evaluate_records([row]) for row in right]
    rng = random.Random(seed)
    deltas = {"f1": [], "ERR": []}
    for _ in range(samples):
        indices = [rng.randrange(len(left)) for _ in range(len(left))]
        aggregate_left = {field: sum(int(left_counts[index][field]) for index in indices) for field in fields}
        aggregate_right = {field: sum(int(right_counts[index][field]) for index in indices) for field in fields}
        left_metrics = _metrics_from_counts(aggregate_left)
        right_metrics = _metrics_from_counts(aggregate_right)
        for metric in deltas:
            deltas[metric].append(left_metrics[metric] - right_metrics[metric])
    result: dict[str, dict[str, float]] = {}
    for metric, values in deltas.items():
        values.sort()
        result[metric] = {
            "mean": sum(values) / len(values),
            "ci95_low": values[int(0.025 * (len(values) - 1))],
            "ci95_high": values[int(0.975 * (len(values) - 1))],
        }
    return result


def _pairwise(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, int]:
    left_correct = [row["prediction_text"] == row["target_text"] for row in left]
    right_correct = [row["prediction_text"] == row["target_text"] for row in right]
    return {
        "left_correct_right_wrong": sum(a and not b for a, b in zip(left_correct, right_correct)),
        "right_correct_left_wrong": sum(b and not a for a, b in zip(left_correct, right_correct)),
        "both_correct": sum(a and b for a, b in zip(left_correct, right_correct)),
        "both_wrong": sum(not a and not b for a, b in zip(left_correct, right_correct)),
    }


def score_benchmark(args: Namespace, *, evaluate_records: Callable[[list[dict[str, Any]]], dict[str, Any]], metric_reference: dict[str, Any]) -> dict[str, Any]:
    """Score frozen A/B predictions and one Model C prediction without promotion."""
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    verify_manifest(manifest, args)
    validator = _load_schema(args.schema)
    generation_hash = manifest["generation_config_hash"]
    test_rows = read_jsonl(args.test)
    prediction_paths = {"model_a": args.model_a_prediction, "model_b": args.model_b_prediction, "model_c": args.model_c_prediction}
    checkpoint_hashes = {
        "model_a": manifest["phase5_model_metrics"]["model_a"]["checkpoint_checksum"],
        "model_b": manifest["phase5_model_metrics"]["model_b"]["checkpoint_checksum"],
        "model_c": manifest["inputs"]["model_c_checkpoint"]["sha256"],
    }
    rows = {model: read_jsonl(path) for model, path in prediction_paths.items()}
    reports: dict[str, dict[str, Any]] = {}
    for model in MODELS:
        report = _report_rows(rows[model], test_rows, model=model, checkpoint_hash=checkpoint_hashes[model], generation_hash=generation_hash, validator=validator, evaluate_records=evaluate_records)
        report["prediction_sha256"] = sha256_file(prediction_paths[model])
        reports[model] = report
    for model in ("model_a", "model_b"):
        historical = manifest["phase5_model_metrics"][model]
        if any(reports[model][key] != historical[key] for key in ("ERR", "precision", "recall", "f1", "prediction_sha256", "checkpoint_checksum")):
            raise ValueError(f"Post-hoc {model} replay differs from frozen Phase 5 metrics")

    deltas: dict[str, Any] = {}
    for other in ("model_a", "model_b"):
        key = f"model_c_minus_{other}"
        deltas[key] = {
            "f1": reports["model_c"]["f1"] - reports[other]["f1"],
            "ERR": reports["model_c"]["ERR"] - reports[other]["ERR"],
            "exact_sentence_match": sum(row["prediction_text"] == row["target_text"] for row in rows["model_c"]) / len(rows["model_c"]) - sum(row["prediction_text"] == row["target_text"] for row in rows[other]) / len(rows[other]),
            "paired_exact": _pairwise(rows["model_c"], rows[other]),
            "bootstrap": _bootstrap_pairwise_metrics(
                rows["model_c"],
                rows[other],
                evaluate_records,
                seed=manifest["bootstrap_seed"],
                samples=manifest["bootstrap_samples"],
            ),
        }

    descriptive_leader = max(MODELS, key=lambda model: (reports[model]["f1"], reports[model]["ERR"], model == "model_a"))
    payload = {
        "schema_version": 1,
        "phase": 9,
        "evaluation_scope": BENCHMARK_SCOPE,
        "test_previously_observed": True,
        "promotion_eligible": False,
        "changes_phase5_selection": False,
        "phase5_selected_model": "model_b",
        "descriptive_leader": descriptive_leader,
        "benchmark_manifest_sha256": sha256_file(args.manifest),
        "metric_code_inventory": inventory(args.metric_code, normalize_text=True),
        "metric_reference": metric_reference,
        "source_revision": git_revision(Path(".")),
        "models": reports,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "pairwise_deltas.json").write_text(json.dumps({"schema_version": 1, "phase": 9, "evaluation_scope": BENCHMARK_SCOPE, "test_previously_observed": True, "promotion_eligible": False, "deltas": deltas}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    comparison = render_comparison(reports, descriptive_leader, manifest)
    (args.output_dir / "comparison.md").write_text(comparison, encoding="utf-8", newline="\n")
    report = {
        "schema_version": 1,
        "phase": 9,
        "evaluation_scope": BENCHMARK_SCOPE,
        "test_previously_observed": True,
        "promotion_eligible": False,
        "changes_phase5_selection": False,
        "phase5_selected_model": "model_b",
        "descriptive_leader": descriptive_leader,
        "disclaimer": "Post-hoc benchmark on previously observed ViLexNorm Test; not eligible for model promotion.",
    }
    (args.output_dir / "benchmark_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"metrics": payload, "deltas": deltas, "report": report}


def render_comparison(reports: dict[str, dict[str, Any]], leader: str, manifest: dict[str, Any]) -> str:
    lines = [
        "# Post-hoc A/B/C ViLexNorm Test benchmark",
        "",
        "> **Warning:** This benchmark uses the previously observed Phase 5 ViLexNorm Test.",
        "> It is descriptive only and cannot promote Model C or change Model B's Phase 5 selection.",
        "",
        "| Model | Samples | ERR | Precision | Recall | F1 | Exact sentence match |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model in MODELS:
        report = reports[model]
        exact = report.get("exact_sentence_match", "n/a")
        exact_text = f"{exact:.6f}" if isinstance(exact, float) else exact
        lines.append(f"| {model} | {report['sample_count']} | {report['ERR']:.6f} | {report['precision']:.6f} | {report['recall']:.6f} | {report['f1']:.6f} | {exact_text} |")
    lines.extend(["", f"**Descriptive leader:** `{leader}`. This is not an application-model selection.", "", f"Benchmark manifest: `{manifest['phase5_manifest_sha256']}` references the immutable Phase 5 history.", ""])
    return "\n".join(lines)


def write_pairwise_error_analysis(args: Namespace) -> int:
    """Write deterministic A/B/C row-level comparison without altering Phase 5 errors."""
    rows = {model: read_jsonl(getattr(args, f"{model}_prediction")) for model in MODELS}
    count = len(rows["model_a"])
    if any(len(rows[model]) != count for model in MODELS):
        raise ValueError("Post-hoc prediction counts differ")
    result: list[dict[str, Any]] = []
    for values in zip(rows["model_a"], rows["model_b"], rows["model_c"]):
        a, b, c = values
        if any(row[field] != a[field] for row in (b, c) for field in ("id", "input_text", "target_text")):
            raise ValueError(f"Post-hoc predictions are not aligned at {a.get('id')!r}")
        categories = {model: categorize(row["input_text"], row["target_text"], row["prediction_text"]) for model, row in zip(MODELS, values)}
        result.append({
            "id": a["id"], "input_text": a["input_text"], "target_text": a["target_text"],
            "model_a_prediction": a["prediction_text"], "model_b_prediction": b["prediction_text"], "model_c_prediction": c["prediction_text"],
            "model_a_category": categories["model_a"], "model_b_category": categories["model_b"], "model_c_category": categories["model_c"],
            "model_c_vs_a": "model_c" if categories["model_c"] == "correct" and categories["model_a"] != "correct" else "model_a" if categories["model_a"] == "correct" and categories["model_c"] != "correct" else "tie",
            "model_c_vs_b": "model_c" if categories["model_c"] == "correct" and categories["model_b"] != "correct" else "model_b" if categories["model_b"] == "correct" and categories["model_c"] != "correct" else "tie",
        })
    write_jsonl(result, args.output)
    return len(result)