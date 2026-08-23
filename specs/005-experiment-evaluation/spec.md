# Đặc tả giai đoạn 5: Đánh giá thực nghiệm Model A và Model B

**Trạng thái**: Chờ Model B
**Phụ thuộc**: checkpoint Model A/Model B đã nghiệm thu trên Dev, artifact provenance Phase 3/4 và freeze manifest Phase 5

## Mục tiêu

So sánh Model A và Model B trên cùng 1.045 mẫu ViLexNorm Test bằng ERR, Precision, Recall,
F1 và error analysis. Đây là lần sử dụng Test duy nhất sau khi freeze.

## Kịch bản

### US1 — Freeze thí nghiệm (P1)
Tạo một manifest bất biến trước khi đọc Test. Manifest ghi checksum/bytes/đường dẫn tương đối của checkpoint A/B, ViLexNorm Test, weak-label/Phase 4 provenance, tokenizer contract, cấu hình generation, mã metric, seed và rule chọn model.

### US2 — Sinh prediction trên Kaggle GPU (P1)
Một notebook load hai checkpoint, generate Test bằng cùng cấu hình và xuất prediction theo ID.

### US3 — Tính metric và phân tích local (P1)
Script local kiểm tra alignment rồi tính metric theo official ViLexNorm protocol và tạo bảng A/B.

## Yêu cầu

- **FR-001**: Freeze manifest phải được tạo và có `status="frozen"` trước khi notebook được phép đọc Test. Notebook/script phải dừng trước khi load Test nếu manifest thiếu, đã thay đổi hoặc checksum checkpoint, Test, tokenizer, generation config hay mã metric không khớp.
- **FR-002**: A và B dùng cùng tokenizer contract, cùng cấu hình generation canonical (beam 4, giới hạn 128 token), seed `2026` và thứ tự Test. Cấu hình canonical phải có hash trong manifest và trong từng prediction.
- **FR-003**: Prediction schema gồm đủ `id`, `input_text`, `target_text`, `prediction_text`, `model`, `checkpoint_checksum`, `generation_config_hash`.
- **FR-004**: Metric chính là ERR, Precision, Recall, F1 theo official protocol.
- **FR-005**: Freeze manifest phải ghi source/version/commit của official ViLexNorm metric. Nếu official code không chạy, bản port phải khớp 100% fixture/reference trước khi dùng Test.
- **FR-006**: Error analysis gán đúng một nhãn chính: `correct`, `missed`, `wrong`, `over-normalization`, `one-to-many`, `many-to-one`, hoặc `suspected-weak-label-noise`. Quy tắc precedence và chọn mẫu audit phải deterministic theo thứ tự ID.
- **FR-007**: Chọn **best model** chỉ giữa checkpoint Model A và Model B đã freeze: F1 Test cao hơn; nếu bằng nhau, ERR thấp hơn; nếu vẫn bằng nhau, Model A vì đơn giản hơn. Không được dùng Test để chọn checkpoint mới.
- **FR-008**: Không rerun training, tạo checkpoint mới, thay prompt/filtering hoặc đổi generation config sau khi xem Test.

## Thành công

- Mỗi model có đúng 1.045 prediction hợp lệ, không thiếu/trùng/lệch ID, với `input_text` và `target_text` khớp Test.
- Bảng A/B đủ bốn metric và tái tạo được từ raw predictions sau khi kiểm tra schema, set ID và thứ tự ID.
- Error analysis có toàn bộ lỗi, kèm audit deterministic tối đa 100 lỗi/model (hoặc toàn bộ nếu ít hơn 100).
- Có quyết định best model theo rule đã ghi trong freeze manifest.