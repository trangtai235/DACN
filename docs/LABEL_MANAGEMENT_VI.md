# Trang Quản lý nhãn

Mở **Quản lý nhãn** trên menu dự án (`#label-management`). Module riêng:
`frontend/src/features/label-management/index.js`. Đây là trang dùng API Django và dữ liệu
ProjectLabel; không có bộ nhãn CRUD riêng trong localStorage.

## Thao tác

- Tên dự án luôn ở đầu trang. Tìm theo tên/mã, lọc đang dùng/ngừng dùng/tất cả.
- **Thêm nhãn**: tên, mã A–Z/0–9/_, màu, mô tả, quy tắc loại trừ, thứ tự và trạng thái.
  Form có xem trước. **Hủy** không gửi yêu cầu lưu.
- **Sửa**: thay tên/mô tả/màu/thứ tự; mã được giữ ổn định. Thứ tự quyết định vị trí nút và phím tắt 1–9.
- **Ngừng dùng / Kích hoạt lại**: giữ ID, mã, nhãn câu/spans và lịch sử đã lưu.
- **Xóa** chỉ hiện khi API báo chưa sử dụng. Backend vẫn kiểm tra lại khi nhận yêu cầu,
  bao gồm nhãn câu, spans, Prediction, lượt chạy, sự kiện undo, snapshot dữ liệu và lượt nghiên cứu.
- **Quay lại gán nhãn**: mở lại workspace đã đến từ đó, đúng dự án/người dùng.

Ở màn hình nhỏ, danh sách chuyển thành thẻ. Trang chỉ đọc khi người dùng không có quyền quản lý
hoặc dự án khóa/lưu trữ. Không tạo lại bộ nhãn mặc định khi đã chủ động xóa hết các nhãn chưa dùng.
Thiết lập mặc định lúc khởi tạo dự án cũ được giữ để tương thích với cách chạy hiện có.

## API chung với HITL

`GET /api/studio/labels?project=ID` trả labels đang dùng/ngừng dùng, revision, quyền, trạng thái
dự án, khả năng xóa, phiên bản schema và tương thích model local đang chọn.

`POST /api/studio/labels` dùng cùng ProjectLabel và kiểm tra membership/manager/project:

```json
{"project":1,"action":"create","key":"SPAM","name":"Quảng cáo","color":"#e7a645","description":"Nội dung quảng cáo","order":2,"enabled":true}
```

Sửa/tắt/kích hoạt/xóa từ trang mới gửi thêm `id` và `revision` đã đọc. Phiên khác đã sửa thì
trả **409**, giữ nội dung form hiện tại để người dùng xem lại; không tự ghi đè bản mới.
`action=delete` chỉ xóa nhãn chưa dùng. Các payload cũ theo key được giữ để tương thích API sẵn có;
giao diện hiện hành dùng ID/revision. Audit ghi trước/sau mỗi thay đổi.

Manual HITL và workspace cặp dự đoán tải lựa chọn từ chính GET này: nhãn mới/tên/màu/thứ tự
được cập nhật, disabled không còn là lựa chọn mới. Snapshot LabelSchema/Prediction vẫn bất biến.
Nếu schema đã đổi, dự đoán cũ hiển thị phiên bản cũ và không được coi là đồng thuận theo schema mới;
quyết định con người lưu schema hiện hành, cùng snapshot nghĩa nhãn trong lịch sử quyết định.
Thêm nhãn không đổi checkpoint, không ánh xạ lại đầu ra và không tự huấn luyện model.

## Giữ bản nháp khi quản lý nhãn

Workspace lưu tạm bản nháp vào **sessionStorage theo user + project**; đây chỉ là bản nháp,
không phải annotation đã nộp hoặc danh sách nhãn chính thức.

- Manual: bình luận, nhãn đang chọn, spans, ghi chú, các từ đang chọn, nguồn và revision.
- HITL cặp: cặp/run, bộ lọc, nhãn/note/hành động đang soạn và hai revision dùng khi lưu.
- Đi qua Quản lý nhãn hoặc reload cùng phiên vẫn khôi phục đúng nội dung.
- Nhãn vừa bị tắt: bản nháp còn nguyên, có cảnh báo và yêu cầu chọn nhãn đang dùng trước khi lưu.
- Không tự nâng revision của bản nháp để đè annotation đã được sửa ở phiên khác.
- Sau khi server xác nhận lưu, bản nháp cũ được xóa; thao tác chọn nhãn không tự nộp.

Mở trang từ menu hoặc nút **Quản lý nhãn** trong workspace. Những popup quản lý nhãn cũ
trong workspace/Cài đặt dự án dẫn đến trang này. Không mất bản nháp khi chuyển trang quản lý.

## Chạy cập nhật

Migration mới thêm `ProjectLabel.revision`; không đổi mã hoặc xóa dữ liệu nhãn hiện có.

```powershell
$env:ANNOTAFLOW_ENV_FILE = (Join-Path (Get-Location) '.env.local')
.venv\Scripts\python.exe backend\manage.py migrate
.venv\Scripts\python.exe scripts\build_frontend.py
.\RUN_NATIVE_WINDOWS.bat
```

Tại bản backend, thử: mở bình luận → chọn nhãn/spans/note chưa lưu → Quản lý nhãn → thêm/sửa/
tắt nhãn → reload trang quản lý → Quay lại gán nhãn. Kiểm tra dữ liệu đã lưu qua API và bản nháp
chưa bị nộp. Xem [VERIFICATION.md](VERIFICATION.md) cho kết quả kiểm thử thực chạy.
