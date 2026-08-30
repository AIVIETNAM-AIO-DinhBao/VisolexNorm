# Hướng dẫn nghiệm thu nhanh Phase 3

## 1. Điều kiện

- Có `data/processed/visolex_unlabeled.jsonl` với 68.411 dòng.
- Có checkpoint Model A load được.
- Tạo `.env` từ `.env.example`; không commit `.env`.

## 2. Nghiệm thu candidate full run

Khi cần sinh mới, mở `notebooks/generate_visolex_candidates_kaggle.ipynb`, chạy từ smoke test
đến full run và tải artifact về. Với full run hiện đã hoàn thành, chạy bằng chứng thay thế đã
được chủ dự án duyệt:

```bash
python -m scripts.candidates audit
```

Kỳ vọng: `outputs/model_a/candidate_full_run_integrity.json` có `passed=true`, đủ 68.411
candidate, 69 chunk liên tục, schema/confidence/config/provenance và ZIP checksum đều hợp lệ.

## 3. Tạo manifest và pilot local

```bash
python -m scripts.candidates select-review --candidates data/intermediate/visolex_model_a_candidates.jsonl --config configs/llm_review_config.json
python -m scripts.reviews run --mode pilot --config configs/llm_review_config.json
```

Kỳ vọng: manifest 20.000 dòng, pilot 240 dòng và 16 request Gemini nếu không retry.
Người thực nghiệm audit toàn bộ; chỉ duyệt khi tỷ lệ lỗi major không vượt 3,0%. Báo cáo phải
chứa `approved=true`, review identity SHA-256 (prompt + lexical policy) và đúng 240
`audited_ids`. Sau đó chạy:

```bash
python -m scripts.reviews freeze-prompt --pilot-report outputs/pilot_review_report_v6.json --approved --replace-existing
```

Batch chính từ chối chạy nếu v1/hash chưa được freeze.

## 4. Review chính và resume

```bash
python -m scripts.reviews run --mode full --config configs/llm_review_config.json
```

Dừng tiến trình sau vài batch rồi chạy lại cùng lệnh. Kỳ vọng: các result đã commit không bị
gọi lại; tiến trình tiếp tục từ sample chưa hoàn thành.

## 5. Xây weak labels

```bash
python -m scripts.data export-protected-hashes
python -m scripts.weak_labels build-initial --protected-hashes data/processed/vilexnorm_protected_input_hashes.txt --model "$GEMINI_MODEL" --config configs/llm_review_config.json --excluded-ids-file outputs/phase3_provider_exclusions.json
python -m scripts.weak_labels audit --weak-labels data/processed/visolex_weak_labeled.jsonl --stats outputs/weak_label_stats.json --approved-exclusions outputs/phase3_provider_exclusions.json
```

Kỳ vọng:
- `data/processed/visolex_weak_labeled.jsonl` chỉ có KEEP/EDIT hợp lệ;
- không có REJECT, duplicate hoặc overlap Dev/Test;
- `outputs/weak_label_stats.json` có tổng số và tỷ lệ theo source/band/decision;
- không có API key trong bất kỳ artifact hoặc log nào.