# Nhiệm vụ: Local inference và Gradio

- [ ] T001 [P] Tạo dependency local và `configs/inference_config.json`
- [ ] T002 [US1] Cài đặt checksum và lazy model loader trong `app/model_loader.py`
- [ ] T003 [US1] Cài đặt validation, normalize và CLI trong `app/inference.py`
- [ ] T004 [P] [US1] Viết unit tests tại `tests/unit/test_inference_validation.py`
- [ ] T005 [US2] Cài đặt Gradio local trong `app/web.py`
- [ ] T006 [P] [US2] Viết UI callback tests tại `tests/unit/test_web_callbacks.py`
- [ ] T007 [US3] Viết integration test cache/offline tại `tests/integration/test_local_inference.py`
- [ ] T008 [US3] Chạy smoke test best checkpoint và xuất `outputs/inference_smoke_test.json`
- [ ] T009 [US3] Chạy `specs/006-local-inference-web/quickstart.md` trên laptop và ghi kết quả offline vào `outputs/inference_smoke_test.json`