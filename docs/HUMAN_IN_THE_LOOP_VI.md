# Human-in-the-loop: người duyệt nhãn

Menu **Quản lý nhãn** (`#label-management`) là trang riêng theo dự án. Nút cùng tên trong
workspace mở trang đó và giữ bình luận/nhãn/spans/note đang soạn khi quay lại hoặc reload.
Chi tiết CRUD, phân quyền và migration: [LABEL_MANAGEMENT_VI.md](LABEL_MANAGEMENT_VI.md).

Hai màn hình nằm trên menu chính:

- **Người duyệt nhãn (HITL)** — `#human-review`: hàng đợi dựa trên cặp gợi ý, quyết định,
  chuyển phân xử và quản lý duyệt phản hồi. Link `#collaboration` cũ vẫn mở được cùng luồng.
- **Gán nhãn thủ công** — `#manual-annotation`: chọn nhãn câu/spans, ghi chú, sửa/hoàn tác
  và lưu annotation khi chưa cần model hoặc API. Bấm một bình luận trong trang Dữ liệu cũng mở màn hình này.

## Gán riêng từng video / nguồn

Ở **Dữ liệu → Video & nguồn dữ liệu**, bấm **Gán nhãn** trên thẻ video để mở HITL của
đúng video đó. Thanh **Video / nguồn đang gán** hiển thị nguồn hiện tại. Hàng đợi, tiến độ,
Trước/Tiếp và lưu rồi chuyển mẫu chỉ dùng bình luận của nguồn đang chọn.

Lượt cũ chứa nhiều video được lọc tại API khi duyệt. Lượt tạo mới đóng băng riêng các
bình luận của nguồn chọn. Lượt tự động cũ trộn nhiều nguồn không được chạy lại/xuất trong
phạm vi một nguồn; tạo lượt riêng cho video thay thế. Backend kiểm tra nguồn thuộc dự án
và từ chối lưu cặp/bình luận khác nguồn được gửi trong request.

Chuyển sang **Gán thủ công**, **Gán tự động**, **Quản lý nhãn** hoặc reload vẫn giữ nguồn.
Mỗi nguồn có bản nháp và vị trí duyệt riêng; bản nháp video B không thay thế video A.
Gán hết một video hiển thị hết mẫu; không tự chuyển sang video khác. Video chưa có cặp
gợi ý có thể gán thủ công hoặc tạo lượt riêng. Trong lúc đổi nguồn, thao tác gán bị chặn
đến khi dữ liệu mới tải xong. Chỉ chọn **Toàn dự án** trên thanh nguồn khi muốn làm toàn bộ.

## Bắt đầu từ máy gợi ý

Ở **Gán nhãn tự động → Bắt đầu gán nhãn**, tùy chọn **Human-in-the-loop** được bật sẵn.
Khi bắt đầu, hệ thống tạo run có snapshot và chuyển thẳng sang hàng đợi người duyệt của run đó.
Không chuyển kết quả máy thành nhãn người. Hai job chạy độc lập; tải tiến độ để thấy kết quả mới.
Chưa có API thì vẫn duyệt được với local/human-only, không hiển thị đồng thuận hai model giả.

Tắt tùy chọn để dùng luồng tự gán cũ. Các run cũ thiếu metadata đầy đủ không được tự biến thành
cặp có provenance mới; chúng vẫn đọc/xuất được riêng. Muốn dùng luồng HITL mới, tạo một lượt hỗ trợ mới.
Tạo lượt có API thật vẫn có thể phát sinh phí theo cấu hình provider.

## Người gán kiểm tra và quyết định

Trang HITL mở trực tiếp một bình luận với cùng thẻ nguồn/tác giả, nút nhãn màu,
gán cụm từ và ghi chú như màn hình thủ công. **Hàng đợi người duyệt** và
**Cấu hình, phản hồi và báo cáo** nằm trong các phần thu gọn phía dưới.

Màn hình chính rút gọn theo bộ giao diện AnnotaFlow: thanh tiến độ cá nhân,
thẻ bình luận và nguồn, một dòng gợi ý, nút nhãn, **Bỏ qua** và **Trước / Tiếp**.
Mở **Lượt hỗ trợ #…** trên thanh tiến độ để đổi lượt, tải tiến độ hoặc tạo lượt mới.
Số đã xác nhận lấy từ quyết định thật của người dùng trong lượt, không phải số liệu thực nghiệm.
Mở **Công cụ bổ sung** để nhập ghi chú, gán cụm từ, yêu cầu ngữ cảnh/phân xử hoặc xem lịch sử.
Các nút lưu nâng cao nằm trong phần này; thao tác bấm nhãn chính vẫn tự lưu và chuyển tiếp.
**Bỏ qua** lưu trạng thái skipped, không biến thành một lớp nội dung hay tạo gold.

1. Đọc bình luận đang mở; chọn mẫu khác trong hàng đợi hoặc dùng **Trước / Tiếp**.
2. Với đồng thuận hợp lệ: vùng **Gợi ý từ mô hình** tự hiện nhãn mà Local và LLM cùng chọn,
   kèm hai nguồn dự đoán. Việc hiển thị được ghi exposure với chính xác Prediction ID;
   không chạy suy luận lại, không tự chọn nhãn và không tạo annotation/gold.
