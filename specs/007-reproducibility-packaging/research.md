# Quyết định nghiên cứu: Đóng gói

## Manifest

**Chọn**: JSON manifest + SHA-256 và verify script Python. Định dạng máy đọc được, đa nền
tảng và kiểm tra được cả tệp nhỏ lẫn checkpoint tải riêng.

**Không chọn chỉ checklist Markdown**: dễ đọc nhưng không tự phát hiện tệp bị đổi/hỏng.

## Model weights

**Chọn**: không commit checkpoint vào Git; phát hành qua Kaggle Dataset/drive bàn giao và ghi
URL cùng SHA-256 trong manifest. Tránh repository phình lớn và giới hạn Git hosting.

## Dependency

**Chọn**: `requirements.txt` cho local app/API scripts, `requirements-kaggle.txt` cho GPU,
`requirements-dev.txt` cho test. Phân tách giúp app cuối không cài Gemini/training package
không cần thiết; các package dùng review được đặt trong local requirements nhưng app không import.