# Danh mục artifact release

## Vai trò model và bằng chứng

| Artifact | Vai trò | Trạng thái release |
|---|---|---|
| `checkpoints/model_c/` | Checkpoint app mặc định theo common Dev selection | Bắt buộc, Kaggle Dataset |
| `checkpoints/model_b/` | Fallback app theo common Dev ranking | Bắt buộc, Kaggle Dataset |
| `checkpoints/model_a/` | Candidate generator và provenance train | Local/external, không cần demo app |
| `outputs/evaluation/best_model.json` | Lựa chọn A/B bất biến: Model B | Bắt buộc |
| `outputs/evaluation_abc_posthoc/metrics.json` | Benchmark A/B/C hậu kiểm: Model C descriptive leader | Bắt buộc, có caveat |
| `outputs/evaluation_dev/model_metrics.json` | Common Dev metrics và ranking A/B/C | Bắt buộc |
| `outputs/app/model_selection.json` | Dev-based selection: Model C + Model B fallback | Bắt buộc |
| `release/training-closure.json` | Closure research: Model C/B app boundary, factorial freeze và C-max20 non-promotion | Bắt buộc |

Model C được chọn cho ứng dụng từ common Dev ERR, F1 và exact match. Artifact selection ghi rõ
`selection_split=dev` và `test_metrics_used_for_selection=false`; Test metrics chỉ dùng báo cáo kết quả.

## Phân phối

| Nhóm | Nơi giữ | Có trong Git | Ghi chú |
|---|---|---:|---|
| Code, config, prompt, notebook, docs | GitHub release tag | Có | Không có secret |
| Model C/B | Kaggle Dataset version cố định | Không | Verify inventory SHA-256 |
| Model A, raw candidate archive | Local/external backup | Không | Chỉ cần cho provenance/retrain |
| Raw/processed data và review cache | Local/private dataset | Không | Có hạn chế phân phối dữ liệu |
| Aggregated metrics, selection, smoke | Release manifest | Có hoặc handoff | Không chứa API key |

## Kaggle Dataset checkpoint

Slug release là `dinhbaobao/visolexnorm-app-checkpoints-v1`. Version đã verify là:

```text
https://www.kaggle.com/datasets/dinhbaobao/visolexnorm-app-checkpoints-v1/versions/1
```

Dataset chứa `checkpoints/model_c/`, `checkpoints/model_b/`, `model_selection.json` và inventory
export. Không upload `.env`, raw data, Gemini cache, prediction có dữ liệu restricted hoặc `.git`.

Checksum inventory app hiện hành dùng artifact ID, không render raw digest trong tài liệu:

| Checkpoint | Artifact ID | Role |
|---|---|---|
| Model C | `APP-DEFAULT` | Application default |
| Model B | `APP-FALLBACK` | Verified rollback |

## Controlled research closure

Artifact IDs và checksum segmented cho factorial/C-max20 nằm trong `release/training-closure.json`.
Không render raw local path hoặc raw full checksum trong tài liệu handoff; chạy
`python scripts/verify_training_closure.py` để verifier nối checksum segments và kiểm artifact.
L8 là factorial winner theo selected Dev-loss protocol. C-max20 là artifact exploratory, không
thuộc checkpoint Dataset app và không promotion Model C/B.

## Chính sách retention

Xem `docs/artifact-retention.json` để biết size/checksum và externalization status. Không xóa
checkpoint hoặc provenance ZIP khi `external_location` còn `null`. Clean-up chỉ áp dụng cho
`.pytest_cache`, `__pycache__` project và `.tmp` sau khi artifact đã verify.