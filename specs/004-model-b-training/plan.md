# Kế hoạch triển khai: Huấn luyện Model B

## Bối cảnh

- Python/PyTorch/Transformers theo Kaggle runtime và được ghi vào artifact. Môi trường tham
  chiếu đã tạo Model A là Python 3.12.13, PyTorch 2.10.0+cu128, Transformers 5.0.0.
- Input frozen: ViLexNorm Train/Dev, 18.970 accepted weak labels, checkpoint Model A và
  `outputs/phase3_manifest.json` đã verify đủ checksum.
- Notebook: `notebooks/train_model_b_kaggle.ipynb`.
- Config: `configs/model_b_config.json`.

## Kiểm tra hiến chương

Đạt: training trên Kaggle; Test không được load; provenance/config/checksum được export;
không gọi LLM; tỷ lệ và siêu tham số đã chốt.

## Thực hiện

1. `scripts/build_model_b_mixture.py` verify Phase 3 manifest/checksum, validate weak labels,
   tạo manifest 3 epoch tỷ lệ 1:1 bằng seed 2026/2027/2028, ưu tiên pseudo chưa dùng.
2. `scripts/train_model_b.py` load checkpoint/tokenizer Model A đã verify, giữ optimizer và
   scheduler liên tục nhưng tạo DataLoader mới cho mixture của từng epoch.
3. Notebook chạy smoke test 400 mẫu = 200 gold + 200 pseudo, kiểm tra loss/generation/save-load.
4. Notebook chạy đủ 3 epoch, evaluate Dev mỗi epoch, lưu best checkpoint theo Dev loss.
5. Generate toàn bộ Dev bằng best checkpoint và xuất metrics/config/manifest.

## Artifact

```text
checkpoints/model_b/
outputs/model_b/dev_predictions.jsonl
outputs/model_b/dev_metrics.json
outputs/model_b/train_config.json
outputs/model_b/training_mixture_manifest.json
outputs/model_b/smoke_test.json
outputs/model_b/artifact_manifest.json
```

Nếu Model B kém Model A rõ rệt trên Dev, trước tiên audit weak labels; lần chạy bổ sung duy
nhất được phép là tỷ lệ 2:1 nghiêng về gold. Quyết định rerun phải ghi thành amendment trong
`research.md`; không được thay đổi dựa trên Test.