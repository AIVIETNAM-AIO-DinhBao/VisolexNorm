from collections import Counter
from visolexnorm.training.mixtures import sample_model_b_epochs

def test_rotation_is_deterministic_balanced_and_complete() -> None:
    gold = [f"g{i}" for i in range(8372)]; pseudo = [f"p{i}" for i in range(18970)]
    first, replaced = sample_model_b_epochs(gold, pseudo, seed=2026, num_epochs=3, pseudo_per_epoch=8372)
    second, _ = sample_model_b_epochs(gold, pseudo, seed=2026, num_epochs=3, pseudo_per_epoch=8372)
    assert first == second and not replaced
    assert [e["epoch_seed"] for e in first] == [2026, 2027, 2028]
    assert all(e["gold_count"] == e["pseudo_count"] == len(set(e["pseudo_ids"])) == 8372 for e in first)
    counts = Counter(x for e in first for x in e["pseudo_ids"])
    assert len(counts) == 18970 and Counter(counts.values()) == {1: 12824, 2: 6146}

def test_small_pool_records_replacement() -> None:
    epochs, replaced = sample_model_b_epochs(["g1"], ["p1", "p2"], seed=2026, num_epochs=1, pseudo_per_epoch=3)
    assert replaced and epochs[0]["replacement_used"] and len(epochs[0]["pseudo_ids"]) == 3