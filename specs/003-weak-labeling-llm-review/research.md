# Nghiên cứu và quyết định: Tạo nhãn yếu bằng LLM

## 1. Quy mô review

**Quyết định**: Sinh candidate cho 68.411 mẫu và review đúng 20.000 mẫu.

**Lý do**: 20.000 mẫu lớn hơn đáng kể tập gold 8.372 mẫu, đủ phân tầng theo nguồn và
confidence nhưng vẫn giới hạn chi phí API và khối lượng audit.

**Phương án không chọn**:
- Review 68.411 mẫu: độ phủ cao; nhược điểm là chi phí, thời gian và audit quá lớn trước khi
  chất lượng prompt được chứng minh.
- Chỉ review confidence cao: tiết kiệm; nhược điểm là thiên lệch và không đo được noise ở
  các vùng confidence khác.

## 2. Kích thước request LLM

**Quyết định**: 15 mẫu/request.

**Lý do**: Nằm giữa khoảng 10–20 theo yêu cầu, giảm overhead so với 10 nhưng an toàn hơn 20
về kích thước response và khả năng mapping ID. Batch cuối được phép nhỏ hơn 15.

**Phương án không chọn**:
- 10 mẫu: response ngắn, retry rẻ; nhiều request hơn 50% so với batch 15.
- 20 mẫu: ít request hơn; response dài hơn, lỗi một batch làm retry nhiều mẫu hơn.

## 3. Điều phối nhiều API key

**Quyết định**: Round-robin trên danh sách khóa đang hoạt động; mỗi khóa có tối đa một
request in-flight; quota error cooldown 60 giây.

**Lý do**: Phân tải công bằng, dễ kiểm thử, không cần dự đoán quota từng khóa và không làm
một khóa bị dồn request đồng thời.

**Phương án không chọn**:
- Random key: đơn giản nhưng phân tải không xác định và khó tái hiện lỗi.
- Dùng hết quota một khóa rồi đổi: dễ làm gián đoạn dài và phân tải không công bằng.

## 4. Cache review

**Quyết định**: SQLite local, WAL mode, commit theo batch thành công.

**Lý do**: Giao dịch nguyên tử, truy vấn trạng thái nhanh, chống record trùng và resume an
toàn hơn append JSONL khi tiến trình dừng giữa lúc ghi.

**Phương án không chọn**:
- JSONL append: dễ đọc nhưng cần tự xử lý dòng hỏng, duplicate và transaction.
- Một tệp JSON lớn: cập nhật tốn chi phí và dễ hỏng toàn tệp.

## 5. Confidence và phân tầng

**Quyết định**: Confidence là trung bình token log-probability được tái dựng bằng
`compute_transition_scores(..., normalize_logits=true)`, bỏ decoder start, padding và EOS.
Không dùng `sequences_scores` vì giá trị này còn phụ thuộc `length_penalty` của generation.
Trong từng source, chia tercile thấp/trung bình/cao theo rank ổn định `(confidence, id)`.

**Lý do**: Score chuẩn hóa giảm thiên lệch theo độ dài; rank ổn định xử lý được nhiều score
bằng nhau và bảo đảm ba nhóm gần bằng nhau.

## 6. Phân bổ source

**Quyết định**: Phân bổ quota 20.000 theo tỷ lệ bốn nguồn còn dữ liệu bằng phương pháp phần
dư lớn nhất; sau đó chia đều quota nguồn cho ba confidence band.

**Lý do**: Giữ phân bố domain của corpus thực tế mà vẫn audit được mọi vùng confidence.
ViHOS được ghi trong thống kê với quota 0 vì Phase 1 không còn record.

## 7. Pilot và đóng băng prompt

**Quyết định**: Pilot 240 mẫu, đúng 20 mẫu cho mỗi tổ hợp bốn source × ba band. Pilot dùng
định danh `lexical_norm_review_draft` và cache theo SHA-256 nội dung. Audit thủ công 100%; khi
đạt, nội dung draft được sao chép nguyên văn thành `lexical_norm_review_v1` và khóa bằng hash.
Nếu không đạt, sửa draft và chạy lại toàn bộ 240 mẫu trong namespace hash mới.

**Lý do**: Thiết kế cân bằng giúp phát hiện failure mode theo domain và confidence trước khi
trả chi phí cho batch lớn.

## 8. Ngưỡng validation

**Quyết định**: Length ratio target/input trong [0,5; 2,0] và normalized character edit ratio
không quá 0,8. Record vượt ngưỡng bị loại và đưa vào audit, không sửa tự động.

**Lý do**: Ngưỡng đủ rộng cho ánh xạ 1→n/n→1 nhưng chặn output bị cắt, giải thích dài hoặc
viết lại cực đoan. Ngưỡng được chốt trước batch chính và không dùng Test để chỉnh.