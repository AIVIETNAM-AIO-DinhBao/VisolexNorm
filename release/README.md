# ViSoLexNorm release candidate

`manifest.json` là inventory checksum cho source/docs/metrics của release candidate. Trạng thái
candidate tồn tại cho đến khi checkpoint Model C và Model B được upload, download lại và xác minh
từ Kaggle Dataset version cố định `dinhbaobao/visolexnorm-app-checkpoints-v1`.

Sau khi URL version được điền, chạy:

```powershell
python scripts/verify_release.py --manifest release/manifest.json --strict-distribution
```

Chỉ khi strict verification pass mới tạo Git tag `v1.0.0`.