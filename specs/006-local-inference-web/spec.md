# Đặc tả giai đoạn 6: Suy luận local và web app

**Trạng thái**: Đang thực hiện — lõi suy luận có từ Phase 10; còn Gradio và CPU smoke test thật
**Môi trường**: Laptop local, không yêu cầu GPU và không gọi LLM API

## Mục tiêu

Cung cấp một module `normalize(text)` và giao diện Gradio chạy local bằng checkpoint ứng dụng
được chọn trong `outputs/app/model_selection.json`. Phase 10 đã triển khai resolver, lazy loader
và CLI với Model C mặc định, Model B rollback. Phase 6 hoàn thiện runtime CPU, Gradio và nghiệm
thu offline; không dùng dependency/artifact review LLM.

## Amendment sau Phase 10

Yêu cầu ban đầu của Phase 6 dùng Model B cố định là ranh giới lịch sử hợp lệ khi Phase 8 đang
huấn luyện. Phase 9 và 10 sau đó tạo một quyết định app riêng có provenance. Vì vậy FR-001 và
FR-009 dưới đây được thay thế cho runtime hiện hành, nhưng vẫn được giữ trong lịch sử Git:

- đọc `outputs/app/model_selection.json`, không sửa `outputs/evaluation/best_model.json`;
- dùng Model C khi inventory khớp;
- fallback sang Model B khi Model C thiếu hoặc mismatch;
- từ chối inference nếu rollback Model B cũng không verify được.

## Kịch bản

### US1 — Chuẩn hóa bằng dòng lệnh (P1)
Người dùng nhập một câu và nhận đúng một chuỗi đã chuẩn hóa; model chỉ load một lần/process.

### US2 — Chuẩn hóa bằng Gradio (P1)
Người dùng mở web local, nhập text, nhấn `Normalize` và xem kết quả hoặc thông báo input rỗng.

### US3 — Chạy offline ổn định (P1)
Sau khi checkpoint/tokenizer đã có local, app chạy không cần Kaggle, dataset hoặc Gemini.

## Yêu cầu

- **FR-001**: Chỉ load selected/rollback checkpoint được ghi trong app selection; inventory phải khớp.
- **FR-002**: `normalize(text)` trim whitespace ngoài; input rỗng trả lỗi tiếng Việt, không infer.
- **FR-003**: Generation dùng beam 4, max length 128 và config đã freeze.
- **FR-004**: Model/tokenizer load lazy một lần và được tái sử dụng.
- **FR-005**: Input dài hơn 128 token bị từ chối với thông báo, không silently truncate.
- **FR-006**: Gradio bind mặc định `127.0.0.1`, không bật share public.
- **FR-007**: Không import Gemini SDK hoặc đọc `GEMINI_API_KEYS` trong inference/app.
- **FR-008**: App xử lý exception bằng thông báo an toàn, không hiển thị stack trace cho UI.
- **FR-009**: Model C là default theo Phase 10; Model B là rollback. Historical Phase 5
  `best_model.json` vẫn chọn Model B và không được dùng như current app-selection artifact.

## Thành công

- CLI và Gradio cho cùng output với cùng input/config.
- Input rỗng, chuẩn, teencode, viết tắt, Unicode và gọi liên tiếp đều pass smoke test.
- Lần gọi thứ hai không reload model.
- App chạy offline sau khi dependency và checkpoint đã có.
- CPU smoke test thật xác nhận tokenizer/model nạp thành công và kết quả suy luận không rỗng.