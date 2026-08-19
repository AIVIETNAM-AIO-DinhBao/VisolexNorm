# Kế hoạch triển khai: Tái lập và đóng gói

## Cấu trúc đầu ra

```text
README.md
docs/
├── reproducibility.md
├── artifact-catalog.md
└── demo-script.md
release/
└── manifest.json
scripts/
└── verify_release.py
requirements.txt
requirements-kaggle.txt
requirements-dev.txt
```

## Trình tự

1. Kiểm kê artifact Phase 1–6 và phân loại tệp Git/ngoài Git.
2. Làm sạch notebook: restart, run-all trên môi trường tương ứng, xóa secret/path cá nhân.
3. Cố định dependency versions từ các lần chạy thành công.
4. Viết README tiếng Việt theo đúng pipeline và môi trường từng bước.
5. Sinh manifest SHA-256, triển khai verify + secret scan.
6. Chạy clean-room local setup cho inference/web và rehearsal demo offline.
7. Gắn version release `1.0.0` sau khi mọi kiểm tra pass.

## Cổng chất lượng

- Không sửa kết quả thí nghiệm khi đóng gói.
- Không đưa raw restricted data hoặc API key vào release.
- Mọi URL checkpoint có checksum và hướng dẫn tải.
- README không còn con số 121.087 như artifact thực tế; phải ghi 68.411 và giải thích ViHOS.