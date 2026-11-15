# Đối chiếu chức năng và phạm vi

Đối chiếu source AnnotaHub tại commit `7fc2689e535f21604baf16f7d79a8b24d6882103` được ghi cụ thể trong [CONTRIBUTION_MATRIX.md](CONTRIBUTION_MATRIX.md). Không tuyên bố đã chạy toàn bộ hệ thống tham khảo hoặc đọc được toàn văn bài báo.

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
| Local model selection/inference | PhoBERT-base, XLM-R base, XLM-R large | Xem báo cáo; suy luận cần backend |
| Train algorithm selector | 3 thuật toán sklearn, CSV3split | Chỉ cấu hình, chạy mới cần backend |
| Gemini/Ollama/OpenAI-compatible | Adapter thật, configurable | Không nhận key/gọi API |
| Paired model/API evaluation | Có, chi phí ước tính, pin artifact/schema | Metrics local có thật; API chưa đo |
| Binary A/B/C/D supplementary review | Có, server state/budget/blindness | Mô phỏng quy trình trên dữ liệu tổng hợp |
| Cặp local–API gắn schema/text/context/Prediction ID | Có, hai job độc lập, lỗi không thành nhãn | Cần native, không tạo số đo giả |
| Preliminary/exposure/confirm/context/escalate | Có, dùng Annotation/Gold/audit/revision | Cần native |
| Human-in-the-loop trong luồng chính | Menu Người duyệt nhãn + Gán nhãn thủ công; chạy máy chuyển vào hàng đợi; quản lý duyệt phản hồi của người khác; xuất nhãn người riêng | Gán thủ công trên demo; cặp gợi ý/audit cần native |
| Schema version/exclusions/compatibility | Có, snapshot bất biến và API-only/human-only | Cần native |
| Trang Quản lý nhãn riêng | CRUD theo dự án, preview, lọc, revision/quyền, bảo vệ nhãn đã dùng; cùng API với HITL và giữ draft khi quay lại/reload | Trang thông báo cần backend, không có CRUD nhãn giả |
| Approved few-shot retrieval | Có, TF-IDF/cosine và guard test/trùng/schema | Cần native, không fine-tune API |
| Feedback dataset/train/validation/activate/rollback | Có, sklearn nhiều lớp và split theo nguồn/video | Demo command tổng hợp, không là kết quả thật |
| Grouping local–API nhiều lớp / heartbeat budget / replay | Có, tách run cũ, seed/snapshot/reason, net fixes toàn quần thể | Chưa có human study |
| Native Windows / optional Docker | Source + scripts | Không có PostgreSQL host kèm |

## Chủ đích và giới hạn

- Khóa/lưu trữ dự án thay vì xóa toàn bộ lịch sử. Source xóa chỉ khi không có nhãn người/lượt nghiên cứu và không có job đang chạy.
- Export converter được viết riêng; các schema như spaCy JSON/HF là interchange data, không tạo sẵn spaCy DocBin hoặc HuggingFace dataset binary. Kiểm tra importer cụ thể khi tích hợp tool khác.
- CSV nhãn nhập là gợi ý, không phải nhãn người độc lập. TF-IDF dự đoán câu, không phải span model.
- Có adapter suy luận PhoBERT/XLM-R với trọng số local phù hợp nhiệm vụ; không tự train Transformer trong đợt này. Không có SSO, realtime collaborative cursor hoặc distributed locks được stress-test, không cam kết production HA.
- So sánh trong báo cáo phải dùng cùng nguồn/split/nhãn, không dùng số đo ViCTSD để khẳng định hơn API trên YouTube.
- Các policy kiểm tra là nhánh nghiên cứu; chưa có human study hay tái lập toàn bộ kết quả bài báo.
