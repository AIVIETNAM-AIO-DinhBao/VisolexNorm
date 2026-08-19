# Nhiệm vụ: Đánh giá thực nghiệm

- [ ] T001 [US1] Cài đặt freeze/checksum gate trong `scripts/freeze_experiment.py`
- [ ] T002 [P] Viết contract test prediction tại `tests/contract/test_prediction_schema.py`
- [ ] T003 [US2] Cài đặt shared generation trong `scripts/generate_test_predictions.py`
- [ ] T004 [US2] Tạo `notebooks/evaluate_models_kaggle.ipynb`
- [ ] T005 [US2] Generate đủ 1.045 prediction cho mỗi model vào `outputs/evaluation/model_a_test_predictions.jsonl` và `outputs/evaluation/model_b_test_predictions.jsonl`
- [ ] T006 [US3] Port/tích hợp official metrics trong `scripts/evaluate_predictions.py`
- [ ] T007 [US3] Thêm fixture parity test tại `tests/unit/test_vilexnorm_metrics.py`
- [ ] T008 [US3] Cài đặt error categorization trong `scripts/build_error_analysis.py`
- [ ] T009 [US3] Xuất metrics, comparison, error analysis và best model vào `outputs/evaluation/`
- [ ] T010 [US3] Chạy `specs/005-experiment-evaluation/quickstart.md` và xác nhận checksum trong `outputs/evaluation/freeze_manifest.json` không đổi