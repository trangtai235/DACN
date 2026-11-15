# Protocol đánh giá đóng góp

## Câu hỏi và giả thuyết

H1: phối hợp hai dự đoán có thể giảm công sức nhưng cần đo lỗi cả trong nhóm đồng thuận.
H2: retrieval phản hồi duyệt và train theo đợt có thể thích ứng schema, không mặc định cải thiện.
H3: ưu tiên bất đồng kèm thăm dò có thể hiệu quả hơn random ở cùng budget.
Đây là giả thuyết, chưa phải kết quả.

## Chốt dữ liệu trước điều kiện có AI

1. Pilot riêng để chỉnh quy tắc nhãn, tỷ lệ thăm dò, tham số retrieval và quy trình đo thời gian.
2. Tập support/train và validation tách nguồn/video; exact duplicate kiểm tra bằng Unicode NFC,
   casefold và whitespace. Các biến thể gần nhau cần nhóm rà thêm bằng similarity/kiểm tra tay;
   hệ thống hiện chưa bảo đảm loại mọi paraphrase.
3. Tập đánh giá cuối giữ riêng theo nguồn/video. Hai người gán độc lập không xem AI;
   người thứ ba phân xử và ghi nguồn gốc. Đây là tham chiếu nhóm, không tự gọi chuẩn chuyên gia.
4. Quản lý chốt `DataPartition` bằng `POST /api/studio/collaboration/partition`
   (`project`, `comment_ids`, `role`: support/pilot/test/reference) TRƯỚC sử dụng mẫu.
   CSV tham chiếu `id,label` nhập qua `/api/references` trước chạy cặp dự đoán.
   Không dùng thao tác quản trị DB để bỏ qua các guard này trong thực nghiệm.
5. Không dùng nhãn test/reference, gợi ý AI chưa duyệt, mẫu đang tranh chấp hoặc trùng chính
   mẫu làm ví dụ. Nguồn/video đã giữ riêng bị loại khỏi feedback eligibility.
   Dataset mới bị từ chối nếu test dự kiến từng được đóng vào prompt retrieval.

## Các điều kiện

- Local-only: model/checksum/schema cố định.
- API chỉ mô tả nhãn: tắt few-shot, cùng schema/text/context/model API.
- API có retrieval: bật few-shot; lưu ID/revision/hash ví dụ và prompt version.
- Phối hợp: con người quyết định; bất đồng có preliminary trước exposure. Đồng thuận vẫn cần xác nhận.
- Local trước/sau một đợt train: dùng cùng validation để quản lý chọn ứng viên; test báo cáo theo
  protocol đã chốt. Nếu nhìn test nhiều lần để điều chỉnh thì phải giữ một tập đánh giá cuối khác.

Lượt hỗ trợ dùng `Annotation`; gold là `GoldAnnotation` có ưu tiên khi xuất nhãn thường.
Lượt kiểm tra ngân sách là overlay nghiên cứu theo `ReviewRun`, không sửa gold hoặc first_label cũ.
Chọn rõ run khi xuất/chấm; không trộn nhiều nguồn nhãn cuối mà không ghi provenance.

## Policy và thời gian

`grouping_strategy=legacy_ai_human` giữ A/B/C/D cũ. `local_api` chỉ phân nhóm agreement/disagreement
trên cặp hợp lệ và schema nhiều lớp. P0 random; P1 disagreement-first; P2 bốn lượt ưu tiên bất đồng,
một lượt thăm dò đồng thuận (fallback khi nhóm rỗng); P3 prior và điểm thay đổi nhãn/giây quan sát,
cập nhật theo batch năm. Điểm này KHÔNG là xác suất sửa đúng; policy không đọc ReferenceLabel.

Mỗi run cố định quần thể, text/context/hash/schema, nhãn đầu, hai Prediction và revision quyết định.
Một việc tại một thời điểm giúp kiểm ngân sách. Không cấp việc mới sau hết budget;
việc đã nhận vẫn nộp/phân xử được, ghi phần vượt. Pause run không tự hoàn thành task.

