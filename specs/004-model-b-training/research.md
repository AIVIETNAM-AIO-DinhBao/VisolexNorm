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

## Xoay vòng pseudo

**Chọn**: Epoch `e` dùng seed `2026 + e`, ưu tiên ID chưa dùng rồi bổ sung deterministic từ
ID đã dùng. Với pool 18.970 và ba epoch × 8.372 pseudo, mọi ID được dùng ít nhất một lần;
12.824 ID dùng một lần và 6.146 ID dùng hai lần. Không có ID lặp trong cùng epoch.

**Không chọn một subset cố định**: đạt tỷ lệ 1:1 nhưng bỏ phí hơn nửa pool pseudo.
**Không chọn shuffle độc lập toàn pool ở mỗi epoch**: deterministic nhưng không bảo đảm
coverage đủ 18.970 sau ba epoch.

## Vòng lặp huấn luyện

**Chọn**: Load model, optimizer và scheduler một lần; tạo DataLoader mới cho mỗi epoch theo
manifest. Run chuẩn luôn chạy đủ ba epoch rồi chọn best checkpoint bằng Dev loss.

**Không chọn Trainer với dataset cố định**: sẽ lặp cùng membership pseudo qua mọi epoch.
**Không early-stop run chuẩn**: dừng trước epoch 3 có thể làm mất coverage pseudo đã cam kết.

## Siêu tham số

**Chọn**: Learning rate 2e-5, 3 epoch. Fine-tune tiếp từ Model A cần bước cập nhật nhỏ hơn
baseline 3e-5; 3 epoch giới hạn overfit vào weak labels. Chỉ thay cấu hình khi Dev cho thấy
lỗi bất thường và mọi lần thử phải được lưu.