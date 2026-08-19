# Quyết định nghiên cứu: Ứng dụng local

## Framework

**Chọn Gradio**: ánh xạ trực tiếp một hàm Python vào textbox/button/output, ít mã, phù hợp
demo mô hình và chạy local.

**Không chọn Streamlit**: mạnh cho dashboard nhưng rerun script theo tương tác cần quản lý
cache model riêng và dư tính năng cho một luồng normalize đơn giản.

## Input dài

**Chọn từ chối rõ ràng khi vượt 128 token**: tránh silently truncate làm mất thông tin và tạo
output sai nghĩa. Không chia câu tự động vì ghép đoạn có thể thay đổi ngữ cảnh và chưa được train.

## Thiết bị

**Chọn tự động CUDA nếu có, nếu không CPU**: app không yêu cầu GPU nhưng tận dụng được GPU
local mà không thay đổi output contract.