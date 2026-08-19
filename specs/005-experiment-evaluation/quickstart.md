# Nghiệm thu nhanh Phase 5

1. Chạy `python scripts/freeze_experiment.py` trước khi gắn Test vào Kaggle.
2. Chạy toàn bộ `notebooks/evaluate_models_kaggle.ipynb` trên GPU.
3. Tải hai prediction JSONL về local.
4. Chạy `python scripts/evaluate_predictions.py` và `python scripts/build_error_analysis.py`.
5. Kiểm tra mỗi model có 1.045 ID, metric đủ và `best_model.json` theo rule đã freeze.