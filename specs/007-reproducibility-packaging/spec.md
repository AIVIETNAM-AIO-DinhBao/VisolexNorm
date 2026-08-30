# Đặc tả giai đoạn 7: Tái lập và đóng gói

**Trạng thái**: Chưa thực hiện — bước tiếp theo sau khi Phase 6 hoàn tất
**Môi trường**: Local; notebook GPU chỉ được xác minh từ artifact đã chạy

## Mục tiêu

Đóng gói mã nguồn, notebook, cấu hình, prompt, metrics, predictions, checkpoint và hướng dẫn
để người khác hiểu đúng pipeline, kiểm tra checksum và chạy lại từng bước theo thứ tự.

## Kịch bản

### US1 — Người mới tái hiện luồng chạy (P1)
Từ README tiếng Việt, người dùng xác định được input/output/lệnh/môi trường của từng Phase.

### US2 — Người chấm kiểm tra artifact (P1)
Chạy một lệnh local để kiểm tra đủ tệp, checksum, schema và không có secret.

### US3 — Nhóm trình diễn offline (P1)
Demo web bằng checkpoint local, trình bày A/B metrics và pipeline weak-label không cần mạng.

## Yêu cầu

- **FR-001**: README chính được viết lại bằng tiếng Việt và phản ánh đúng 68.411 ViSoLex,
  20.000 review Phase 3, 48.411 review mở rộng Phase 8 và trạng thái Model B/Model C.
- **FR-002**: Có lệnh duy nhất `python scripts/verify_release.py` kiểm tra release manifest.
- **FR-003**: Manifest ghi path, loại artifact, Phase, SHA-256, kích thước và required/optional.
- **FR-004**: Notebook không chứa output secret, đường dẫn cá nhân hoặc biến trạng thái ẩn.
- **FR-005**: Dependency được tách thành local, Kaggle và development/test.
- **FR-006**: `.env.example` chỉ chứa placeholder và mô tả nhiều key phân tách bằng dấu phẩy.
- **FR-007**: Checkpoint lớn không commit Git; README chỉ rõ nơi tải và checksum.
- **FR-008**: Kịch bản demo cố định gồm input, output, bảng A/B và giải thích KEEP/EDIT/REJECT.
- **FR-009**: Release phân biệt rõ Model C là current app checkpoint theo Phase 10, Model B là
  rollback và historical winner Phase 5; Phase 9 là hậu kiểm trên Test đã quan sát, không phải
  holdout độc lập.

## Thành công

- Verify script exit 0 trên gói hoàn chỉnh và exit khác 0 khi thiếu/sai checksum.
- Secret scan không tìm thấy API key hoặc `.env` trong gói.
- Một người mới làm theo README chạy được local inference và web app.
- Demo web hoạt động khi tắt mạng.