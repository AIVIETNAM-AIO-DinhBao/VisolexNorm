# Nhiệm vụ: Huấn luyện Model B

- [x] T001 Đồng bộ quyết định sampler/runtime/training trong bộ tài liệu `specs/004-model-b-training/`
- [x] T002 [P] Tạo `configs/model_b_config.json` và mở rộng `contracts/train-config.schema.json`
- [x] T003 [P] Viết contract/unit tests tại `tests/contract/test_model_b_contracts.py` và `tests/unit/test_model_b_mixture.py`
- [x] T004 [US1] Cài đặt deterministic epoch sampler trong `scripts/build_model_b_mixture.py`
- [x] T005 [US1] Viết integration test và xuất `outputs/model_b/training_mixture_manifest.json`
- [x] T006 [US2] Cài đặt training/evaluation/export Model B trong `scripts/train_model_b.py`
- [x] T007 [US2] Tạo `notebooks/train_model_b_kaggle.ipynb`
- [ ] T008 [US2] Chạy smoke test 200 gold + 200 pseudo và ghi `outputs/model_b/smoke_test.json`
- [ ] T009 [US2] Chạy full training 3 epoch, lưu best checkpoint tại `checkpoints/model_b/`
- [ ] T010 [US3] Xuất Dev predictions/metrics/config vào `outputs/model_b/`
- [ ] T011 [US3] Chạy quickstart, ghi `artifact_manifest.json` và lập Phase 4 exit report

## Trạng thái thực thi GPU

T008–T011 là runtime gates trên Kaggle GPU, không được đánh dấu hoàn thành chỉ bằng kiểm thử
local. Mã nguồn, contract, notebook và 41 kiểm thử local đã sẵn sàng; người thực nghiệm phải
chạy smoke gate trước full run rồi tải artifact về để nghiệm thu các task còn lại.