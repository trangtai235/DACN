# Thiết kế đánh giá cho đồ án

## Bộ model hiện tại

Ba model từ `vihos-models-full.zip`: **PhoBERT-base, XLM-R base, XLM-R large**.
Trọng số đặt tại `backend/artifacts/transformers/vihos-full/` và chạy offline trên backend.
Xem [MODELS_VI.md](../MODELS_VI.md) để tải, cài đặt và kiểm tra model.

| Model | Span F1 partial | Span F1 strict | Char F1 |
|---|---:|---:|---:|
| PhoBERT-base | 0,7419 | 0,5006 | 0,6559 |
| XLM-R base | 0,7786 | 0,5400 | 0,6848 |
| XLM-R large | 0,7825 | 0,5505 | 0,7023 |

Đây là số liệu test từ `metrics.json` được cung cấp, chưa được đo lại trong ứng dụng.
Không diễn giải F1 span thành accuracy hoặc Macro-F1 phân loại câu. Nhãn câu được suy ra
từ span độc hại. Chưa có điểm API hoặc kết quả thí nghiệm người dùng cho bộ model này.

Các trọng số TF-IDF cũ đã được bỏ. Demo tĩnh hiển thị báo cáo; suy luận Transformer cần
chạy source Django. Lịch sử model cũ trong database được giữ ở trạng thái `retired`.

## Nhánh API cần chạy sau khi có khóa

Model và API (Gemini/Ollama/OpenAI-compatible) phải dùng cùng text và đúng cùng ID test. Các chỉ số ghép cặp được tính lại trên tập giao nhau; không so model 1.000 mẫu với Gemini 50 mẫu như thể cùng điều kiện.

Ứng dụng gọi Gemini với prompt cố định, temperature 0, JSON schema, lưu model ID, token và ước tính chi phí theo .env. Cần lưu thêm thời điểm, phiên prompt và tài khoản hạn mức khi báo cáo chính thức. Không sửa prompt theo lỗi trên test. Mẫu lỗi API làm job thất bại, không ép thành nhãn âm. Studio v3 hỗ trợ checkpoint/tiếp tục benchmark và pin model, artifact, schema, endpoint, giá. Response đã nhận được checkpoint trước khi dừng. Lỗi mạng tại nhà cung cấp vẫn có thể phát sinh phí mà server chưa nhận được response; không bảo đảm exactly-once cho request mạng.

Hiện **chưa có kết quả API**, chưa có căn cứ kết luận model hay API tốt hơn. Không chép kết quả trong bài báo làm số liệu của nhóm.

## Đánh giá quy trình con người

AnnotaHub là nền tảng tạo dữ liệu có LLM và con người. Đánh giá model/API trên benchmark chỉ là một thí nghiệm của đồ án, không tự thay thế đánh giá chất lượng nhãn cuối hoặc công sức con người.

1. Thu dữ liệu YouTube mới, giữ nguồn và ngữ cảnh; chọn pilot riêng.
2. Hai người tạo tham chiếu không xem AI, người thứ ba phân xử; khóa tham chiếu trước lượt đầu.
3. Dùng một bộ gợi ý đã cache cho từng điều kiện; người lượt đầu xem và giữ/sửa, khóa nhóm A/B/C/D.
4. So P0 ngẫu nhiên, P1 ưu tiên C/D, P2 ưu tiên C/D + thăm dò A/B và P3 thích nghi ở cùng ngân sách.
5. Chấm cả mẫu chưa được chọn, dùng nhãn lượt đầu của chúng. Lỗi giảm ròng = sai sửa đúng − đúng sửa sai.
6. Báo F1 nhãn AI, lượt đầu và nhãn cuối; thời gian lượt đầu/kiểm tra/phân xử, mẫu chưa chốt và phần vượt ngân sách.

Ba người kiêm nhiệm gây hiệu ứng nhớ; ẩn nhãn trên UI không tạo ra hội đồng độc lập. Cần tách phiên, đổi ID/thứ tự và nêu giới hạn; không gọi tham chiếu nhóm là chuẩn chuyên gia.

Nếu đo có/không AI như hướng bài báo, chia điều kiện có đối trọng thứ tự và độ khó. Hiện ứng dụng chưa tự tổ chức thử nghiệm ngẫu nhiên đó; không suy diễn từ click demo.

## Trạng thái chức năng và việc còn làm

- Đã có policy thật, claim tuần tự, quyết định mù, phân xử người thứ ba, budget ledger cơ bản, snapshot quần thể và xuất nhãn theo run.
- P3 có prior khởi tạo p0=0,15, t0=20 giây, alpha=5; cập nhật chọn sau mỗi 5 kết quả hoàn tất và thăm dò mỗi 5 lượt. Đây là giá trị khởi tạo, **chưa được hiệu chỉnh bằng pilot của nhóm**.
- Thời gian lượt đầu do client báo; lượt hai và phân xử là thời gian từ nhận đến nộp. Chưa tách hoàn toàn thời gian nghỉ/tab ẩn. Không gọi số này là thời gian lao động chủ động đã chuẩn hóa.
- Cần bổ sung replay nhiều seed, ablation, khoảng tin cậy theo video và quy tắc pause/resume trước thực nghiệm nghiên cứu hoàn chỉnh.
- Bản UI demo có thể thao tác nhưng chỉ dùng văn bản minh họa; không phải thí nghiệm người dùng đã thu thập.

Nguồn bài báo: https://doi.org/10.1016/j.softx.2026.103072. Kiến trúc tham khảo: https://github.com/vdhong/AnnotaHub.
