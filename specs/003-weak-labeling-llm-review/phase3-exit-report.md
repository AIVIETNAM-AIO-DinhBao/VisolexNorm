# Phase 3 Exit Report

**Ngày đóng**: 2026-08-22

**Trạng thái**: `completed_with_approved_provider_exclusions`

**Review identity**: `54c63d3ca8fb448fe9930598e123b33584295c7e0db298f97f97df21317bae6a`

## Kết quả

| Hạng mục | Kết quả |
|---|---:|
| ViSoLex canonical inputs / Model A candidates | 68.411 |
| Review manifest IDs | 20.000 |
| Gemini reviews hợp lệ | 19.997 |
| Approved provider exclusions | 3 |
| KEEP / EDIT / REJECT | 9.043 / 9.952 / 1.002 |
| Final accepted weak labels | 18.970 |
| Final KEEP / EDIT | 9.034 / 9.936 |
| Validation drops ngoài REJECT/exclusion | 25 |
| Weak-label audit rows | 720 |

Ba input bị Gemini trả `PROHIBITED_CONTENT` trước inference sau năm recovery attempts từng
mẫu và một structured-output retry. Chủ dự án phê duyệt loại ngày 2026-08-22; chi tiết nằm
trong `outputs/phase3_provider_exclusions.json`. Không có review giả được tạo.

## Exit gates

- Candidate full-run integrity: pass; 68.411 unique IDs, 69 chunks liên tục.
- Manifest accounting: `19.997 + 3 = 20.000`.
- Cache: 1.429 batch succeeded, 10 historical attempts superseded, 0 unresolved failed.
- Weak labels: 18.970 unique IDs và unique inputs; 0 schema error.
- Leakage: 0 overlap với 2.095 protected ViLexNorm Dev/Test hashes.
- Final output chỉ có KEEP/EDIT; không có REJECT.
- Test suite: 32 passed.
- Secret scan: 0 configured Gemini API key xuất hiện trong code/config/spec/test/notebook/output.

## Artifact preservation

Binary/data artifacts được `.gitignore` và phải lưu ngoài Git. Hai bundle phục hồi gốc:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `model_a_artifacts.zip` | 1.693.704.834 | `54f4c73e74a2ec24d06c7bbbc1512e80894b947988f32b9a0bd5050dc636775a` |
| `visolex_model_a_candidates.zip` | 11.420.105 | `3e71d507baaf3a966eac09cee66ad71fdc6953534bc800a877b0111775fd2ffe` |

`outputs/phase3_manifest.json` là inventory/checksum machine-readable của 24 artifact Phase
1–3, gồm canonical inputs, Model A, candidates, review cache, prompt/policy và final outputs.
Không xóa hoặc ghi đè bundle ngoài Git trước khi có ít nhất một bản sao độc lập.

## Lệnh xác minh

```bash
python -m pytest -q
python scripts/audit_candidate_full_run.py
python scripts/build_weak_labels.py --protected-hashes data/processed/vilexnorm_protected_input_hashes.txt --model gemini-3.5-flash-lite --config configs/llm_review_config.json --excluded-ids-file outputs/phase3_provider_exclusions.json --quiet
python scripts/audit_weak_labels.py --weak-labels data/processed/visolex_weak_labeled.jsonl --stats outputs/weak_label_stats.json --approved-exclusions outputs/phase3_provider_exclusions.json --quiet
```

## Handoff sang Phase 4

- Input pseudo duy nhất: `data/processed/visolex_weak_labeled.jsonl` (18.970 records).
- Phase 4 phải verify checksum từ `outputs/phase3_manifest.json` trước khi xây mixture.
- Model B khởi tạo từ `checkpoints/model_a/`, không từ BARTpho gốc.
- ViLexNorm Test không được load trong training notebook.
- Không gọi lại LLM hoặc thay đổi weak-label artifact trong Phase 4.