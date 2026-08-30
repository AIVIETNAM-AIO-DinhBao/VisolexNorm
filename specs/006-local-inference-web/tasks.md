# Nhiệm vụ: Local inference và Gradio

- [x] T001 [P] Tạo dependency/config local. **Kết quả Phase 10:** `requirements-inference.txt` và `configs/app_inference_config.json`.
- [x] T002 [US1] Cài đặt inventory verification và lazy model loader. **Kết quả Phase 10:** `visolexnorm/app/selection.py`, `loader.py` với Model C default/Model B rollback.
- [x] T003 [US1] Cài đặt validation, `normalize` và CLI. **Kết quả Phase 10:** `visolexnorm/app/inference.py`.
- [x] T004 [P] [US1] Viết unit tests resolver/rollback và promotion artifact tại `tests/app/`.
- [ ] T005 [US2] Cài đặt Gradio local trong `visolexnorm/app/web.py`.
- [ ] T006 [P] [US2] Viết UI callback tests tại `tests/app/test_web_callbacks.py`.
- [ ] T007 [US3] Viết integration test model cache và offline inference tại `tests/app/test_local_inference.py`.
- [ ] T008 [US3] Cài dependency và chạy CPU smoke test thật: nạp tokenizer/model, sinh kết quả không rỗng và kiểm tra rollback; cập nhật `outputs/app/model_c_promotion_smoke_test.json`.
- [ ] T009 [US3] Chạy `specs/006-local-inference-web/quickstart.md` trên laptop và ghi nghiệm thu offline end-to-end.