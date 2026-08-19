# Đặc tả giai đoạn 5: Đánh giá thực nghiệm Model A và Model B

**Trạng thái**: Chờ Model B
**Phụ thuộc**: Model A, Model B và cấu hình thí nghiệm đã freeze

## Mục tiêu

So sánh Model A và Model B trên cùng 1.045 mẫu ViLexNorm Test bằng ERR, Precision, Recall,
F1 và error analysis. Đây là lần sử dụng Test duy nhất sau khi freeze.

## Kịch bản

### US1 — Freeze thí nghiệm (P1)
Tạo manifest chứa checksum checkpoint A/B, weak labels, config generation và mã evaluation.

### US2 — Sinh prediction trên Kaggle GPU (P1)
Một notebook load hai checkpoint, generate Test bằng cùng cấu hình và xuất prediction theo ID.

### US3 — Tính metric và phân tích local (P1)
Script local kiểm tra alignment rồi tính metric theo official ViLexNorm protocol và tạo bảng A/B.

## Yêu cầu

- **FR-001**: Freeze manifest trước khi notebook được phép đọc Test.
- **FR-002**: A và B dùng cùng tokenizer contract, beam 4, max length 128 và thứ tự Test.
- **FR-003**: Prediction schema gồm `id`, `input_text`, `target_text`, `prediction_text`, `model`.
- **FR-004**: Metric chính là ERR, Precision, Recall, F1 theo official protocol.
- **FR-005**: Nếu official code không chạy, bản port phải khớp 100% fixture/reference trước dùng.
- **FR-006**: Error analysis gán một nhãn chính: correct, missed, wrong, over-normalization,
  one-to-many, many-to-one, suspected-weak-label-noise.
- **FR-007**: Chọn best checkpoint theo F1 Test; nếu F1 bằng nhau, chọn ERR thấp hơn; nếu vẫn
  bằng nhau, chọn Model A vì đơn giản hơn.
- **FR-008**: Không rerun training, prompt hoặc filtering sau khi xem Test.

## Thành công

- 1.045 prediction/model, không thiếu/trùng/lệch ID.
- Bảng A/B đủ bốn metric và tái tạo được từ raw predictions.
- Error analysis có ít nhất 100 lỗi/model hoặc toàn bộ lỗi nếu ít hơn 100.
- Có quyết định best checkpoint theo rule cố định.