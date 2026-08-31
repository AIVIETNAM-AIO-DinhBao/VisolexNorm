# Nhiệm vụ: Local inference và Gradio

- [x] T001 [P] Tạo dependency/config local. **Kết quả Phase 10:** `requirements-inference.txt` và `configs/app_inference_config.json`.
- [x] T002 [US1] Cài đặt inventory verification và lazy model loader. **Kết quả Phase 10:** `visolexnorm/app/selection.py`, `loader.py` với Model C default/Model B rollback.
- [x] T003 [US1] Cài đặt validation, `normalize` và CLI. **Kết quả Phase 10:** `visolexnorm/app/inference.py`.
- [x] T004 [P] [US1] Viết unit tests resolver/rollback và promotion artifact tại `tests/app/`.
- [x] T005 [US2] Cài đặt Gradio local trong `visolexnorm/app/web.py`: responsive UI, example input, clear action, callback an toàn, loopback-only và không share public.
- [x] T006 [P] [US2] Viết UI callback tests tại `tests/app/test_web_callbacks.py`.
- [x] T007 [US3] Viết integration test model cache, validation, Model C/Model B rollback và offline inference bằng stub tại `tests/app/test_local_inference.py`.
- [x] T008 [US3] Cài dependency và chạy CPU smoke test thật: nạp tokenizer/model, sinh kết quả không rỗng và kiểm tra rollback; cập nhật `outputs/app/model_c_promotion_smoke_test.json`. Model C nạp 518 weights, lượt đầu 19.888 giây, lượt cache 2.286 giây.
- [x] T009 [US3] Chạy `specs/006-local-inference-web/quickstart.md` trên laptop và nghiệm thu offline end-to-end: CLI Unicode, Gradio HTTP 200/callback, loopback-only và không public share.