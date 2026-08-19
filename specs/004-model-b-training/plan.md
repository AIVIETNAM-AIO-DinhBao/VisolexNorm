# Kế hoạch triển khai: Huấn luyện Model B

## Bối cảnh

- Python 3.11, Transformers/PyTorch; chạy Kaggle GPU.
- Input: ViLexNorm Train/Dev, accepted weak labels, checkpoint Model A.
- Notebook: `notebooks/train_model_b_kaggle.ipynb`.
- Config: `configs/model_b_config.json`.

## Kiểm tra hiến chương

Đạt: training trên Kaggle; Test không được load; provenance/config/checksum được export;
không gọi LLM; tỷ lệ và siêu tham số đã chốt.

## Thực hiện

1. `scripts/build_model_b_mixture.py` validate weak labels, tạo manifest 3 epoch tỷ lệ 1:1.
2. `scripts/train_model_b.py` dùng chung pipeline seq2seq của Model A nhưng load checkpoint A.
3. Notebook chạy smoke test 400 mẫu, kiểm tra loss/generation/save-load.
4. Notebook chạy full train, evaluate Dev mỗi epoch, lưu best checkpoint theo Dev loss.
5. Generate toàn bộ Dev bằng best checkpoint và xuất metrics/config/manifest.

## Artifact

```text
checkpoints/model_b/
outputs/model_b/dev_predictions.jsonl
outputs/model_b/dev_metrics.json
outputs/model_b/train_config.json
outputs/model_b/training_mixture_manifest.json
```

Nếu Model B kém Model A rõ rệt trên Dev, trước tiên audit weak labels; lần chạy bổ sung duy
nhất được phép là tỷ lệ 2:1 nghiêng về gold. Quyết định rerun phải ghi thành amendment trong
`research.md`; không được thay đổi dựa trên Test.