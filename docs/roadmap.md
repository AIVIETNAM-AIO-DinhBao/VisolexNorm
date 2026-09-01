# Roadmap hiện hành

Tài liệu này là nguồn trạng thái hiện hành của dự án. Số Phase là mã định danh lịch sử gắn với
mã nguồn, kiểm thử, manifest và artifact; số này không đồng nghĩa mọi nhánh công việc phải hoàn thành tuần
tự. Không đổi số một Phase đã sinh artifact đóng băng.

## Trạng thái tổng thể

### Đã hoàn thành

```text
001 Chuẩn bị dữ liệu
 → 002 Model A
 → 003 Weak-label review
 → 004 Model B
 → 005 Đánh giá A/B đóng băng
      └→ 008 Mở rộng review và huấn luyện Model C
           → 009 Benchmark A/B/C hậu kiểm
           → 010 Chọn Model C cho ứng dụng, Model B rollback
```

| Mã lịch sử | Nhánh công việc | Trạng thái hiện hành |
|---|---|---|
| 001 | Chuẩn bị dữ liệu | Hoàn thành |
| 002 | Baseline Model A | Hoàn thành |
| 003 | Model A candidates và LLM review | Hoàn thành |
| 004 | Huấn luyện Model B | Hoàn thành |
| 005 | Đánh giá A/B | Hoàn thành và đóng băng; Model B là lựa chọn lịch sử |
| 008 | Mở rộng review và Model C | Hoàn thành; ranh giới app cũ đã được Phase 10 thay thế |
| 009 | Benchmark A/B/C hậu kiểm | Hoàn thành; Model C dẫn đầu về mặt mô tả |
| 010 | Quyết định checkpoint ứng dụng | Hoàn thành; Model C mặc định, Model B rollback |

### Hoàn thành — Phase 006

Phase 10 đã cung cấp phần lõi cho suy luận local, và Phase 006 đã hoàn thiện nghiệm thu runtime/web:

- artifact chọn checkpoint ứng dụng;
- kiểm tra inventory checkpoint;
- bộ nạp model/tokenizer theo nhu cầu;
- CLI `normalize(text)`;
- chuyển dự phòng từ Model C về Model B;
- kiểm thử đơn vị cho bộ phân giải và rollback.
- Gradio responsive chỉ bind `127.0.0.1`, không public share và không gọi LLM API;
- kiểm thử callback/tích hợp cho validation, cache, Model C/Model B rollback và UI;
- CPU smoke thật: Model C nạp 518 weights, tạo output không rỗng và tái sử dụng runtime ở lần gọi thứ hai;
- nghiệm thu Gradio HTTP 200 cùng callback end-to-end trên loopback.

### Hoàn thành — Phase 007

Phase 007 hoàn thành sau khi Phase 006 có smoke test offline thật và nghiệm thu Gradio. Kết quả gồm:

- tài liệu tái lập và artifact catalog;
- manifest/checksum bản phát hành và quét secret;
- tách dependency;
- làm sạch notebook;
- Kaggle Dataset checkpoint Model C/B version cố định và inventory checksum;
- demo CLI offline từ checkpoint đã tải lại;
- strict release verification, secret scan và manifest/report phát hành.

## Đồ thị thực hiện thực tế

```text
001 → 002 → 003 → 004 → 005
                         ├→ 008 → 009 → 010  (đã hoàn thành)
                          └→ 006              (đã hoàn thành)
                               ↓
                                007             (đã hoàn thành)
```

Phase 008 được thiết kế chạy song song với Phase 006 nên có thể hoàn thành trước. Phase 009 và
010 là các quyết định hậu kiểm phát sinh từ nhánh Model C; chúng không làm thay đổi Phase
005 và không chứng minh một benchmark độc lập chưa từng quan sát.

## Vai trò checkpoint hiện tại

- **Ứng dụng hiện tại**: Model C, được chọn từ common Dev metrics theo `outputs/app/model_selection.json`.
- **Fallback**: Model B, đứng thứ hai trong common Dev ranking và có inventory được xác minh.
- **Lịch sử Phase 005**: `outputs/evaluation/best_model.json` vẫn chọn Model B giữa A và B.
- **Giới hạn khoa học**: Phase 009 dùng Test đã được quan sát; một holdout độc lập vẫn cần thiết
  nếu muốn đưa ra kết luận khoa học cuối cùng mạnh hơn.