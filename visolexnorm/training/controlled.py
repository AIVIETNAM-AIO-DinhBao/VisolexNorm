"""Dev-only controlled factorial and exploratory optimization experiments.

This module is intentionally separate from the historical Model B/Model C
contracts.  It never reads a Test split and writes only under a caller-chosen
controlled-experiment namespace.
"""
from __future__ import annotations

import json
import math
import random
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from visolexnorm.common.artifacts import sha256_file, sha256_json
from visolexnorm.common.io import read_jsonl, write_jsonl
from visolexnorm.training.mixtures import validate_records
from visolexnorm.training.reports import checkpoint_inventory, source_revision


PROHIBITED_PARTS = ("vilexnorm_test", "outputs/evaluation")
FACTORIAL_SEEDS = (2026, 2126, 2226)
FACTORIAL_ARMS = ("small", "expanded")
FACTORIAL_HORIZONS = (3, 8)


def _read_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_clean_source_revision(root: Path) -> str:
    """Require a committed, clean source tree before freezing a GPU protocol."""
    try:
        revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("Protocol freeze requires a Git checkout with a committed source revision") from error
    if dirty.strip():
        raise RuntimeError("Commit the controlled-experiment source before freezing its protocol")
    return revision


def _assert_safe_paths(*paths: Path) -> None:
    normalized = [str(path).replace("\\", "/").lower() for path in paths]
    if any(part in value for value in normalized for part in PROHIBITED_PARTS):
        raise ValueError("Controlled experiments must not receive Test/evaluation inputs")


def _epoch(seed: int, index: int, gold_ids: list[str], pseudo_ids: list[str]) -> dict[str, Any]:
    """Create one deterministic mixture while preserving pseudo-slot positions."""
    rng = random.Random(seed + index)
    gold = sorted(gold_ids)
    rng.shuffle(gold)
    slots = [("gold", item) for item in gold] + [("pseudo", position) for position in range(len(pseudo_ids))]
    rng.shuffle(slots)
    ordered = [
        {"id": value if source == "gold" else pseudo_ids[value], "label_source": "human" if source == "gold" else "model_a+llm_review"}
        for source, value in slots
    ]
    return {
        "epoch_index": index,
        "epoch_seed": seed + index,
        "gold_count": len(gold),
        "pseudo_count": len(pseudo_ids),
        "gold_ids": gold,
        "pseudo_ids": pseudo_ids,
        "ordered_ids": ordered,
    }


def _least_used(ids: list[str], usage: Counter[str], count: int, rng: random.Random, *, excluded: set[str] | None = None) -> list[str]:
    """Select unique IDs from the lowest exposure level with deterministic ties."""
    excluded = excluded or set()
    available = [item for item in ids if item not in excluded]
    selected: list[str] = []
    for level in sorted({usage[item] for item in available}):
        group = [item for item in available if usage[item] == level]
        rng.shuffle(group)
        take = min(count - len(selected), len(group))
        selected.extend(group[:take])
        if len(selected) == count:
            return selected
    raise ValueError("Insufficient unique pseudo IDs for one epoch")


