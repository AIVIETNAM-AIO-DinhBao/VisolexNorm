# Nhiệm vụ: Đánh giá thực nghiệm

## Chặng 1 — Freeze và quality gate local

- [x] T001 [US1] Cài đặt freeze/checksum gate trong `scripts/freeze_experiment.py`. **Hoàn thành khi:** tạo manifest `status="frozen"` có inventory SHA-256/bytes/path cho checkpoint A/B, Test, tokenizer, generation config, metric code và provenance Phase 3/4; seed 2026/rule chọn model được ghi; thiếu hoặc mismatch phải fail và không ghi đè manifest frozen.
- [x] T002 [P] [US1] Viết contract test PredictionRecord tại `tests/contract/test_prediction_schema.py`. **Hoàn thành khi:** xác nhận đủ 7 trường theo `contracts/prediction.schema.json`, enum model và format SHA-256; record thiếu/sai trường bị từ chối.
- [ ] T003 [P] [US3] Tích hợp hoặc port official ViLexNorm metric trong `scripts/evaluate_predictions.py` và thêm fixture parity test tại `tests/unit/test_vilexnorm_metrics.py`. **Trạng thái:** đã có port deterministic và fixture nội bộ; còn cần fixture/reference độc lập từ evaluator/protocol gốc để xác nhận parity 100% trước khi Test được dùng.

## Chặng 2 — Generation trên Kaggle GPU

- [x] T004 [US2] Cài đặt shared generation trong `scripts/generate_test_predictions.py`. **Hoàn thành khi:** script verify freeze manifest trước khi load Test, dùng generation canonical (beam 4, giới hạn 128, seed 2026), giữ test order và ghi 7 trường PredictionRecord cho từng model.
- [x] T005 [US2] Tạo `notebooks/evaluate_models_kaggle.ipynb`. **Hoàn thành khi:** notebook chạy từ đầu đến cuối trên Kaggle GPU, gọi shared generation cho A rồi B, không chứa secret/trạng thái ẩn và export JSONL vào `/kaggle/working`.
- [x] T006 [US2] Generate và validate hai raw prediction tại `outputs/evaluation/model_a_test_predictions.jsonl` và `outputs/evaluation/model_b_test_predictions.jsonl`. **Kết quả:** hai file đều có 1.045 ID unique, schema/set/order/input/target/model/checksum/config-hash khớp Test và `freeze_manifest.json`.

## Chặng 3 — Đánh giá, phân tích và nghiệm thu local

- [x] T007 [US3] Hoàn thiện `scripts/evaluate_predictions.py` để revalidate raw predictions, xuất `outputs/evaluation/test_metrics.json`, `comparison.md` và `best_model.json`. **Kết quả:** Model B được chọn theo F1 (`0.742215` so với `0.718184`), trước khi ERR tie-break lịch sử được kích hoạt.
- [x] T008 [US3] Cài đặt error categorization trong `scripts/build_error_analysis.py`. **Kết quả:** `error_analysis.jsonl` chứa 1.045 record với một nhãn chính/model; `error_audit.json` chứa tối đa 100 lỗi/model theo thứ tự prediction ID.
- [x] T009 [US3] Chạy `specs/005-experiment-evaluation/quickstart.md` và nghiệm thu Phase 5. **Kết quả:** 41 tests pass; metrics/analysis tái tạo từ raw predictions; SHA-256 manifest và raw predictions không đổi sau replay; Phase 5 artifact sẵn sàng cho Phase 6. **Ngoại lệ được ghi nhận:** T003 vẫn chờ fixture/reference metric độc lập, nên metric port được đánh dấu provisional trong `metric_reference.json`.