# Chạy source tải từ GitHub

Đọc `QUICKSTART_VI.md` và chạy `RUN_NATIVE_WINDOWS.bat` để cài môi trường Python và cấu hình ứng dụng.

Repo không chứa `.venv`, `.env.local`, database, dữ liệu người dùng hoặc bộ model Transformer dung lượng lớn. Các file này vẫn được giữ trên máy gốc.

Để dùng PhoBERT/XLM-R offline, chép bộ model tương ứng vào `backend/artifacts/transformers/` từ bản dự án đầy đủ, rồi làm theo `MODELS_VI.md` để kiểm tra và đăng ký model. Source trên GitHub không tự tải các trọng số này.

Không chia sẻ `.env.local` hoặc thư mục `backend/private_data/` khi chuyển dự án sang máy khác.
