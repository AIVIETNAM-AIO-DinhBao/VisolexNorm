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
| `prompt_version` | null | Phiên bản prompt đã freeze |

## TrainingMixtureManifest

Lưu checksum Phase 3 manifest, gold/Dev/pseudo, số mẫu, seed và danh sách ID theo epoch, tỷ
lệ 1:1, prompt version, phân bố KEEP/EDIT và source. Mỗi epoch có `epoch_index`,
`epoch_seed`, `gold_ids`, `pseudo_ids`, `ordered_ids`, count và cờ replacement. Manifest
không sao chép nội dung Test.

## CheckpointInventory

Danh sách deterministic các file trong checkpoint Model A theo relative POSIX path. Mỗi entry
gồm `path`, `bytes`, `sha256`. `inventory_sha256` là SHA-256 của canonical JSON inventory
(`ensure_ascii=false`, sort keys, separators compact, UTF-8). Inventory được verify lại trước
smoke test và full training.