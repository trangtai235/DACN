# Trạng thái triển khai M1–M3

Cập nhật 15/11/2026: có trang riêng **Quản lý nhãn** (`#label-management`), GET/POST
`studio/labels` chung với HITL, revision chống ghi đè, kiểm tra lịch sử và khôi phục bản nháp
qua điều hướng/reload. Lượt hồi quy mới nhất **121 tests, OK** gồm hai test browser;
chi tiết ở [VERIFICATION.md](VERIFICATION.md), [LABEL_MANAGEMENT_VI.md](LABEL_MANAGEMENT_VI.md).
Các số kiểm thử của đợt HITL bên dưới được giữ làm lịch sử.

Ngày 14/11/2026, branch `feat/code-update-20261114`, base `5e24ba55ad200bef45246f56f6f8d37d09ac9e8c`.
Không push/deploy, không thay lịch sử Git. Không thay .env.local hay tải lại checkpoint lớn.

## Đã hiện thực

| Mốc | Dữ liệu/API/giao diện | Kiểm chứng |
|---|---|---|
| M1 | AutoLabelRun mở rộng; PredictionPair, PairDecision; snapshot text/context/schema; trạng thái từng nhánh, Prediction ID, errors/tokens/cost; idempotent run/retry; preliminary/exposure/confirm/context/escalate/gold; Annotation và audit cũ được tái sử dụng. | Thứ tự local/API, retry, lỗi output, stale context/schema, revision, mù qua nhiều endpoint, cùng sai, phân quyền. |
| M2 | LabelSchema bất biến, version/hướng dẫn/loại trừ; TF-IDF/cosine approved retrieval; compatibility/API-only/human-only; dữ liệu feedback theo lớp; source/video/duplicate-grouped snapshot; sklearn candidate/validation/activate/rollback. | Retrieval có ID/revision/hash, loại test/reference/trùng/khác dự án/chưa duyệt; train nhiều lớp thật trên fixture, artifact và kích hoạt/rollback. |
| M3 | ReviewRun mới có grouping local_api/input snapshot, lịch sử A–D giữ nguyên; P0–P3 có reason/seed; đồng hồ heartbeat/pause/resume/idle/adjudication; báo cáo/replay/multi-seed; strict-paired metrics và bootstrap cụm khi đủ dữ liệu. | Seed/thăm dò đồng thuận, cap heartbeat/pause/budget/overrun, net fixes trừ harmed, replay yêu cầu quan sát đủ, migration giữ run/prediction cũ. |

Routes UI: `#human-review` (giữ alias `#collaboration`), `#manual-annotation`, `#budget`;
nguồn trong `frontend/src/features/` và build qua Python sang dist.
API/command và cách demo: [DEMO_SCRIPT_VI.md](DEMO_SCRIPT_VI.md).

Luồng HITL nối từ chạy tự động → người duyệt → phân xử → quản lý duyệt phản hồi → xuất nhãn người.
Router gán nhãn thủ công đã được nối; chọn nhãn không tự nộp ngay. Quản lý có màn hình giám sát
quyết định của người khác; việc xem được audit và loại khỏi lượt nghiên cứu độc lập.
Chi tiết: [HUMAN_IN_THE_LOOP_VI.md](HUMAN_IN_THE_LOOP_VI.md).

## Kết quả kiểm tra

Lượt cuối **111 tests, OK**: 86 test cũ, 24 test về M1–M3/HITL/migration và một browser smoke test
qua HTTP frontend/backend thực trên SQLite cách ly. Bao gồm demo command, report/pause,
clock quyết định lượt đầu và giữ tính năng xóa dự án có xác nhận khi có lịch sử mới.
Bằng chứng/lệnh và giới hạn ở [VERIFICATION.md](VERIFICATION.md); không lấy lượt lỗi làm bằng chứng pass.
`pip check` đã qua; Django system check và migration dry-run đã qua;
frontend build và kiểm tra syntax/import targets cho 60 module đã qua.
Windows build được sửa thông báo console ASCII để không lỗi cp1258.

Browser: đồng thuận/bất đồng mù/cùng sai/API lỗi/pause-resume/phân xử đã thao tác thành công,
không có page error. Đây là kiểm tra phần mềm trên fixture, không phải thí nghiệm với người.

## Chưa kiểm chứng/chưa đo

- Chưa gọi API thương mại/Ollama thật trong đợt này, không kiểm quota/phí/hóa đơn. Mock lỗi/timeout
  không chứng minh adapter đạt độ chính xác thực. Adapter prompt/result dùng cấu trúc có sẵn.
- Thư mục trọng số PhoBERT/XLM-R đã có trên máy; đợt này không chạy lại suy luận checkpoint lớn
  hay đo lại metrics. Compatibility không biến các checkpoint độc hại thành classifier schema tùy ý.
- Chưa đo thời gian hoặc chất lượng người dùng thật, không có kết quả cải thiện F1/ngân sách để kết luận.
  Demo command tạo quyết định scripted, không phải quan sát con người.
- SQLite tests không thay thế PostgreSQL locks/concurrency, Redis/Celery hoặc tải production;
  chưa tuyên bố chạy lại toàn bộ integration trên PostgreSQL 15–18/Windows native thật.
- Chưa kiểm toàn bộ AnnotaHub khi chạy; chỉ đối chiếu source tại commit nêu trong contribution matrix.
  Toàn văn bài báo bị chặn truy cập, không bịa nội dung.
- Chuẩn hóa phát hiện trùng chính xác, không bảo đảm phát hiện tất cả biến thể gần nhau.
  Heartbeat là proxy vận hành; mất mạng không thể phân biệt hoàn hảo với làm offline.

## Phần nhóm phải làm

Thu pilot/nguồn giữ riêng, tạo tham chiếu hai người + người thứ ba trước AI;
chốt schema, protocol/prompt/partition; chạy adapter và model thật trên cùng ID;
cân bằng thứ tự/độ khó, ghi thời gian và usage; thu đủ kết quả trước replay;
báo hạn chế ba thành viên kiêm nhiệm. Xem [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md).
