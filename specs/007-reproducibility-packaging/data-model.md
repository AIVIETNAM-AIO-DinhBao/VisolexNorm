# Mô hình dữ liệu: Release manifest

## ReleaseArtifact

| Trường | Ý nghĩa |
|---|---|
| `path` | Đường dẫn tương đối hoặc tên artifact ngoài Git |
| `phase` | 1–10; mã Phase tạo artifact |
| `artifact_type` | code, config, prompt, data, checkpoint, metrics, predictions, docs |
| `kind` | `file` hoặc `directory`; checkpoint dùng inventory directory deterministic |
| `location` | `repository`, `local-handoff` hoặc `external` |
| `sha256` | Checksum 64 ký tự |
| `size_bytes` | Kích thước mong đợi |
| `required` | Bắt buộc hay tùy chọn |
| `distribution_url` | URL version cố định nếu artifact cần tải ngoài Git; release chính thức bắt buộc URL Kaggle cho Model C/B |
| `contains_sensitive_data` | Luôn false với gói phát hành |

## ReleaseVerification

Thời gian chạy, Python/Git revision, số artifact pass/fail/missing, secret scan, distribution
warnings và exit code. `manifest.json` không tự hash chính nó hoặc verification report để tránh
self-reference.