# Xác minh AnnotaFlow Studio 3

Ngày tạo bản dựng: 24–25/10/2026 (UTC và giờ Việt Nam).

## Kiểm tra bổ sung trên Windows ngày 25/10/2026

- Đã tạo database PostgreSQL 18.6 UTF-8 trong `backend/private_data/postgres18` với provider `builtin`, locale `C.UTF-8`, các mục `LC_*` là `C` và múi giờ UTC sau khi installer gặp lỗi encoding.
- Đã chạy toàn bộ migrations và seed demo trên PostgreSQL thật; kiểm tra cả ba tài khoản demo, đăng nhập HTTP và tải workspace thành công.
- Trang chủ, JavaScript và CSS trả HTTP 200; truy vấn tiếng Việt qua database giữ nguyên nội dung.
- Đã dừng database và kiểm tra helper khởi động lại thành công, kết nối được bằng tài khoản ứng dụng. Native startup ưu tiên `.env.local` để tránh biến `DEBUG` của terminal làm mất tài nguyên giao diện.
- Các kết quả bên dưới ghi nhận bản dựng ban đầu; kiểm tra bổ sung này không thay thế toàn bộ integration tests hoặc thử tải production.

## Đã chạy

- **56 kiểm thử backend** qua trên profile SQLite **chỉ dành cho test**: tài khoản/CSRF/quyền dự án, nghiên cứu mù/người thứ ba/ngân sách, Unicode spans, optimistic revision, redundancy, skip/undo, sticky AI exposure, khóa dự án, nhãn chỉ dùng trong spans, đồng thuận/gold, phiên bản/backup/null gold/monotonic revision, 16 exports/XLSX, mã hóa key, endpoint allowlist, mocked Ollama, invitation/revoke/email/reset, real local prediction job không Redis, pin cấu hình, mocked YouTube resume giữa reply page và thay đổi khóa khi request đang chạy.
- Pipeline train thật cho cả 3 thuật toán; test bổ sung train đủ 3 lớp cho mỗi thuật toán.
- Seed dữ liệu idempotent và đăng ký 3 model theo dự án; tạo mới không ghi đè password cũ.
- Bộ model hiện tại: PhoBERT-base, XLM-R base và XLM-R large từ ZIP ViHOS. Kiểm tra nạp trọng số và suy luận thật bằng `import_transformers --verify`; điểm test là báo cáo được cung cấp, chưa đo lại.
- 16 browser export converters sinh được output; Unicode/partial-token BIO đúng fixture; XLSX của browser được đọc lại bằng openpyxl, đủ 3 sheets.
- Django system check không có lỗi; migration check không thiếu thay đổi; Python compile, JS syntax và pip check qua.
- Windows CPython 3.12 x86_64 dependency resolution được kiểm tra bằng pip dry-run/only-binary; không cần biên dịch scientific packages bằng C trên máy Windows.
- Compose YAML được parse/kiểm tra: PostgreSQL 15, Redis, web/worker, worker chờ web healthy, cổng web localhost. Không chạy daemon.
- Browser QA: mở login/demo, chuyển vai, tạo/chuyển dự án, lưu cấu hình, chọn model, dự đoán câu mới, hiển thị đánh giá, chọn token/span, lưu nhãn và chuyển mẫu. Ảnh giao diện từ trình duyệt được giữ làm bằng chứng phiên làm việc; không phải kết quả human study.

## Chưa chạy

- Không có PostgreSQL 15 hoặc Docker daemon hoạt động trong môi trường tạo bản dựng. Chưa kiểm tra transaction/concurrency trên PostgreSQL thật. CI PostgreSQL 15 đã cấu hình, **chưa có kết quả workflow chạy**.
- Chưa thực thi installer trên Windows thật. Dry-run package resolution không thay thế thử toàn bộ startup PostgreSQL/migrations/threads trên Windows.
- Chưa gọi Gemini/Ollama/OpenAI-compatible/YouTube thật bằng tài khoản có khóa, chưa kiểm tra quota/phí/provider model ID. API tests dùng mocks. Email dùng local backend; SMTP chưa gửi thật.
- Chưa thử tải production, nhiều worker tranh chấp, thiết bị di động thật, backup PostgreSQL/restore máy mới hoặc human study độc lập.
- Bản Site online chỉ host static demo. Dữ liệu demo lưu trong browser; không có PostgreSQL/backend/API host kèm. Source native/Docker là bản backend để nhóm tự chạy.

## Lệnh kiểm tra lại

Từ thư mục backend:

```bash
python manage.py test tests --settings=config.settings_test
python manage.py makemigrations --check --dry-run --settings=config.settings_test
```

Từ root:

```bash
python scripts/build_frontend.py
node scripts/check_exports.mjs
npm run check
```

Node chỉ dùng cho kiểm tra cú pháp/converter, không bắt buộc để build hoặc chạy web.

Sau khi có PostgreSQL thật: dùng cấu hình development riêng và `python manage.py test tests` không dùng settings_test; role test cần quyền tạo test database. Thử multi-user cùng sửa 1 record, hủy/tiếp tục job đang gọi API, restart server, khóa và thu hồi quyền giữa job, sau đó kiểm tra dữ liệu/history.
