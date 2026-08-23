# Mô hình dữ liệu: Review mở rộng và Model C

## RemainingReviewManifest

Mỗi record kế thừa `CandidateRecord` Phase 3 và thêm `review_scope="phase8_remaining"`,
`prior_manifest=false`, `selection_seed=2026`, `selection_rank` theo thứ tự candidate gốc.
Manifest phải có đúng 48.411 ID; không giao với `visolex_review_manifest.jsonl`.

## ExpandedWeakLabelRecord

Giữ nguyên schema `WeakLabelRecord` Phase 3; không thêm trường trên từng record và không tạo
migration schema/validation mới. `prompt_version`, `llm_model`, `llm_decision`, source và
candidate provenance hiện có vẫn đủ truy vết record.

`outputs/expanded_review/artifact_manifest.json` ghi SHA-256 của weak-label artifact Phase 3,
manifest Phase 8, cache identity/prompt hash và số record từ từng nguồn. Chỉ KEEP/EDIT đã
validate được export; ID phải unique trên union Phase 3/8.

## ModelCTrainingMixtureManifest

Ghi checksum pool mở rộng, inventory Model A, số epoch suy ra, seed từng epoch, `gold_ids`,
`pseudo_ids`, cờ `replacement_used` và `pseudo_union_count`. `pseudo_union_count` phải bằng
`expanded_weak_label_count`; không chứa ID Dev/Test.

## ModelCExitReport

Ghi đường dẫn/checksum artifact Phase 8, count theo review decision, pool size, coverage,
checkpoint inventory, best Dev loss và xác nhận `test_inputs_loaded=false`. Không chứa metric
hoặc prediction ViLexNorm Test.