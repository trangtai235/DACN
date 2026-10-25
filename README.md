# AnnotaFlow Studio 3

Website đồ án chuyên ngành cho nhóm 3 người, viết mới bằng **Django 5.2 + PostgreSQL 15**, tham khảo [AnnotaHub](https://github.com/vdhong/AnnotaHub). Giao diện navy, tiếng Việt/Anh, responsive. Không dùng máy chủ, tài khoản hay thương hiệu của AnnotaHub.

## Chạy trên Windows — không cần Docker

1. Cài **Python 3.12 64-bit** và **PostgreSQL 18 (hoặc 15–17)**. Ghi nhớ mật khẩu tài khoản PostgreSQL `postgres` khi cài.
2. Giải nén source vào đường dẫn ngắn, ví dụ `C:\AnnotaFlow`.
3. Nhấp đúp `RUN_NATIVE_WINDOWS.bat`. Lần đầu script hỏi kết nối PostgreSQL, tạo role ứng dụng riêng, database, migrations và dữ liệu demo.
4. Mở http://127.0.0.1:8000. Dùng `tv1`, `tv2`, `tv3` với mật khẩu demo script in trên máy bạn. Lần sau xem `DEMO_PASSWORD` trong `.env.local` nếu cần.

Web native dùng duy nhất cổng 8000 cho cả giao diện và API. Nhấn Ctrl+C hoặc đóng terminal chạy `RUN_NATIVE_WINDOWS.bat` để dừng server và giải phóng cổng. Đóng tab trình duyệt không dừng server. PostgreSQL chạy riêng để lưu dữ liệu.

Xem [QUICKSTART_VI.md](QUICKSTART_VI.md). Cách này không cần Docker, WSL, Redis hoặc GPU. Tác vụ dùng 2 luồng trong tiến trình web, phù hợp local/nhóm nhỏ; không phải hàng đợi production bền vững. Có recovery sau khi tiến trình dừng.

## Các chức năng đã triển khai

- Tài khoản: đăng ký/đăng nhập/đăng xuất, nhớ phiên, đổi mật khẩu, xác minh email, reset mật khẩu. Mặc định email local ghi vào file; SMTP cần cấu hình để gửi thật.
- Dự án: tạo/chuyển dự án; bộ nhãn tùy chỉnh; hướng dẫn; khóa/mở lại; lưu trữ; redundancy; chế độ độc lập; quyền manager/annotator; mời theo email bằng liên kết có hạn.
- Dữ liệu: văn bản, CSV UTF-8 có mapping, YouTube bình luận gốc + replies phân trang, ngữ cảnh cha, lọc/tìm/phân trang, quản lý nguồn, tiến độ, dừng/tiếp tục tác vụ.
- Gán nhãn: nhãn câu và spans riêng, Unicode offsets, chọn từ/Shift dải, phím tắt, skip, sửa nhãn có revision, undo, ghi chú, lịch sử, theo dõi tiếp xúc AI.
- Chất lượng: Krippendorff alpha nominal, Cohen kappa theo cặp, đóng góp, bất đồng câu hoặc spans, phân xử gold. Đồng thuận không tự chứng minh độ đúng.
- Phiên bản dữ liệu: snapshot/checksum, tải JSON, khôi phục lớp nhãn trên cùng ID/văn bản với backup tự động, giữ dữ liệu khác và lớp lượt đầu nghiên cứu.
- **16 định dạng xuất**: CoNLL/BIO, full CoNLL, HF JSONL, spaCy JSON, Doccano, Label Studio, sentence/token JSON, JSONL, XML, sentence/token/span/annotation CSV, XLSX, chat JSONL. Phạm vi all/labelled/human/gold.
- **Model tự train**: chọn Logistic Regression, Linear SVM hoặc Complement Naive Bayes, upload train/validation/test, loại giao nhau, chọn siêu tham số trên validation, đăng ký artifact và báo cáo.
- **API thay được trên UI**: Gemini, Ollama, OpenAI-compatible; model ID, endpoint, khóa mã hóa, giá token và kiểm tra kết nối. Chọn model/API theo dự án.
- Đánh giá: accuracy, precision/recall/macro-F1, từng lớp, confusion matrix, baseline đa số, API ghép cặp cùng mẫu test, token/latency/chi phí ước tính và lịch sử từng lượt.
- Thực nghiệm nhị phân: lượt đầu có AI được đóng băng, nhóm A/B/C/D, random/fixed/fixed+exploration/adaptive, lượt hai mù, người thứ ba phân xử, ngân sách và tham chiếu độc lập.

## Kết quả đã đo thật

Cả 3 model dùng ViCTSD, cùng nguồn/split, seed 42, train sạch 6.943, validation 1.988, test 1.000. Mô hình TF-IDF ký tự 3–5 grams. Chỉ chọn siêu tham số trên validation, không fit test.

| Model | Accuracy | Macro-F1 |
|---|---:|---:|
| Logistic Regression | 0,880 | 0,69110 |
| Linear SVM | 0,879 | 0,69224 |
| Complement Naive Bayes | 0,867 | 0,69495 |

Artifacts và metrics nằm ở `backend/artifacts/`. Ba model online dùng trọng số thật dạng portable, kiểm tra khớp sklearn trên 3 × 1.000 dự đoán. Đây là kết quả ViCTSD, chưa chứng minh khả năng tổng quát hóa sang YouTube.

Chưa gọi API thật, chưa có điểm API, không có nhãn chuyên gia hay kết quả thí nghiệm người thật được tạo sẵn.

## Sửa API, chọn model và chỉnh giao diện

- Thay nhà cung cấp/model API: trang **Model & API → Thêm kết nối**, nhập protocol, endpoint, model ID, API key. Chọn kết nối rồi bấm kiểm tra khi muốn gửi request thật.
- Host mới cần thêm vào `AI_ALLOWED_HOSTS` trong `.env.local`/`.env` rồi khởi động lại. Không mở allowlist tùy tiện.
- Chọn model đã train bằng nút **Chọn model**; train phiên mới bằng **Huấn luyện mới**. Không cần sửa source để đổi trong 3 thuật toán đã có.
- Giao diện nguồn ở `frontend/src/features/<tính-năng>/`, shared ở `frontend/src/core/`. Chạy `python scripts/build_frontend.py` sau khi sửa. `dist/` là output, không chỉnh trực tiếp.
- Thêm adapter mới: [docs/EXTENDING.md](docs/EXTENDING.md). Cấu trúc: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Docker tùy chọn

```bash
python scripts/setup_env.py
docker compose up --build
```

Windows có `START_WINDOWS.bat`. Docker dùng PostgreSQL 15 + Redis + Celery, cổng web chỉ localhost. Không chạy cả native và Docker cùng cổng 8000.

## Kiểm thử và giới hạn bàn giao

Xem [docs/VERIFICATION.md](docs/VERIFICATION.md) và [docs/FEATURE_MATRIX.md](docs/FEATURE_MATRIX.md). Backend local cần PostgreSQL thật; bản online tĩnh chỉ là demo trình duyệt, không có backend PostgreSQL được host kèm.

Môi trường bàn giao chưa chạy PostgreSQL 15/Windows thật hoặc thử tải production; không mô tả bản này là production đã kiểm chứng. Các luồng API/YouTube/email được kiểm tra bằng mocks/local mail, cần khóa/cấu hình của nhóm để chạy thật.

Dữ liệu minh họa 36 câu là văn bản tự tạo. Mã nguồn tham khảo và dataset được ghi tại [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
