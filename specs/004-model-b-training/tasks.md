# Nhiệm vụ: Huấn luyện Model B

- [x] T001 Đồng bộ quyết định sampler/runtime/training trong bộ tài liệu `specs/004-model-b-training/`
- [x] T002 [P] Tạo `configs/model_b_config.json` và mở rộng `contracts/train-config.schema.json`
- [x] T003 [P] Viết contract/unit tests tại `tests/contract/test_model_b_contracts.py` và `tests/unit/test_model_b_mixture.py`
- [x] T004 [US1] Cài đặt deterministic epoch sampler trong `scripts/build_model_b_mixture.py`
- [x] T005 [US1] Viết integration test và xuất `outputs/model_b/training_mixture_manifest.json`
- [x] T006 [US2] Cài đặt training/evaluation/export Model B trong `scripts/train_model_b.py`
- [x] T007 [US2] Tạo `notebooks/train_model_b_kaggle.ipynb`
- [x] T008 [US2] Chạy smoke test 200 gold + 200 pseudo trên Kaggle
- [x] T009 [US2] Chạy full training 3 epoch, lưu best checkpoint tại `checkpoints/model_b/`
- [x] T010 [US3] Xuất 1.050 Dev predictions/metrics/config vào `outputs/model_b/`
- [x] T011 [US3] Xác minh artifact manifest và ghi `outputs/model_b/phase4_exit_report.json`

## Trạng thái thực thi GPU

Đã đóng sau full Kaggle run. Checkpoint lớn được giữ ngoài Git thường; provenance và checksum
được ghi trong `outputs/model_b/`.