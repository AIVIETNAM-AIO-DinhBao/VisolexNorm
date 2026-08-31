# ViSoLexNorm

ViSoLexNorm là hệ thống chuẩn hóa từ vựng tiếng Việt mạng xã hội bằng BARTpho. Hệ thống xử lý viết tắt, teencode, slang, thiếu dấu và lỗi chính tả từ vựng; không được thiết kế để paraphrase, đổi sắc thái, tự kiểm duyệt hoặc thêm thông tin.

## Trạng thái release

- **Ứng dụng hiện tại:** Model C.
- **Rollback:** Model B.
- **Kết quả khoa học lịch sử Phase 5:** Model B thắng Model A trên ViLexNorm Test đóng băng.
- **Lưu ý Phase 9:** Model C dẫn đầu ở benchmark A/B/C hậu kiểm trên Test đã quan sát; đây không phải independent holdout và không thay đổi kết luận Phase 5.

Phase 6 local app đã hoàn thành. Phase 7 tạo release candidate; tag `v1.0.0` chỉ được tạo sau khi Kaggle Dataset checkpoint version cố định được upload, tải lại và strict verification pass.

## Pipeline thực tế

```text
ViLexNorm + ViSoLex
  → Model A trên Kaggle
  → candidate cho ViSoLex
  → Gemini review: KEEP / EDIT / REJECT
  → Model B trên Kaggle
  → A/B evaluation Phase 5 đóng băng
  ├→ review phần còn lại → Model C Dev-only → A/B/C hậu kiểm → app selection
  └→ local inference + Gradio
  → release
```

Xem [`docs/reproducibility.md`](docs/reproducibility.md) để biết lệnh và artifact của Phase 1–10.

## Dữ liệu và weak labels

### Phase 1

| Artifact/source | Số câu giữ lại |
|---|---:|
| ViLexNorm Train | 8.372 |
| ViLexNorm Dev | 1.050 |
| ViLexNorm Test | 1.045 |
| ViSoLex / ViHSD | 30.579 |
| ViSoLex / UIT-VSMEC | 6.916 |
| ViSoLex / ViHOS | 0 |
| ViSoLex / ViSpamReviews | 19.805 |
| ViSoLex / UIT-ViSFD | 11.111 |
| **ViSoLex canonical** | **68.411** |

ViHOS trùng exact với ViHSD đã được nạp trước nên global deduplication giữ provenance ViHSD và ViHOS có quota 0. Raw data, processed data và review cache bị ignore khỏi Git để bảo vệ quyền phân phối và dữ liệu nhạy cảm.

### Review và training

| Giai đoạn | Phạm vi | Kết quả |
|---|---:|---:|
| Phase 3 | 20.000 candidate | 18.970 weak labels accepted |
| Phase 8 | 48.411 candidate còn lại | 45.843 weak labels accepted |
| Pool Model C | union Phase 3 + 8 | 64.813 weak labels |

Mỗi candidate phải qua một trong ba quyết định: **KEEP** dùng candidate, **EDIT** dùng corrected text tối thiểu, **REJECT** bị loại khỏi training.

## Kết quả

### Phase 5 — A/B trên Test đóng băng

| Model | ERR | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Model A | 0.703037 | 0.733999 | 0.703037 | 0.718184 |
| Model B | 0.723847 | 0.761538 | 0.723847 | 0.742215 |

Model B là historical winner theo F1 cao hơn. Artifact bất biến là `outputs/evaluation/best_model.json`.

### Phase 9 — A/B/C hậu kiểm mô tả

| Model | F1 |
|---|---:|
| Model A | 0.718184 |
| Model B | 0.742215 |
| Model C | 0.764993 |

Model C cao hơn Model B `+0.022778` F1, bootstrap CI95 `[0.012063, 0.033228]`. Kết quả này dùng ViLexNorm Test đã quan sát nên không phải bằng chứng holdout độc lập. Phase 10 tạo selection artifact cho app: Model C mặc định, Model B rollback.

## Cài đặt theo môi trường

| Mục đích | Lệnh |
|---|---|
| Review/weak label local | `pip install -r requirements.txt` |
| App offline Model C/B | `pip install -r requirements-inference.txt` |
| Test/verifier | `pip install -r requirements-dev.txt` |
| Notebook Kaggle GPU | `pip install -r requirements-kaggle.txt` |

Tạo `.env` từ `.env.example` chỉ khi chạy Gemini review. File `.env` không được commit; inference và web app không đọc API key hay gọi Gemini.

## Chạy app local/offline

1. Tải Kaggle Dataset checkpoint version được ghi trong `release/manifest.json`.
2. Giải nén để có `checkpoints/model_c/` và `checkpoints/model_b/`.
3. Verify release:

```powershell
python scripts/verify_release.py --manifest release/manifest.json
```

4. Chạy CLI:

```powershell
python -m visolexnorm.app.inference --smoke
python -m visolexnorm.app.inference --text "mik ko bt hnay đi hc ko"
```

Kết quả smoke đã xác nhận:

```text
mình không biết hôm nay đi học không
```

5. Chạy Gradio local:

```powershell
python -m visolexnorm.app.web
```

App bind `127.0.0.1`, không public share. Sau khi dependency/checkpoint đã local, đặt `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1` để diễn tập offline.

## Tái lập pipeline

- Chuẩn bị data: `python -m scripts.data ...`
- Candidate: `python -m scripts.candidates ...`
- Review: `python -m scripts.reviews ...`
- Weak labels: `python -m scripts.weak_labels ...`
- Train: `python -m scripts.training ...`
- Evaluation: `python -m scripts.evaluation ...`

Notebook Kaggle nằm trong [`notebooks/`](notebooks/). Các checkpoint lớn không nằm trong Git; xem [`docs/artifact-catalog.md`](docs/artifact-catalog.md) và [`docs/artifact-retention.json`](docs/artifact-retention.json).

## Verify release và demo

```powershell
python scripts/verify_release.py --manifest release/manifest.json --report release/verification-report.json
python -m pytest -q
```

Sau khi Kaggle Dataset có URL version cố định, chạy thêm:

```powershell
python scripts/verify_release.py --manifest release/manifest.json --strict-distribution
```

Chỉ strict verification pass mới cho phép tạo tag `v1.0.0`. Kịch bản trình diễn offline nằm tại [`docs/demo-script.md`](docs/demo-script.md).