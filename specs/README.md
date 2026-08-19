# Bản đồ đặc tả ViSoLexNorm

Thư mục này quản lý dự án theo Spec Kit. Mỗi thư mục con tương ứng với một **giai đoạn
dự án**, có phạm vi, đầu vào, đầu ra và cổng nghiệm thu độc lập.

## Trạng thái

| Mã | Giai đoạn | Trạng thái | Môi trường chính | Phụ thuộc |
|---|---|---|---|---|
| 001 | Chuẩn hóa dữ liệu | Hoàn thành | Local | Không |
| 002 | Baseline Model A | Hoàn thành | Kaggle GPU | 001 |
| 003 | Model A candidates và LLM review | Sẵn sàng triển khai | Kaggle GPU + Local | 001, 002 |
| 004 | Huấn luyện Model B | Chờ đầu vào Phase 3 | Kaggle GPU | 003 |
| 005 | Đánh giá thực nghiệm | Chờ Model B | Kaggle GPU + Local | 002, 004 |
| 006 | Suy luận local và web app | Chờ chọn checkpoint | Local | 005 |
| 007 | Tái lập và đóng gói | Chờ các giai đoạn trước | Local | 001–006 |

## Luồng artifact

```text
001 dữ liệu đã xử lý
  → 002 Model A
  → 003 candidates → Gemini review → weak labels
  → 004 Model B
  → 005 kết quả A/B và error analysis
  → 006 checkpoint tốt nhất và Gradio
  → 007 gói bàn giao tái lập được
```

## Quy ước tài liệu

- Nội dung dùng tiếng Việt; tên thư mục không dấu để tương thích công cụ.
- Phase 1–2 chỉ có `spec.md` lịch sử vì đã hoàn thành.
- Phase 3–7 có `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`,
  `contracts/`, `checklists/requirements.md` và `tasks.md`.
- “Phase” trong mẫu `tasks.md` của Spec Kit là nhóm nhiệm vụ nội bộ, không phải số giai
  đoạn dự án trong bảng trên.
- Tất cả bước train/fine-tune hoặc batch inference BARTpho dùng Kaggle GPU. Các bước còn
  lại chạy local.

## Cách tiếp tục với Spec Kit

Trước khi làm một giai đoạn, đặt `.specify/feature.json` trỏ đến thư mục tương ứng hoặc
truyền `SPECIFY_FEATURE_DIRECTORY`, rồi chạy tuần tự:

```text
/speckit-clarify
→ /speckit-plan
→ /speckit-tasks
→ /speckit-analyze
→ /speckit-implement
```

Các tài liệu thiết kế hiện có là quyết định đã chốt. Nếu thay đổi quyết định, phải cập nhật
`research.md`, contract liên quan và chạy lại bước phân tích nhất quán trước triển khai.