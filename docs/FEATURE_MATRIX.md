# Đối chiếu chức năng và phạm vi

Tham khảo AnnotaHub README + code đã đọc tại commit `7fc2689e535f21604baf16f7d79a8b24d6882103`. Website tham khảo có tường đăng nhập; không tuyên bố đã kiểm thử tất cả màn hình bên trong server gốc. Đây là triển khai mới cùng nhóm nghiệp vụ, không chứng nhận tương đương mọi edge case của bản gốc.

| Nhóm | Backend PostgreSQL | Demo online |
|---|---|---|
| Login/register/session/reset/verification | Có; mail file local hoặc SMTP | Màn hình xem trước, không thu password |
| Projects/labels/guidelines/lock/archive | Có | Có, localStorage |
| Members/invite/role | Có, kiểm quyền | Xem nhóm 3 người, đổi vai demo |
| Text/CSV import | Có, mapping/backend job | Text/CSV cơ bản; cột text/Comment |
| YouTube roots + paginated replies | Có, cursor resume, key cần cấu hình | Hướng dẫn chạy backend |
| Sentence + span annotation/skip/edit/undo | Có, revision/offset validation | Có |
| Independent queue/AI exposure | Có, ẩn gợi ý trước nộp + ghi exposure | Có; không bảo đảm chưa xem văn bản ngoài hệ thống |
| Agreement/conflicts/gold | Có | Tính trên dữ liệu demo |
| Dataset versions/restore | Có, nhãn người/gold cùng ID + text | Có cho lớp nhãn demo |
| 16 exports/scopes/history | Có, checksum/private file + history | 16 formats; không audit server |
| Local model selection/inference | 3 model có sẵn + model train mới | 3 model nhị phân có trọng số thật |
| Train algorithm selector | 3 thuật toán sklearn, CSV3split | Chỉ cấu hình, chạy mới cần backend |
| Gemini/Ollama/OpenAI-compatible | Adapter thật, configurable | Không nhận key/gọi API |
| Paired model/API evaluation | Có, chi phí ước tính, pin artifact/schema | Metrics local có thật; API chưa đo |
| Binary A/B/C/D supplementary review | Có, server state/budget/blindness | Mô phỏng quy trình trên dữ liệu tổng hợp |
| Native Windows / optional Docker | Source + scripts | Không có PostgreSQL host kèm |

## Chủ đích và giới hạn

- Khóa/lưu trữ dự án thay vì xóa toàn bộ lịch sử. Source xóa chỉ khi không có nhãn người/lượt nghiên cứu và không có job đang chạy.
- Export converter được viết riêng; các schema như spaCy JSON/HF là interchange data, không tạo sẵn spaCy DocBin hoặc HuggingFace dataset binary. Kiểm tra importer cụ thể khi tích hợp tool khác.
- CSV nhãn nhập là gợi ý, không phải nhãn người độc lập. TF-IDF dự đoán câu, không phải span model.
- Không có Transformer/PhoBERT, SSO, realtime collaborative cursor, distributed locks được stress-test hay cam kết production HA.
- So sánh trong báo cáo phải dùng cùng nguồn/split/nhãn, không dùng số đo ViCTSD để khẳng định hơn API trên YouTube.
- Các policy kiểm tra là nhánh nghiên cứu; chưa có human study hay tái lập toàn bộ kết quả bài báo.
