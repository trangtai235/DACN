# Model Transformer cục bộ

Model nằm trong `backend/artifacts/transformers/`. PhoBERT-base và XLM-R large
được đăng ký khi đã kiểm tra nạp trọng số và suy luận thật. XLM-R base và smoke
chưa có trọng số trong bộ Downloads.rar nên không hiển thị là model sẵn sàng.

Trên máy mới:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements/transformers.txt
$env:ANNOTAFLOW_ENV_FILE = Join-Path (Get-Location) '.env.local'
.venv/Scripts/python.exe backend/manage.py import_transformers --verify
```

Khởi động lại server sau khi cập nhật mã. Trong Nâng cao → Model & API,
chọn model, nhập bình luận để thử dự đoán hoặc chạy gợi ý cho nguồn dữ liệu.
Các model cũ được chuyển sang trạng thái `retired`, giữ bản ghi để truy vết
lịch sử; không còn xuất hiện trong danh sách lựa chọn của backend.

Đây là model BIO (`O`, `B-T`, `I-T`) theo âm tiết, không phải bộ phân loại câu.
Adapter dùng token con đầu tiên của mỗi âm tiết, giữ offsets trong văn bản gốc,
chia cửa sổ với bình luận dài để không bỏ phần cuối. Nhãn câu được suy ra:
có span → `TOXIC`, không có → `NON_TOXIC`. Dự án cần bật hai nhãn này.
Quy tắc tổng hợp câu không có báo cáo accuracy riêng. F1 hiển thị là số liệu
span từ metrics.json do người dùng cung cấp, chưa được đo lại trên tập test.

Không tải mã hoặc trọng số từ mạng khi suy luận. Chỉ nạp một model vào RAM
mỗi thời điểm; chuyển model có thể mất thời gian. Mặc định chạy CPU, 4 luồng;
đổi bằng biến môi trường `TRANSFORMER_CPU_THREADS` nếu cần.
