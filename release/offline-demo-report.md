# Báo cáo demo offline — release candidate

## Kết quả đã xác minh trên local

Phase 6 đã xác minh CPU runtime thật với checkpoint Model C local:

| Hạng mục | Kết quả |
|---|---|
| Tokenizer/model Model C | Nạp thành công, 518 weight entries |
| Input | `mik ko bt hnay đi hc ko` |
| Output | `mình không biết hôm nay đi học không` |
| Lượt đầu | 19.888 giây, gồm nạp model và generation |
| Lượt thứ hai | 2.286 giây, tái sử dụng runtime |
| Gradio | HTTP 200, callback end-to-end pass |
| Bind | `127.0.0.1`, không public share |
| LLM/Gemini | Không import/call trong app runtime |

Chi tiết machine-readable nằm trong `outputs/app/model_c_promotion_smoke_test.json`.

## Cổng clean-room còn chờ

Kaggle CLI và credential chưa có trên máy release nên checkpoint Model C/B chưa được upload vào
`dinhbaobao/visolexnorm-app-checkpoints-v1`, và chưa thể tải lại một Kaggle Dataset version cố
định. Vì vậy báo cáo này **không thay thế** clean-room acceptance cho tag `v1.0.0`.

Sau khi upload Dataset, thực hiện trên thư mục/venv mới:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-inference.txt
python scripts/verify_release.py --manifest release/manifest.json --strict-distribution
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
.venv\Scripts\python.exe -m visolexnorm.app.inference --text "mik ko bt hnay đi hc ko"
.venv\Scripts\python.exe -m visolexnorm.app.web
```

Ghi phiên bản Python/package, Kaggle Dataset URL/version, inventory checksum, CLI output, HTTP
status Gradio và thời gian lần đầu/lần cache vào báo cáo này trước khi gắn tag.