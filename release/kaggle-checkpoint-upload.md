# Upload checkpoint lên Kaggle Dataset

## Điều kiện trước upload

1. Đã kiểm tra quyền phân phối fine-tuned BARTpho checkpoint và metadata tokenizer.
2. Không upload raw/processed dataset, `.env`, API key, Gemini cache, SQLite review cache, `.git`
   hoặc notebook output.
3. Đã chạy release verifier local và ghi lại inventory Model C/B.

## Staging directory

Tạo thư mục ngoài Git, ví dụ `.tmp/kaggle-checkpoints-v1/`:

```text
checkpoints/
├── model_c/
└── model_b/
model_selection.json
checkpoint-inventory.json
README.md
```

`model_selection.json` là bản copy byte-identical của `outputs/app/model_selection.json`.
`checkpoint-inventory.json` phải ghi size và inventory SHA-256 sau:

| Model | Inventory SHA-256 |
|---|---|
| Model C | `e2f4b33dae20b2ed86a2b51d163b3cbe2063fbc24dc9b4a4e0cfe774f69fa622` |
| Model B | `0361cfab6bad4b6e4d95367f5125320fb61d6d3327b92481d0a31a937140d0b7` |

## Dataset

Tạo Kaggle Dataset với slug:

```text
dinhbaobao/visolexnorm-app-checkpoints-v1
```

Khởi tạo private trước. Kaggle credential phải được cấu hình ngoài repository; không commit
`kaggle.json` hoặc chạy lệnh upload với credential hiển thị trong log.

## Upload đã verify

Version đã upload và verify là
`https://www.kaggle.com/datasets/dinhbaobao/visolexnorm-app-checkpoints-v1/versions/1`.

Bundle version 1 đã được tải lại vào workspace, inventory Model C/B khớp bảng trên, strict
verifier pass và release dùng tag `v1.0.0`. Kaggle version mới trong tương lai phải lặp lại đầy đủ
download, inventory, offline demo và strict verification trước khi có release tag mới.