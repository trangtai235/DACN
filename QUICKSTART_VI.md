# Bắt đầu — Windows không Docker

## 1. Chuẩn bị một lần

- Python **3.12, Windows installer 64-bit**: https://www.python.org/downloads/windows/ . Bật Python Launcher khi cài. Kiểm tra bằng `py -3.12 --version`.
- PostgreSQL **18** (hoặc 15–17): https://www.postgresql.org/download/windows/ . Chọn PostgreSQL Server và Command Line Tools khi cài. Giữ service hoạt động, thường port 5432. Nhớ mật khẩu quản trị `postgres`. Có thể bỏ qua Stack Builder.
- Giải nén source thành `C:\AnnotaFlow`. Cần Internet lần đầu để tải package Python. Không cần GPU, Node.js, Docker, WSL hoặc Redis.

## 2. Chạy

Trong PowerShell tại thư mục dự án:

```powershell
cd C:\Users\taitr\Downloads\AnnotaFlow
.\RUN_NATIVE_WINDOWS.bat
```

Ở lần chạy đầu, nhấn Enter để dùng host `127.0.0.1`, port `5432`, database `annotaflow`, tài khoản ứng dụng `annotaflow_app` và quản trị `postgres`. Nếu cài PostgreSQL ở cổng khác, nhập cổng đó. Nhập mật khẩu `postgres` đã đặt khi cài; khi gõ sẽ không hiện ký tự. Nếu tài khoản ứng dụng đã tồn tại, script sẽ hỏi mật khẩu hiện tại của tài khoản đó.

Script tự tạo và nạp `.env.local`; không cần sao chép `.env.example` hoặc tự tạo database.
Khi chạy native, các giá trị trong `.env.local` được ưu tiên hơn biến môi trường cùng tên của terminal.

Nhấp đúp `RUN_NATIVE_WINDOWS.bat` từ thư mục dự án. Script tạo `.venv`, cài dependency, hỏi host/port/database/role/password PostgreSQL, tạo tài khoản ứng dụng riêng có quyền trên database của nó, migrate, chuẩn bị 3 model và 3 người demo, chạy web.

- Mở http://127.0.0.1:8000.
- Tài khoản `tv1` quản lý; `tv2`, `tv3` người gán. Mật khẩu demo tạo ngẫu nhiên được in lần đầu và lưu trong `.env.local`. Không có mật khẩu mặc định chung.
- Lần sau nhấp đúp lại. Nhấn Ctrl+C ở cửa sổ server để dừng. Không đóng cửa sổ khi đang train/gọi API.
- Không chia sẻ `.env.local`, `.env.local.backup`, `backend/private_data/` hoặc `.venv/`.

Nếu cổng 8000 đang dùng, dừng server cũ trước. Nếu lỗi kết nối DB, mở `services.msc`, kiểm tra dịch vụ PostgreSQL (ví dụ `postgresql-x64-18`), cổng và mật khẩu. Để cấu hình lại:

```powershell
.venv\Scripts\python.exe scripts\native_setup.py --configure
```

Giữ nguyên `DJANGO_SECRET_KEY`: nó bảo vệ khóa API đã mã hóa. Đổi secret yêu cầu nhập lại các khóa API; không tự mất database.

### PostgreSQL riêng trong thư mục dự án

Trên máy đã được sửa lỗi khởi tạo UTF-8, database nằm ở `backend/private_data/postgres18`, dùng PostgreSQL 18 với locale provider `builtin`, locale `C.UTF-8`, các mục `LC_*` là `C` và múi giờ UTC. Database này chạy ở `127.0.0.1:5432`, không cần Windows service. `RUN_NATIVE_WINDOWS.bat` tự khởi động lại database này khi cần, rồi nạp `.env.local` và chạy web. Không chạy lại `initdb` trên thư mục dữ liệu.

