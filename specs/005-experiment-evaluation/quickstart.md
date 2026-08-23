# Nghiệm thu nhanh Phase 5

1. Sau khi có hai checkpoint local, tạo freeze manifest **trước khi** gắn Test vào Kaggle:
   ```powershell
   python scripts/freeze_experiment.py --model-a-checkpoint checkpoints/model_a --model-b-checkpoint checkpoints/model_b
   ```
   Xác nhận manifest có `status="frozen"`, tokenizer contract chung và inventory checksum hợp lệ. Không ghi đè manifest; khi cần kiểm tra lại, chạy cùng lệnh thêm `--verify`.
2. Chạy `python -m pytest tests/contract/test_prediction_schema.py tests/unit/test_vilexnorm_metrics.py tests/unit/test_freeze_experiment.py tests/unit/test_generate_test_predictions.py -q`; chỉ tiếp tục khi contract và fixture parity nội bộ đều pass. **Lưu ý:** port metric đang chờ fixture/reference độc lập trước khi công bố metric Test.
3. Chạy toàn bộ `notebooks/evaluate_models_kaggle.ipynb` trên GPU; notebook phải verify manifest trước khi load Test và export hai JSONL từ `/kaggle/working`.
4. Tải hai prediction JSONL về local vào `outputs/evaluation/`, chạy `python scripts/evaluate_predictions.py` rồi `python scripts/build_error_analysis.py`.
5. Kiểm tra mỗi model có đúng 1.045 ID unique, schema/set/order/input/target khớp Test, đủ bốn metric, `comparison.md`, `best_model.json`, `error_analysis.jsonl` và `error_audit.json`. Template mới dùng F1 cao hơn → ERR (Error Reduction Rate) cao hơn → Model A; lượt Test lịch sử luôn theo rule đã freeze trong manifest.
6. Chạy lại evaluation từ raw predictions; xác nhận checksum `freeze_manifest.json` không đổi trước khi đánh dấu Phase 5 hoàn thành.