# ViSoLexNorm

ViSoLexNorm là hệ thống chuẩn hóa từ vựng tiếng Việt mạng xã hội bằng BARTpho. Hệ thống xử lý viết tắt, teencode, slang, thiếu dấu và lỗi chính tả từ vựng; không được thiết kế để paraphrase, đổi sắc thái, tự kiểm duyệt hoặc thêm thông tin.

## Trạng thái release

- **Ứng dụng hiện tại:** Model C.
- **Rollback:** Model B.
- **Kết quả khoa học lịch sử Phase 5:** Model B thắng Model A trên ViLexNorm Test đóng băng.
- **Lưu ý Phase 9:** Model C dẫn đầu ở benchmark A/B/C hậu kiểm trên Test đã quan sát; đây không phải independent holdout và không thay đổi kết luận Phase 5.

Phase 6 local app và Phase 7 release đã hoàn thành. Checkpoint Kaggle Dataset version 1 đã được tải lại, checksum đã verify và strict release verification pass; release được đánh dấu bằng tag `v1.0.0`.

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
| Phase 3 | 20.000 candidate | 18.970 LLM-reviewed weak labels accepted |
| Phase 8 | 48.411 candidate còn lại | 45.843 LLM-reviewed weak labels accepted |
| Pool Model C | union Phase 3 + 8 | 64.813 LLM-reviewed weak labels |

Mỗi candidate phải qua một trong ba quyết định: **KEEP** dùng candidate, **EDIT** dùng corrected text tối thiểu, **REJECT** bị loại khỏi training.
Reviewer là `gemini-3.5-flash-lite`, prompt `lexical_norm_review_v1`, temperature 0 và structured JSON schema. Đây không phải nhãn đã được con người xác minh toàn bộ.

## Kết quả

### Phase 5 — A/B trên Test đóng băng

| Model | ERR | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Model A | 0.600250 | 0.733999 | 0.703037 | 0.718184 |
| Model B | 0.633111 | 0.761538 | 0.723847 | 0.742215 |

Model B là historical winner theo F1 cao hơn. Artifact bất biến là `outputs/evaluation/best_model.json`.

### A/B/C trên common Test

| Model | ERR | F1 |
|---|---:|---:|
| Model A | 0.600250 | 0.718184 |
| Model B | 0.633111 | 0.742215 |
| Model C | 0.664725 | 0.764993 |

Model C được chọn trước bằng common Dev ERR (`0.670380`), Dev F1 (`0.759233`) và Dev exact match (`0.561905`). Test không tham gia model selection. Trên Test, Model C cao hơn Model B `+0.022778` F1, bootstrap CI95 `[0.012063, 0.033228]`. Model C là checkpoint app mặc định và Model B là fallback.

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
- Controlled factorial/optimization: `python -m scripts.controlled_experiments ...`
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

Kịch bản trình diễn offline nằm tại [`docs/demo-script.md`](docs/demo-script.md).