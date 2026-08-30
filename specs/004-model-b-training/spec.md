# Đặc tả giai đoạn 4: Huấn luyện Model B

**Trạng thái**: Hoàn thành — checkpoint và exit report Model B đã nghiệm thu
**Phụ thuộc**: `specs/003-weak-labeling-llm-review/`
**Môi trường**: Kaggle Notebook có GPU

## Mục tiêu

Fine-tune Model B từ checkpoint Model A bằng ViLexNorm Gold Train và pool ViSoLex weak
labels đã được chấp nhận. Pool 18.970 record là đầu vào pseudo đã đóng băng; mỗi epoch dùng
toàn bộ 8.372 gold và đúng 8.372 pseudo để giữ tỷ lệ gold:pseudo 1:1. Pseudo sampler xoay
vòng qua pool để mọi weak label được dùng ít nhất một lần trong ba epoch; checkpoint được
chọn duy nhất bằng ViLexNorm Dev.

Input pseudo được đóng băng ở 18.970 record trong
`data/processed/visolex_weak_labeled.jsonl`. Trước khi train, notebook PHẢI xác minh checksum
theo `outputs/phase3_manifest.json`; không được tự build lại weak labels trong Phase 4.

## Kịch bản và nghiệm thu

### US1 — Xây hỗn hợp huấn luyện có provenance (P1)

Người thực nghiệm tạo epoch dataset gồm 8.372 gold và 8.372 pseudo. Epoch `e` dùng seed
`2026 + e`, ưu tiên pseudo chưa dùng trước đó rồi mới bổ sung từ tập đã dùng. Không lấy lặp
trong cùng epoch khi pool có ít nhất 8.372 record. Mỗi record giữ `label_source` và ID gốc.

**Kiểm thử độc lập**: Cùng seed 2026 và epoch index tạo cùng danh sách; gold:pseudo = 1:1.

### US2 — Train và chọn Model B trên Kaggle (P1)

Notebook load Model A, chạy smoke test rồi full training đủ ba epoch để hoàn tất coverage
pseudo; Dev chỉ được dùng để chọn best checkpoint theo Dev loss. Patience 2 được ghi trong
config làm guard cho run mở rộng, không dừng run chuẩn trước epoch 3.

**Kiểm thử độc lập**: Smoke test 200 gold + 200 pseudo giảm loss, save/load được checkpoint.

### US3 — Export artifact đầy đủ (P1)

Checkpoint, config, Dev predictions/metrics và data manifest được tải độc lập khỏi session.

## Yêu cầu chức năng

- **FR-001**: Model B khởi tạo từ best checkpoint Model A, không từ BARTpho gốc.
- **FR-002**: Tất cả 8.372 gold được dùng mỗi epoch và có trọng số tương đương 8.372 pseudo.
- **FR-003**: Pseudo sampler seed = `2026 + epoch_index`; không replacement trong epoch.
- **FR-003a**: Sampler ưu tiên pseudo chưa dùng; sau 3 epoch union pseudo ID phải đủ 18.970.
- **FR-004**: Nếu accepted pseudo < 8.372, sample pseudo có replacement để vẫn giữ 1:1 và
  ghi cảnh báo vào train config.
- **FR-005**: Train config khởi đầu: learning rate `2e-5`, 3 epoch, batch 8, gradient
  accumulation 2, weight decay 0,01, warmup ratio 0,1, beam 4, patience 2.
- **FR-006**: Max source/target length 128 và tokenizer đi cùng Model A checkpoint.
- **FR-007**: Dev không được trộn vào train; Test không được load trong notebook.
- **FR-008**: Export số gold/pseudo, decision/source distribution, prompt version và checksum
  weak-label artifact trong `train_config.json`.
- **FR-009**: Data manifest phải ghi checksum Phase 3 manifest, checksum weak-label artifact,
  18.970 accepted records và completion status `completed_with_approved_provider_exclusions`.
- **FR-010**: Checkpoint Model A thực tế được load phải có inventory relative path, byte size
  và SHA-256 từng file; checksum canonical của inventory được lưu trong train config.

## Tiêu chí thành công

- Smoke test pass và checkpoint load lại được.
- Mỗi epoch đúng tỷ lệ 1:1, union pseudo qua ba epoch đủ 18.970, không có ID Dev/Test trong train.
- Có `checkpoints/model_b/`, Dev predictions, Dev metrics, train config và data manifest.
- Có thể xác định chính xác weak-label artifact nào đã tạo checkpoint.

## Ngoài phạm vi

Tuning bằng Test, thay kiến trúc mô hình, tạo thêm weak labels hoặc gọi LLM trong training.