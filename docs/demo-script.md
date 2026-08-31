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
3. Phase 3 review 20.000 ID, nhận 18.970 weak labels.
4. Phase 8 review thêm 48.411 ID; pool mở rộng nhận 64.813 weak labels.

## Bảng kết quả cần trình bày

### Historical Phase 5 A/B trên Test đóng băng

| Model | ERR | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Model A | 0.703037 | 0.733999 | 0.703037 | 0.718184 |
| Model B | 0.723847 | 0.761538 | 0.723847 | 0.742215 |

Model B là historical winner vì F1 cao hơn.

### Phase 9 A/B/C hậu kiểm

| Model | F1 |
|---|---:|
| Model A | 0.718184 |
| Model B | 0.742215 |
| Model C | 0.764993 |

Model C cao hơn Model B `+0.022778` F1 (bootstrap CI95 `[0.012063, 0.033228]`) và là app
checkpoint hiện tại. Phải nói rõ đây là hậu kiểm trên Test đã quan sát, không phải holdout độc
lập; Model B vẫn luôn sẵn sàng rollback.