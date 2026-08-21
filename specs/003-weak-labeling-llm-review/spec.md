# Đặc tả giai đoạn 3: Tạo nhãn yếu bằng Model A và LLM reviewer

**Trạng thái**: Hoàn thành với 3 approved provider exclusions
**Ưu tiên**: P1
**Phụ thuộc**: Phase 1 và Phase 2 đã hoàn thành
**Đầu vào**: `data/processed/visolex_unlabeled.jsonl`, `checkpoints/model_a/`

## Mục tiêu

Tạo tập ViSoLex weak-labeled có chất lượng và truy vết được bằng quy trình cố định:

```text
68.411 ViSoLex inputs
→ Model A sinh candidate + confidence trên Kaggle GPU
→ chọn manifest 20.000 mẫu có phân tầng
→ Gemini review local theo lô 15 mẫu/request và round-robin API key
→ KEEP / EDIT / REJECT
→ validation, filtering và audit
→ visolex_weak_labeled.jsonl
```

Model A chỉ đề xuất. Mọi mẫu xuất hiện trong tập train Model B phải có review hợp lệ từ LLM.
Ba mẫu bị Gemini chặn ở lớp provider trước inference sau mọi recovery attempt được phép loại
theo phê duyệt rõ ràng của chủ dự án; chúng không được giả lập review hoặc đưa vào weak labels.

## Kịch bản sử dụng và kiểm thử

### US1 — Sinh candidate có thể tái lập (P1)

Người thực nghiệm chạy một Kaggle Notebook để Model A sinh candidate và confidence cho toàn
bộ 68.411 mẫu mà không đổi ID hoặc thứ tự.

**Kiểm thử độc lập**: Notebook chạy trên một subset cố định, resume sau khi dừng, rồi cho
kết quả giống lần chạy liền mạch về ID, candidate và confidence trong sai số số thực cho phép.

**Tình huống nghiệm thu**:
1. Khi checkpoint và config hợp lệ, notebook xuất mỗi input đúng một candidate record.
2. Khi một chunk đã tồn tại và hợp lệ, chạy lại bỏ qua chunk đó thay vì sinh trùng.
3. Khi checkpoint thiếu, notebook dừng trước inference với thông báo rõ đường dẫn.

### US2 — Chọn manifest review cân bằng (P1)

Người thực nghiệm tạo manifest đúng 20.000 mẫu, phân bổ theo tỷ lệ của bốn nguồn còn dữ liệu
và cân bằng ba dải confidence trong từng nguồn.

**Kiểm thử độc lập**: Hai lần chạy với seed 2026 tạo manifest có cùng ID và thứ tự.

**Tình huống nghiệm thu**:
1. Khi đủ candidate, manifest có đúng 20.000 ID duy nhất.
2. Mỗi nguồn được cấp quota theo tỷ lệ số candidate, dùng phương pháp phần dư lớn nhất.
3. Trong mỗi nguồn, ba dải confidence có quota chênh nhau không quá một mẫu nếu đủ dữ liệu.
4. ViHOS có quota bằng 0 và được ghi rõ do không có mẫu sau deduplicate.

### US3 — Review bằng Gemini an toàn và resume được (P1)

Người thực nghiệm gọi Gemini API trên laptop local. Mỗi request chứa 15 cặp SOURCE/CANDIDATE,
các request được cấp lần lượt cho các API key bằng round-robin.

**Kiểm thử độc lập**: Dùng API giả lập để chứng minh thứ tự cấp khóa, batch size, retry,
cooldown, schema validation và resume từ SQLite.

**Tình huống nghiệm thu**:
1. Với N mẫu, số request bằng `ceil(N/15)`; mọi request trừ request cuối có đúng 15 mẫu.
2. Với K khóa hợp lệ, request i dùng khóa `i mod K` trong số khóa đang hoạt động.
3. Lỗi 429/quota đưa khóa vào cooldown và request được thử lại bằng khóa tiếp theo.
4. Tiến trình khởi động lại không gọi lại các mẫu đã có review hợp lệ trong SQLite.
5. Response thiếu ID, trùng ID, thừa ID hoặc sai decision bị từ chối toàn batch và retry.

