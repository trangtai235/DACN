# Bộ model ViHOS

Ứng dụng dùng **PhoBERT-base, XLM-R base và XLM-R large** từ file
`vihos-models-full.zip` trong [thư mục Drive được cung cấp](https://drive.google.com/drive/folders/181y1V8mv0BAjRqk9xRSVguU8Gx0vHL0h).

Đặt ba thư mục model tại:

```text
backend/artifacts/transformers/vihos-full/
  phobert-base/
  xlmr-base/
  xlmr-large/
```

Mỗi thư mục cần `model.safetensors`, `config.json`, tokenizer và `metrics.json`
từ bộ tải về. Không đưa trọng số dung lượng lớn lên Git.

Sau khi cấu hình ứng dụng trên máy mới:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements/transformers.txt
$env:ANNOTAFLOW_ENV_FILE = Join-Path (Get-Location) '.env.local'
.venv/Scripts/python.exe -X utf8 backend/manage.py import_transformers --verify
```

Lệnh nạp trọng số thật, kiểm tra suy luận và offsets trước khi đăng ký model cho
các dự án. Các model cũ chuyển sang `retired` để giữ lịch sử nhưng không còn trong
danh sách chọn. Khởi động lại server sau khi thay bộ model.

Đây là model BIO (`O`, `B-T`, `I-T`) theo âm tiết. Adapter giữ offsets trong văn bản
gốc, lấy nhãn token con đầu tiên của mỗi âm tiết, chia cửa sổ cho văn bản dài.
Nhãn câu suy ra: có span độc hại → `TOXIC`, không có → `NON_TOXIC`.

Trang Đánh giá hiển thị precision, recall và F1 span theo `partial`, `strict`, `char`
từ `metrics.json` được cung cấp. Đây không phải accuracy phân loại câu và chưa phải
kết quả đo lại trên tập test trong ứng dụng. Chạy thử suy luận chỉ xác nhận model
nạp được và trả kết quả hợp lệ.

Suy luận chạy offline trên backend, chỉ giữ một model trong RAM. Chuyển model có
thể mất thời gian; CPU mặc định dùng 4 luồng (`TRANSFORMER_CPU_THREADS`). Bản demo
tĩnh xem được báo cáo nhưng cần backend để chạy các model Transformer.
