# Bản đồ đặc tả ViSoLexNorm

Thư mục này quản lý dự án theo Spec Kit. Mỗi thư mục con tương ứng với một **giai đoạn
dự án**, có phạm vi, đầu vào, đầu ra và cổng nghiệm thu độc lập.

## Trạng thái

| Mã | Giai đoạn | Trạng thái | Môi trường chính | Phụ thuộc |
|---|---|---|---|---|
| 001 | Chuẩn hóa dữ liệu | Hoàn thành | Local | Không |
| 002 | Baseline Model A | Hoàn thành | Kaggle GPU | 001 |
| 003 | Model A candidates và LLM review | Hoàn thành | Kaggle GPU + Local | 001, 002 |
| 004 | Huấn luyện Model B | Hoàn thành | Kaggle GPU | 003 |
| 005 | Đánh giá thực nghiệm A/B | Hoàn thành; Model B được chọn | Kaggle GPU + Local | 002, 004 |
| 006 | Suy luận local và web app | Sẵn sàng triển khai với Model B | Local | 005 |
| 008 | Mở rộng LLM review và huấn luyện Model C | Đã lên kế hoạch; chạy song song 006 | Local + Kaggle GPU | 002, 003, 005 |
| 007 | Tái lập và đóng gói | Chờ 006 và 008 | Local | 001–006, 008 |

## Luồng artifact

```text
001 dữ liệu đã xử lý
  → 002 Model A
  → 003 candidates → Gemini review → weak labels
  → 004 Model B
  → 005 kết quả A/B, chọn Model B và đóng băng Test
  ├→ 006 Model B và Gradio local
  └→ 008 review phần candidate còn lại → Model C (Dev-only)
       └→ 007 gói bàn giao tái lập được
```

## Quy ước tài liệu

- Nội dung dùng tiếng Việt; tên thư mục không dấu để tương thích công cụ.
- Phase 1–2 chỉ có `spec.md` lịch sử vì đã hoàn thành.
- Phase 3–8 có `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`,
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
`research.md`, contract liên quan và chạy lại bước phân tích nhất quán trước triển khai. Test
đã mở ở Phase 5 không được dùng để chọn Model C hoặc thay checkpoint cho Phase 6.