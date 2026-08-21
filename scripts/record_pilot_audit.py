"""Record reviewed pilot findings in the exported audit worksheet.

This script preserves all machine-generated columns and only writes the four
human-audit columns. It is intentionally scoped to the rejected pilot run.
"""

from __future__ import annotations

import csv
from pathlib import Path


AUDIT_PATH = Path("outputs/pilot_review_audit.csv")

MAJOR = {
    "visolex_022418": ("WRONG_LEXICAL_DISAMBIGUATION;MEANING_CHANGE", "EDIT", "Candidate changes dính to dịch; retain intended dính."),
    "visolex_024546": ("UNSUPPORTED_EXPANSION;MEANING_CHANGE", "EDIT", "Do not expand c to cậu without support; intended address is chị."),
    "visolex_034886": ("INCOMPLETE_EDIT_TARGET;NO_OP_EDIT", "EDIT", "Correct nhưg to nhưng."),
    "visolex_035352": ("FALSE_KEEP;UNDER_NORMALIZATION", "EDIT", "Correct không lồ to khổng lồ."),
    "visolex_036717": ("INCOMPLETE_EDIT_TARGET;UNDER_NORMALIZATION", "EDIT", "Expand ol to online; preserve emoji."),
    "visolex_042084": ("MEANING_CHANGE;UNSUPPORTED_EXPANSION", "REJECT", "Candidate changes sp to cuộc sống."),
    "visolex_042613": ("MEANING_UNCERTAIN;NONLEXICAL_GIBBERISH", "REJECT", "Unreliable target; reject rather than preserve gibberish."),
    "visolex_043258": ("FALSE_KEEP;UNDER_NORMALIZATION", "EDIT", "Recoverable missing diacritics are left unnormalized."),
    "visolex_047238": ("CONTENT_DELETION;MEANING_CHANGE", "REJECT", "Candidate loses explicit rating clause."),
    "visolex_049811": ("MEANING_CHANGE;UNSUPPORTED_SUBSTITUTION", "REJECT", "Candidate substitutes product attribute dẻo with rất."),
    "visolex_050152": ("CONTENT_DELETION;MEANING_CHANGE", "REJECT", "Candidate corrupts topic boundary/content."),
    "visolex_057634": ("FALSE_KEEP;UNDER_NORMALIZATION", "EDIT", "Correct dam to RAM."),
    "visolex_057711": ("MEANING_CHANGE;CONTENT_DELETION", "EDIT", "Restore tìm mọi cài đặt; do not delete content."),
    "visolex_059003": ("TARGET_REGRESSION;UNDER_NORMALIZATION", "EDIT", "Correct bin/wep/ko and retain source content."),
    "visolex_063094": ("FALSE_KEEP;UNDER_NORMALIZATION", "EDIT", "Multiple clear typos remain, including khômg and điều khiện."),
    "visolex_065830": ("FALSE_KEEP;UNDER_NORMALIZATION", "EDIT", "Clear lexical noise remains: wiffi/bin/đc."),
    "visolex_065950": ("INCOMPLETE_EDIT_TARGET;UNDER_NORMALIZATION", "EDIT", "Normalize missing diacritics in san pham dep va chat luong."),
    "visolex_066733": ("TARGET_REGRESSION;UNDER_NORMALIZATION", "EDIT", "Correct bủi/qá/bth/íu/đt/khôq instead of reverting candidate."),
}
MINOR = {
    "visolex_005903": "NON_MINIMAL_EDIT", "visolex_033369": "NON_MINIMAL_EDIT",
    "visolex_037543": "NON_MINIMAL_EDIT", "visolex_040145": "NON_MINIMAL_EDIT",
    "visolex_052101": "NON_MINIMAL_EDIT", "visolex_056447": "NON_MINIMAL_EDIT",
    "visolex_057100": "NON_MINIMAL_EDIT", "visolex_057546": "NON_MINIMAL_EDIT",
    "visolex_060880": "DECISION_NO_OP_EDIT", "visolex_062758": "NON_MINIMAL_EDIT",
    "visolex_063195": "UNDER_NORMALIZATION", "visolex_063528": "TARGET_REGRESSION",
    "visolex_064452": "UNDER_NORMALIZATION",
}


def main() -> None:
    with AUDIT_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames
    if len(rows) != 240:
        raise ValueError(f"Expected 240 pilot rows, got {len(rows)}")
    if not fields:
        raise ValueError("Pilot audit CSV is missing its header")
    for row in rows:
        row.update({"human_verdict": "PASS", "issue_tags": "", "human_expected_target": "", "reviewer_note": "Reviewed against lexical-only prompt scope."})
        if row["id"] in MINOR:
            row.update({"human_verdict": "MINOR_ISSUE", "issue_tags": MINOR[row["id"]], "reviewer_note": "Usable decision but requires stricter minimal/exhaustive lexical policy."})
        if row["id"] in MAJOR:
            tags, expected, note = MAJOR[row["id"]]
            row.update({"human_verdict": "MAJOR_ISSUE", "issue_tags": tags, "human_expected_target": expected, "reviewer_note": note})
    with AUDIT_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Recorded audit: pass={len(rows) - len(MAJOR) - len(MINOR)} minor={len(MINOR)} major={len(MAJOR)}")


if __name__ == "__main__":
    main()