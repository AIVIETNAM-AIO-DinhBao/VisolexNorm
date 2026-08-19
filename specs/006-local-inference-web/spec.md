# Đặc tả giai đoạn 6: Suy luận local và web app

**Trạng thái**: Chờ best checkpoint Phase 5
**Môi trường**: Laptop local, không yêu cầu GPU và không gọi LLM API

## Mục tiêu

Cung cấp một module `normalize(text)` và giao diện Gradio chạy local bằng checkpoint được
chọn trong `outputs/evaluation/best_model.json`.

## Kịch bản

### US1 — Chuẩn hóa bằng dòng lệnh (P1)
Người dùng nhập một câu và nhận đúng một chuỗi đã chuẩn hóa; model chỉ load một lần/process.

### US2 — Chuẩn hóa bằng Gradio (P1)
Người dùng mở web local, nhập text, nhấn `Normalize` và xem kết quả hoặc thông báo input rỗng.

### US3 — Chạy offline ổn định (P1)
Sau khi checkpoint/tokenizer đã có local, app chạy không cần Kaggle, dataset hoặc Gemini.

## Yêu cầu

- **FR-001**: Chỉ load checkpoint được ghi trong `best_model.json`; checksum phải khớp.
- **FR-002**: `normalize(text)` trim whitespace ngoài; input rỗng trả lỗi tiếng Việt, không infer.
- **FR-003**: Generation dùng beam 4, max length 128 và config đã freeze.
- **FR-004**: Model/tokenizer load lazy một lần và được tái sử dụng.
- **FR-005**: Input dài hơn 128 token bị từ chối với thông báo, không silently truncate.
- **FR-006**: Gradio bind mặc định `127.0.0.1`, không bật share public.
- **FR-007**: Không import Gemini SDK hoặc đọc `GEMINI_API_KEYS` trong inference/app.
- **FR-008**: App xử lý exception bằng thông báo an toàn, không hiển thị stack trace cho UI.

## Thành công

- CLI và Gradio cho cùng output với cùng input/config.
- Input rỗng, chuẩn, teencode, viết tắt, Unicode và gọi liên tiếp đều pass smoke test.
- Lần gọi thứ hai không reload model.
- App chạy offline sau khi dependency và checkpoint đã có.