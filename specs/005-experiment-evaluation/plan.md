# Kế hoạch triển khai: Đánh giá A/B

## Công cụ và môi trường

- `scripts/freeze_experiment.py`: local, tạo freeze manifest.
- `notebooks/evaluate_models_kaggle.ipynb`: Kaggle GPU, chỉ generate predictions.
- `scripts/evaluate_predictions.py`: local, official metric protocol.
- `scripts/build_error_analysis.py`: local, tạo dataset và sample audit.

## Trình tự

1. Validate Dev artifacts và tạo `outputs/evaluation/freeze_manifest.json`.
2. Khóa manifest; notebook từ chối chạy nếu checksum đầu vào không khớp.
3. Generate A rồi B trên cùng Test/order/config và export JSONL.
4. Local validate 1.045 ID mỗi model và alignment với Test.
5. Tính metric, tạo bảng kết quả và error analysis.
6. Chọn best checkpoint theo F1 → ERR → Model A.

## Artifact

```text
outputs/evaluation/freeze_manifest.json
outputs/evaluation/model_a_test_predictions.jsonl
outputs/evaluation/model_b_test_predictions.jsonl
outputs/evaluation/test_metrics.json
outputs/evaluation/comparison.md
outputs/evaluation/error_analysis.jsonl
outputs/evaluation/best_model.json
```