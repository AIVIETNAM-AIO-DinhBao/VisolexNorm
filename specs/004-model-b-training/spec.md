# Đặc tả giai đoạn 4: Huấn luyện Model B

**Trạng thái**: Chờ weak labels Phase 3
**Phụ thuộc**: `specs/003-weak-labeling-llm-review/`
**Môi trường**: Kaggle Notebook có GPU

## Mục tiêu

Fine-tune Model B từ checkpoint Model A bằng ViLexNorm Gold Train và toàn bộ ViSoLex weak
labels đã được chấp nhận. Mỗi epoch dùng tỷ lệ lấy mẫu gold:pseudo đúng 1:1 để pseudo-data
không áp đảo gold; checkpoint được chọn duy nhất bằng ViLexNorm Dev.

## Kịch bản và nghiệm thu

### US1 — Xây hỗn hợp huấn luyện có provenance (P1)

Người thực nghiệm tạo epoch dataset gồm 8.372 gold và 8.372 pseudo được sample không hoàn
lại trong epoch khi đủ pseudo; qua các epoch sampler xoay vòng deterministic để tận dụng
toàn bộ pseudo. Mỗi record giữ `label_source` và ID gốc.

**Kiểm thử độc lập**: Cùng seed 2026 và epoch index tạo cùng danh sách; gold:pseudo = 1:1.

### US2 — Train và chọn Model B trên Kaggle (P1)

Notebook load Model A, chạy smoke test rồi full training; chỉ dùng Dev để early stopping và
chọn best checkpoint.

**Kiểm thử độc lập**: Smoke test 200 gold + 200 pseudo giảm loss, save/load được checkpoint.

### US3 — Export artifact đầy đủ (P1)

Checkpoint, config, Dev predictions/metrics và data manifest được tải độc lập khỏi session.

## Yêu cầu chức năng

- **FR-001**: Model B khởi tạo từ best checkpoint Model A, không từ BARTpho gốc.
- **FR-002**: Tất cả 8.372 gold được dùng mỗi epoch và có trọng số tương đương 8.372 pseudo.
- **FR-003**: Pseudo sampler seed = `2026 + epoch_index`; không replacement trong epoch.
- **FR-004**: Nếu accepted pseudo < 8.372, sample pseudo có replacement để vẫn giữ 1:1 và
  ghi cảnh báo vào train config.
- **FR-005**: Train config khởi đầu: learning rate `2e-5`, 3 epoch, batch 8, gradient
  accumulation 2, weight decay 0,01, warmup ratio 0,1, beam 4, patience 2.
- **FR-006**: Max source/target length 128 và tokenizer đi cùng Model A checkpoint.
- **FR-007**: Dev không được trộn vào train; Test không được load trong notebook.
- **FR-008**: Export số gold/pseudo, decision/source distribution, prompt version và checksum
  weak-label artifact trong `train_config.json`.

## Tiêu chí thành công

- Smoke test pass và checkpoint load lại được.
- Mỗi epoch đúng tỷ lệ 1:1, không có ID Dev/Test trong train.
- Có `checkpoints/model_b/`, Dev predictions, Dev metrics, train config và data manifest.
- Có thể xác định chính xác weak-label artifact nào đã tạo checkpoint.

## Ngoài phạm vi

Tuning bằng Test, thay kiến trúc mô hình, tạo thêm weak labels hoặc gọi LLM trong training.