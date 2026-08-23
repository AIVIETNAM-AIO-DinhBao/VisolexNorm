# Quyết định nghiên cứu: Mở rộng weak-label pool

## 1. Phạm vi review

**Chọn**: Review 48.411 candidate chưa nằm trong manifest 20.000 Phase 3 để coverage review
toàn bộ 68.411 candidate; không gọi lại 20.000 ID cũ.

**Lý do**: Review cũ đã có cache, decision, audit và provenance hợp lệ. Dùng hiệu tập tránh
tốn chi phí, tạo decision mâu thuẫn và làm mất tính tái lập.

**Không chọn**: Gọi lại toàn bộ 68.411 mẫu vì vừa trùng 20.000 review cũ vừa có thể cho quyết
định khác với prompt/model runtime không còn hoàn toàn giống nhau.

## 2. Identity reviewer

**Chọn**: Giữ `lexical_norm_review_v1`, policy `lexical_policy_v1`, prompt hash đã freeze và
model identity Phase 3; batch 15, retry/cache/key pool giữ nguyên.

**Lý do**: Thay prompt/policy sau khi Test Phase 5 đã mở sẽ vi phạm chống rò rỉ và làm hai phần
pool không đồng nhất. Thay model provider chỉ được xem xét nếu identity Phase 3 không khả dụng
và phải có amendment được phê duyệt trước run, không dùng Test làm căn cứ.

## 3. Khởi tạo Model C

**Chọn**: Fine-tune Model C từ Model A, không tiếp tục Model B.

**Lý do**: So sánh Dev B/C khi cùng điểm xuất phát cho biết ảnh hưởng của quy mô weak label,
tránh trộn hiệu ứng train hai lần hoặc lịch optimizer cũ.

## 4. Số epoch và tỷ lệ mixture

**Chọn**: `ceil(pool_size / 8372)` epoch; mỗi epoch chính xác 8.372 gold + 8.372 pseudo và
sampler ưu tiên pseudo chưa dùng.

**Lý do**: Giữ cân bằng gold:pseudo đã chứng minh hiệu quả ở Model B, đồng thời đảm bảo mọi weak
label được dùng tối thiểu một lần. Wrap deterministic ở epoch cuối chỉ là cơ chế lấp batch.

## 5. Đánh giá sau Test

**Chọn**: Model C chọn bằng Dev-only và không thay Model B trong app.

**Lý do**: Test Phase 5 đã là dữ liệu đã quan sát. Dùng lại để chọn/tune Model C tạo leakage.
Promotion yêu cầu một holdout độc lập, freeze contract trước khi load holdout.

## 6. Trạng thái khoa học của Model C

**Chọn**: Model C là một thí nghiệm hậu kiểm tách biệt với kết luận A/B đã freeze của Phase 5.

**Lý do**: Quyết định mở rộng corpus được đưa ra sau khi biết Test A/B, nên không thể xem Model C
là một phần của so sánh Test đã đăng ký. Phase 5 giữ nguyên artifact/kết luận; Phase 8 chỉ báo cáo
Dev và phải được mô tả là exploratory cho tới khi có holdout độc lập.