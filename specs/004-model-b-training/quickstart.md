# Nghiệm thu nhanh Phase 4

1. Gắn repository, Model A, ViLexNorm và weak labels vào Kaggle Notebook GPU.
2. Mở `notebooks/train_model_b_kaggle.ipynb`, chạy smoke test 400 mẫu = 200 gold + 200 pseudo.
3. Xác nhận ratio 1:1, generation không rỗng và checkpoint load lại được. Smoke report ghi
   `initial_dev_loss`/`best_dev_loss`; loss không giảm trong chỉ 400 mẫu là cảnh báo để review,
   không phải lỗi hạ tầng. Dùng Dev loss của full 3-epoch run để chọn checkpoint.
4. Chạy full training và tải thư mục `checkpoints/model_b`, `outputs/model_b` về local.
5. Kiểm tra train config có checksum, 8.372 gold, 8.372 pseudo/epoch, union 18.970 pseudo và
   không chứa Test ID.