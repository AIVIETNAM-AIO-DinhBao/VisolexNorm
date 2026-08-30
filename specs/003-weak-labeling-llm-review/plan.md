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
- **Kiểm thử**: pytest local; full-run integrity audit cho artifact Kaggle đã hoàn thành.
- **Nền tảng**: Kaggle Linux GPU cho BARTpho; Windows 11 local cho API và xử lý dữ liệu.
- **Quy mô**: 68.411 candidate; manifest 20.000 gồm 19.997 review hợp lệ và 3 approved exclusions; 15 mẫu/request ở batch chính.
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
├── generate_model_a_candidates.py
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
Các output chỉ còn special token được giữ với trạng thái audit riêng; nếu được chọn review thì
chỉ EDIT/REJECT mới hợp lệ. Full-run integrity audit được chủ dự án duyệt làm bằng chứng mạnh
hơn smoke test sau khi artifact Kaggle smoke riêng bị mất.

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
Cổng duyệt là tỷ lệ lỗi major không vượt quá 3,0%. Pilot v6 ghi 7/240 lỗi major (2,9167%) và
được chủ dự án duyệt ngày 2026-08-21. Khi đạt, nội dung draft được sao chép nguyên văn và
freeze thành v1 bằng review identity SHA-256 của prompt cộng lexical policy versioned. Nếu
không đạt, sửa draft/policy và pilot lại toàn bộ trong cache namespace mới; batch chính chỉ
chấp nhận v1.

Trong metadata, `prompt_content_sha256` chỉ băm file prompt, `policy_sha256` băm file policy,
còn `review_identity_sha256` băm chung nội dung của cả hai và là khóa namespace cache.

### 4. Batch review local

Sau freeze, xử lý đủ manifest 20.000. API keys được parse từ `GEMINI_API_KEYS`; scheduler
round-robin chỉ chọn key không cooldown và chưa có request in-flight. SQLite WAL commit cả
batch sau khi response đủ đúng 15 ID. Retry tối đa 5 lần; lỗi cuối được ghi `failed` để chạy
resume sau, không tạo nhãn thiếu.

Ba input cuối bị provider trả `PROHIBITED_CONTENT` trước inference dù đã retry từng mẫu và
thử JSON schema transport. Theo phê duyệt chủ dự án ngày 2026-08-22, completion được reconcile
thành 19.997 review hợp lệ + 3 exclusion có audit; không tạo review giả cho các input này.

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

Chỉ kết thúc Phase 3 khi candidate đủ 68.411, manifest đúng 20.000, mọi item có review hợp lệ
hoặc approved provider exclusion, không còn failed batch chưa được giải trình,
weak labels qua schema/validation, stats đầy đủ và audit thủ công đã được ghi nhận.