# Kế hoạch triển khai: Suy luận local và Gradio

## Cấu trúc

```text
visolexnorm/app/
├── __init__.py          # đã có
├── inference.py         # đã có
├── loader.py            # đã có
├── selection.py         # đã có
└── web.py               # còn triển khai
configs/app_inference_config.json
outputs/app/model_selection.json
tests/app/
```

## Triển khai

1. `selection.py` đọc app selection, xác minh inventory và fallback Model C → Model B — đã có.
2. `loader.py` nạp tokenizer/model theo nhu cầu và cache theo checkpoint — đã có.
3. `inference.py` kiểm tra input trước khi sinh kết quả và cung cấp CLI — đã có.
4. `web.py` tạo Gradio Blocks, bind local, chuyển exception sang thông báo tiếng Việt — còn làm.
5. Test dùng model stub cho validation/cache; smoke thật dùng Model C và kiểm tra rollback — còn làm.
6. Dependency suy luận local tách khỏi dependency training và Gemini.

## Ranh giới với Phase 8

Trong thời gian Phase 8 chạy, Phase 6 dùng Model B và không cho Model C tự promotion. Sau đó
Phase 9 thực hiện benchmark hậu kiểm và Phase 10 tạo `outputs/app/model_selection.json`. Runtime
hiện dùng Model C mặc định, Model B rollback; `outputs/evaluation/best_model.json` vẫn là quyết
định A/B lịch sử của Phase 5.

## Artifact

- `configs/app_inference_config.json`
- `outputs/app/model_selection.json`
- `outputs/app/model_c_promotion_smoke_test.json`
- lệnh CLI: `python -m visolexnorm.app.inference --text "..."`
- lệnh web dự kiến: `python -m visolexnorm.app.web`