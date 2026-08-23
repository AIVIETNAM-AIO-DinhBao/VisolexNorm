# Kế hoạch triển khai: Đánh giá A/B

## Phương án đã chọn

Freeze mọi đầu vào local, generate hai prediction bằng một module dùng chung trên Kaggle GPU, rồi validate/đánh giá/error analysis tại local. Test chỉ được mở sau khi freeze manifest thành công. Phase 5 chỉ chọn **Model A hoặc Model B đã freeze**, không chọn checkpoint mới.

## Công cụ và môi trường

- `scripts/freeze_experiment.py`: local; kiểm tra artifact đầu vào và tạo manifest bất biến.
- `scripts/generate_test_predictions.py`: module/script dùng chung; kiểm tra manifest rồi generate theo một config canonical.
- `notebooks/evaluate_models_kaggle.ipynb`: Kaggle GPU; chạy module chung cho Model A rồi Model B và export JSONL tại `/kaggle/working`.
- `scripts/evaluate_predictions.py`: local; validate prediction và tính official ViLexNorm metrics.
- `scripts/build_error_analysis.py`: local; tạo phân loại lỗi và mẫu audit deterministic.

## Freeze contract

`outputs/evaluation/freeze_manifest.json` có `status: "frozen"`, seed `2026`, timestamp, rule chọn Model A/B và inventory (relative path, bytes, SHA-256) cho checkpoint A/B, ViLexNorm Test, tokenizer contract, generation config, metric implementation và provenance Phase 3/4. Manifest không được ghi đè; mọi checksum mismatch phải fail trước khi Test được load.

Generation canonical dùng beam 4, giới hạn 128 token, cùng thứ tự Test và cùng tokenizer contract cho hai model. Mỗi prediction bắt buộc tuân thủ `contracts/prediction.schema.json`.

## Trình tự

1. Local: xác minh output Phase 4 và tạo freeze manifest.
2. Local: contract test PredictionRecord và parity fixture cho official metric/port phải pass.
3. Kaggle GPU: đọc/verify manifest, generate A rồi B theo cùng Test/order/config, export raw JSONL.
4. Local: validate schema, đúng 1.045 ID unique, cùng set/order và `input_text`/`target_text` khớp Test.
5. Local: tính ERR, Precision, Recall, F1; xuất so sánh và chọn best model theo F1 → ERR → Model A.
6. Local: tạo error analysis đầy đủ và audit deterministic theo thứ tự ID; replay quickstart để xác nhận checksum manifest không đổi và metrics tái tạo được.

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