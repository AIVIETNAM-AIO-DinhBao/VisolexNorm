# Kế hoạch triển khai: Review toàn bộ ViSoLex và huấn luyện Model C

## Phương án đã chọn

Tạo workstream độc lập `008-expanded-visolex-training` chạy song song Phase 6. Tái sử dụng
candidate và protocol đã được kiểm định ở Phase 3, chỉ review 48.411 ID chưa có review hợp lệ.
Pool mở rộng train Model C từ Model A theo mixture 1:1. Artifact dùng namespace riêng; không sửa
lịch sử Phase 3–5 và không nhân bản pipeline khi extension bằng config/manifest là đủ.

## Bằng chứng khởi động

| Kiểm tra | Giá trị |
|---|---:|
| Candidate unique | 68.411 |
| Manifest review Phase 3 unique | 20.000 |
| ID còn review | 48.411 |
| Weak label KEEP/EDIT Phase 3 | 18.970 |
| F1 Model A Phase 5 | 0,718184 |
| F1 Model B Phase 5 | 0,742215 |

48.411 mẫu tương ứng tối thiểu 3.228 request batch-15 thành công, chưa tính retry.

## Luồng song song

```text
Phase 5 ──→ Phase 6: app boundary ban đầu dùng Model B ───┐
       └──→ Phase 8A: review 48.411 ID còn lại (local)     │
                       → pool weak label mở rộng           │
                       → Phase 8B: train Model C (Kaggle)  │
                       → Dev-only report                   │
                        → Phase 9 hậu kiểm → Phase 10 app   │
                                                           └→ Phase 6 hoàn tất → Phase 7 đóng gói
```

Phase 6 không chờ Phase 8 và không import Gemini/training dependency. Boundary Model B ở đây là
quyết định trong thời gian Phase 8 chạy. Phase 9/10 về sau chọn Model C cho app với Model B
rollback. Phase 7 bắt đầu sau khi Phase 6 hoàn tất real offline smoke và Gradio acceptance.

## Cấu trúc tối thiểu

```text
configs/expanded_review_config.json
configs/model_c_config.json
scripts/select_remaining_review_manifest.py
scripts/build_expanded_weak_labels.py
scripts/build_model_c_mixture.py
scripts/train_model_c.py
notebooks/train_model_c_kaggle.ipynb
data/intermediate/visolex_remaining_review_manifest.jsonl
data/intermediate/visolex_expanded_review_cache.sqlite3
data/processed/visolex_weak_labeled_expanded.jsonl
outputs/expanded_review/
outputs/model_c/
checkpoints/model_c/
```

`review_candidates.py`, cache schema, key pool, validation và audit Phase 3 phải được tái sử
dụng qua config/path mới nếu interface hiện có đáp ứng yêu cầu. Chỉ tách module mới khi có một
khác biệt domain rõ ràng; không copy-paste pipeline Phase 3.

## Trình tự

### A. Review mở rộng trên local

1. Verify inventory checksum candidate, manifest Phase 3, cache, frozen prompt và policy.
2. Tạo manifest hiệu tập; assert `(68.411, 20.000, 48.411)`, unique và intersection bằng 0.
3. Dry-run mock API để kiểm tra batch, cache namespace, round-robin, retry và resume.
4. Chạy Gemini bằng identity Phase 3; không gửi lại ID cũ đã có review hợp lệ.
5. Reconcile từng ID thành valid decision hoặc approved provider exclusion.
6. Build/audit pool mở rộng; ghi distribution theo source, confidence, decision và provenance.

### B. Huấn luyện Model C trên Kaggle

1. Verify pool mở rộng và inventory Model A trước khi load model.
2. Tính `num_epochs = ceil(expanded_weak_label_count / 8372)` rồi freeze config/mixture manifest.
3. Mỗi epoch dùng mọi gold + 8.372 pseudo; ưu tiên ID chưa dùng, wrap deterministic ở epoch cuối
   nếu cần để giữ 1:1; optimizer/scheduler liên tục.
4. Smoke test 200 gold + 200 pseudo; xác nhận loss, generation và save/load.
5. Full run tới khi pseudo union phủ toàn pool; evaluate Dev mỗi epoch, chọn best Dev loss.
6. Export checkpoint, config/runtime/inventory/checksum, Dev artifacts và exit report.

### C. Cổng đánh giá và promotion

- Báo cáo Model B/Model C chỉ dùng Dev và ghi rõ không phải final Test comparison.
- Model C là thí nghiệm exploratory hậu kiểm; không sửa hoặc diễn giải lại kết luận A/B frozen
  của Phase 5 thành kết quả Model C.
- Không load ViLexNorm Test hoặc file `outputs/evaluation/` trong run Model C.
- Phase 8 không được tự thay checkpoint app. Phase 9/10 chịu trách nhiệm benchmark hậu kiểm,
  công bố caveat và quyết định Model C mặc định/Model B rollback. Holdout độc lập vẫn là yêu cầu
  nếu muốn kết luận khoa học cuối cùng mạnh hơn.

## Artifact bắt buộc

```text
outputs/expanded_review/remaining_manifest_report.json
outputs/expanded_review/review_stats.json
outputs/expanded_review/review_audit.jsonl
outputs/expanded_review/artifact_manifest.json
data/processed/visolex_weak_labeled_expanded.jsonl
outputs/model_c/training_mixture_manifest.json
outputs/model_c/smoke_test.json
outputs/model_c/dev_predictions.jsonl
outputs/model_c/dev_metrics.json
outputs/model_c/train_config.json
outputs/model_c/artifact_manifest.json
outputs/model_c/phase8_exit_report.json
checkpoints/model_c/
```

## Ràng buộc kỹ thuật

- LLM review chạy local; BARTpho train/batch inference chạy Kaggle GPU.
- API key không có trong source, notebook, log, cache, artifact hoặc Git.
- Tác vụ dài phải cache/resume; artifact ghi count, checksum, prompt/model identity và phân bố.
- Mọi sửa prompt, threshold hoặc hyperparameter phải là amendment trước run và không dựa Test.