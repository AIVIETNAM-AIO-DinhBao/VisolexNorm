<!--
Sync Impact Report
- Phiên bản: mẫu chưa định nghĩa → 1.0.0
- Nguyên tắc được thiết lập: ngôn ngữ; phạm vi chuẩn hóa; dữ liệu và rò rỉ;
  tái lập; môi trường thực thi; bí mật và API; quyết định minh bạch; cổng chất lượng.
- Phần bổ sung: ràng buộc kỹ thuật và quy trình phát triển.
- Phần loại bỏ: không có.
- Việc cần theo dõi: không có.
-->

# Hiến chương dự án ViSoLexNorm

## Nguyên tắc cốt lõi

### I. Tiếng Việt là ngôn ngữ chính

Tài liệu, thông báo người dùng, chú thích nghiệp vụ và báo cáo PHẢI dùng tiếng Việt.
Chỉ giữ tiếng Anh đối với tên riêng hoặc thuật ngữ đã phổ biến trong dự án như API, GPU,
checkpoint, JSONL, prompt, BARTpho, Gemini và Gradio. Không viết câu pha trộn hai ngôn ngữ
khi đã có cách diễn đạt tiếng Việt tự nhiên.

### II. Giới hạn đúng bài toán chuẩn hóa từ vựng

Mọi thành phần PHẢI phục vụ chuẩn hóa từ vựng tiếng Việt mạng xã hội: viết tắt,
teencode, slang, thiếu dấu và lỗi chính tả mang tính từ vựng. Hệ thống KHÔNG ĐƯỢC
paraphrase, sửa toàn bộ ngữ pháp, làm văn phong trang trọng hơn, tự kiểm duyệt nội dung,
hoặc thêm bớt thông tin. Nghĩa, sắc thái, emoji, hashtag và dấu câu PHẢI được bảo toàn
trừ khi thay đổi là cần thiết cho chuẩn hóa từ vựng.

### III. Bảo toàn dữ liệu và chống rò rỉ

Mỗi mẫu PHẢI giữ ID ổn định, nguồn dữ liệu và provenance cần thiết để truy vết.
ViLexNorm Train chỉ dùng huấn luyện; Dev chỉ dùng chọn checkpoint, cấu hình và ngưỡng;
Test chỉ được mở sau khi thí nghiệm đã đóng băng để đánh giá cuối. ViSoLex PHẢI loại
exact overlap với Dev/Test. Không được dùng Test để sửa prompt, bộ lọc hoặc siêu tham số.

### IV. Tái lập là yêu cầu bắt buộc

Mọi bước chọn mẫu, sinh candidate, gọi LLM, lọc dữ liệu, huấn luyện và đánh giá PHẢI
lưu cấu hình, seed, phiên bản prompt, tên mô hình, checkpoint, thống kê đầu vào/đầu ra và
đường dẫn artifact. Tác vụ dài PHẢI có cache, resume và không thay đổi thứ tự hoặc ID.
Các lựa chọn ngẫu nhiên PHẢI dùng seed cố định `2026` nếu đặc tả không quy định seed khác.

### V. Phân tách môi trường thực thi

Mọi bước train, fine-tune hoặc suy luận BARTpho theo lô lớn cần GPU PHẢI được triển khai
bằng Kaggle Notebook. Xử lý dữ liệu, chọn mẫu, gọi Gemini API, validation, thống kê,
đánh giá từ prediction có sẵn và ứng dụng web PHẢI chạy được trên laptop local.
Ứng dụng web cuối chỉ dùng checkpoint BARTpho và KHÔNG ĐƯỢC gọi LLM API.

### VI. Bí mật và sử dụng LLM API an toàn

API key chỉ được đọc từ biến môi trường hoặc secret. Giá trị khóa KHÔNG ĐƯỢC xuất hiện
trong mã nguồn, notebook, log, cache, artifact hoặc Git. Pipeline review PHẢI hỗ trợ nhiều
khóa Gemini bằng round-robin, cooldown khi chạm quota, retry có backoff và resume.
Mỗi request review PHẢI chứa đúng 15 mẫu để tiết kiệm quota, trừ request cuối của một lượt
có thể chứa ít hơn khi tổng số mẫu không chia hết cho 15.

