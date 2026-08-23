# Kế hoạch triển khai: Local inference và Gradio

## Cấu trúc

```text
app/
├── __init__.py
├── inference.py
├── model_loader.py
└── web.py
configs/inference_config.json
tests/unit/test_inference_validation.py
tests/integration/test_local_inference.py
```

## Triển khai

1. `model_loader.py` đọc best model/config, xác minh checksum, lazy-load tokenizer/model.
2. `inference.py` validate bằng tokenizer trước generation và cung cấp CLI.
3. `web.py` tạo Gradio Blocks, bind local, map exception sang thông báo tiếng Việt.
4. Test dùng model stub cho validation/cache; smoke test thật dùng best checkpoint.
5. Dependency inference local tách khỏi dependency training và Gemini.

## Ranh giới với Phase 8

Phase 6 dùng duy nhất Model B được ghi trong `outputs/evaluation/best_model.json` của Phase 5.
Workstream Phase 8 có thể review/huấn luyện Model C song song, nhưng không được thay đổi file
chọn model, checkpoint Phase 6, dependency inference hoặc tiêu chí nghiệm thu app. Model C chỉ
có thể được cân nhắc cho một app/release sau một cổng đánh giá độc lập đã freeze trước inference.

## Artifact

- `configs/inference_config.json`
- `outputs/inference_smoke_test.json`
- lệnh chạy: `python -m app.web`