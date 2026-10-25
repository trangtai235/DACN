# Gán nhãn tự động trên nhánh huong-moi

## Sử dụng

1. Nhập bình luận ở **Dữ liệu** từ YouTube, CSV hoặc văn bản.
2. Chọn ML Local ở **Model & API**. Bộ nhãn dự án phải khớp đúng bộ nhãn model;
   PhoBERT/XLM-R hiện dùng `NON_TOXIC` và `TOXIC`.
3. Nếu cần LLM, lưu API key vào kết nối đang bật. Hệ thống ưu tiên kết nối đang
   chọn; nếu kết nối đó chưa có key thì dùng kết nối có key đầu tiên trong dự án.
   Không có key thì chỉ ML Local chạy.
4. Mở **Gán nhãn tự động → Bắt đầu gán nhãn**, chọn model và phạm vi nguồn.
   Nếu có kết nối API, thao tác này gửi bình luận đến API thật và dùng hạn mức tài khoản.
5. Theo dõi hai luồng, biểu đồ, thời gian và kết quả ngay trên trang này.
   Bật **Chỉ xem nhãn khác nhau** để xem những bình luận có đủ hai kết quả và khác nhãn câu.
6. Tải CSV tại trang kết quả hoặc **Xuất dữ liệu**. File có nhãn của từng luồng và thời gian từng mẫu.

## Cách lưu và so sánh

Mỗi lượt chốt danh sách ID, văn bản, nguồn và bộ nhãn lúc bắt đầu. Bình luận thêm
sau đó thuộc lượt mới. Hai tác vụ ML/LLM chạy qua hai worker riêng; trên Windows,
`JOB_RUNNER=threads` có hai luồng. Lỗi của một nhánh không hủy nhánh còn lại.

Biểu đồ tròn dùng số kết quả đã hoàn thành của từng nhánh làm mẫu số; danh mục
nhãn luôn giống nhau, kể cả nhãn có số lượng bằng 0. Mức bất đồng chỉ tính trên
các bình luận đã có đủ kết quả ML và LLM. Khác nhãn không tự xác định bên nào đúng.

Thời gian tính bằng đồng hồ đơn điệu trong từng worker, gồm chuẩn bị model/API,
suy luận, xử lý và lưu kết quả; không gồm chờ hàng đợi hoặc khoảng dừng giữa các
lần tiếp tục. Trung bình tính trên số bình luận đã gán. Chỉ hiển thị tỷ lệ tổng thời
gian giữa hai nhánh khi cả hai hoàn tất cùng tập dữ liệu. Thời gian từng bình luận
được lưu riêng trong CSV.

Có thể dừng và tiếp tục từng nhánh. Các kết quả đã lưu được giữ lại và không gọi
API lần nữa cho những mẫu đó. Yêu cầu API đang thực thi phải kết thúc trước khi
dừng; nếu tiến trình chết sau khi API đã xử lý nhưng trước khi lưu, lần chạy tiếp
có thể gọi lại mẫu đó. Thay endpoint/model/key của kết nối hoặc trọng số ML cần
tạo lượt mới để không trộn cấu hình.

## Phạm vi nhánh này

Giao diện gán thủ công và các mục nghiên cứu/kiểm tra nhãn thủ công đã được gỡ
khỏi điều hướng. Dữ liệu và API cũ được giữ cho lịch sử. Kết quả tự động có bảng
riêng, không ghi đè nhãn người hoặc mặc định trở thành gold. Nút chạy gán nhãn
theo nguồn/dự án đưa về cùng trang tự động. Công cụ thử dự đoán một câu vẫn nằm
ở Model & API.

Khi cập nhật source, chạy lại `RUN_NATIVE_WINDOWS.bat` để migrate bảng mới và
build giao diện. Trọng số Transformer vẫn tải riêng theo `MODELS_VI.md`.
