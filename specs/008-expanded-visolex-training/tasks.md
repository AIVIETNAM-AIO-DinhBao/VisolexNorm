# Nhiệm vụ: Mở rộng LLM review và huấn luyện Model C

## Chặng 1 — Manifest, config và quality gate local

- [x] T001 [P] Tạo `configs/expanded_review_config.json` kế thừa immutable identity Phase 3. **Hoàn thành khi:** config ghi prompt/policy hash, batch 15, retry/cooldown, đường dẫn manifest/cache Phase 8 và không sửa `configs/llm_review_config.json`.
- [x] T002 [P] Tạo `configs/model_c_config.json`. **Hoàn thành khi:** config ghi Model A inventory, 8.372 gold/pseudo, hyperparameter Phase 4, công thức số epoch và cấm input Test/`outputs/evaluation/`.
- [x] T003 [US1] Cài đặt `scripts/select_remaining_review_manifest.py`. **Hoàn thành khi:** tạo `data/intermediate/visolex_remaining_review_manifest.jsonl` với đúng 48.411 ID; test assert candidate=68.411, old=20.000, intersection=0, union=68.411.
- [x] T004 [P] Viết contract/unit test tại `tests/unit/test_expanded_review_manifest.py`. **Hoàn thành khi:** test reject duplicate, old-manifest ID và candidate thiếu provenance; seed/order lặp lại cho kết quả giống nhau.

## Chặng 2 — Review và weak-label pool mở rộng local

- [x] T005 [US2] Mở rộng entrypoint `scripts/review_candidates.py` bằng config/path Phase 8, không copy pipeline. **Hoàn thành khi:** dùng `data/intermediate/visolex_expanded_review_cache.sqlite3`, resume đúng và không gửi lại ID Phase 3.
- [x] T006 [US2] Chạy mock integration test tại `tests/integration/test_expanded_llm_review.py`. **Hoàn thành khi:** assert batch 15, round-robin, cooldown/retry và resume trên manifest Phase 8.
- [x] T007 [US2] Chạy full review Phase 8 và export `outputs/expanded_review/review_stats.json`. **Hoàn thành khi:** mọi 48.411 ID có decision hợp lệ hoặc approved exclusion; không có secret trong cache/log/export.
- [x] T008 [US3] Cài đặt `scripts/build_expanded_weak_labels.py`. **Kết quả:** pool union unique có 64.813 record (18.970 Phase 3 + 45.843 Phase 8), chỉ KEEP/EDIT hợp lệ, không overlap Dev/Test; SHA-256 `8d0d7fda61fef5805d1d79c3ec9a7a09bf38c875123f21bdd1dad8d120d79386`.
- [x] T009 [US3] Audit pool tại `scripts/audit_weak_labels.py` qua input config mới. **Kết quả:** đã xuất `outputs/expanded_review/review_audit.jsonl` và frozen `artifact_manifest.json` với checksum/count/source/confidence/decision distribution, SHA-256 artifact Phase 3 và identity cache/prompt; không đổi schema `WeakLabelRecord`.

## Chặng 3 — Model C trên Kaggle GPU

- [x] T010 [P] Cài đặt unit test tại `tests/unit/test_model_c_mixture.py`. **Kết quả:** assert 1:1 mỗi epoch, seed `2026 + epoch_index`, coverage toàn pool và wrap deterministic chỉ ở epoch cuối.
- [x] T011 [US4] Cài đặt `scripts/build_model_c_mixture.py`. **Kết quả:** pool/Model A inventory đã verify; manifest 8 epoch đã xuất tại `outputs/model_c/training_mixture_manifest.json`, pseudo union đủ 64.813.
- [x] T012 [US4] Cài đặt `scripts/train_model_c.py` và `notebooks/train_model_c_kaggle.ipynb`. **Kết quả:** notebook run-all tại source revision `2c7646b`, runtime Tesla T4, không load Test và đã export `/kaggle/working`.
- [x] T013 [US4] Chạy smoke test 200 gold + 200 pseudo. **Kết quả:** generation, checkpoint save/load, Model A inventory và cờ `test_inputs_loaded=false` đều pass.
- [x] T014 [US4] Chạy full training Model C. **Kết quả:** đủ 8 epoch, pseudo union 64.813; checkpoint, 1.050 Dev predictions, metrics, config và 11 artifact đều khớp SHA-256.

## Chặng 4 — Dev-only nghiệm thu và ranh giới app

- [x] T015 [US5] Tạo `outputs/model_c/phase8_exit_report.json`. **Kết quả:** report Dev-only ghi best Dev loss `0,193742`, provenance, coverage, mọi checksum pass, `test_inputs_loaded=false` và không chứa Test metric/prediction.
- [ ] T016 [US5] Xác minh Phase 6 vẫn đọc `outputs/evaluation/best_model.json` Model B. **Hoàn thành khi:** smoke test app không đọc artifact Model C và kết quả ghi trong `outputs/inference_smoke_test.json`.

## Phụ thuộc

```text
T001–T004 → T005–T009 → T010–T014 → T015
Phase 6 chạy song song T001–T015; T016 chỉ chạy khi Phase 6 hoàn thành.
```