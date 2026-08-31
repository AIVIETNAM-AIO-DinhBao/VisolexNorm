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

## Nghiệm thu offline từ checkpoint Kaggle v1

Kaggle Dataset version 1 đã được tải lại, Model C/B được đặt đúng `checkpoints/model_c/` và
`checkpoints/model_b/`, sau đó chạy với cả `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1`:

| Hạng mục | Kết quả |
|---|---|
| Input | `mik ko bt hnay đi hc ko` |
| Output | `mình không biết hôm nay đi học không` |
| Thời gian nạp + inference | 15.989 giây |
| Network model hub | Tắt bằng hai biến offline |
| Checkpoint inventory | Model C/B khớp Kaggle Dataset v1 |

Trên Windows, SentencePiece không mở được một số đường dẫn có ký tự Unicode. Runtime sao chép
chỉ các tokenizer assets nhỏ vào `%TEMP%/visolexnorm-tokenizers/`; `model.safetensors` vẫn được
nạp trực tiếp từ checkpoint vừa verify, không bị nhân bản.

Chi tiết machine-readable nằm trong `outputs/app/model_c_promotion_smoke_test.json`.

## Kaggle checkpoint handoff

Kaggle Dataset `dinhbaobao/visolexnorm-app-checkpoints-v1` version 1 đã được tải lại và xác minh:

| Model | Inventory SHA-256 | Kết quả |
|---|---|---|
| Model C | `e2f4b33dae20b2ed86a2b51d163b3cbe2063fbc24dc9b4a4e0cfe774f69fa622` | Khớp |
| Model B | `0361cfab6bad4b6e4d95367f5125320fb61d6d3327b92481d0a31a937140d0b7` | Khớp |

Version URL: `https://www.kaggle.com/datasets/dinhbaobao/visolexnorm-app-checkpoints-v1/versions/1`.
Bundle tải về có thêm một thư mục `checkpoints/` lồng nhau; trước inference, Model C/B được đặt
lại đúng layout `checkpoints/model_c/` và `checkpoints/model_b/`.

## Clean-room checklist

Tạo một venv mới và lặp lại các lệnh sau khi checkout release tag:

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
status Gradio và thời gian lần đầu/lần cache vào báo cáo này khi chạy trên máy sạch thứ hai.