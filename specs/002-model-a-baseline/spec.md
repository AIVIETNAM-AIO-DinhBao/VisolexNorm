# Đặc tả giai đoạn 2: Baseline Model A

**Trạng thái**: Hoàn thành
**Phụ thuộc**: `specs/001-data-preparation/spec.md`
**Phạm vi tài liệu**: Ghi nhận ngắn kết quả đã triển khai, không lập lại kế hoạch.

## Mục tiêu đã hoàn thành

Chuẩn bị quy trình fine-tune `vinai/bartpho-syllable` bằng ViLexNorm Train, lựa chọn
checkpoint bằng ViLexNorm Dev và xuất artifact có thể dùng làm baseline cũng như candidate
generator cho Phase 3.

## Thành phần hiện có

- `configs/model_a_config.json`: seed và siêu tham số đã chốt.
- `scripts/train_model_a.py`: quy trình tokenize, train, đánh giá Dev và export.
- `notebooks/train_model_a_kaggle.ipynb`: điểm chạy chính trên Kaggle GPU.
- `requirements-kaggle.txt`: dependency cho notebook.

## Cấu hình chính

- Mô hình: `vinai/bartpho-syllable`.
- Seed: `2026`.
- Độ dài source/target tối đa: 128 token.
- Learning rate: `3e-5`; epoch: 5.
- Batch train/eval: 8; gradient accumulation: 2.
- Beam search: 4; early stopping patience: 2.

## Artifact bắt buộc của một lần chạy thành công

```text
checkpoints/model_a/
outputs/model_a/dev_predictions.jsonl
outputs/model_a/dev_metrics.json
outputs/model_a/train_config.json
```

## Ranh giới sử dụng

- Model A là supervised baseline trên gold data.
- Trong Phase 3, Model A chỉ sinh `candidate_text` và confidence.
- Prediction Model A KHÔNG phải ground-truth và không được đưa thẳng vào Model B.
- Test không được dùng trong quá trình train hoặc chọn checkpoint Model A.

## Tiêu chí nghiệm thu

- Notebook chạy trên Kaggle GPU và export được checkpoint cùng Dev artifact.
- Checkpoint tải lại độc lập và generate được chuỗi hợp lệ.
- Cấu hình export khớp cấu hình dùng trong lần train đã chọn.