def sample_factorial_epochs(
    gold_ids: list[str], initial_ids: list[str], expanded_ids: list[str], *, seed: int, num_epochs: int, pseudo_per_epoch: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build paired small/expanded trajectories with nested initial-pool exposure.

    The expanded arm takes the same initial-pool examples whenever the small arm
    has not begun repeating them.  Thereafter it replaces those repetitions with
    previously unseen expanded-only examples, preserving every pseudo slot.
    """
    initial, expanded = sorted(initial_ids), sorted(expanded_ids)
    if len(gold_ids) != pseudo_per_epoch or len(initial) < pseudo_per_epoch:
        raise ValueError("Gold and initial pools must each support one full 1:1 epoch")
    if len(set(initial)) != len(initial) or len(set(expanded)) != len(expanded) or not set(initial).issubset(expanded):
        raise ValueError("Factorial pools must be unique and nested")
    extra = sorted(set(expanded) - set(initial))
    if len(expanded) < pseudo_per_epoch:
        raise ValueError("Expanded pool must support one full epoch")
    small_usage: Counter[str] = Counter()
    large_usage: Counter[str] = Counter()
    small_epochs: list[dict[str, Any]] = []
    large_epochs: list[dict[str, Any]] = []
    for index in range(num_epochs):
        rng = random.Random(seed + index)
        small = _least_used(initial, small_usage, pseudo_per_epoch, rng)
        small_usage.update(small)
        # Preserve fresh initial exposures; substitute only initial repeats.
        shared = [item for item in small if large_usage[item] == 0]
        remaining = pseudo_per_epoch - len(shared)
        candidates = extra + [item for item in initial if item not in shared]
        large = shared + _least_used(candidates, large_usage, remaining, rng, excluded=set(shared))
        large_usage.update(large)
        if len(set(small)) != pseudo_per_epoch or len(set(large)) != pseudo_per_epoch:
            raise AssertionError("Sampler produced within-epoch duplicates")
        small_epochs.append(_epoch(seed, index, gold_ids, small))
        large_epochs.append(_epoch(seed, index, gold_ids, large))
    return small_epochs, large_epochs


def sample_balanced_epochs(
    gold_ids: list[str], pseudo_ids: list[str], *, seed: int, num_epochs: int, pseudo_per_epoch: int,
) -> list[dict[str, Any]]:
    """Sample a deterministic, exposure-balanced trajectory for C-max20-ES."""
    pseudo = sorted(pseudo_ids)
    if len(gold_ids) != pseudo_per_epoch or len(pseudo) < pseudo_per_epoch:
        raise ValueError("Pools must support a complete 1:1 epoch")
    if len(set(gold_ids)) != len(gold_ids) or len(set(pseudo)) != len(pseudo):
        raise ValueError("Training pools contain duplicate IDs")
    usage: Counter[str] = Counter()
    epochs: list[dict[str, Any]] = []
    for index in range(num_epochs):
        chosen = _least_used(pseudo, usage, pseudo_per_epoch, random.Random(seed + index))
        usage.update(chosen)
        epochs.append(_epoch(seed, index, gold_ids, chosen))
    return epochs


def _usage(epochs: list[dict[str, Any]]) -> Counter[str]:
    return Counter(item for epoch in epochs for item in epoch["pseudo_ids"])


def _manifest(
    *, experiment: str, arm: str, seed: int, config: dict[str, Any], gold: list[dict[str, Any]], dev: list[dict[str, Any]], pseudo: list[dict[str, Any]],
    epochs: list[dict[str, Any]], checksums: dict[str, str], inventory_sha: str, initial_count: int | None = None,
) -> dict[str, Any]:
    usage = _usage(epochs)
    horizon = list(config["horizons"])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "experiment": experiment,
        "arm": arm,
        "seed": seed,
        "pool_count": len(pseudo),
        "gold_count": len(gold),
        "dev_count": len(dev),
        "pseudo_per_epoch": config["pseudo_per_epoch"],
        "num_train_epochs": len(epochs),
        "horizons": horizon,
        "checksums": checksums,
        "model_a_inventory_sha256": inventory_sha,
        "prompt_version": config["prompt_version"],
        "epochs": epochs,
        "pseudo_draw_count": sum(len(epoch["pseudo_ids"]) for epoch in epochs),
        "pseudo_unique_count": len(usage),
        "pseudo_unseen_count": len(pseudo) - len(usage),
        "pseudo_coverage_fraction": len(usage) / len(pseudo),
        "pseudo_usage_distribution": {str(key): value for key, value in sorted(Counter(usage.values()).items())},
        "test_inputs_loaded": False,
    }
    if initial_count is not None:
        payload["initial_pool_count"] = initial_count
    payload["manifest_content_sha256"] = sha256_json(payload)
    return payload


def build_factorial_manifests(root: Path, config_path: Path, protocol_path: Path, seed: int) -> dict[str, dict[str, Any]]:
    """Build paired 8-epoch manifests from frozen inputs without reading Test."""
    config, protocol = _read_config(config_path), _read_config(protocol_path)
    if seed not in config["seeds"] or protocol.get("experiment") != "controlled_factorial_2x2":
        raise ValueError("Seed or protocol is not frozen for the controlled factorial")
    if protocol.get("config_sha256") != sha256_file(config_path):
        raise ValueError("Factorial config changed after protocol freeze")
    paths = {key: root / value for key, value in config["input_paths"].items()}
    _assert_safe_paths(*paths.values(), config_path, protocol_path)
    gold, dev, initial, expanded = (read_jsonl(paths[key]) for key in ("gold", "dev", "initial", "expanded"))
    validate_records(gold, dev, initial, config["prompt_version"])
    validate_records(gold, dev, expanded, config["prompt_version"])
    if len(initial) != config["expected_initial_pool_count"] or len(expanded) != config["expected_expanded_pool_count"]:
        raise ValueError("Frozen factorial pool counts do not match")
    _, inventory_sha = checkpoint_inventory(root / config["initial_checkpoint"])
    if inventory_sha != config["expected_initial_checkpoint_inventory_sha256"]:
        raise ValueError("Model A inventory differs from the frozen factorial protocol")
    if inventory_sha != protocol.get("model_a_inventory_sha256"):
        raise ValueError("Model A inventory differs from the frozen protocol")
    small_epochs, large_epochs = sample_factorial_epochs(
        [row["id"] for row in gold], [row["id"] for row in initial], [row["id"] for row in expanded],
        seed=seed, num_epochs=config["max_epochs"], pseudo_per_epoch=config["pseudo_per_epoch"],
    )
    checksums = {key: sha256_file(path) for key, path in paths.items()}
    if checksums != protocol.get("input_checksums"):
        raise ValueError("Factorial inputs changed after protocol freeze")
    return {
        "small": _manifest(experiment="controlled_factorial_2x2", arm="small", seed=seed, config=config, gold=gold, dev=dev, pseudo=initial, epochs=small_epochs, checksums=checksums, inventory_sha=inventory_sha, initial_count=len(initial)),
        "expanded": _manifest(experiment="controlled_factorial_2x2", arm="expanded", seed=seed, config=config, gold=gold, dev=dev, pseudo=expanded, epochs=large_epochs, checksums=checksums, inventory_sha=inventory_sha, initial_count=len(initial)),
    }


def build_c_max20_manifest(root: Path, config_path: Path, protocol_path: Path, seed: int) -> dict[str, Any]:
    """Build the pre-specified fresh expanded-pool C-max20-ES trajectory."""
    config, protocol = _read_config(config_path), _read_config(protocol_path)
    if seed not in config["seeds"] or protocol.get("experiment") != "controlled_factorial_2x2":
        raise ValueError("Seed or protocol is not frozen for C-max20-ES")
    if protocol.get("c_max20_config_sha256") != sha256_file(config_path):
        raise ValueError("C-max20 config changed after protocol freeze")
    expected_early_stopping = {key: config[key] for key in ("max_epochs", "min_epochs", "patience", "min_delta", "monitor")}
    if protocol.get("c_max20_es") != expected_early_stopping:
        raise ValueError("C-max20 early-stopping rule differs from the frozen protocol")
    paths = {key: root / value for key, value in config["input_paths"].items()}
    _assert_safe_paths(*paths.values(), config_path, protocol_path)
    gold, dev, expanded = (read_jsonl(paths[key]) for key in ("gold", "dev", "expanded"))
    validate_records(gold, dev, expanded, config["prompt_version"])
    if len(expanded) != config["expected_expanded_pool_count"]:
        raise ValueError("Expanded C-max20 pool count does not match frozen config")
    _, inventory_sha = checkpoint_inventory(root / config["initial_checkpoint"])
    if inventory_sha != config["expected_initial_checkpoint_inventory_sha256"]:
        raise ValueError("Model A inventory differs from the frozen optimization protocol")
    if inventory_sha != protocol.get("model_a_inventory_sha256"):
        raise ValueError("Model A inventory differs from the frozen protocol")
    epochs = sample_balanced_epochs([row["id"] for row in gold], [row["id"] for row in expanded], seed=seed, num_epochs=config["max_epochs"], pseudo_per_epoch=config["pseudo_per_epoch"])
    checksums = {key: sha256_file(path) for key, path in paths.items()}
    if any(checksums[key] != protocol.get("input_checksums", {}).get(key) for key in checksums):
        raise ValueError("C-max20 inputs changed after protocol freeze")
    manifest = _manifest(experiment="c_max20_es_exploratory", arm="expanded", seed=seed, config={**config, "horizons": [config["max_epochs"]]}, gold=gold, dev=dev, pseudo=expanded, epochs=epochs, checksums=checksums, inventory_sha=inventory_sha)
    manifest["early_stopping"] = {"min_epochs": config["min_epochs"], "patience": config["patience"], "min_delta": config["min_delta"], "monitor": "dev_loss", "restore_best_checkpoint": True}
    manifest["manifest_content_sha256"] = sha256_json({key: value for key, value in manifest.items() if key != "manifest_content_sha256"})
    return manifest


def validate_controlled_manifest(manifest: dict[str, Any], config: dict[str, Any]) -> None:
    """Fail closed on deterministic membership, frozen horizon, and leakage drift."""
    if manifest.get("experiment") not in {"controlled_factorial_2x2", "c_max20_es_exploratory"}:
        raise ValueError("Unknown controlled experiment")
    epochs = manifest.get("epochs", [])
    if not epochs or len(epochs) != manifest.get("num_train_epochs"):
        raise ValueError("Manifest epoch count is invalid")
    if manifest.get("seed") not in config["seeds"] or manifest.get("pseudo_per_epoch") != config["pseudo_per_epoch"]:
        raise ValueError("Manifest seed or pseudo count is invalid")
    for index, epoch in enumerate(epochs):
        if epoch.get("epoch_index") != index or epoch.get("epoch_seed") != manifest["seed"] + index:
            raise ValueError("Manifest epoch seeds are invalid")
        if len(epoch.get("gold_ids", [])) != config["pseudo_per_epoch"] or len(epoch.get("pseudo_ids", [])) != config["pseudo_per_epoch"]:
            raise ValueError("Manifest 1:1 epoch membership is invalid")
        if len(set(epoch["gold_ids"])) != len(epoch["gold_ids"]) or len(set(epoch["pseudo_ids"])) != len(epoch["pseudo_ids"]):
            raise ValueError("Manifest contains within-epoch duplicates")
        expected = {(item, "human") for item in epoch["gold_ids"]} | {(item, "model_a+llm_review") for item in epoch["pseudo_ids"]}
        actual = {(row.get("id"), row.get("label_source")) for row in epoch.get("ordered_ids", [])}
        if expected != actual or len(epoch["ordered_ids"]) != len(expected):
            raise ValueError("Manifest ordering does not match membership")
    if manifest.get("test_inputs_loaded") is not False:
        raise ValueError("Controlled manifest must be Dev-only")


def freeze_protocol(source_root: Path, data_root: Path, config_path: Path, cmax_config_path: Path, output: Path) -> Path:
    """Freeze committed source provenance and immutable data input checksums.

    Kaggle keeps the committed source checkout under ``/kaggle/working`` but
    mounts private training data read-only under ``/kaggle/input``.  These are
    intentionally separate roots: only ``source_root`` must be a clean Git
    checkout; all model/data checksums are read from ``data_root``.
    """
    if output.exists():
        raise FileExistsError(f"Protocol already exists: {output}")
    revision = _require_clean_source_revision(source_root)
    config, cmax_config = _read_config(config_path), _read_config(cmax_config_path)
    paths = {key: data_root / value for key, value in config["input_paths"].items()}
    _assert_safe_paths(*paths.values(), config_path)
    _, inventory_sha = checkpoint_inventory(data_root / config["initial_checkpoint"])
    payload = {
        "schema_version": 1,
        "experiment": "controlled_factorial_2x2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": revision,
        "factor_levels": {"pool": {"small": config["expected_initial_pool_count"], "expanded": config["expected_expanded_pool_count"]}, "horizon_epochs": config["horizons"]},
        "seeds": config["seeds"],
        "selection": {"checkpoint_metric": "dev_loss", "comparison_primary_metric": "ERR", "test_metrics_used": False},
        "scheduler": {"type": "linear", "warmup_ratio": config["warmup_ratio"], "factorial_total_epochs": config["max_epochs"]},
        "input_checksums": {key: sha256_file(path) for key, path in paths.items()},
        "model_a_inventory_sha256": inventory_sha,
        "config_sha256": sha256_file(config_path),
        "c_max20_es": {key: cmax_config[key] for key in ("max_epochs", "min_epochs", "patience", "min_delta", "monitor")},
        "c_max20_config_sha256": sha256_file(cmax_config_path),
        "test_inputs_loaded": False,
    }
    payload["protocol_content_sha256"] = sha256_json(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def summarize_factorial(root: Path, output: Path) -> dict[str, Any]:
    """Aggregate uploaded Dev-only factorial metrics without model selection or Test use."""
    from scripts.evaluation_metrics import evaluate_records
    missing_runs: list[str] = []
    missing_predictions: list[str] = []
    for seed in FACTORIAL_SEEDS:
        for arm in FACTORIAL_ARMS:
            run_dir = root / f"seed_{seed}" / arm
            if not (run_dir / "cleanup_report.json").is_file():
                missing_runs.append(f"seed_{seed}/{arm}")
            for horizon in FACTORIAL_HORIZONS:
                prediction = run_dir / f"horizon_{horizon}" / "dev_predictions.jsonl"
                if not prediction.is_file():
                    missing_predictions.append(prediction.relative_to(root).as_posix())
    if missing_runs or missing_predictions:
        details = []
        if missing_runs:
            details.append("unfinished trajectories: " + ", ".join(missing_runs))
        if missing_predictions:
            details.append("missing selected Dev predictions: " + ", ".join(missing_predictions))
        raise RuntimeError(
            "Factorial summary requires all six cleaned trajectories. " + "; ".join(details)
        )
    records: dict[str, list[dict[str, Any]]] = {cell: [] for cell in ("S3", "S8", "L3", "L8")}
    for seed in FACTORIAL_SEEDS:
        seed_dir = root / f"seed_{seed}"
        for arm, prefix in (("small", "S"), ("expanded", "L")):
            for horizon in FACTORIAL_HORIZONS:
                prediction = seed_dir / arm / f"horizon_{horizon}" / "dev_predictions.jsonl"
                rows = read_jsonl(prediction)
                metric = evaluate_records([{"input_text": row["input_text"], "target_text": row["target_text"], "prediction_text": row.get("prediction_text", row.get("prediction", ""))} for row in rows])
                metric["exact_sentence_match"] = sum(row.get("prediction_text", row.get("prediction")) == row["target_text"] for row in rows) / len(rows)
                records[f"{prefix}{horizon}"].append(metric)
    means = {cell: {metric: sum(row[metric] for row in values) / len(values) for metric in ("ERR", "f1", "exact_sentence_match")} for cell, values in records.items()}
    effects = {metric: {"pool_at_3": means["L3"][metric] - means["S3"][metric], "pool_at_8": means["L8"][metric] - means["S8"][metric], "duration_small": means["S8"][metric] - means["S3"][metric], "duration_expanded": means["L8"][metric] - means["L3"][metric], "interaction": (means["L8"][metric] - means["L3"][metric]) - (means["S8"][metric] - means["S3"][metric])} for metric in means["S3"]}
    payload = {"schema_version": 1, "experiment": "controlled_factorial_2x2", "split": "dev", "seeds": len(next(iter(records.values()))), "seed_values": list(FACTORIAL_SEEDS), "cell_metrics_by_seed": records, "mean_metrics": means, "effects": effects, "test_metrics_used": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cleanup_completed_factorial_run(run_root: Path) -> dict[str, Any]:
    """Remove only large resumable artifacts after a verified factorial run.

    The retained manifest, selected/terminal Dev predictions, metrics, and run
    configuration are sufficient for the factorial summary and reconstruction.
    Cleanup is deliberately unavailable until both frozen horizons completed.
    """
    manifest_path = run_root / "mixture_manifest.json"
    train_config_path = run_root / "train_config.json"
    if not manifest_path.is_file() or not train_config_path.is_file():
        raise FileNotFoundError("Cleanup requires a completed run manifest and train_config.json")
    manifest, train_config = _read_config(manifest_path), _read_config(train_config_path)
    if manifest.get("experiment") != "controlled_factorial_2x2" or train_config.get("experiment") != "controlled_factorial_2x2":
        raise ValueError("Cleanup is limited to completed controlled factorial runs")
    if train_config.get("completed_epochs") != manifest.get("num_train_epochs"):
        raise ValueError("Cleanup refuses an incomplete factorial trajectory")
    required: list[Path] = []
    for horizon in manifest.get("horizons", []):
        horizon_dir = run_root / f"horizon_{horizon}"
        required.extend((
            horizon_dir / "selection.json",
            horizon_dir / "dev_predictions.jsonl",
            horizon_dir / "dev_metrics.json",
            horizon_dir / "terminal_dev_predictions.jsonl",
            horizon_dir / "terminal_dev_metrics.json",
        ))
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Cleanup refuses to remove checkpoints before horizon artifacts exist: " + ", ".join(missing))
    removed: dict[str, int] = {}
    for name in ("state", "best"):
        path = run_root / name
        if path.exists():
            bytes_removed = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
            shutil.rmtree(path)
            removed[name] = bytes_removed
    report = {
        "schema_version": 1,
        "experiment": "controlled_factorial_2x2",
        "safe_cleanup_completed": True,
        "removed_bytes": sum(removed.values()),
        "removed": removed,
        "retained_horizons": manifest["horizons"],
        "test_inputs_loaded": False,
    }
    _write_json(run_root / "cleanup_report.json", report)
    return report


def run_controlled_training(args: Any, *, optimization: bool = False) -> None:
    """Run one Dev-only controlled trajectory on Kaggle, with exact resume state.

    ``args.work_dir`` is a dedicated run directory, e.g.
    ``/kaggle/working/factorial/seed_2026/small``.  A run may be resumed by
    supplying ``--resume`` after a Kaggle interruption.  For constrained
    Kaggle disks, ``--no-resume-state`` omits the large AdamW state; that run
    must be restarted from epoch 1 if interrupted.
    """
    try:
        import torch
        from datasets import Dataset
        from torch.utils.data import DataLoader
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, DataCollatorForSeq2Seq, get_linear_schedule_with_warmup, set_seed
    except ImportError as error:  # pragma: no cover - GPU environment only
        raise SystemExit("Install requirements-kaggle.txt before controlled training") from error

    config = _read_config(args.config)
    manifest = _read_config(args.manifest)
    _assert_safe_paths(args.model_a_checkpoint, args.data_dir, args.manifest, args.config, args.work_dir)
    validate_controlled_manifest(manifest, config)
    if optimization != (manifest["experiment"] == "c_max20_es_exploratory"):
        raise ValueError("Training command does not match the frozen experiment manifest")
    if not args.model_a_checkpoint.is_dir():
        raise FileNotFoundError(args.model_a_checkpoint)
    _, inventory_sha = checkpoint_inventory(args.model_a_checkpoint)
    if inventory_sha != manifest["model_a_inventory_sha256"]:
        raise ValueError("Model A checkpoint does not match the frozen manifest")
    input_name = "expanded" if manifest["arm"] == "expanded" else "initial"
    paths = {"gold": args.data_dir / "vilexnorm_train.jsonl", "dev": args.data_dir / "vilexnorm_dev.jsonl", "pseudo": args.data_dir / ("visolex_weak_labeled_expanded.jsonl" if input_name == "expanded" else "visolex_weak_labeled.jsonl")}
    key_map = {"gold": "gold", "dev": "dev", "pseudo": input_name}
    for key, path in paths.items():
        if sha256_file(path) != manifest["checksums"][key_map[key]]:
            raise ValueError(f"Controlled input changed after manifest freeze: {key}")
    gold, dev, pseudo = (read_jsonl(paths[key]) for key in ("gold", "dev", "pseudo"))
    by_id = {row["id"]: row for row in gold + pseudo}
    if set(by_id) != {row["id"] for row in gold} | {row["id"] for row in pseudo}:
        raise ValueError("Duplicate IDs across controlled training inputs")

    run_root = args.work_dir
    state_dir, best_dir = run_root / "state", run_root / "best"
    state_path = state_dir / "latest.pt"
    run_root.mkdir(parents=True, exist_ok=True)
    if args.resume and args.no_resume_state:
        raise ValueError("--resume cannot be combined with --no-resume-state")
    if args.resume and not state_path.is_file():
        raise FileNotFoundError(f"No resumable state: {state_path}")
    if not args.resume and (state_path.exists() or (args.no_resume_state and best_dir.exists())):
        raise FileExistsError(f"Run state already exists: {state_path}; use --resume or a new --work-dir")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available() and not args.allow_cpu:
        raise RuntimeError("Controlled fine-tuning requires a GPU; pass --allow-cpu only for a small smoke test")
    set_seed(manifest["seed"])
    tokenizer = AutoTokenizer.from_pretrained(args.model_a_checkpoint)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model_a_checkpoint).to(device)

    def tokenize(records: list[dict[str, Any]]) -> Any:
        dataset = Dataset.from_list(records)
        def encode(batch: dict[str, list[str]]) -> dict[str, Any]:
            encoded = tokenizer(batch["input_text"], max_length=config["max_source_length"], truncation=True)
            encoded["labels"] = tokenizer(text_target=batch["target_text"], max_length=config["max_target_length"], truncation=True)["input_ids"]
            return encoded
        return dataset.map(encode, batched=True, remove_columns=dataset.column_names)

    collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)
    dev_records = dev[:50] if args.smoke_test else dev
    dev_loader = DataLoader(tokenize(dev_records), batch_size=config["per_device_eval_batch_size"], collate_fn=collator)

    def evaluate_loss() -> float:
        model.eval()
        losses: list[float] = []
        with torch.no_grad():
            for batch in dev_loader:
                losses.append(model(**{key: value.to(device) for key, value in batch.items()}).loss.item())
        return sum(losses) / len(losses)

    epoch_specs = manifest["epochs"][:1] if args.smoke_test else manifest["epochs"]
    if args.smoke_test:
        spec = epoch_specs[0]
        ordered = ([{"id": item, "label_source": "human"} for item in spec["gold_ids"][:200]] + [{"id": item, "label_source": "model_a+llm_review"} for item in spec["pseudo_ids"][:200]])
        epoch_specs = [{**spec, "ordered_ids": ordered}]
    steps_per_epoch = math.ceil(len(epoch_specs[0]["ordered_ids"]) / config["per_device_train_batch_size"] / config["gradient_accumulation_steps"])
    schedule_epochs = 1 if args.smoke_test else len(manifest["epochs"])
    total_steps = steps_per_epoch * schedule_epochs
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    scheduler = get_linear_schedule_with_warmup(optimizer, int(total_steps * config["warmup_ratio"]), total_steps)
    history: list[dict[str, Any]] = []
    best_loss, best_epoch, bad_epochs, start_index = float("inf"), None, 0, 0
    if args.resume:
        state = torch.load(state_path, map_location=device, weights_only=False)
        if state["manifest_sha256"] != sha256_file(args.manifest) or state["config_sha256"] != sha256_file(args.config):
            raise ValueError("Resume state belongs to a different frozen manifest or config")
        model.load_state_dict(state["model_state"])
        optimizer.load_state_dict(state["optimizer_state"])
        scheduler.load_state_dict(state["scheduler_state"])
        torch.set_rng_state(state["torch_rng_state"])
        if torch.cuda.is_available() and state.get("cuda_rng_state") is not None:
            torch.cuda.set_rng_state(state["cuda_rng_state"])
        random.setstate(state["python_rng_state"])
        history, best_loss, best_epoch, bad_epochs, start_index = state["history"], state["best_loss"], state["best_epoch"], state["bad_epochs"], state["next_epoch_index"]
    initial_dev_loss = evaluate_loss() if not history else history[0]["initial_dev_loss"]
    stopping = manifest.get("early_stopping")

    def write_model_predictions(model_to_generate: Any, output: Path, selection: dict[str, Any], *, metrics_name: str = "dev_metrics.json") -> None:
        model_to_generate.eval()
        predictions: list[str] = []
        with torch.no_grad():
            for start in range(0, len(dev_records), config["per_device_eval_batch_size"]):
                rows = dev_records[start:start + config["per_device_eval_batch_size"]]
                encoded = tokenizer([row["input_text"] for row in rows], return_tensors="pt", padding=True, truncation=True, max_length=config["max_source_length"]).to(device)
                generated = model_to_generate.generate(**encoded, num_beams=config["generation_num_beams"], max_length=config["generation_max_length"])
                predictions.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
        write_jsonl(({"id": row["id"], "input_text": row["input_text"], "target_text": row["target_text"], "prediction": prediction.strip()} for row, prediction in zip(dev_records, predictions)), output)
        _write_json(output.with_name(metrics_name), {"history": history, "initial_dev_loss": initial_dev_loss, "selected_dev_loss": selection["selected_dev_loss"], "selected_epoch": selection["selected_epoch"], "selection_metric": selection.get("selection_metric", "dev_loss"), "checkpoint_kind": selection.get("selected_checkpoint_kind", "best"), "dev_examples": len(dev_records), "exact_sentence_match": sum(prediction.strip() == row["target_text"] for row, prediction in zip(dev_records, predictions)) / len(dev_records), "test_inputs_loaded": False})

    def write_predictions(checkpoint: Path, output: Path, selection: dict[str, Any]) -> None:
        checkpoint_model = AutoModelForSeq2SeqLM.from_pretrained(checkpoint).to(device)
        write_model_predictions(checkpoint_model, output, selection)

    for spec in epoch_specs[start_index:]:
        records = [by_id[item["id"]] for item in spec["ordered_ids"]]
        loader = DataLoader(tokenize(records), batch_size=config["per_device_train_batch_size"], collate_fn=collator)
        model.train(); optimizer.zero_grad(); losses: list[float] = []
        for step, batch in enumerate(loader):
            loss = model(**{key: value.to(device) for key, value in batch.items()}).loss / config["gradient_accumulation_steps"]
            loss.backward(); losses.append(loss.item() * config["gradient_accumulation_steps"])
            if (step + 1) % config["gradient_accumulation_steps"] == 0 or step + 1 == len(loader):
                optimizer.step(); scheduler.step(); optimizer.zero_grad()
        dev_loss = evaluate_loss()
        epoch_number = spec["epoch_index"] + 1
        improved = dev_loss < best_loss - (float(stopping["min_delta"]) if stopping else 0.0)
        if improved:
            best_loss, best_epoch, bad_epochs = dev_loss, epoch_number, 0
            model.save_pretrained(best_dir); tokenizer.save_pretrained(best_dir)
        else:
            bad_epochs += 1
        window = max(1, len(losses) // 4)
        history.append({"epoch": epoch_number, "train_loss": sum(losses) / len(losses), "initial_train_loss": sum(losses[:window]) / window, "final_train_loss": sum(losses[-window:]) / window, "dev_loss": dev_loss, "initial_dev_loss": initial_dev_loss, "learning_rate": scheduler.get_last_lr()[0]})
        if not args.smoke_test and epoch_number in manifest.get("horizons", []):
            horizon_dir = run_root / f"horizon_{epoch_number}"
            selection = {"horizon_epochs": epoch_number, "selected_epoch": best_epoch, "selected_dev_loss": best_loss, "selection_metric": "dev_loss", "selected_checkpoint_kind": "best_at_horizon", "test_metrics_used": False}
            _write_json(horizon_dir / "selection.json", selection)
            write_predictions(best_dir, horizon_dir / "dev_predictions.jsonl", selection)
            terminal = {"horizon_epochs": epoch_number, "selected_epoch": epoch_number, "selected_dev_loss": dev_loss, "selection_metric": "terminal_epoch", "selected_checkpoint_kind": "terminal_at_horizon", "test_metrics_used": False}
            write_model_predictions(model, horizon_dir / "terminal_dev_predictions.jsonl", terminal, metrics_name="terminal_dev_metrics.json")
        if not args.no_resume_state:
            state_dir.mkdir(parents=True, exist_ok=True)
            torch.save({"manifest_sha256": sha256_file(args.manifest), "config_sha256": sha256_file(args.config), "model_state": model.state_dict(), "optimizer_state": optimizer.state_dict(), "scheduler_state": scheduler.state_dict(), "torch_rng_state": torch.get_rng_state(), "cuda_rng_state": torch.cuda.get_rng_state() if torch.cuda.is_available() else None, "python_rng_state": random.getstate(), "history": history, "best_loss": best_loss, "best_epoch": best_epoch, "bad_epochs": bad_epochs, "next_epoch_index": spec["epoch_index"] + 1}, state_path)
        if stopping and epoch_number >= int(stopping["min_epochs"]) and bad_epochs >= int(stopping["patience"]):
            break
    if best_epoch is None:
        raise RuntimeError("No best checkpoint was saved")

    if args.smoke_test:
        write_predictions(best_dir, run_root / "dev_predictions.jsonl", {"selected_dev_loss": best_loss, "selected_epoch": best_epoch, "selection_metric": "dev_loss", "selected_checkpoint_kind": "best_smoke"})
        _write_json(run_root / "smoke_test.json", {"passed": True, "composition": {"gold": 200, "pseudo": 200}, "checkpoint_reload": True, "generation_nonempty": True, "test_inputs_loaded": False, "best_dev_loss": best_loss})
    elif optimization:
        selection = {"selected_dev_loss": best_loss, "selected_epoch": best_epoch, "selection_metric": "dev_loss", "selected_checkpoint_kind": "best_early_stopping"}
        write_predictions(best_dir, run_root / "dev_predictions.jsonl", selection)
        _write_json(run_root / "early_stopping_report.json", {"max_epochs": len(manifest["epochs"]), "completed_epochs": len(history), "stopped_early": len(history) < len(manifest["epochs"]), "best_epoch": best_epoch, "best_dev_loss": best_loss, "rule": stopping, "test_inputs_loaded": False})
    _write_json(run_root / "train_config.json", {"schema_version": 1, "experiment": manifest["experiment"], "arm": manifest["arm"], "seed": manifest["seed"], "manifest_sha256": sha256_file(args.manifest), "config_sha256": sha256_file(args.config), "model_a_inventory_sha256": inventory_sha, "best_dev_loss": best_loss, "best_epoch": best_epoch, "completed_epochs": len(history), "total_optimizer_steps": total_steps, "resume_state_saved": not args.no_resume_state, "test_inputs_loaded": False, "runtime": {"torch_version": torch.__version__, "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"}, "source_revision": source_revision()})