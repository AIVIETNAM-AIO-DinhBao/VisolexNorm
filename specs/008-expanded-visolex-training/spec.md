# Đặc tả giai đoạn 8: Mở rộng LLM review và huấn luyện Model C

**Trạng thái**: Đã lên kế hoạch — chưa triển khai
**Lịch thực hiện**: Workstream nghiên cứu chạy song song với Phase 6
**Phụ thuộc**: Candidate/cache Phase 3, checkpoint Model A và kết quả Phase 5
**Môi trường**: Gemini review trên local; huấn luyện BARTpho trên Kaggle GPU

## Bối cảnh và mục tiêu

Phase 5 chọn Model B với F1 `0,742215`, cao hơn Model A (`0,718184`) trên Test đã freeze.
Để kiểm tra tác động của việc tăng dữ liệu weak label, giai đoạn này mở rộng review đến toàn bộ
68.411 candidate Model A đã sinh. Phase 3 đã xử lý 20.000 ID; Phase 8 chỉ review **48.411 ID
còn lại**, sau đó hợp nhất KEEP/EDIT hợp lệ với 18.970 weak label cũ và huấn luyện **Model C**.

Đây là thí nghiệm hậu kiểm sau khi Test đã được mở. Test Phase 5 không được load, dùng chọn
checkpoint hoặc dùng chỉnh prompt/filter/siêu tham số. Phase 6 tiếp tục dùng Model B được ghi
trong `outputs/evaluation/best_model.json`; Model C chỉ có thể được promotion sau một cổng đánh
giá độc lập đã freeze trước khi mở dữ liệu đánh giá.

## Kịch bản và nghiệm thu

### US1 — Lập manifest phần candidate chưa review (P1)

Người thực nghiệm tạo manifest bằng hiệu giữa 68.411 candidate và 20.000 ID manifest Phase 3,
giữ thứ tự candidate gốc và provenance.

**Kiểm thử độc lập**: 48.411 ID mới là unique; không giao với manifest cũ; union hai manifest
bằng đúng 68.411 candidate.

### US2 — Review phần còn lại bằng protocol đã freeze (P1)

Reviewer tái sử dụng nguyên prompt, lexical policy và identity model đã freeze ở Phase 3; mỗi
request có 15 mẫu, dùng SQLite cache/resume, round-robin key, cooldown và retry/backoff.

**Kiểm thử độc lập**: Resume không gửi lại một ID đã review thành công; mọi ID kết thúc bằng
KEEP/EDIT/REJECT hợp lệ hoặc provider exclusion đã được chủ dự án phê duyệt.

### US3 — Xây pool weak label toàn corpus (P1)

KEEP dùng candidate, EDIT dùng corrected text; REJECT và validation drop không vào train. Pool
mới là union không trùng của 18.970 weak label Phase 3 và accepted record mới.

**Kiểm thử độc lập**: Pool không có ID trùng, REJECT hay exact overlap ViLexNorm Dev/Test; mọi
record giữ source, prompt version, decision và artifact provenance.

### US4 — Huấn luyện Model C với coverage toàn pool (P1)

Model C khởi tạo từ checkpoint Model A để đo riêng tác động quy mô dữ liệu. Mỗi epoch dùng toàn
bộ 8.372 gold và đúng 8.372 pseudo, ưu tiên pseudo chưa dùng. Số epoch là
`ceil(expanded_weak_label_count / 8372)`; epoch cuối bổ sung deterministic từ ID đã dùng nếu
cần để vẫn giữ tỷ lệ 1:1.

**Kiểm thử độc lập**: Mixture lặp lại với cùng config/seed; union pseudo ID qua các epoch phủ
toàn pool; checkpoint best Dev load lại được.

### US5 — Chọn checkpoint không rò rỉ (P1)

Notebook chỉ evaluate ViLexNorm Dev mỗi epoch và chọn best Model C theo Dev loss.

**Kiểm thử độc lập**: Test Phase 5, raw prediction Test và metric Test không nằm trong input
inventory/notebook của Model C.

## Yêu cầu chức năng

- **FR-001**: Verify 68.411 candidate unique, 20.000 ID manifest cũ là subset và tạo đúng
  48.411 ID còn lại, với intersection rỗng.
- **FR-002**: Không gọi LLM lại cho 20.000 ID cũ; reuse review/cache hợp lệ theo prompt hash
  `54c63d3ca8fb448fe9930598e123b33584295c7e0db298f97f97df21317bae6a`.
- **FR-003**: Review mới giữ batch 15 (trừ batch cuối), round-robin key, cooldown 60 giây,
  tối đa 5 retry, backoff/resume SQLite; API key chỉ đọc từ secret hoặc biến môi trường.
- **FR-004**: Mỗi ID mới phải có KEEP/EDIT/REJECT hợp lệ hoặc provider exclusion được phê duyệt;
  không giả lập review.
- **FR-005**: Pool mở rộng union không trùng 18.970 weak label cũ với KEEP/EDIT mới; REJECT,
  validation drop và exact overlap Dev/Test không được vào train.
- **FR-006**: Model C khởi tạo từ inventory checkpoint Model A đã verify, không từ Model B.
- **FR-007**: Mỗi epoch dùng 8.372 gold + 8.372 pseudo, seed `2026 + epoch_index`, ưu tiên ID
  pseudo chưa dùng; union qua các epoch phải phủ pool mở rộng.
- **FR-008**: Giữ learning rate `2e-5`, batch 8, gradient accumulation 2, weight decay `0,01`,
  warmup `0,1`, beam 4 và max source/target 128; số epoch suy ra theo FR-007 và freeze trước run.
- **FR-009**: Dev chỉ dùng chọn best checkpoint; run Model C không load Test, Test predictions
  hoặc Test metrics Phase 5.
- **FR-010**: Export manifest review, stats/audit, weak-label pool, mixture manifest,
  config/runtime/checksum, Dev predictions/metrics, checkpoint và exit report trong namespace mới.
- **FR-011**: Phase 6 vẫn dùng Model B trong `best_model.json`; Model C không tự động thay thế.
- **FR-012**: Promotion Model C yêu cầu một đặc tả đánh giá mới với holdout độc lập chưa mở và
  freeze contract trước inference; nếu chưa có holdout, Model C chỉ là checkpoint nghiên cứu Dev-only.

## Tiêu chí thành công

- 48.411 ID còn lại được reconcile; toàn bộ 68.411 candidate có trạng thái review cuối hoặc
  exclusion được phê duyệt.
- Pool mở rộng có checksum, không trùng, không có REJECT và không overlap Dev/Test.
- Model C cover toàn bộ pseudo pool, checkpoint load lại được và có Dev artifacts đầy đủ.
- Không code path/artifact input Model C nào đọc Test Phase 5.
- Phase 6 chạy độc lập bằng Model B trong suốt workstream này.

## Ngoài phạm vi

Chỉnh prompt/policy/filter bằng Test, review lại 20.000 ID cũ, ghi đè Model B, tuyên bố Model C
tốt hơn Model B trên Test cũ hoặc tự động đổi checkpoint Phase 6 sang Model C.