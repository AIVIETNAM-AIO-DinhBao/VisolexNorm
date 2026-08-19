# Quyết định nghiên cứu: Model B

## Khởi tạo

**Chọn**: Khởi tạo từ Model A. Cách này tiếp tục từ mô hình đã học đúng task trên gold và
giảm nguy cơ pseudo-data kéo mô hình lệch ngay từ đầu.

**Không chọn BARTpho gốc**: độc lập hơn nhưng cần học lại task và tốn GPU, không tận dụng
baseline đã xác nhận.

## Trộn dữ liệu

**Chọn**: 1:1 theo mỗi epoch, toàn bộ 8.372 gold + 8.372 pseudo.

**Không chọn tỷ lệ tự nhiên**: pseudo có thể lớn gấp đôi gold và áp đảo supervision sạch.
**Không chọn loss weighting nhưng giữ toàn pseudo**: phức tạp hơn, batching dài hơn và khó
giải thích so với sampler cân bằng.

## Siêu tham số

**Chọn**: Learning rate 2e-5, 3 epoch. Fine-tune tiếp từ Model A cần bước cập nhật nhỏ hơn
baseline 3e-5; 3 epoch giới hạn overfit vào weak labels. Chỉ thay cấu hình khi Dev cho thấy
lỗi bất thường và mọi lần thử phải được lưu.