# Nhiệm vụ: Huấn luyện Model B

- [ ] T001 [P] Tạo `configs/model_b_config.json` theo siêu tham số đã chốt
- [ ] T002 [P] Viết test sampler 1:1 tại `tests/unit/test_model_b_mixture.py`
- [ ] T003 [US1] Cài đặt deterministic epoch sampler trong `scripts/build_model_b_mixture.py`
- [ ] T004 [US1] Xuất và validate `outputs/model_b/training_mixture_manifest.json`
- [ ] T005 [US2] Cài đặt training/evaluation Model B trong `scripts/train_model_b.py`
- [ ] T006 [US2] Tạo `notebooks/train_model_b_kaggle.ipynb`
- [ ] T007 [US2] Chạy smoke test 400 mẫu và ghi kết quả save/load vào `outputs/model_b/smoke_test.json`
- [ ] T008 [US2] Chạy full training và lưu best checkpoint chọn bằng Dev tại `checkpoints/model_b/`
- [ ] T009 [US3] Xuất checkpoint, Dev predictions/metrics và train config vào `checkpoints/model_b/` và `outputs/model_b/`
- [ ] T010 [US3] Chạy quickstart và ghi checksum vào `outputs/model_b/artifact_manifest.json`