### US4 — Xây weak labels đã kiểm định (P1)

Người thực nghiệm biến review thành target cuối, lọc record lỗi và xuất thống kê/audit.

**Kiểm thử độc lập**: Chạy builder trên fixture chứa đủ KEEP, EDIT, REJECT và lỗi validation;
chỉ KEEP/EDIT hợp lệ xuất hiện trong artifact cuối.

**Tình huống nghiệm thu**:
1. KEEP tạo `target_text = candidate_text`.
2. EDIT tạo `target_text = llm_corrected_text` không rỗng.
3. REJECT và record lỗi validation không vào tập cuối nhưng vẫn có thống kê/reason code.
4. Tập cuối không exact-overlap với ViLexNorm Dev/Test và không trùng input.

## Trường hợp biên

- `.env` không có khóa hợp lệ: dừng trước request đầu tiên, không tạo review giả.
- Candidate có `generation_status=empty_after_special_token_decode` được giữ để audit và có
  thể vào manifest; reviewer phải EDIT hoặc REJECT, không được KEEP candidate rỗng.
- Response Gemini bị bọc trong đúng một code fence được chấp nhận. Parser cũng cho phép một
  phần dẫn ngắn nếu response vẫn chứa đúng một JSON object cân bằng; schema và tập ID vẫn phải
  khớp tuyệt đối, nếu không toàn batch bị retry.
- Batch cuối có 1–14 mẫu: được phép gửi đúng số mẫu còn lại.
- Tất cả khóa đang cooldown: chờ đến thời điểm cooldown gần nhất, không busy-loop.
- Một sample quá mơ hồ: reviewer phải REJECT, không cố tạo target.
- Provider trả `PROHIBITED_CONTENT` trước inference (không candidate/text) sau retry riêng:
  ghi approved exclusion audit và loại sample; không quy đổi thành REJECT giả.
- SOURCE đã chuẩn: KEEP chỉ khi candidate giữ nguyên hoặc là normalization tương đương tối thiểu.

## Yêu cầu chức năng

- **FR-001**: Sinh candidate cho đúng 68.411 record bằng Model A trên Kaggle GPU.
- **FR-002**: Confidence là trung bình log-xác suất token sinh, được tính bằng
  `compute_transition_scores(..., normalize_logits=true)` trên các token sau decoder start,
  bỏ padding nhưng giữ EOS; không dùng trực tiếp `sequences_scores`. Công thức và phiên bản Transformers
  phải được lưu trong config.
- **FR-003**: Candidate generation chia chunk 1.000 mẫu, ghi atomically và resume theo chunk.
- **FR-004**: Manifest có đúng 20.000 mẫu, seed 2026, phân tầng source × confidence tercile.
- **FR-005**: Pilot gồm đúng 240 mẫu: bốn nguồn × ba dải × 20 mẫu.
- **FR-006**: Prompt yêu cầu reviewer chuẩn hóa SOURCE độc lập trước khi so với CANDIDATE.
- **FR-007**: Reviewer chỉ trả KEEP, EDIT hoặc REJECT theo contract.
- **FR-008**: Mỗi Gemini request chứa 15 mẫu, trừ request cuối.
- **FR-009**: API keys đọc từ `GEMINI_API_KEYS`, model đọc từ `GEMINI_MODEL`.
- **FR-010**: Request được điều phối round-robin; mỗi khóa tối đa một request đang chạy.
- **FR-011**: Retry tối đa 5 lần với backoff 2, 4, 8, 16, 32 giây và jitter 0–1 giây.
- **FR-012**: Khóa gặp 429/quota cooldown 60 giây; lỗi xác thực loại khóa đến hết lần chạy.
- **FR-013**: Cache SQLite lưu theo sample ID và review identity; không lưu API key. Review
  identity là SHA-256 chung của nội dung prompt và toàn bộ lexical policy có phiên bản.
