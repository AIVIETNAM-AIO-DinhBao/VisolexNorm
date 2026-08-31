# Tái lập ViSoLexNorm

## Mục tiêu và ranh giới

Tài liệu này mô tả luồng artifact đã tạo ra bản release, không yêu cầu chạy lại toàn bộ train
trên laptop. Train/generate BARTpho theo lô chạy trên Kaggle GPU; chuẩn bị dữ liệu, review,
kiểm tra checksum, inference và Gradio chạy local. Seed mặc định là `2026`.

```text
001 dữ liệu → 002 Model A → 003 candidate + review → 004 Model B → 005 A/B freeze
                                                       ├→ 008 Model C Dev-only → 009 hậu kiểm → 010 app selection
                                                       └→ 006 local inference/Gradio → 007 release
```

Phase 5 là so sánh A/B lịch sử trên ViLexNorm Test đã freeze. Phase 9 dùng chính Test đã quan
sát nên chỉ là benchmark hậu kiểm mô tả; nó không thay thế kết luận khoa học Phase 5.

## Môi trường

| Công việc | Môi trường | Dependency |
|---|---|---|
| Chuẩn bị dữ liệu, review Gemini, weak-label audit | Local | `requirements.txt` |
| Model A/B/C, candidate batch, prediction batch | Kaggle GPU | `requirements-kaggle.txt` |
| App CPU/Gradio offline | Local | `requirements-inference.txt` |
| Test và verify release | Local | `requirements-dev.txt` |

Checkpoint runtime dùng Model C mặc định và Model B rollback. Tải chúng từ Kaggle Dataset được
ghi trong `release/manifest.json`, đặt đúng tại `checkpoints/model_c/` và `checkpoints/model_b/`,
rồi chạy verifier trước inference.

## Luồng đã chạy

### Phase 1 — dữ liệu

```powershell
python -m scripts.data prepare-vilexnorm --train data/raw/vilexnorm/train.csv --dev data/raw/vilexnorm/dev.csv --test data/raw/vilexnorm/test.csv --input-field original --target-field normalized
python -m scripts.data prepare-visolex --source ViHSD data/raw/visolex/ViHSD.csv free_text --source UIT-VSMEC data/raw/visolex/UIT-VSMEC.csv Sentence --source ViHOS data/raw/visolex/ViHOS.csv sentence --source ViSpamReviews data/raw/visolex/ViSpamReviews.csv Comment --source UIT-ViSFD data/raw/visolex/UIT-ViSFD.csv comment
python -m scripts.data validate
```

Artifact canonical có 8.372 Train, 1.050 Dev, 1.045 Test và 68.411 câu ViSoLex. ViHOS có 0 câu
giữ lại vì toàn bộ exact-duplicate ViHSD được nạp trước; raw vẫn giữ local để audit.

### Phase 2–4 — Model A, review và Model B

Chạy `notebooks/train_model_a_kaggle.ipynb` trên Kaggle GPU để tạo Model A. Sinh candidate toàn
bộ corpus trên Kaggle, sau đó local chọn review manifest 20.000 ID, chạy pilot/freeze prompt và
review đầy đủ:

```powershell
python -m scripts.candidates select-review --candidates data/intermediate/visolex_model_a_candidates.jsonl --config configs/llm_review_config.json
python -m scripts.reviews run --mode pilot --config configs/llm_review_config.json
python -m scripts.reviews freeze-prompt --pilot-report outputs/pilot_review_report.json --approved
python -m scripts.reviews run --mode full --config configs/llm_review_config.json
```

Chạy `notebooks/train_model_b_kaggle.ipynb` với artifact review đã freeze. Model B dùng 18.970
weak labels accepted, 3 epoch, mixture gold:pseudo 1:1 và chỉ dùng Train/Dev.

### Phase 5 — evaluation A/B đóng băng

```powershell
python -m scripts.evaluation verify-freeze
python -m scripts.evaluation score
python -m scripts.evaluation analyze-errors
```

Không sửa `outputs/evaluation/best_model.json`, `freeze_manifest.json`, raw prediction hoặc
`scripts/evaluation_metrics.py` khi tái lập/release.

### Phase 8–10 — Model C và app selection

Phase 8 review 48.411 ID còn lại, có 5 approved provider exclusions và tạo pool 64.813 weak
labels. `notebooks/train_model_c_kaggle.ipynb` chạy Dev-only, không nhận Test làm input.

Phase 9 sinh một prediction Model C trên Test đã quan sát và score hậu kiểm. Phase 10 dùng
artifact này để tạo `outputs/app/model_selection.json`; app dùng Model C, Model B giữ rollback.

### Phase 6 — local app

```powershell
python -m visolexnorm.app.inference --smoke
python -m visolexnorm.app.inference --text "mik ko bt hnay đi hc ko"
python -m visolexnorm.app.web
```

Sau khi dependency/checkpoint đã local, đặt `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1` để
xác minh app không cần mạng.

## Cổng release

```powershell
python scripts/verify_release.py --manifest release/manifest.json --report release/verification-report.json
python -m pytest -q
python -m scripts.evaluation verify-freeze
```

Thêm `--strict-distribution` chỉ sau khi Kaggle Dataset có URL version cố định. Lệnh strict là
điều kiện gắn tag `v1.0.0`.