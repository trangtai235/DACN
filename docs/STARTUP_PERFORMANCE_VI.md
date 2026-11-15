# Khởi động và chuyển trang

Giao diện native dùng `GET /api/bootstrap?compact=1`: chỉ tải thông tin người dùng,
dự án, thống kê, nguồn, bộ nhãn và tên model. Danh sách bình luận, báo cáo model đầy đủ,
snapshot phiên bản và dữ liệu thực nghiệm không nằm trong gói khởi động. Các màn dữ liệu,
HITL và đánh giá gọi API riêng khi mở. API bootstrap đầy đủ cũ vẫn hoạt động để giữ tương thích.

Mở **Đánh giá** mới tải `GET /api/model-reports?project=<id>`. Endpoint kiểm tra thành viên,
dự án và trạng thái review mù; không trả báo cáo model trong lượt mù. Gói compact không
ghi AIExposure vì chưa hiển thị gợi ý hoặc nội dung bình luận.

Module JavaScript của từng tính năng được import khi cần. Native không tải module demo
hay bộ xuất browser lúc mở trang. Sau khi nhận thông tin dự án, menu hiện trước nội dung
đang tải; chuyển nhanh nhiều trang chỉ giữ trang được chọn cuối. Lỗi mạng có nút thử lại,
session/bootstrap hết thời gian chờ sau 15 giây. Metadata được tái sử dụng tối đa 15 giây
khi chuyển trang; thao tác ghi và làm mới chủ động vẫn tải lại. Backend luôn kiểm tra quyền.

Font Be Vietnam Pro được phục vụ tại `/assets/fonts/`, `font-display: swap`; bỏ CSS import
Google Fonts lúc runtime. Các tệp WOFF2 không sửa đổi, giấy phép OFL và SHA-256/source URL
được giữ trong `frontend/public/fonts/`. Nguồn font: [Google Fonts](https://github.com/google/fonts/tree/main/ofl/bevietnampro),
[giấy phép đi kèm](https://github.com/google/fonts/blob/main/ofl/bevietnampro/OFL.txt).
Khởi động không cần kết nối mạng Google/CDN; gọi AI/YouTube vẫn cần kết nối tương ứng.

Sau khi cập nhật, khởi động lại `RUN_NATIVE_WINDOWS.bat` để Python nạp API mới. Build
đã đổi version CSS/module để tránh dùng cache cũ. Không xóa dữ liệu trình duyệt hoặc database.

Số đo và phạm vi kiểm tra nằm trong [VERIFICATION.md](VERIFICATION.md). Không suy ra thời
gian mở BAT, tốc độ suy luận model hoặc hiệu năng production từ fixture browser.
