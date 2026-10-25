> Muốn bỏ Docker/WSL: dùng `RUN_NATIVE_WINDOWS.bat`, xem [QUICKSTART_VI.md](../QUICKSTART_VI.md). Các hướng dẫn bên dưới dành riêng cho Docker tùy chọn.

# Chạy AnnotaFlow trên Windows

## Lỗi trong ảnh bạn gửi

Thông báo `docker : The term 'docker' is not recognized` xuất hiện vì PowerShell không tìm thấy chương trình Docker. Nguyên nhân có thể là chưa cài Docker Desktop hoặc terminal chưa nhận PATH sau khi cài. Lệnh chưa chạy tới ứng dụng hay PostgreSQL.

1. Tải và cài **Docker Desktop for Windows** từ [hướng dẫn chính thức](https://docs.docker.com/desktop/setup/install/windows-install/), chọn bản phù hợp CPU của máy.
2. Dùng WSL 2 / Linux containers. Nếu trình cài yêu cầu WSL, làm theo hướng dẫn của Docker và khởi động lại máy khi được yêu cầu.
3. Mở **Docker Desktop**, hoàn tất các bước thiết lập của bạn và chờ Docker Engine hoạt động. Cài xong chưa có nghĩa Docker đã chạy.
4. Đóng rồi mở lại VS Code và PowerShell để terminal nhận PATH mới.
5. Kiểm tra:

```powershell
docker --version
docker compose version
docker info
```

Hai lệnh đầu xác nhận CLI/Compose; lệnh cuối cần kết nối được Engine. Nếu vẫn không nhận `docker`, kiểm tra hoặc sửa cài đặt Docker Desktop thay vì đổi cơ sở dữ liệu. Nếu CLI chạy nhưng `docker info` lỗi, mở Docker Desktop và xem trạng thái Engine.

## Khởi động dự án

Giải nén bản source mới, mở thư mục chứa `docker-compose.yml` trong VS Code. Không chạy lệnh ở ngoài thư mục đó.

```powershell
.\START_WINDOWS.bat
```

Script kiểm tra Docker/Compose/Engine, tạo `.env` nếu chưa có rồi chạy Compose. Script không tự cài Docker và không thay đổi PATH của máy. Nếu cần tạo `.env`, máy cần Python 3. Mật khẩu ba tài khoản demo được script Python in tại máy bạn khi tạo cấu hình lần đầu.

Hoặc chạy từng bước:

```powershell
python scripts/setup_env.py
docker compose up --build
```

Nếu `.env` đã tồn tại thì giữ file đó và chạy ngay lệnh Compose. Thông báo “.env đã tồn tại” không phải lỗi Docker. Không xóa volume để sửa lỗi CLI vì volume chứa dữ liệu PostgreSQL.

Mở **http://localhost:8000**. Đăng nhập `tv1`, `tv2`, `tv3` bằng mật khẩu `DEMO_PASSWORD` trong `.env` của bạn, hoặc chọn **Tạo tài khoản**. Tài khoản mới bắt đầu với không gian trống, không tự tham gia các dự án demo. Bạn có thể tạo dự án riêng rồi thêm tài khoản khác từ trang Thành viên.

Để dừng các container khi đang chạy foreground, bấm Ctrl+C. Để xem lỗi khởi động:

```powershell
docker compose logs --tail 80 web worker
```

Không chia sẻ file `.env` hoặc ảnh chụp có khóa API/mật khẩu.

## Bản online và bản chạy máy

- Bản online là demo giao diện: bấm **Mở không gian demo**. Đăng nhập/đăng ký được tắt và không nhận mật khẩu.
- Bản source chạy Django có đăng nhập, tạo tài khoản, phiên có/không ghi nhớ và lưu PostgreSQL **15**. Không có bước xác minh email, quên mật khẩu hay gửi email trong MVP này.
- Chỉ trang đăng nhập/đăng ký hỗ trợ chuyển Việt/Anh; các màn hình làm việc hiện dùng tiếng Việt.
- Model baseline đã được huấn luyện. Muốn train mới, gọi Gemini hoặc thu bình luận YouTube cần web + worker và cấu hình tương ứng trong `.env`.

Tham khảo: [Docker Desktop Windows](https://docs.docker.com/desktop/setup/install/windows-install/).
