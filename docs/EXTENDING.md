# Thay API / thêm model / sửa giao diện

## Dùng API có sẵn — không sửa code

Trang Model & API → thêm kết nối → chọn Gemini / Ollama / OpenAI-compatible → base URL → model ID thực có trong tài khoản → API key → lưu → chọn → kiểm tra.

- Gemini base: `https://generativelanguage.googleapis.com/v1beta`.
- OpenAI-compatible base: endpoint gốc dạng `https://provider.example/v1`, không thêm `/chat/completions`.
- Ollama native: `http://127.0.0.1:11434`; Docker dùng `http://host.docker.internal:11434` khi máy host có Ollama phù hợp.
- Model ID không hardcode danh sách thương mại: nhập model đang có ở nhà cung cấp hoặc model đã pull vào Ollama.
- Custom hostname thêm vào `AI_ALLOWED_HOSTS`, khởi động lại server. Cấm URL userinfo, query, fragment; HTTP chỉ cho hostname local được cho phép; không follow redirects.
- Key mã hóa trong DB, UI chỉ trả key_configured. Ô key trống khi sửa giữ key cũ; clear_key mới xóa. Backup và giữ `DJANGO_SECRET_KEY` an toàn.
- Chọn provider là cấu hình dự án. YouTube key thuộc tài khoản và được mã hóa.

## Thêm giao thức API mới

1. Tạo adapter ở `backend/integrations/providers/<provider>.py` theo `base.py` và adapter hiện có.
2. Trả chung `label, spans, model_version, latency_ms, input_tokens, output_tokens`. Dùng validate_endpoint, prompt_for, parse_result; không đổi parse error thành nhãn bình thường.
3. Đăng ký factory trong `integrations/registry.py`; thêm kind và validation ở model/API. Nếu thay schema DB, tạo migration.
4. Thêm lựa chọn UI ở `frontend/src/features/models/index.js` và ví dụ allowlist vào env.
5. Viết test mocked request cho timeout/quota/JSON sai/label sai/offset sai, key không lộ và project permission; chạy một smoke test bằng tài khoản riêng trước báo cáo thực nghiệm thật.

## Thêm thuật toán học máy

1. `backend/experiments/algorithms/registry.py` quản lý estimator factory, tên, grid và parameter.
2. `experiments/training.py` dùng TF-IDF + classifier, fit train; chọn validation macro-F1; test chỉ chấm cấu hình đã chọn.
3. `core/jobs/training.py` đăng ký artifact mới vào ModelRun. UI lấy registry từ backend nên tự hiện thuật toán khi factory tương thích pipeline hiện có.
4. `core/services/providers.py` load ModelRun đã thuộc project; báo cáo lưu label_keys, counts, SHA-256, hyperparameter, confusion matrix, metrics, predictions.
5. Với PhoBERT/Transformer, cần trainer/inference adapter riêng, dependency/GPU và nghiên cứu split; không đặt neural model vào factory sklearn rồi coi đã hỗ trợ. Bản này chưa tích hợp Transformer.

## Sửa giao diện

Mỗi tính năng export `load`, `render`, `action`, `submit` và optional `change`. Router `frontend/src/app.js` đăng ký feature. View dùng T(vi,en), esc() cho văn bản, không đưa key vào HTML. Demo actions nằm riêng trong `core/demo.js`; hành vi cần backend hiển thị rõ yêu cầu backend, không trả metrics giả.

```bash
python scripts/build_frontend.py
```

Kiểm thử backend từ thư mục backend:

```bash
python manage.py test tests --settings=config.settings_test
```

SQLite chỉ dùng trong test cô lập. Production database luôn PostgreSQL 15. CI PostgreSQL cần chạy trong môi trường có server/runner phù hợp.
