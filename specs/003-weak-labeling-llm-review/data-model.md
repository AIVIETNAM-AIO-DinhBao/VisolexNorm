# Mô hình dữ liệu: Candidate và LLM review

## CandidateRecord

| Trường | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| `id` | string | Có | Duy nhất, giữ từ ViSoLex |
| `dataset` | string | Có | Luôn là `ViSoLex` |
| `original_source` | enum | Có | Một trong 5 tên nguồn chuẩn; ViHOS không có record thực tế |
| `input_text` | string | Có | Không rỗng, không sửa từ Phase 1 |
| `candidate_text` | string | Có | Không rỗng |
| `model_a_confidence` | number | Có | Hữu hạn |
| `candidate_checkpoint` | string | Có | Tên/checksum checkpoint |
| `generation_config_hash` | string | Có | SHA-256 config generation |
| `sequence_token_count` | integer | Có | Lớn hơn 0 |

## ReviewManifestItem

Kế thừa toàn bộ CandidateRecord và thêm:

| Trường | Kiểu | Quy tắc |
|---|---|---|
| `confidence_band` | enum | `low`, `medium`, `high` |
| `source_quota` | integer | Quota nguồn trong 20.000 |
| `selection_rank` | integer | Thứ tự chọn ổn định trong strata |
| `selection_seed` | integer | Luôn `2026` |
| `is_pilot` | boolean | Đúng với 240 mẫu pilot |

## ReviewBatch

| Trường | Kiểu | Quy tắc |
|---|---|---|
| `batch_id` | string | SHA-256 rút gọn từ prompt version và danh sách ID |
| `sample_ids` | array[string] | 15 ID; batch cuối được 1–14 |
| `prompt_version` | string | `lexical_norm_review_draft` khi pilot; `lexical_norm_review_v1` sau freeze |
| `prompt_hash` | string | SHA-256 nội dung prompt; là một phần khóa cache |
| `llm_model` | string | Giá trị `GEMINI_MODEL` |
| `attempt_count` | integer | 0–5 |
| `status` | enum | pending, in_flight, succeeded, retry_wait, failed |
| `created_at` | datetime | UTC ISO-8601 |
| `completed_at` | datetime/null | UTC ISO-8601 |

## ReviewResult

| Trường | Kiểu | Quy tắc |
|---|---|---|
| `id` | string | Phải thuộc đúng batch |
| `decision` | enum | KEEP, EDIT, REJECT |
| `corrected_text` | string/null | Bắt buộc không rỗng cho EDIT; null cho KEEP/REJECT |
| `reason_code` | string/null | Bắt buộc cho REJECT |
| `raw_response` | string | Chỉ lưu trong SQLite audit |
| `reviewed_at` | datetime | UTC ISO-8601 |

Reason code REJECT chuẩn: `AMBIGUOUS`, `MEANING_UNCERTAIN`, `CANDIDATE_UNUSABLE`,
`NOT_LEXICAL_NORMALIZATION`, `OTHER`.

## WeakLabelRecord

| Trường | Kiểu | Quy tắc |
|---|---|---|
| `id` | string | Duy nhất |
| `dataset` | string | `ViSoLex` |
| `original_source` | string | Giữ provenance |
| `input_text` | string | SOURCE gốc |
| `candidate_text` | string | Output Model A |
| `model_a_confidence` | number | Giữ để phân tích |
| `confidence_band` | string | low/medium/high |
| `llm_decision` | enum | Chỉ KEEP hoặc EDIT |
| `llm_corrected_text` | string/null | Có khi EDIT |
| `target_text` | string | Candidate nếu KEEP, corrected nếu EDIT |
| `label_source` | string | `model_a+llm_review` |
| `llm_model` | string | Model đã review |
| `prompt_version` | string | Prompt đã freeze |
| `accepted` | boolean | Luôn true trong artifact cuối |

## Chuyển trạng thái

```text
candidate → selected → batched → reviewed
reviewed KEEP/EDIT → validated → accepted hoặc validation_dropped
reviewed REJECT → rejected
API/schema error → retry_wait → batched hoặc failed
```

Chỉ trạng thái `accepted` được export vào `visolex_weak_labeled.jsonl`.