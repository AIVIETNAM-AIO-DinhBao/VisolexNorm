from pathlib import Path
from visolexnorm.training.mixtures import build_model_b_manifest

ROOT = Path(__file__).parents[2]

def test_real_frozen_inputs_build_expected_manifest() -> None:
    result = build_model_b_manifest(ROOT, ROOT / "configs/model_b_config.json", ROOT / "outputs/phase3_manifest.json")
    assert (result["gold_count"], result["dev_count"], result["weak_label_count"]) == (8372, 1050, 18970)
    assert result["pseudo_union_count"] == 18970
    assert result["decision_distribution"] == {"EDIT": 9936, "KEEP": 9034}
    assert all(len(e["ordered_ids"]) == 16744 for e in result["epochs"])