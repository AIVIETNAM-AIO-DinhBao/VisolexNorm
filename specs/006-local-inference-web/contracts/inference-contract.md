# Hợp đồng suy luận

## Python

```python
normalize(text: str) -> str
```

- Trả chuỗi chuẩn hóa không rỗng khi input hợp lệ.
- Ném `InputValidationError` cho input rỗng hoặc quá 128 token.
- Không sửa trạng thái model giữa các lần gọi.

## CLI

```text
python -m app.inference --text "mik ko bt hnay"
```

Exit 0 và in kết quả ra stdout; lỗi input exit 2 và in thông báo ra stderr.

## Gradio

Textbox input → nút `Normalize` → textbox output. Không có API LLM và không share public.