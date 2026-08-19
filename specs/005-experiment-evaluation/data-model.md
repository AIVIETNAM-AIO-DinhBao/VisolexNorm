# Mô hình dữ liệu: Đánh giá

## PredictionRecord

`id`, `input_text`, `target_text`, `prediction_text`, `model`, `checkpoint_checksum`,
`generation_config_hash`.

## MetricReport

Mỗi model có `sample_count`, `ERR`, `precision`, `recall`, `f1`, timestamp, evaluation code
checksum và prediction checksum.

## ErrorAnalysisRecord

Gồm input, gold, prediction A/B, category A/B, model tốt hơn và ghi chú `weak_label_evidence`
chỉ khi lỗi Model B có liên hệ hợp lý với pattern trong weak-label audit.