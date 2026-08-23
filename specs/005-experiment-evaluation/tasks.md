# Nhiệm vụ: Đánh giá thực nghiệm

## Chặng 1 — Freeze và quality gate local

- [x] T001 [US1] Cài đặt freeze/checksum gate trong `scripts/freeze_experiment.py`. **Hoàn thành khi:** tạo manifest `status="frozen"` có inventory SHA-256/bytes/path cho checkpoint A/B, Test, tokenizer, generation config, metric code và provenance Phase 3/4; seed 2026/rule chọn model được ghi; thiếu hoặc mismatch phải fail và không ghi đè manifest frozen.
- [x] T002 [P] [US1] Viết contract test PredictionRecord tại `tests/contract/test_prediction_schema.py`. **Hoàn thành khi:** xác nhận đủ 7 trường theo `contracts/prediction.schema.json`, enum model và format SHA-256; record thiếu/sai trường bị từ chối.
- [ ] T003 [P] [US3] Tích hợp hoặc port official ViLexNorm metric trong `scripts/evaluate_predictions.py` và thêm fixture parity test tại `tests/unit/test_vilexnorm_metrics.py`. **Trạng thái:** đã có port deterministic và fixture nội bộ; còn cần fixture/reference độc lập từ evaluator/protocol gốc để xác nhận parity 100% trước khi Test được dùng.

## Chặng 2 — Generation trên Kaggle GPU

- [x] T004 [US2] Cài đặt shared generation trong `scripts/generate_test_predictions.py`. **Hoàn thành khi:** script verify freeze manifest trước khi load Test, dùng generation canonical (beam 4, giới hạn 128, seed 2026), giữ test order và ghi 7 trường PredictionRecord cho từng model.
- [x] T005 [US2] Tạo `notebooks/evaluate_models_kaggle.ipynb`. **Hoàn thành khi:** notebook chạy từ đầu đến cuối trên Kaggle GPU, gọi shared generation cho A rồi B, không chứa secret/trạng thái ẩn và export JSONL vào `/kaggle/working`.
- [ ] T006 [US2] Generate và validate hai raw prediction tại `outputs/evaluation/model_a_test_predictions.jsonl` và `outputs/evaluation/model_b_test_predictions.jsonl`. **Phụ thuộc:** T001–T005. **Hoàn thành khi:** mỗi file có đúng 1.045 ID unique; schema, set/order ID, `input_text`, `target_text`, model/checksum/config-hash đều khớp Test và freeze manifest.

## Chặng 3 — Đánh giá, phân tích và nghiệm thu local

- [ ] T007 [US3] Hoàn thiện `scripts/evaluate_predictions.py` để revalidate raw predictions, xuất `outputs/evaluation/test_metrics.json`, `comparison.md` và `best_model.json`. **Hoàn thành khi:** báo cáo có ERR/Precision/Recall/F1, checksum prediction/mã metric và áp dụng đúng F1 → ERR → Model A giữa hai model đã freeze.
- [ ] T008 [US3] Cài đặt error categorization trong `scripts/build_error_analysis.py`. **Hoàn thành khi:** `outputs/evaluation/error_analysis.jsonl` gán đúng một nhãn chính cho mỗi prediction theo precedence được ghi trong docstring, giữ toàn bộ lỗi và tạo audit tối đa 100 lỗi/model theo thứ tự ID.
- [ ] T009 [US3] Chạy `specs/005-experiment-evaluation/quickstart.md` và nghiệm thu Phase 5. **Phụ thuộc:** T006–T008. **Hoàn thành khi:** metrics tái tạo từ raw predictions, checksum `freeze_manifest.json` không đổi, toàn bộ quality gate pass và artifact Phase 5 sẵn sàng cho Phase 6.