# Nghiệm thu nhanh Phase 6

```bash
pip install -r requirements-inference.txt
python -m visolexnorm.app.inference --smoke
python -m visolexnorm.app.inference --text "mik ko bt hnay đi hc ko"
python -m visolexnorm.app.web
```

Mở URL local Gradio, thử input rỗng, câu chuẩn, teencode, viết tắt và nhiều lần liên tiếp.
Tắt mạng sau khi checkpoint/tokenizer có local và xác nhận app vẫn chuẩn hóa được. Trước khi
Phase 6 triển khai `visolexnorm.app.web`, hai lệnh CLI dùng để nghiệm thu phần inference core.