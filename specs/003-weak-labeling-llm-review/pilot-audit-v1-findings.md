# Pilot audit v1 findings (historical)

**Trạng thái:** historical, không phải runtime configuration hay executable code.
**Nguồn lưu trữ trước refactor:** `scripts/record_pilot_audit.py`.
**Artifact liên quan:** `outputs/pilot_review_audit.csv`,
`outputs/pilot_review_report.json`.

## Mục đích lưu trữ

Pilot v1 gồm 240 mẫu và bị từ chối: 18 major issue (7,5%) vượt quality gate 2%.
Script một lần trước đây chỉ điền các kết luận dưới đây vào một CSV local. Script đã
được xóa trong refactor sau Phase 8 vì không phải logic tái sử dụng; dữ liệu audit
được giữ lại trong tài liệu này và trong report JSON historical.

Kết quả này **không** phải pilot v6 được freeze. Prompt/policy được phép dùng cho
full review vẫn được xác định bởi `outputs/pilot_review_report_v6.json`,
`prompts/lexical_norm_review_v1.txt` và identity hash đã freeze.

## Major findings

| ID | Tags | Expected verdict | Reviewer note |
|---|---|---|---|
| `visolex_022418` | `WRONG_LEXICAL_DISAMBIGUATION;MEANING_CHANGE` | `EDIT` | Candidate changes dính to dịch; retain intended dính. |
| `visolex_024546` | `UNSUPPORTED_EXPANSION;MEANING_CHANGE` | `EDIT` | Do not expand c to cậu without support; intended address is chị. |
| `visolex_034886` | `INCOMPLETE_EDIT_TARGET;NO_OP_EDIT` | `EDIT` | Correct nhưg to nhưng. |
| `visolex_035352` | `FALSE_KEEP;UNDER_NORMALIZATION` | `EDIT` | Correct không lồ to khổng lồ. |
| `visolex_036717` | `INCOMPLETE_EDIT_TARGET;UNDER_NORMALIZATION` | `EDIT` | Expand ol to online; preserve emoji. |
| `visolex_042084` | `MEANING_CHANGE;UNSUPPORTED_EXPANSION` | `REJECT` | Candidate changes sp to cuộc sống. |
| `visolex_042613` | `MEANING_UNCERTAIN;NONLEXICAL_GIBBERISH` | `REJECT` | Unreliable target; reject rather than preserve gibberish. |
| `visolex_043258` | `FALSE_KEEP;UNDER_NORMALIZATION` | `EDIT` | Recoverable missing diacritics are left unnormalized. |
| `visolex_047238` | `CONTENT_DELETION;MEANING_CHANGE` | `REJECT` | Candidate loses explicit rating clause. |
| `visolex_049811` | `MEANING_CHANGE;UNSUPPORTED_SUBSTITUTION` | `REJECT` | Candidate substitutes product attribute dẻo with rất. |
| `visolex_050152` | `CONTENT_DELETION;MEANING_CHANGE` | `REJECT` | Candidate corrupts topic boundary/content. |
| `visolex_057634` | `FALSE_KEEP;UNDER_NORMALIZATION` | `EDIT` | Correct dam to RAM. |
| `visolex_057711` | `MEANING_CHANGE;CONTENT_DELETION` | `EDIT` | Restore tìm mọi cài đặt; do not delete content. |
| `visolex_059003` | `TARGET_REGRESSION;UNDER_NORMALIZATION` | `EDIT` | Correct bin/wep/ko and retain source content. |
| `visolex_063094` | `FALSE_KEEP;UNDER_NORMALIZATION` | `EDIT` | Multiple clear typos remain, including khômg and điều khiện. |
| `visolex_065830` | `FALSE_KEEP;UNDER_NORMALIZATION` | `EDIT` | Clear lexical noise remains: wiffi/bin/đc. |
| `visolex_065950` | `INCOMPLETE_EDIT_TARGET;UNDER_NORMALIZATION` | `EDIT` | Normalize missing diacritics in san pham dep va chat luong. |
| `visolex_066733` | `TARGET_REGRESSION;UNDER_NORMALIZATION` | `EDIT` | Correct bủi/qá/bth/íu/đt/khôq instead of reverting candidate. |

## Minor findings

| ID | Tag |
|---|---|
| `visolex_005903` | `NON_MINIMAL_EDIT` |
| `visolex_033369` | `NON_MINIMAL_EDIT` |
| `visolex_037543` | `NON_MINIMAL_EDIT` |
| `visolex_040145` | `NON_MINIMAL_EDIT` |
| `visolex_052101` | `NON_MINIMAL_EDIT` |
| `visolex_056447` | `NON_MINIMAL_EDIT` |
| `visolex_057100` | `NON_MINIMAL_EDIT` |
| `visolex_057546` | `NON_MINIMAL_EDIT` |
| `visolex_060880` | `DECISION_NO_OP_EDIT` |
| `visolex_062758` | `NON_MINIMAL_EDIT` |
| `visolex_063195` | `UNDER_NORMALIZATION` |
| `visolex_063528` | `TARGET_REGRESSION` |
| `visolex_064452` | `UNDER_NORMALIZATION` |