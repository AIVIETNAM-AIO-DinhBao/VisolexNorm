# Kế hoạch triển khai: Tạo nhãn yếu bằng Model A và LLM reviewer

**Đặc tả**: [spec.md](spec.md)
**Ngày**: 2026-08-19

## Tóm tắt

Model A sinh candidate cho toàn bộ ViSoLex trên Kaggle GPU. Laptop local chọn manifest
20.000 mẫu, gọi Gemini theo lô 15 mẫu bằng round-robin API key, lưu SQLite, rồi validation
và export weak labels. Pilot 240 mẫu phải hoàn thành và prompt phải freeze trước batch chính.

## Bối cảnh kỹ thuật

- **Ngôn ngữ**: Python 3.11.
- **Dependency Kaggle**: PyTorch, Transformers, Datasets, Accelerate, SentencePiece.
- **Dependency local**: Gemini Python SDK, python-dotenv, jsonschema, tenacity, pytest.
- **Lưu trữ**: JSONL cho artifact, SQLite WAL cho cache review, JSON cho config/stats.
- **Kiểm thử**: pytest local; smoke test notebook trên Kaggle.
- **Nền tảng**: Kaggle Linux GPU cho BARTpho; Windows 11 local cho API và xử lý dữ liệu.
- **Quy mô**: 68.411 candidate; 20.000 review; 15 mẫu/request; khoảng 1.334 request.
- **Ràng buộc**: không dùng Test; không lộ secret; resume; giữ ID/provenance.

## Kiểm tra hiến chương

| Cổng | Kết quả | Bằng chứng |
|---|---|---|
| Tiếng Việt chính | Đạt | Toàn bộ tài liệu dùng tiếng Việt |
| GPU chỉ ở Kaggle | Đạt | Candidate generation là notebook; API chạy local |
| Không rò rỉ Test | Đạt | Manifest/filter chỉ dùng ViSoLex và Dev/Test để loại overlap đã chốt |
| Model A không là nhãn cuối | Đạt | Mọi weak label cần review KEEP/EDIT |
| API key an toàn | Đạt | Chỉ đọc `.env`, không lưu key |
| Kế hoạch dứt khoát | Đạt | Quy mô, batch, quota, retry và ngưỡng đã chốt |

## Cấu trúc mã nguồn dự kiến

```text
configs/
├── candidate_generation_config.json
└── llm_review_config.json
notebooks/
└── generate_visolex_candidates_kaggle.ipynb
prompts/
└── lexical_norm_review_v1.txt
scripts/
├── generate_candidates.py
├── select_review_manifest.py
├── review_candidates.py
├── build_weak_labels.py
└── audit_weak_labels.py
tests/
├── contract/
├── integration/
└── unit/
```

## Luồng triển khai

### 1. Candidate generation trên Kaggle

Notebook nhận checkpoint Model A, config và `visolex_unlabeled.jsonl`; gọi script inference
theo chunk 1.000, beam 4, max length 128. Confidence được tính từ transition scores đã
normalize, không dùng trực tiếp sequence score. Mỗi chunk ghi tệp tạm rồi rename atomically.
Cuối notebook ghép chunk theo index, validate 68.411 ID và export candidate JSONL cùng config.

### 2. Manifest local

Script kiểm tra candidate schema, chia confidence tercile trong từng source bằng sort
`(confidence, id)`, cấp quota source theo phần dư lớn nhất:

| Source | Quota review | Low | Medium | High |
|---|---:|---:|---:|---:|
| ViHSD | 8.940 | 2.980 | 2.980 | 2.980 |
| UIT-VSMEC | 2.022 | 674 | 674 | 674 |
| ViSpamReviews | 5.790 | 1.930 | 1.930 | 1.930 |
| UIT-ViSFD | 3.248 | 1.083 | 1.083 | 1.082 |
| ViHOS | 0 | 0 | 0 | 0 |

Trong từng strata, shuffle bằng seed 2026 rồi lấy quota. Pilot lấy 20 mẫu đầu theo rank của
mỗi tổ hợp bốn source × ba band, tổng 240 mẫu.

### 3. Pilot Gemini local

Prompt draft gồm quy tắc lexical normalization, SOURCE/CANDIDATE và JSON schema. Script gom
15 mẫu/request, tức 16 request cho pilot. Toàn bộ 240 kết quả được export thành bảng audit.
Khi đạt, nội dung draft được sao chép nguyên văn và freeze thành v1 bằng SHA-256. Nếu không
đạt, sửa draft và pilot lại toàn bộ trong cache namespace mới; batch chính chỉ chấp nhận v1.

### 4. Batch review local

Sau freeze, xử lý đủ manifest 20.000. API keys được parse từ `GEMINI_API_KEYS`; scheduler
round-robin chỉ chọn key không cooldown và chưa có request in-flight. SQLite WAL commit cả
batch sau khi response đủ đúng 15 ID. Retry tối đa 5 lần; lỗi cuối được ghi `failed` để chạy
resume sau, không tạo nhãn thiếu.

### 5. Validation, filtering và audit

Builder join manifest với review theo ID; áp dụng decision rule, Unicode, length ratio,
edit ratio, artifact, overlap và deduplicate. Xuất weak labels theo thứ tự manifest, stats và
audit sample gồm 30 record mỗi decision/source/confidence band khi strata đủ record.

## Artifact đầu ra

```text
data/intermediate/visolex_model_a_candidates.jsonl
data/intermediate/visolex_review_manifest.jsonl
data/intermediate/visolex_review_cache.sqlite3
data/processed/visolex_weak_labeled.jsonl
outputs/weak_label_stats.json
outputs/weak_label_audit.jsonl
outputs/pilot_review_audit.jsonl
```

## Cổng hoàn thành

Chỉ kết thúc Phase 3 khi candidate đủ 68.411, manifest đúng 20.000, không còn review failed,
weak labels qua schema/validation, stats đầy đủ và audit thủ công đã được ghi nhận.