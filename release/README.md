# ViSoLexNorm release 1.0.0

`manifest.json` là inventory checksum cho source/docs/metrics và checkpoint app release. Model C
và Model B đã được upload, tải lại và xác minh từ Kaggle Dataset version cố định:

```text
https://www.kaggle.com/datasets/dinhbaobao/visolexnorm-app-checkpoints-v1/versions/1
```

Chạy strict verifier:

```powershell
python scripts/verify_release.py --manifest release/manifest.json --strict-distribution
```

Tag Git tương ứng là `v1.0.0`.