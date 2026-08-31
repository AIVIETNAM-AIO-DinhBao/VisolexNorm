# Nghiệm thu nhanh Phase 7

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-inference.txt
.venv\Scripts\python.exe scripts/verify_release.py --manifest release/manifest.json
.venv\Scripts\python.exe -m visolexnorm.app.inference --text "mik ko bt hnay đi hc ko"
.venv\Scripts\python.exe -m visolexnorm.app.web
```

Tải Model C/B từ Kaggle Dataset version được ghi trong manifest, đặt ở `checkpoints/`, rồi chạy
verifier trước inference. Sau khi dependency/checkpoint đã sẵn sàng, tắt mạng hoặc đặt
`HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1`, lặp lại hai lệnh app. Đối chiếu bảng metrics,
selection artifact và checksum với manifest. Verify phải báo rõ mọi artifact pass.

Chỉ khi Kaggle Dataset đã có URL version cố định mới chạy:

```powershell
.venv\Scripts\python.exe scripts/verify_release.py --manifest release/manifest.json --strict-distribution
```