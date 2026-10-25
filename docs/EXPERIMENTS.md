# Thiết kế đánh giá cho đồ án

## Kết quả baseline đã chạy

Nguồn: UIT-ViCTSD, https://github.com/tarudesu/ViCTSD, commit `e1ffb854ef7b7b7ae45a56d132c1f125e02e55e2`.

Tập gốc train/validation/test là 7.000 / 2.000 / 1.000 bình luận. Dùng **Toxicity**, không dùng Constructiveness làm nhãn độc hại. Sau chuẩn hóa Unicode, chữ thường và khoảng trắng để phát hiện trùng: train còn 6.943, validation còn 1.988, giữ nguyên 1.000 test. Việc làm sạch xóa cả trùng nội bộ và giao nhau với split được bảo vệ; không chuyển nhãn test vào train.

Model TF-IDF char 3–5 gram, 60.000 features, sublinear TF, L2; Logistic Regression class_weight=balanced, seed 42. Thử C=0.5,2,8 trên train; chọn C=8 bằng validation Macro-F1. Chỉ chấm test sau khi chọn; không huấn luyện lại trên validation.

| Chỉ số trên 1.000 test | Giá trị |
| --- | ---: |
| Accuracy | 88,00% |
| Precision macro | 69,27% |
| Recall macro | 68,96% |
| Macro-F1 | 69,11% |
| F1 NON_TOXIC | 93,27% |
| F1 TOXIC | 44,95% |

Confusion matrix theo thứ tự [NON_TOXIC,TOXIC], hàng thật/cột dự đoán: `[[831,59],[61,49]]`. Có 61 mẫu độc hại bị bỏ sót. Model không được coi là đủ tin cậy để tự động chốt nhãn.

Test có 890 mẫu không độc hại và 110 độc hại. Một bộ đoán tất cả NON_TOXIC đạt accuracy 89%, cao hơn baseline này, nhưng Macro-F1 chỉ khoảng 47,09%. Vì vậy phải báo từng lớp và Macro-F1, không chỉ chọn accuracy để chứng minh hiệu quả.

Trọng số, file metrics.json và test_predictions.json nằm trong `backend/artifacts/victsd-logreg-v1/`. Hash CSV nguồn nằm trong metrics.json. Thời gian đo là trên máy chạy thực nghiệm, gồm một batch test; không so trực tiếp với độ trễ request mạng mà không nêu giao thức.

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

## Ba thuật toán trong Studio v3

Ngoài logistic regression, đã train thật Linear SVM (accuracy 87,9%, macro-F1 69,22365%) và Complement NB (accuracy 86,7%, macro-F1 69,49534%). Cùng clean split và protocol; báo cáo riêng trong artifacts. Khoảng chênh nhỏ chưa chứng minh ý nghĩa thống kê. UI chọn model và API theo dự án; benchmark lưu local_model_id để không gán kết quả cho model khác.
