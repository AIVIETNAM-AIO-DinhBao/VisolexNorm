# Quyết định nghiên cứu: Đánh giá

## Protocol metric

**Chọn**: official ViLexNorm evaluation implementation. Đây là cách bảo đảm kết quả so sánh
được với công trình gốc. Nếu không tương thích môi trường, port nguyên logic sang Python hiện
tại và chứng minh output khớp fixture/reference trước khi đánh giá Test.

**Không chọn metric dựa trên BLEU/ROUGE**: đo giống chuỗi nhưng không trực tiếp phản ánh
precision/recall của thao tác lexical normalization theo yêu cầu nghiên cứu.

## Nơi chạy

**Chọn**: Generate A/B trên một Kaggle GPU notebook; tính metrics local. GPU giảm thời gian
suy luận, còn local giúp đóng băng và audit mã evaluation độc lập với session Kaggle.

## Chọn checkpoint cuối

**Chọn**: F1 cao nhất, sau đó ERR thấp nhất, sau đó Model A. Rule được freeze trước Test để
không lựa chọn hậu nghiệm theo ví dụ đẹp.