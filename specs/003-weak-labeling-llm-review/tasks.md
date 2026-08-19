# Nhiệm vụ: Tạo nhãn yếu bằng Model A và LLM reviewer

## Nhóm 1 — Hạ tầng và hợp đồng

- [x] T001 Thêm dependency local và test vào `requirements.txt` và giữ dependency GPU trong `requirements-kaggle.txt`
- [x] T002 [P] Tạo cấu hình sinh candidate tại `configs/candidate_generation_config.json`
- [x] T003 [P] Tạo cấu hình manifest/review/validation tại `configs/llm_review_config.json`
- [x] T004 [P] Viết prompt reviewer 15 mẫu tại `prompts/lexical_norm_review_draft.txt`
- [x] T005 [P] Tạo fixture contract tại `tests/fixtures/phase3/`

## Nhóm 2 — US1 Candidate generation trên Kaggle

- [x] T006 [US1] Viết module batch generation, sequence confidence và chunk resume trong `scripts/generate_candidates.py`
- [x] T007 [US1] Tạo notebook điều phối GPU tại `notebooks/generate_visolex_candidates_kaggle.ipynb`
- [x] T008 [US1] Thêm contract/unit tests cho candidate và ghép chunk tại `tests/contract/test_phase3_schemas.py` và `tests/unit/test_candidate_chunks.py`
- [ ] T009 [US1] Chạy smoke test 100 mẫu trên Kaggle và ghi kết quả vào `outputs/model_a/candidate_smoke_test.json`

## Nhóm 3 — US2 Manifest và pilot

- [x] T010 [US2] Cài đặt phần dư lớn nhất, confidence tercile và chọn mẫu seed 2026 trong `scripts/select_review_manifest.py`
- [x] T011 [US2] Thêm test quota 20.000 và pilot 240 mẫu tại `tests/unit/test_review_manifest.py`
- [ ] T012 [US2] Sinh và kiểm tra `data/intermediate/visolex_review_manifest.jsonl`

## Nhóm 4 — US3 Gemini reviewer

- [x] T013 [US3] Cài đặt SQLite WAL schema và repository trong `scripts/review_cache.py`
- [x] T014 [US3] Cài đặt round-robin key pool, cooldown và retry trong `scripts/gemini_key_pool.py`
- [x] T015 [US3] Cài đặt batch 15, prompt rendering và response validation trong `scripts/review_candidates.py`
- [x] T016 [US3] Hoàn thiện test API giả lập cho round-robin, quota, auth, retry và resume tại `tests/integration/test_llm_review_pipeline.py`
- [ ] T017 [US3] Chạy pilot 240 mẫu và xuất `outputs/pilot_review_audit.jsonl`
- [ ] T018 [US3] Audit 100% pilot, sao chép draft đạt yêu cầu thành `prompts/lexical_norm_review_v1.txt`, freeze hash trong config và ghi `outputs/pilot_review_report.md`
- [ ] T019 [US3] Chạy review đủ 20.000 mẫu local và xác nhận không còn batch failed trong `data/intermediate/visolex_review_cache.sqlite3`

## Nhóm 5 — US4 Weak labels và kiểm định

- [x] T020 [US4] Cài đặt decision mapping, validation, leakage và deduplicate trong `scripts/build_weak_labels.py`
- [x] T021 [US4] Cài đặt stats và stratified audit trong `scripts/audit_weak_labels.py`
- [x] T022 [US4] Thêm contract/integration tests tại `tests/contract/test_phase3_schemas.py` và `tests/integration/test_build_weak_labels.py`
- [ ] T023 [US4] Xuất `data/processed/visolex_weak_labeled.jsonl`, `outputs/weak_label_stats.json` và `outputs/weak_label_audit.jsonl`
- [ ] T024 [US4] Chạy toàn bộ quickstart và ghi checksum artifact Phase 3 vào `outputs/phase3_manifest.json`

## Phụ thuộc và thứ tự

```text
T001–T005
  → T006–T009
  → T010–T012
  → T013–T018
  → T019
  → T020–T024
```

T002–T005 chạy song song. T013 và T014 có thể triển khai song song sau khi manifest/prompt
đã chốt. Không chạy T019 trước khi T018 xác nhận prompt đã freeze.

## Tiêu chí kết thúc

- Tất cả nhiệm vụ được đánh dấu hoàn thành và test pass.
- Candidate 68.411; manifest 20.000; pilot 240; batch size 15.
- Không có review failed, API key bị lộ, REJECT trong weak labels hoặc overlap Test.