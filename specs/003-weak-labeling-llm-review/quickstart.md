# Hướng dẫn nghiệm thu nhanh Phase 3

## 1. Điều kiện

- Có `data/processed/visolex_unlabeled.jsonl` với 68.411 dòng.
- Có checkpoint Model A load được.
- Tạo `.env` từ `.env.example`; không commit `.env`.

## 2. Candidate smoke test trên Kaggle

Mở `notebooks/generate_visolex_candidates_kaggle.ipynb`, đặt chế độ smoke test 100 mẫu và
chạy toàn bộ notebook. Kỳ vọng: 100 candidate đúng ID, confidence hữu hạn, chạy lại bỏ qua
chunk đã hoàn thành. Sau đó tắt smoke test để sinh đủ 68.411 candidate và tải artifact về.

## 3. Tạo manifest và pilot local

```bash
python scripts/select_review_manifest.py --candidates data/intermediate/visolex_model_a_candidates.jsonl --config configs/llm_review_config.json
python scripts/review_candidates.py --mode pilot --config configs/llm_review_config.json
```

Kỳ vọng: manifest 20.000 dòng, pilot 240 dòng và 16 request Gemini nếu không retry.
Người thực nghiệm audit toàn bộ và tạo `outputs/pilot_review_report.json` chứa
`approved=true`, SHA-256 của draft và đúng 240 `audited_ids`. Sau đó chạy:

```bash
python scripts/freeze_review_prompt.py --pilot-report outputs/pilot_review_report.json --approved
```

Batch chính từ chối chạy nếu v1/hash chưa được freeze.

## 4. Review chính và resume

```bash
python scripts/review_candidates.py --mode full --config configs/llm_review_config.json
```

Dừng tiến trình sau vài batch rồi chạy lại cùng lệnh. Kỳ vọng: các result đã commit không bị
gọi lại; tiến trình tiếp tục từ sample chưa hoàn thành.

## 5. Xây weak labels

```bash
python scripts/export_protected_hashes.py
python scripts/build_weak_labels.py --protected-hashes data/processed/vilexnorm_protected_input_hashes.txt --model "$GEMINI_MODEL" --config configs/llm_review_config.json
python scripts/audit_weak_labels.py --weak-labels data/processed/visolex_weak_labeled.jsonl --stats outputs/weak_label_stats.json
```

Kỳ vọng:
- `data/processed/visolex_weak_labeled.jsonl` chỉ có KEEP/EDIT hợp lệ;
- không có REJECT, duplicate hoặc overlap Dev/Test;
- `outputs/weak_label_stats.json` có tổng số và tỷ lệ theo source/band/decision;
- không có API key trong bất kỳ artifact hoặc log nào.