# Mô hình dữ liệu: Đánh giá

## PredictionRecord

Gồm đúng bảy trường bắt buộc: `id`, `input_text`, `target_text`, `prediction_text`, `model`,
`checkpoint_checksum`, `generation_config_hash`. `model` chỉ là `model_a` hoặc `model_b`; hai
checksum phải khớp artifact đã khóa trong freeze manifest. Schema máy đọc là
`contracts/prediction.schema.json`.

## MetricReport

Mỗi model có `sample_count`, `ERR`, `precision`, `recall`, `f1`, timestamp, evaluation code
checksum và prediction checksum. `best_model.json` chỉ chọn giữa hai model đã freeze theo
`f1` cao hơn → `ERR` cao hơn → `model_a` cho manifest mới; report lưu nguyên rule từ
manifest lịch sử để tái lập những lượt Test đã freeze.

## ErrorAnalysisRecord

Gồm input, gold, prediction A/B, category A/B, model tốt hơn và ghi chú `weak_label_evidence`
chỉ khi lỗi Model B có liên hệ hợp lý với pattern trong weak-label audit đã freeze. Mỗi dự đoán
có đúng một nhãn; audit lấy tối đa 100 lỗi/model theo thứ tự ID.