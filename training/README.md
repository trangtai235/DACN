# Huấn luyện và bằng chứng chạy thực tế

- `vihos/`: ba script nguyên bản từ ZIP trước train; hash được giữ nguyên.
- `configs/three_models.json`: cấu hình lệnh theo hồ sơ được cung cấp.
- `provenance/import_manifest.json`: ghi nhận việc nhập dữ liệu và đối chiếu
  nguồn; không phải log của lần train trước đây.
- `evidence/imported/`: báo cáo/tài liệu người dùng cung cấp, giữ nguyên.
- `evidence/runs/`: chỉ được tạo khi thực sự chạy `run_experiment.py`.
- `runs/`: đầu ra model mới của mỗi lần chạy; bị bỏ qua bởi Git.
- `run_experiment.py`: wrapper gọi đúng mã gốc, ghi commit, hash, tham số,
  môi trường, thiết bị, log, thời gian và hash đầu ra của lần chạy đó.

Mẫu lệnh kiểm tra, không train:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/verify_training_bundle.py --weights
.venv/Scripts/python.exe -X utf8 training/vihos/train_vihos.py --check-data --data-root datasets/ViHOS
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model xlmr-base --dry-run
```

Notebook đã được bỏ khỏi source theo yêu cầu. Pipeline huấn luyện dùng các script Python trong `training/vihos/`. Các báo cáo có số liệu epoch không tự chứng minh thời gian,
thiết bị hoặc commit lịch sử. Để chứng minh một lần train mới từ source này,
commit các input và script trước, rồi chạy wrapper mà không dùng `--dry-run`.

Hướng dẫn đầy đủ: `docs/HUONG_DAN_TICH_HOP_DATASET_VA_MINH_CHUNG_TRAIN.md`.
