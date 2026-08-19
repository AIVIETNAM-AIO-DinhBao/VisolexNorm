# Nghiệm thu nhanh Phase 7

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
python scripts/verify_release.py --manifest release/manifest.json
python -m app.inference --text "mik ko bt hnay đi hc ko"
python -m app.web
```

Sau khi dependency/checkpoint đã sẵn sàng, tắt mạng và lặp lại hai lệnh app. Đối chiếu bảng
metrics, best model và checksum với manifest. Verify phải báo rõ mọi artifact pass.