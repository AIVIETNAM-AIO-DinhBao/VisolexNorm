# Nhiệm vụ: Tái lập và đóng gói

- [x] T001 [US1] Viết lại `README.md` bằng tiếng Việt theo pipeline và trạng thái Phase 1–10.
- [x] T002 [P] [US1] Viết `docs/reproducibility.md` với lệnh chạy Phase 1–10 và execution graph thực tế.
- [x] T003 [P] [US1] Tạo `docs/artifact-catalog.md`, phân biệt Model C app, Model B rollback và historical Phase 5 selection.
- [x] T004 [US1] Tách và cố định `requirements.txt`, `requirements-kaggle.txt`, `requirements-dev.txt`.
- [x] T005 [US2] Làm sạch toàn bộ notebook trong `notebooks/` và kiểm tra không có secret/path cá nhân.
- [x] T006 [US2] Cài đặt manifest/checksum/secret scan trong `scripts/verify_release.py`.
- [x] T007 [US2] Tạo `release/manifest.json` theo contract, `release/checkpoint-inventory.json` và test tại `tests/integration/test_release_verification.py`. Candidate verifier pass; strict distribution chờ Kaggle URL version.
- [x] T008 [US3] Viết kịch bản trình diễn cố định tại `docs/demo-script.md`.
- [ ] T009 [US3] Chạy clean-room local setup và ghi kết quả demo offline vào `release/offline-demo-report.md`. Báo cáo candidate đã có; còn chờ Kaggle Dataset upload/download.
- [ ] T010 [US3] Chạy verify strict cuối, gắn release 1.0.0 và lưu báo cáo tại `release/verification-report.json`. Chờ Kaggle Dataset URL version cố định.