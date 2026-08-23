# Checklist đặc tả: Review mở rộng và Model C

- [x] Phạm vi số lượng xác định: 68.411 candidate, 20.000 cũ, 48.411 còn lại.
- [x] Không review lại ID Phase 3; provenance/cached review được bảo toàn.
- [x] Prompt, policy, batch, retry và cache/resume được quy định cụ thể.
- [x] KEEP/EDIT/REJECT, validation và chống overlap Dev/Test được quy định.
- [x] Model C, checkpoint khởi tạo, mixture, coverage và hyperparameter được xác định.
- [x] Test Phase 5 bị cấm làm input cho Model C và promotion có cổng độc lập.
- [x] Phase 6 giữ Model B và chạy song song không phụ thuộc Gemini/training.
- [x] Tasks có ID, đường dẫn tệp và tiêu chí hoàn thành kiểm thử được.