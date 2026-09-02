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

Sau khi có Dev predictions của A/B/C, chạy `python -m scripts.evaluation dev-score` rồi
`python -m scripts.evaluation dev-select`. Common Dev ERR chọn Model C và Model B làm fallback;
Test metrics không tham gia selection. Test predictions sau đó chỉ dùng báo cáo kết quả A/B/C.

### Controlled factorial and C-max20-ES — Dev-only follow-up

The historical Model B/C artifacts remain immutable. The controlled follow-up uses a separate
namespace and never receives ViLexNorm Test or `outputs/evaluation/` as an input.

1. Create a private Kaggle Dataset (or `controlled_training_input.zip`) with exactly:

   ```text
   checkpoints/model_a/
   data/processed/vilexnorm_train.jsonl
   data/processed/vilexnorm_dev.jsonl
   data/processed/visolex_weak_labeled.jsonl
   data/processed/visolex_weak_labeled_expanded.jsonl
   ```

   Do not include `vilexnorm_test.jsonl`, raw data, or `outputs/evaluation/`.

2. Commit the controlled-experiment source, then run
   `notebooks/controlled_factorial_kaggle.ipynb` on a Kaggle GPU. It freezes a protocol and
   executes the small/expanded paired trajectories for seeds `2026`, `2126`, and `2226` to a
   fixed eight-epoch horizon without early stopping. It exports Dev predictions for horizon 3
   and horizon 8 and a Dev-only factorial summary.

3. Download `controlled_factorial_protocol.json`, `controlled_factorial_summary.json`, and
   `controlled_factorial_artifacts.zip`. The factorial archive intentionally excludes large
   model weights and resumable optimizer states; the frozen source revision, Model A inventory,
   input checksums, and mixture manifests make a trajectory reconstructible.

4. Freeze the factorial conclusion before running
   `notebooks/c_max20_early_stopping_kaggle.ipynb`. This fresh exploratory run starts again from
   Model A on the expanded pool, has a maximum of 20 epochs, requires at least 8 epochs, and
   stops only after four non-improving Dev-loss epochs with `min_delta=1e-4`. It is not a
   factorial cell and must not be used to revise the causal factorial conclusion.

The factorial notebook uses disk-safe `--no-resume-state`: it runs one trajectory at a time,
exports the required Dev artifacts, then safely removes its large checkpoint and AdamW state.
Attach the Kaggle Dataset as an unpacked directory rather than a ZIP, so Model A and data remain
under `/kaggle/input` and are never duplicated into `/kaggle/working`. If a disk-safe trajectory
is interrupted, reset only that incomplete trajectory and restart it from epoch 1; do not use
`--resume`. The C-max20 notebook retains resumable state by default because it is a single run;
if disk is constrained, use the same no-resume trade-off deliberately.

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