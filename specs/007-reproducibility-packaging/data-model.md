# Mô hình dữ liệu: Release manifest

## ReleaseArtifact

| Trường | Ý nghĩa |
|---|---|
| `path` | Đường dẫn tương đối hoặc tên artifact ngoài Git |
| `phase` | 1–7 |
| `artifact_type` | code, config, prompt, data, checkpoint, metrics, predictions, docs |
| `sha256` | Checksum 64 ký tự |
| `size_bytes` | Kích thước mong đợi |
| `required` | Bắt buộc hay tùy chọn |
| `distribution_url` | URL tải nếu không nằm trong repo |
| `contains_sensitive_data` | Luôn false với gói phát hành |

## ReleaseVerification

Thời gian chạy, phiên bản Python, số artifact pass/fail/missing, secret scan result và exit code.