### VII. Quyết định minh bạch, không lấp lửng

Mỗi kế hoạch PHẢI nêu một phương án chính đã chọn, lý do chọn và thông số cụ thể.
Không được để lại cách diễn đạt “có thể dùng A hoặc B” trong kế hoạch đã duyệt. Khi quyết
định cần nghiên cứu, `research.md` PHẢI đặt phương án đề xuất lên đầu, sau đó ghi ngắn gọn
ưu và nhược điểm của các phương án không chọn.

### VIII. Cổng chất lượng trước triển khai

Mỗi giai đoạn chưa thực hiện PHẢI có `spec.md`, checklist yêu cầu, `plan.md`, tài liệu thiết
kế liên quan và `tasks.md` nhất quán trước khi viết mã. Yêu cầu PHẢI kiểm thử được; nhiệm vụ
PHẢI có ID, đường dẫn tệp và tiêu chí hoàn thành. Không được triển khai khi còn điểm cần làm
rõ ảnh hưởng đến phạm vi, dữ liệu, chi phí hoặc kết quả nghiên cứu.

## Ràng buộc kỹ thuật và nghiên cứu

- Nguồn gold duy nhất là ViLexNorm; nguồn unlabeled duy nhất là corpus ViSoLex đã xử lý.
- Mô hình chính là `vinai/bartpho-syllable`.
- Model A chỉ là candidate generator; prediction của Model A không tự động trở thành nhãn.
- Mọi mẫu pseudo dùng train Model B PHẢI qua LLM với quyết định KEEP, EDIT hoặc REJECT.
- KEEP dùng candidate; EDIT dùng corrected text; REJECT không được vào tập huấn luyện.
- Artifact trao đổi giữa các bước dùng JSONL UTF-8; cấu hình dùng JSON; cache review dùng
  SQLite local.
- Final evaluation so sánh Model A và Model B trên cùng ViLexNorm Test bằng ERR,
  Precision, Recall và F1 theo protocol ViLexNorm.

## Quy trình phát triển và kiểm duyệt

1. Mỗi giai đoạn đi theo thứ tự: đặc tả → làm rõ → kế hoạch → thiết kế → nhiệm vụ →
   phân tích nhất quán → triển khai → nghiệm thu.
2. Phase 1 và Phase 2 đã hoàn thành được lưu dưới dạng đặc tả lịch sử ngắn; không tạo lại
   nhiệm vụ trừ khi phát hiện lỗi làm sai đầu vào của Phase 3.
3. Mọi thay đổi schema phải cập nhật contract, data model, validation và quickstart trước mã.
4. Mọi notebook Kaggle phải chạy từ đầu đến cuối, cài dependency rõ ràng, không có secret,
   không phụ thuộc trạng thái ẩn và xuất artifact ra `/kaggle/working`.
5. Mỗi giai đoạn chỉ được đánh dấu hoàn thành khi đạt toàn bộ tiêu chí thành công trong spec.

## Quản trị

Hiến chương này có ưu tiên cao hơn các kế hoạch và nhiệm vụ khác trong kho mã. Thay đổi
nguyên tắc phải nêu lý do, ảnh hưởng, kế hoạch chuyển đổi và tăng phiên bản theo semantic
versioning: MAJOR khi thay đổi không tương thích; MINOR khi thêm hoặc mở rộng nguyên tắc;
PATCH khi chỉ làm rõ câu chữ. Mọi lần duyệt đặc tả, kế hoạch và pull request phải kiểm tra
tuân thủ hiến chương. Ngoại lệ phải được ghi trong mục theo dõi độ phức tạp của `plan.md`
và được chủ dự án phê duyệt trước khi triển khai.

**Phiên bản**: 1.0.0 | **Phê chuẩn**: 2026-08-19 | **Sửa đổi gần nhất**: 2026-08-19
