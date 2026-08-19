# Nhiệm vụ: Tái lập và đóng gói

- [ ] T001 [US1] Viết lại `README.md` bằng tiếng Việt theo pipeline và số liệu thực tế
- [ ] T002 [P] [US1] Viết `docs/reproducibility.md` với lệnh chạy Phase 1–7
- [ ] T003 [P] [US1] Tạo `docs/artifact-catalog.md` mô tả input/output từng Phase
- [ ] T004 [US1] Tách và cố định `requirements.txt`, `requirements-kaggle.txt`, `requirements-dev.txt`
- [ ] T005 [US2] Làm sạch toàn bộ notebook trong `notebooks/` và kiểm tra không có secret/path cá nhân
- [ ] T006 [US2] Cài đặt manifest/checksum/secret scan trong `scripts/verify_release.py`
- [ ] T007 [US2] Tạo `release/manifest.json` theo contract và thêm test tại `tests/integration/test_release_verification.py`
- [ ] T008 [US3] Viết kịch bản trình diễn cố định tại `docs/demo-script.md`
- [ ] T009 [US3] Chạy clean-room local setup và ghi kết quả demo offline vào `release/offline-demo-report.md`
- [ ] T010 [US3] Chạy verify cuối, gắn release 1.0.0 và lưu báo cáo tại `release/verification-report.json`