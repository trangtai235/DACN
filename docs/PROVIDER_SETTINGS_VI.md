# Cài đặt → Mô hình & API

Trang dùng frontend ES modules, CSS và modal hiện có; backend Django, session
đăng nhập và PostgreSQL. Quản trị dự án được xem và thay đổi cấu hình. Người dùng
thường không được đọc các API cấu hình, xuất JSON, kiểm tra hoặc xóa nhà cung cấp.

## Nhà cung cấp và mô hình

- DeepSeek là cấu hình tích hợp sẵn, mặc định tắt khi chưa có key. Có thể chỉnh
  tên, key, danh sách model, mặc định và bật/tắt; không thể xóa hoặc đổi endpoint.
- Nhà cung cấp mới dùng OpenAI-compatible. Các kết nối Gemini/Ollama đã lưu từ
  bản cũ được giữ; không tạo kết nối nội bộ mới từ trang này.
- Model ID nhập mỗi dòng một ID. Model mặc định phải thuộc danh sách đó.
- Để trống API key khi sửa sẽ giữ key cũ. Khi bật nhà cung cấp từ xa phải có key.
- Chọn nhà cung cấp mặc định bằng dropdown. ML Local vẫn được chọn riêng ở phần
  ML Local phía dưới; luồng tự gán nhãn tiếp tục hoạt động như trước.

Sidebar Chung và Cấu hình agent dẫn đến cấu hình/quy tắc dự án hiện có;
Plugin tích hợp dẫn đến trang tài khoản có thiết lập YouTube. Không thêm hệ thống
plugin hoặc agent giả.

## Kiểm tra thật, không sinh nội dung

Nút Kiểm tra kết nối gửi request qua Django. Backend gọi HTTPS `GET /models`,
kiểm tra key, định dạng trả về và quyền thấy model mặc định. Không tự gọi
`/chat/completions` khi kiểm tra. API không hỗ trợ metadata thì giữ trạng thái
chưa xác minh và thông báo rõ, không suy diễn thành thành công.

Trạng thái phân biệt key sai/thiếu quyền, URL không hợp lệ, DNS, TLS/mạng,
timeout, hết hạn mức/giới hạn yêu cầu và model không có trong danh sách trả về.
Nhà cung cấp tắt hoặc chưa kiểm tra có chấm xám; chỉ metadata xác minh thành công
mới có chấm xanh. Kiểm tra thất bại có chấm đỏ.

Kiểm tra form chưa lưu không tự lưu key. Một bằng chứng có chữ ký server,
hết hạn sau 10 phút và gắn với người dùng/dự án/cấu hình, cho phép lưu đúng kết
quả đã kiểm tra cùng form. Chỉnh key, URL hoặc model sẽ hủy trạng thái kiểm tra.
Kiểm tra cấu hình đã lưu không đổi `updated_at`, để không làm gián đoạn các lượt
tự gán nhãn đang đối chiếu cấu hình.

## Bảo mật và lưu trữ

Key được mã hóa Fernet trong database theo cơ chế hiện có, không đưa vào response,
localStorage, bundle hoặc JSON xuất. Backend không trả nguyên lỗi/body từ nhà
cung cấp để tránh lộ key. Luôn dùng session và CSRF hiện có.

API từ xa chỉ dùng HTTPS cổng 443, không có tài khoản/query/fragment trong URL.
Địa chỉ loopback, private/link-local, metadata, DNS trỏ nội bộ và chuyển hướng bị
chặn. Backend kiểm tra toàn bộ IP mà DNS trả về và kết nối vào IP đã kiểm tra;
Host và TLS SNI giữ hostname gốc để xác minh chứng chỉ. Tắt proxy môi trường cho
các request API để không đi vòng qua cơ chế chống SSRF. Ollama nội bộ đã được
quản trị cấu hình ở bản cũ được giữ riêng; không cho đổi endpoint nội bộ đó.

Xem tệp cấu hình mở JSON trong modal hoặc tải xuống, không mở file trực tiếp trên
máy. Bản xuất dùng danh sách trường cho phép; không có khóa mã hóa hoặc API key.

## Xóa dự án

Nút Xóa ở danh sách dự án và cuối Cài đặt chung. Chỉ chủ dự án có quyền; phải nhập
đúng tên, không được có tác vụ đang chạy. Thao tác xóa dữ liệu dự án trong database
theo giao dịch, gồm nguồn, bình luận, nhãn, kết quả tự động, phiên bản và kết nối
API. Những dự án khác và trọng số ML dùng chung không bị xóa.

## Sửa lỗi LLM trả offset sai

Luồng so sánh tự động chỉ yêu cầu nhãn câu từ LLM, không yêu cầu span/offset.
Model vẫn phải trả JSON có nhãn hợp lệ trong bộ nhãn đã chốt. Các tính năng cần
span riêng vẫn kiểm tra offsets chặt chẽ. Các lượt LLM bị dừng vì offset có thể
tiếp tục từ mẫu chưa lưu; không gọi lại các mẫu đã lưu thành công.