UI gửi heartbeat 10 giây, server cộng tối đa 20 giây giữa hai mốc hoạt động;
thời gian dư hoặc pause tính chờ/nghỉ. Tab ẩn gửi pause; mất mạng/đóng tab
không thể phân biệt hoàn hảo với người vẫn làm offline: tối đa 20 giây đầu được tính hoạt động,
phần còn lại tính chờ khi có mốc tiếp theo. Sau trở lại cần bấm Tiếp tục.
Phân xử có đồng hồ riêng. Không gọi số đo này là lao động chuẩn hóa; run cũ vẫn dùng wall-clock cũ.
Trang quyết định lượt đầu cũng có heartbeat/pause/resume theo cùng cap, lưu thời gian
vào PairDecision/Annotation.seconds. Báo cáo tách first_decision_active/idle khỏi
ngân sách review/adjudication. Đây là thời gian của phiên quyết định đầu được ghi nhận,
không tự suy ra thời gian cho công việc đã làm ngoài app hoặc các lần sửa lịch sử khác.

Người kiểm tra khác người lượt đầu và chưa có Annotation/AIExposure trên mẫu.
Người phân xử khác hai người gán. Bộ nhớ, ảnh chụp, công cụ ngoài app và quyền admin DB
không được lớp ẩn API kiểm soát; ba thành viên kiêm nhiệm phải công bố hạn chế đó.

## Chỉ số và xuất báo cáo

`GET /api/studio/collaboration/report?project=P&runs=R1,R2&bootstrap=1`
trả schema/checksum/Prediction/decision revision, cùng ID/hash, metrics từng điều kiện,
strict paired metrics trên cùng tập thành công, coverage/lỗi, token/latency/chi phí ước tính.
Không có tham chiếu thì metrics=null. Chi phí response thất bại chưa có usage không được coi là 0 đồng thực trả.

`GET /api/studio/budget/runs/R/report?download=1` chấm toàn bộ quần thể có tham chiếu:
mẫu chưa kiểm tra/chưa hoàn thành giữ nhãn đầu. Báo macro-F1, từng lớp, confusion matrix,
fixed, harmed, `net_fixes=fixed-harmed`, tỷ lệ hai model cùng sai trong nhóm đồng thuận,
pending, active/idle/adjudication/overrun. Reference coverage phải được nêu cùng kết quả.

`&replay=1&seeds=7,42,103` chạy lại P0–P3 chỉ khi mọi mẫu trong quần thể đã có kết quả
con người thực được quan sát. Thứ tự tái lập với seed và snapshot không đổi. Replay dùng nhãn/cost
lịch sử đã quan sát; không mô phỏng quyết định người rồi coi là nghiên cứu mới. Thay budget ở
service `reviewing.paired.replay` để xuất nhiều điểm chất lượng/ngân sách.

Bootstrap trong báo cáo model dùng resampling cụm nguồn/video, 200 lần, seed 42;
chỉ xuất khoảng khi ít nhất 5 cụm và 20 mẫu tham chiếu. Đây là điều kiện vận hành tối thiểu,
không bảo đảm mẫu đại diện hay độ chính xác thống kê. Thiếu dữ liệu ghi unavailable.
Không so confidence local với API như cùng thang xác suất; không dùng span F1/char F1 làm accuracy câu.

## Nhóm phải tự thu

Lập bảng phân công/đối trọng thứ tự và độ khó; hạn chế cùng người làm lại cùng mẫu.
Thu quyết định độc lập, lý do, exposure, pause/heartbeat, phân xử, API usage/lỗi,
thông tin nguồn/quyền sử dụng và log model/dataset. Nhiều seed không thay thế nhiều người quan sát.
Không xuất số liệu minh họa, fixture hoặc điểm checkpoint thành kết quả thực nghiệm mới.
