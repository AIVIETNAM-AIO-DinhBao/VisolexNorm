# Bản đồ đặc tả ViSoLexNorm

Thư mục này quản lý dự án theo Spec Kit. Mỗi thư mục con tương ứng với một **giai đoạn
dự án**, có phạm vi, đầu vào, đầu ra và cổng nghiệm thu độc lập.

## Trạng thái

Số Phase là mã định danh lịch sử gắn với artifact, không phải hàng đợi thực hiện tuần tự. Xem
[`docs/roadmap.md`](../docs/roadmap.md) để biết thứ tự thực hiện và phần việc còn lại hiện hành.

| Mã | Giai đoạn | Trạng thái | Môi trường chính | Phụ thuộc |
|---|---|---|---|---|
| 001 | Chuẩn hóa dữ liệu | Hoàn thành | Local | Không |
| 002 | Baseline Model A | Hoàn thành | Kaggle GPU | 001 |
| 003 | Model A candidates và LLM review | Hoàn thành | Kaggle GPU + Local | 001, 002 |
| 004 | Huấn luyện Model B | Hoàn thành | Kaggle GPU | 003 |
| 005 | Đánh giá thực nghiệm A/B | Hoàn thành; Model B được chọn | Kaggle GPU + Local | 002, 004 |
| 006 | Hoàn thiện suy luận local và Gradio | Đang thực hiện; core inference đã có, còn Gradio và real CPU smoke | Local | 005, 010 |
| 007 | Tái lập, đóng gói và release | Chưa thực hiện; làm sau khi 006 hoàn tất | Local | 001–006, 008–010 |
| 008 | Mở rộng LLM review và huấn luyện Model C | Hoàn thành; boundary task cũ được 010 thay thế | Local + Kaggle GPU | 002, 003, 005 |
| 009 | Benchmark A/B/C hậu kiểm | Hoàn thành; Model C là descriptive leader | Kaggle GPU + Local | 005, 008 |
| 010 | Chọn checkpoint cho ứng dụng | Hoàn thành; Model C mặc định, Model B rollback | Local | 005, 009 |

## Luồng artifact

```text
001 dữ liệu đã xử lý
  → 002 Model A
  → 003 candidates → Gemini review → weak labels
  → 004 Model B
  → 005 kết quả A/B, chọn Model B và đóng băng Test
  ├→ 008 review phần candidate còn lại → Model C
  │    → 009 benchmark hậu kiểm → 010 chọn Model C cho app, Model B rollback
  └→ 006 hoàn thiện local inference và Gradio
       → 007 gói bàn giao tái lập được
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

Các tài liệu thiết kế giữ lại quyết định tại thời điểm mỗi Phase được thực hiện. Quyết định app
hiện hành nằm trong Phase 10: Model C là mặc định và Model B là rollback. Điều này không sửa
historical selection của Phase 5 và không biến benchmark hậu kiểm Phase 9 thành holdout độc lập.