Mật khẩu quản trị được lưu riêng ở `backend/private_data/postgres-admin-password.txt`; mật khẩu tài khoản ứng dụng và `DEMO_PASSWORD` nằm trong `.env.local`. Giữ các file này riêng tư. Ctrl+C dừng web; database có thể tiếp tục chạy. Để dừng database sau khi dừng web:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" -D ".\backend\private_data\postgres18" -m fast -w stop
```

## 3. Dùng ứng dụng

1. TV1 tạo dự án hoặc dùng dự án demo. Chỉnh bộ nhãn/hướng dẫn/redundancy trước khi nhập dữ liệu.
2. **Dữ liệu & nguồn → Nhập dữ liệu**: text, CSV mapping hoặc YouTube. Key YouTube nhập ở Tài khoản; không nhập ở bản online demo.
3. **Model & API**: chọn một trong 3 model có sẵn; thử câu; chạy gợi ý. Hoặc cấu hình API thật. Bản local không cần API key để dùng model tự train.
4. **Không gian gán nhãn**: mỗi người nộp nhãn riêng, có nhãn câu và spans; chế độ độc lập mặc định ẩn AI trước khi nộp. Nhãn đã xem AI được đánh dấu assisted khi có ghi nhận tiếp xúc.
5. **Đồng thuận & gold**: quản lý kiểm tra bất đồng câu/spans và chốt gold kèm lý do.
6. **Phiên bản dữ liệu**: chụp snapshot, tải JSON. Khôi phục lớp nhãn có backup; không rollback toàn database.
7. **Xuất dữ liệu**: chọn scope human hoặc gold cho tập dùng nghiên cứu. All có thể gồm AI chưa duyệt.
8. **Thực nghiệm kiểm tra** là luồng riêng nhị phân A/B/C/D: lượt đầu → tạo phiên → người khác kiểm tra mù → người thứ ba phân xử.

## 4. Train và đánh giá API

Huấn luyện mới cần 3 CSV UTF-8 riêng `text,label` (hoặc `Comment,Toxicity`). Label là key dự án hoặc chỉ số lớp theo thứ tự hiển thị. Mỗi split cần đủ lớp; loại giao nhau có thể làm thiếu lớp và job sẽ báo lỗi. Tập test không dùng fit/chọn cấu hình.

Ba model có sẵn là PhoBERT-base, XLM-R base và XLM-R large; xem `MODELS_VI.md` để cài trọng số từ bộ Drive. Chúng dự đoán spans BIO trên backend. Mã huấn luyện TF-IDF vẫn hỗ trợ thí nghiệm riêng với dữ liệu CSV; các trọng số TF-IDF cũ đã được bỏ khỏi bộ bàn giao. Bản demo tĩnh không chạy Transformer trong trình duyệt.

Chấm API baseline cần tải đúng ViCTSD test về máy:

```powershell
.venv\Scripts\python.exe backend\manage.py fetch_victsd
```

Model tự train dùng tập test đã upload của phiên. Vào Đánh giá → chọn model/API/số mẫu. Chỉ bấm chạy khi sẵn sàng gửi văn bản test đến nhà cung cấp và chấp nhận phí theo tài khoản của bạn. Giá cấu hình chỉ là ước tính.

## 5. Email và làm việc nhóm

Email mặc định ghi file ở `backend/private_data/emails`; không gửi thật. Để gửi thư mời/xác minh/reset ra ngoài, cấu hình SMTP theo `.env.example`, `SITE_URL` chính xác và `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`. Có thể bật `REQUIRE_EMAIL_VERIFICATION=1` sau khi mail hoạt động.

Local server chỉ bind máy bạn. Ba người có thể thử bằng 3 phiên trình duyệt. Chạy trên LAN/VPS cần cấu hình host, CSRF, HTTPS, firewall và backend chung; không dùng DEBUG=1 trên Internet.

## 6. Sửa code

Chỉnh `frontend/src/`, chạy `py -3.12 scripts/build_frontend.py`, reload trình duyệt. Backend chia theo module trong `backend/studio/api`, `studio/services`, `integrations/providers`, `experiments/algorithms`, `core/jobs`. Xem `docs/EXTENDING.md`.
