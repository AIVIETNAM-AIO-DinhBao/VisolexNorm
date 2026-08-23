# Nghiệm thu nhanh Phase 8

1. Chạy test manifest/review/mixture local:

```bash
pytest tests/unit/test_expanded_review_manifest.py tests/integration/test_expanded_llm_review.py tests/unit/test_model_c_mixture.py
```

2. Tạo manifest 48.411 ID và xác minh report count/union/intersection:

```bash
python scripts/select_remaining_review_manifest.py --config configs/expanded_review_config.json
```

3. Chạy review local bằng secret Gemini đã cấu hình, có thể resume từ cache Phase 8:

```bash
python scripts/review_candidates.py --config configs/expanded_review_config.json
python scripts/build_expanded_weak_labels.py --config configs/expanded_review_config.json
```

4. Sau audit pool pass, chạy `notebooks/train_model_c_kaggle.ipynb` từ đầu đến cuối trên Kaggle.
Xác nhận output ở `/kaggle/working`, tải `checkpoints/model_c/` và `outputs/model_c/` về local.

5. Xác nhận `phase8_exit_report.json` ghi `test_inputs_loaded=false`. Không chạy evaluator Test
Phase 5, không sửa `outputs/evaluation/best_model.json`, và giữ app Phase 6 trên Model B.