- **FR-014**: Pilot dùng `lexical_norm_review_draft`; sau khi audit đạt, nội dung prompt được
  sao chép nguyên văn, ghi SHA-256 và freeze thành `lexical_norm_review_v1` trước batch chính.
  Nếu pilot không đạt, sửa draft, đổi prompt hash và chạy lại toàn bộ pilot; không ghi đè cache cũ.
- **FR-014a**: Cổng pilot đạt khi tỷ lệ lỗi major sau audit toàn bộ 240 mẫu không vượt quá 3,0%.
  Review identity/cache key PHẢI băm chung nội dung prompt và versioned lexical policy đã audit.
- **FR-015**: Validation áp dụng length ratio trong [0,5; 2,0] và normalized edit ratio ≤ 0,8;
  ngoài ngưỡng bị drop với reason code, không auto-correct.
- **FR-016**: Xuất thống kê candidate, reviewed, KEEP/EDIT/REJECT, retry, API error,
  validation drop, accepted và số lượng theo source/confidence.
- **FR-017**: Raw response tối thiểu được giữ trong SQLite để audit, không đưa vào target.
- **FR-018**: Completion review gồm đúng 20.000 manifest item được reconcile thành review hợp
  lệ hoặc approved provider exclusion. Ngoại lệ phải lưu ID/lý do/phê duyệt; không vào target.

## Thực thể chính

- **CandidateRecord**: input ViSoLex kèm candidate, confidence và metadata generation.
- **ReviewManifestItem**: candidate được chọn, source, confidence band và selection rank.
- **ReviewBatch**: tối đa 15 item cùng request ID, prompt/model version và trạng thái.
- **ReviewResult**: decision, corrected text, reason code và metadata API.
- **WeakLabelRecord**: record KEEP/EDIT đã qua validation dùng cho Model B.
- **WeakLabelStats**: thống kê toàn pipeline và lý do loại.

## Tiêu chí thành công

- **SC-001**: 100% input hợp lệ có đúng một candidate record và giữ đúng ID/thứ tự.
- **SC-002**: Manifest có 20.000 ID duy nhất và tái tạo giống hệt với seed 2026.
- **SC-003**: 100% request không phải cuối có đúng 15 mẫu; không có API key trong log/cache.
- **SC-004**: 100% review hợp lệ ánh xạ đủ và chỉ đủ các ID của batch.
- **SC-004a**: 20.000 manifest item được giải trình đầy đủ: 19.997 review hợp lệ và 3 approved
  provider exclusions; không có item thiếu trạng thái.
- **SC-005**: 100% weak label cuối là KEEP/EDIT hợp lệ và truy được về candidate/review.
- **SC-006**: Pipeline resume sau gián đoạn mà không tạo review trùng hoặc mất record đã commit.
- **SC-007**: Báo cáo có đầy đủ tỷ lệ quyết định, drop và phân bố theo bốn nguồn thực tế.
- **SC-008**: Báo cáo pilot lưu số lỗi major, ngưỡng 3,0%, quyết định duyệt của chủ dự án và
  240 audited IDs gắn với review identity đã freeze.

## Ngoài phạm vi

- Train Model B, đánh giá Test và web app.
- Auto-accept candidate dựa trên confidence.
- Review toàn bộ 68.411 mẫu trong thí nghiệm chính.
- Dùng ViLexNorm Test để chọn prompt, manifest hoặc ngưỡng lọc.

## Giả định

- Checkpoint Model A và 68.411 input đã sẵn sàng trước khi chạy.
- Gemini model trong `.env` hỗ trợ structured JSON đủ lớn cho 15 kết quả/request.
- Người thực nghiệm có ít nhất hai API key; pipeline vẫn hoạt động với một khóa hợp lệ.