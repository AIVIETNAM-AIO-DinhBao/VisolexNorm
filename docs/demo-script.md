# Kịch bản demo offline

## Chuẩn bị

1. Đã tải Kaggle Dataset checkpoint version được ghi trong `release/manifest.json`.
2. Checkpoint ở `checkpoints/model_c/` và `checkpoints/model_b/`.
3. Cài `requirements-inference.txt`.
4. Tắt mạng hoặc đặt biến môi trường sau:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
```

5. Xác minh release:

```powershell
python scripts/verify_release.py --manifest release/manifest.json
```

## Trình diễn app

Chạy Gradio:

```powershell
python -m visolexnorm.app.web
```

Mở URL `http://127.0.0.1:7860`, nhập:

```text
mik ko bt hnay đi hc ko
```

Kết quả demo đã smoke test:

```text
mình không biết hôm nay đi học không
```

Nêu rõ hệ thống chuẩn hóa từ vựng như viết tắt/teencode/lỗi chính tả; không được thiết kế để
paraphrase, đổi sắc thái, thêm thông tin hoặc gọi LLM API khi inference.

## Giải thích weak-label

1. Model A tạo candidate từ câu ViSoLex unlabeled.
2. Gemini reviewer xác định chuẩn hóa độc lập rồi trả một trong ba quyết định:
   - **KEEP**: candidate dùng được;
   - **EDIT**: dùng corrected text tối thiểu;
   - **REJECT**: loại khỏi train.
3. Phase 3 review 20.000 ID, nhận 18.970 LLM-reviewed weak labels.
4. Phase 8 review thêm 48.411 ID; pool mở rộng nhận 64.813 LLM-reviewed weak labels.
Reviewer là `gemini-3.5-flash-lite`, prompt `lexical_norm_review_v1`, temperature 0 và structured JSON schema.

## Bảng kết quả cần trình bày

### Historical Phase 5 A/B trên Test đóng băng

| Model | ERR | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Model A | 0.600250 | 0.733999 | 0.703037 | 0.718184 |
| Model B | 0.633111 | 0.761538 | 0.723847 | 0.742215 |

Model B là historical winner vì F1 cao hơn.

### Common A/B/C Test

| Model | ERR | F1 |
|---|---:|---:|
| Model A | 0.600250 | 0.718184 |
| Model B | 0.633111 | 0.742215 |
| Model C | 0.664725 | 0.764993 |

Model C được chọn trên Dev trước khi báo cáo Test. Selection artifact ghi `selection_split=dev` và
`test_metrics_used_for_selection=false`. Model C là app checkpoint; Model B là fallback.