# Mô hình dữ liệu: Local inference

## InferenceConfig

`checkpoint_path`, `checkpoint_checksum`, `model_name`, `max_source_length=128`,
`generation_num_beams=4`, `generation_max_length=128`, `device=auto`.

## NormalizeResult

`input_text`, `normalized_text`, `model_id`, `elapsed_ms`; trường nội bộ, UI chỉ hiển thị
normalized text. Lỗi validation trả mã `EMPTY_INPUT` hoặc `INPUT_TOO_LONG` và thông báo Việt.