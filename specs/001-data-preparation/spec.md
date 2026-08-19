# Đặc tả giai đoạn 1: Chuẩn hóa dữ liệu

**Trạng thái**: Hoàn thành
**Nguồn yêu cầu**: `SPECIFICATIONS.md`, `PLAN.md`
**Phạm vi tài liệu**: Ghi nhận ngắn kết quả đã triển khai, không lập lại kế hoạch.

## Mục tiêu đã hoàn thành

Chuẩn hóa ViLexNorm và corpus ViSoLex về JSONL có schema ổn định mà không làm mất lexical
noise, đồng thời tách Train/Dev/Test và loại exact overlap với Dev/Test.

## Artifact và mã nguồn

- `data/processed/vilexnorm_train.jsonl`: 8.372 mẫu.
- `data/processed/vilexnorm_dev.jsonl`: 1.050 mẫu.
- `data/processed/vilexnorm_test.jsonl`: 1.045 mẫu.
- `data/processed/visolex_unlabeled.jsonl`: 68.411 mẫu.
- `scripts/prepare_vilexnorm.py`
- `scripts/prepare_visolex.py`
- `scripts/check_data.py`
- `scripts/data_utils.py`

## Kết quả ViSoLex thực tế

| `original_source` | Số mẫu giữ lại |
|---|---:|
| ViHSD | 30.579 |
| UIT-VSMEC | 6.916 |
| ViHOS | 0 |
| ViSpamReviews | 19.805 |
| UIT-ViSFD | 11.111 |
| **Tổng** | **68.411** |

Public release hiện dùng không đạt con số kỳ vọng khoảng 121.087 câu. Toàn bộ ViHOS trùng
exact với ViHSD đã được nạp trước nên deduplicate toàn cục giữ provenance ViHSD và để ViHOS
bằng 0. Raw ViHOS vẫn được giữ local để audit. Các giai đoạn sau PHẢI dùng số liệu thực tế
68.411 và không giả định ViHOS còn mẫu.

## Quy tắc đã áp dụng

- Loại null/empty, chuẩn hóa Unicode và whitespace, tạo ID ổn định.
- Deduplicate exact input trên corpus ViSoLex kết hợp.
- Loại exact overlap với ViLexNorm Dev/Test.
- Không sửa teencode, chính tả, hoa thường, dấu câu hoặc dấu tiếng Việt.
- Giữ `dataset`, `split`, `label_source` và `original_source` theo schema tương ứng.

## Tiêu chí nghiệm thu

- Bốn JSONL đọc được, đúng schema và không trộn split.
- Không có input ViSoLex exact-overlap với ViLexNorm Dev/Test.
- Chạy lại cùng raw data và thứ tự nguồn cho cùng ID, số lượng và nội dung.
- Thống kê theo nguồn khớp bảng trên.