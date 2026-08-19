# Mô hình dữ liệu: Hỗn hợp train Model B

## TrainingExample

| Trường | Gold | Pseudo |
|---|---|---|
| `id` | ViLexNorm ID | ViSoLex ID |
| `input_text` | Bắt buộc | Bắt buộc |
| `target_text` | Human target | LLM-reviewed target |
| `label_source` | `human` | `model_a+llm_review` |
| `llm_decision` | null | KEEP hoặc EDIT |
| `original_source` | null | Source ViSoLex |

## TrainingMixtureManifest

Lưu checksum gold/pseudo, số mẫu, seed, danh sách ID theo epoch, tỷ lệ 1:1, prompt version,
phân bố KEEP/EDIT và source. Manifest không sao chép nội dung Test.