3. **Bấm nhãn**, **Dùng gợi ý** hoặc **Chọn nhãn Local/LLM** sẽ lưu ngay và chuyển sang mẫu
   tiếp theo sau khi server xác nhận. Thêm cụm từ hoặc ghi chú trước khi bấm nhãn để lưu kèm.
   Với bất đồng, lần bấm đầu chỉ lưu lựa chọn độc lập và giữ nguyên mẫu để mở hai gợi ý;
   sau đó bấm nhãn để xác nhận nhãn cuối và tiếp tục. Bản nháp cụm từ vẫn được giữ qua bước này.
4. Không đủ thông tin thì chọn **Cần thêm ngữ cảnh**, **Không thể quyết định**, **Bỏ qua**
   hoặc **Chuyển phân xử**. Các trạng thái này không bị biến thành một lớp nội dung.
5. **Lưu quyết định** giữ nguyên bình luận; **Lưu & tiếp tục** chỉ chuyển sau khi lưu thành công.
   Bước lưu độc lập vẫn giữ mẫu để xem và xác nhận gợi ý. Nhãn người/spans nằm trong Annotation,
   có revision và lịch sử, không ghi đè hai Prediction. Phím 1–9 chọn và lưu nhãn;
   Enter lưu; Shift + Enter lưu và tiếp tục khi không nhập văn bản.

Nếu lưu lỗi (mất mạng, nhãn ngừng dùng hoặc revision xung đột), không chuyển bình luận.
Lựa chọn, ghi chú và cụm từ được giữ để thử lại. Trong lúc lưu, các thao tác chọn tiếp bị chặn
để tránh nộp trùng. Chỉ hiển thị gợi ý đồng thuận vẫn không tự tạo nhãn người.

Nếu thấy **Cần cập nhật backend**, khởi động lại server Python rồi tải lại trang.
Launcher native chạy với `--noreload` để giữ các job thread: thay file Python không tự nạp code mới.
Ctrl + F5 chỉ cập nhật frontend; cần dừng/khởi động lại backend sau khi cập nhật code backend,
khi không có job đang chạy. API detail dùng workspace_version để phát hiện bản không tương thích.

Mẫu lỗi, đang xử lý, model không tương thích hoặc schema/văn bản cũ có thông báo riêng;
không hiển thị đồng thuận giả. Nhãn vừa tạo chỉ dùng để người gán chọn; model cần được train/đánh giá
cho bộ nhãn đó. Mỗi mẫu giữ bản nháp riêng trong phiên trình duyệt. Reload hoặc quay lại từ
Quản lý nhãn khôi phục đúng bình luận, lựa chọn, cụm từ và ghi chú; backend tiếp tục kiểm tra revision.

Ở màn hình thủ công, bấm nhãn chỉ chọn; kiểm tra spans/ghi chú rồi **Lưu & tiếp tục**.
Không tự nộp ngay khi bấm một lớp. Luồng này dùng queue, offsets, revision và undo đã có.

## Phân xử và duyệt phản hồi

Quản lý có thể mở **Xem nhãn người & duyệt phản hồi** để xem quyết định của thành viên khác,
không phải tự tạo một annotation của mình để duyệt. Chức năng này bị chặn khi đang làm lượt mù.
Việc đọc nhãn người khác được ghi audit; người đã xem không được nhận lại mẫu đó như một
quan sát kiểm tra độc lập trong nghiên cứu ngân sách.

Mẫu được chuyển phân xử có nút **Phân xử** cho người có quyền và chưa gán mẫu.
Người phân xử chọn nhãn cuối, ghi lý do; không để người lượt đầu tự phân xử mẫu của mình.
Gold, quyết định người và gợi ý máy được phân biệt. Khi quyết định đã xác nhận hợp lệ,
quản lý có thể **Duyệt phản hồi này**. Quyết định thay revision cần được duyệt lại.

Retrieval/train tiếp tục lọc schema, revision annotation, trạng thái tranh chấp, chính mẫu,
trùng mẫu và tập giữ riêng. Dấu duyệt quản lý không làm mọi phản hồi tự động đủ điều kiện train;
readiness hiển thị tập thực sự đủ điều kiện theo quy tắc đó.

## Đầu ra và vòng phản hồi

**Xuất dữ liệu** có CSV/JSONL nhãn con người và CSV gold, tách khỏi CSV gợi ý máy cũ.
Scope human có thể chứa nhãn người chưa đạt gold; không tự gọi chúng là tham chiếu độc lập.
Phản hồi hợp lệ có thể được retrieval hoặc chụp dataset/train theo đợt như M2;
model mới vẫn cần validation và quản lý kích hoạt.

Demo không cần key: chạy `seed_collaboration_demo` rồi mở dự án MINH HỌA ở `#human-review`.
Đây là dữ liệu/script minh họa, không phải kết quả thực nghiệm. Xem [DEMO_SCRIPT_VI.md](DEMO_SCRIPT_VI.md).
