# Nghiệm thu nhanh Phase 4

1. Gắn repository, Model A, ViLexNorm và weak labels vào Kaggle Notebook GPU.
2. Mở `notebooks/train_model_b_kaggle.ipynb`, chạy smoke test 400 mẫu.
3. Xác nhận ratio 1:1, loss giảm, generation không rỗng và checkpoint load lại được.
4. Chạy full training và tải thư mục `checkpoints/model_b`, `outputs/model_b` về local.
5. Kiểm tra train config có checksum, 8.372 gold, 8.372 pseudo/epoch và không chứa Test ID.