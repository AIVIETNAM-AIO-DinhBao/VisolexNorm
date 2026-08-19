from __future__ import annotations

from collections import Counter, defaultdict

from scripts.select_review_manifest import create_manifest, largest_remainder_quotas


SOURCES = ["ViHSD", "UIT-VSMEC", "ViHOS", "ViSpamReviews", "UIT-ViSFD"]


def candidate(index: int, source: str) -> dict:
    return {
        "id": f"visolex_{index:06d}", "dataset": "ViSoLex", "original_source": source,
        "input_text": f"source {index}", "candidate_text": f"candidate {index}",
        "model_a_confidence": -float(index), "candidate_checkpoint": "model_a",
        "generation_config_hash": "a" * 64, "sequence_token_count": 2,
        "generation_status": "generated_text",
    }


def config() -> dict:
    return {
        "seed": 2026, "review_budget": 20000, "pilot_per_stratum": 20,
        "source_order": SOURCES, "confidence_bands": ["low", "medium", "high"],
    }


def test_largest_remainder_matches_frozen_phase1_counts() -> None:
    counts = {"ViHSD": 30579, "UIT-VSMEC": 6916, "ViHOS": 0, "ViSpamReviews": 19805, "UIT-ViSFD": 11111}
    assert largest_remainder_quotas(counts, 20000, SOURCES) == {
        "ViHSD": 8940, "UIT-VSMEC": 2022, "ViHOS": 0,
        "ViSpamReviews": 5790, "UIT-ViSFD": 3248,
    }


def test_manifest_is_deterministic_balanced_and_has_240_pilot_samples() -> None:
    counts = {"ViHSD": 9000, "UIT-VSMEC": 3000, "ViHOS": 0, "ViSpamReviews": 6000, "UIT-ViSFD": 4000}
    rows = []
    index = 0
    for source, count in counts.items():
        for _ in range(count):
            index += 1
            rows.append(candidate(index, source))
    first = create_manifest(rows, config())
    second = create_manifest(rows, config())
    assert [row["id"] for row in first] == [row["id"] for row in second]
    assert len(first) == 20000
    assert sum(row["is_pilot"] for row in first) == 240
    by_source_band = defaultdict(Counter)
    for row in first:
        by_source_band[row["original_source"]][row["confidence_band"]] += 1
    for source, band_counts in by_source_band.items():
        assert max(band_counts.values()) - min(band_counts.values()) <= 1, source