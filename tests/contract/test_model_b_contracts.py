import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).parents[2]
SCHEMA = json.loads((ROOT / "specs/004-model-b-training/contracts/train-config.schema.json").read_text())

def valid_config() -> dict:
    d = "a" * 64
    return {"run_type":"full","initial_checkpoint":"checkpoints/model_a","checkpoint_inventory_sha256":d,"phase3_manifest_sha256":d,"training_mixture_manifest_sha256":d,"gold_checksum":d,"dev_checksum":d,"weak_label_checksum":d,"seed":2026,"gold_count":8372,"dev_count":1050,"weak_label_count":18970,"pseudo_per_epoch":8372,"gold_pseudo_ratio":"1:1","completion_status":"completed_with_approved_provider_exclusions","prompt_version":"lexical_norm_review_v1","decision_distribution":{"KEEP":9034,"EDIT":9936},"source_distribution":{"ViHSD":8460},"epoch_seeds":[2026,2027,2028],"replacement_used":False,"hyperparameters":{},"runtime":{"python_version":"3.12","torch_version":"2.10","transformers_version":"5.0","device":"T4"},"best_checkpoint":"checkpoints/model_b","best_dev_loss":0.4}

def test_complete_config_is_valid() -> None: Draft202012Validator(SCHEMA).validate(valid_config())

@pytest.mark.parametrize("field,value", [("gold_count",8371),("gold_pseudo_ratio","2:1"),("epoch_seeds",[2026]*3)])
def test_baseline_drift_is_invalid(field, value) -> None:
    config = valid_config(); config[field] = value
    with pytest.raises(ValidationError): Draft202012Validator(SCHEMA).validate(config)