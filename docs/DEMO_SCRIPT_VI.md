# Demo M1–M3 trên Windows/native

Menu hiện tại: **Người duyệt nhãn (HITL)** (`#human-review`) thay tên Phối hợp hai mô hình;
link `#collaboration` cũ vẫn dùng được. **Gán nhãn thủ công** (`#manual-annotation`) nằm ngay
trên menu chính. Bắt đầu gán tự động mặc định mở hàng đợi HITL khi bật checkbox tương ứng.
Xem [hướng dẫn thao tác HITL](HUMAN_IN_THE_LOOP_VI.md), gồm giám sát/duyệt phản hồi và xuất nhãn người.

## Chuẩn bị

Giữ cách chạy cũ: `RUN_NATIVE_WINDOWS.bat` (PostgreSQL, không cần Redis),
hoặc Docker `START_WINDOWS.bat`. Không chạy cả hai cùng cổng.
Từ root, sau cập nhật source và trước khởi động lại web:

```powershell
.venv\Scripts\python.exe scripts\build_frontend.py
$env:ANNOTAFLOW_ENV_FILE = (Join-Path (Get-Location) '.env.local')
.venv\Scripts\python.exe backend\manage.py migrate
.venv\Scripts\python.exe backend\manage.py seed_collaboration_demo --owner tv1 --reviewer tv2 --judge tv3
```

Ba tài khoản phải tồn tại (native setup/`seed_demo` đã tạo); command không đổi mật khẩu.
Command tạo dự án MINH HỌA mới, không sửa dự án nghiên cứu đang dùng. Lưu model nhỏ trong private_data.
Không cần API key hoặc Transformer cho demo này. API mock chỉ được patch trong command;
sau command kết nối fixture bị tắt. Trọng số sklearn được train thật nhưng trên dữ liệu tổng hợp.
Output in ID project/run/model/dataset. Bốn dự đoán M1 được cố định để demo, gắn `mock_predictions=true`.

Nếu chạy Docker, thay `.venv\Scripts\python.exe backend\manage.py` bằng
`docker compose exec web python manage.py`. Build frontend trước `docker compose up --build`.
Không dùng `settings_test` với database thực nghiệm.

## M1: dự đoán và quyết định

1. Đăng nhập tv1, chuyển sang dự án MINH HỌA, mở **Phối hợp hai mô hình**.
2. Chọn lượt mới có bốn mẫu. Đồng thuận: mở gợi ý rồi xác nhận; trước click không có gold.
3. Bất đồng: mở bình luận, xem thông báo không đồng thuận cùng hai nhãn Local/API đang hiện.
   Kiểm tra hai Prediction ID và exposure; chọn nhãn cuối để lưu. Đây là gán có hỗ trợ máy.
   Bấm **Dịch sang tiếng Việt** để xem bản dịch cạnh bản gốc; reload giữ kết quả và ghi chú.
   Dịch cần kết nối API mặc định; khi kiểm thử tự động dùng mock, không gọi dịch vụ thật.
4. Mẫu “hai model cùng sai”: cả hai dự đoán NON_TOXIC nhưng người đổi sang TOXIC.
   Đây là tình huống scripted, không phải tỷ lệ sai đo trên dữ liệu thật.
5. Mẫu API lỗi: local còn nguyên, API báo lỗi, không hiển thị như bất đồng/đồng thuận.
6. Chọn Cần thêm ngữ cảnh/Không thể quyết định/Chuyển phân xử. Đổi tv3 để phân xử có lý do;
   tv1 đã gán không được tự phân xử. Không thay key nhãn hoặc offsets của spans.
7. Mở hai phiên cùng sửa một quyết định: phiên cũ bị revision guard từ chối.

## M2: schema và thích ứng

1. Cài đặt dự án: preset **Độc hại / Quảng cáo / Bình thường**, có định nghĩa và loại trừ.
   Vừa quảng cáo vừa công kích ưu tiên TOXIC. Lịch sử schema nằm ở trang phối hợp.
2. Trong dự án độc hại cũ, thêm SPAM: model PhoBERT/XLM-R nhị phân báo không tương thích;
   chọn Human/API-only. Không đổi nhãn độc hại thành spam.
3. Với dữ liệu người dùng thật: xác nhận nhãn → quản lý bấm **Duyệt dùng cho hỗ trợ/train**.
   Mẫu test/reference/pilot, cùng video giữ riêng, trùng và chưa duyệt không vào retrieval.
4. Trong demo, đã có sáu nguồn tổng hợp và feedback scripted để minh họa readiness/dataset.
   Bấm Train ứng viên trên dataset đã chụp; xem job ở Dữ liệu, tải lại trang phối hợp.
5. Xem validation (và incumbent trên cùng validation khi có), quản lý ghi lý do kích hoạt.
   Kích hoạt lại phiên cũ để rollback. Không tự diễn giải model mới tốt hơn.
6. API thật: **Mô hình & API** tạo provider/endpoint/model ID/key, cấu hình AI_ALLOWED_HOSTS;
   tạo hai lượt trên cùng mẫu/schema, bật/tắt retrieval. Việc chọn API có thể phát sinh phí.
   Không retry fixture sau khi sửa cấu hình để giả thành cùng điều kiện: tạo lượt mới.

## M3: ngân sách và báo cáo

1. Hoàn tất quyết định lượt đầu cho các cặp hợp lệ ở M1.
2. **Kiểm tra theo ngân sách** → Tạo phiên → chọn run, P0/P1/P2/P3, seed và budget.
   Quần thể chỉ gồm cặp đủ hai nhánh hợp lệ và nhãn người đã xác nhận.
3. tv2 nhận mẫu mù; API trả text/schema, không trả AI/first/reference/group.
   Pause → chờ → Resume; thử ẩn tab. Nhãn khác lượt đầu chuyển tv3 phân xử.
4. Hết budget không cấp việc mới; việc đang làm được hoàn tất, ghi overrun.
5. Tải JSON báo cáo. Không có tham chiếu thì không có F1/net fixes đo được.
6. Replay nhiều seed chỉ chạy khi đã quan sát đủ toàn bộ quần thể. Nếu chưa đủ, API báo rõ;
   không tự bịa nhãn cho các mẫu còn thiếu để lấp báo cáo.
7. Xuất so sánh theo ID ở trang phối hợp: nhập các run cùng schema; response chứa coverage,
   lỗi và metrics rỗng nếu chưa có tham chiếu. Xem protocol để chuẩn bị dữ liệu thật trước khi chạy AI.

## Kiểm chứng tự động không có keys

```powershell
.venv\Scripts\python.exe backend\manage.py test tests --settings=config.settings_test --noinput
.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run --settings=config.settings_test
.venv\Scripts\python.exe scripts\build_frontend.py
npm run check
npm run test:exports
```

Profile SQLite chỉ dùng kiểm thử; chưa thay thử transaction/concurrency trên PostgreSQL thật.
Để chạy thêm Chromium smoke test, xem biến môi trường và lệnh tại [VERIFICATION.md](VERIFICATION.md).
Không đặt đường dẫn Playwright thì test browser báo skip rõ ràng.
