# Danh mục artifact release

## Vai trò model và bằng chứng

| Artifact | Vai trò | Trạng thái release |
|---|---|---|
| `checkpoints/model_c/` | Checkpoint app mặc định theo Phase 10 | Bắt buộc, Kaggle Dataset |
| `checkpoints/model_b/` | Rollback app và historical winner Phase 5 | Bắt buộc, Kaggle Dataset |
| `checkpoints/model_a/` | Candidate generator và provenance train | Local/external, không cần demo app |
| `outputs/evaluation/best_model.json` | Lựa chọn A/B bất biến: Model B | Bắt buộc |
| `outputs/evaluation_abc_posthoc/metrics.json` | Benchmark A/B/C hậu kiểm: Model C descriptive leader | Bắt buộc, có caveat |
| `outputs/app/model_selection.json` | Quyết định app: Model C + Model B rollback | Bắt buộc |

Phase 9 dùng ViLexNorm Test đã quan sát, nên không phải independent holdout. Model C được chọn
cho ứng dụng theo artifact Phase 10; điều đó không sửa historical Phase 5 selection của Model B.

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

Checksum inventory app hiện hành:

| Checkpoint | Inventory SHA-256 |
|---|---|
| Model C | `e2f4b33dae20b2ed86a2b51d163b3cbe2063fbc24dc9b4a4e0cfe774f69fa622` |
| Model B | `0361cfab6bad4b6e4d95367f5125320fb61d6d3327b92481d0a31a937140d0b7` |

## Chính sách retention

Xem `docs/artifact-retention.json` để biết size/checksum và externalization status. Không xóa
checkpoint hoặc provenance ZIP khi `external_location` còn `null`. Clean-up chỉ áp dụng cho
`.pytest_cache`, `__pycache__` project và `.tmp` sau khi artifact đã verify.