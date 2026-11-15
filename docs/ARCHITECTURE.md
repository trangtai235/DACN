# Cấu trúc dự án

## Quản lý nhãn và bản nháp workspace

`#label-management` là route/module riêng, đọc/ghi cùng `/api/studio/labels` với workspace.
GET trả quyền/catalog/usage/revision/compatibility; POST khóa ProjectSettings rồi kiểm manager,
project ID, revision và lịch sử trước cập nhật/xóa. ProjectLabel có revision tăng khi sửa;
ID/key/project giữ ổn định. Snapshot schema giữ nghĩa cũ; metadata màu/thứ tự vẫn cập nhật cho UI.

`core/workspace-drafts.js` lưu session draft theo user/project. Router gọi beforeLeave và
afterRender để lưu/khôi phục đúng bình luận. Nhãn bị ngừng dùng giữ trong bản nháp và lịch sử,
nhưng không cho chọn mới hoặc nộp như nhãn đang dùng. Bản nháp không thay thế API/server revision.
Run dự đoán giữ schema cũ; con người có thể dùng catalog hiện hành, lịch sử quyết định chụp
schema từng revision. Model không được tự diễn giải lại đầu ra khi quản lý thêm nhãn.

## Luồng M1–M3 bổ sung 14/11/2026

`AutoLabelRun.schema/options/request_key` mở rộng run đã có; run lịch sử giữ schema=null.
`PredictionPair` ghép hai FK Prediction chính xác, cùng Comment, text/context/hash và schema bất biến.
Hai job `paired_predict` đi qua dispatcher threads/Celery cũ; không ghi đè `Comment.ai_label`.
Mỗi nhánh có pending/running/complete/error/missing/incompatible, timestamp/attempts và lỗi rõ.
State tổng: pending, agreement, disagreement, partial_error, incompatible, stale; quyết định
con người hiển thị riêng status/revision. Chỉ nhãn câu đơn lựa chọn được so sánh; spans của local
vẫn giữ Unicode offsets, nguồn riêng. API trong luồng mới chỉ được yêu cầu nhãn câu.

`PairDecision` lưu preliminary, exposure timestamp và chính xác Prediction ID đã xem,
schema, revision, lịch sử và clock cho lần quyết định lượt đầu. Khi xác nhận dùng lại `Annotation` và `AnnotationEvent`;
không tự tạo gold. Gold do người có quyền phân xử, có lý do và revision chống ghi đè.
Nhãn xuất thường ưu tiên GoldAnnotation rồi annotation người theo cơ chế cũ; report nghiên cứu
có run sử dụng snapshot nhãn đầu và final của task complete, không thay gold/first_label toàn cục.
Không gán lại first_label/origin_group cũ để làm thay đổi nghĩa A/B/C/D.

`LabelSchema` là snapshot bất biến gồm định nghĩa nhãn (kể cả disabled), loại trừ và guidelines.
Snapshot thay đổi khi sửa schema; màu/thứ tự giao diện không đổi nghĩa nhãn.
`FeedbackApproval` là opt-in do quản lý duyệt, không lấy AI tự gán làm gold.
`DataPartition` và ReferenceLabel bảo vệ tập giữ riêng; eligibility kiểm annotation revision,
tranh chấp, canonical duplicates, nguồn/video và schema. Retrieval TF-IDF/cosine tái lập,
đóng ví dụ vào từng nhánh ngay khi tạo run. Adapter thật nhận prompt_context qua registry cũ.

`FeedbackDataset` chụp ID/approval/text/label/source/split/seed/checksum. Thành phần liên thông
theo nguồn/video và text trùng ngăn giao nhau. `feedback_train` tái sử dụng experiments.training;
validation chọn siêu tham số và chấm incumbent trên cùng mẫu. Test chỉ báo cáo.
Ứng viên ModelRun có schema hash, dataset hash và artifact; quản lý kích hoạt/rollback qua API có audit.
Hash artifact lớn một lần mỗi branch; giữa các mẫu kiểm signature file để tránh đọc lại hàng GB mỗi click.

`ReviewRun.grouping_strategy=legacy_ai_human` đọc lịch sử như trước. `local_api` dùng snapshot
nhiều lớp và service `reviewing/paired.py`, tái sử dụng ReviewTask/P0–P3.
Đồng hồ phase review/adjudication heartbeat cap 20s, pause/resume, idle và overrun;
claim tuần tự, không cấp mới khi hết budget. Replay cần lịch sử quan sát đầy đủ.
Thời gian quyết định lượt đầu được lưu vào Annotation.seconds và snapshot nghiên cứu,
tách khỏi ngân sách kiểm tra bổ sung; quyết định scripted có thời gian 0 và cờ demo.
Tham chiếu chỉ được đọc trong report, không được dùng làm feature hoặc score chọn mẫu.

API mới ở `/api/studio/collaboration*` và `/api/studio/budget*`; UI chính `#human-review`
(alias `#collaboration`) / `#manual-annotation` / `#budget`.
Router gán thủ công dùng lại module features/annotation với namespace sự kiện manual-annotation;
module features/automatic giữ namespace annotation. Chạy máy bật HITL chuyển sang đúng run ở hàng đợi.
Giám sát quyết định người có kiểm quyền và audit exposure; những người đã xem không được cấp
mẫu đó ở lượt nghiên cứu độc lập. Export human/gold tách khỏi export dự đoán tự động.
Source UI vẫn dưới frontend/src, dist chỉ là output. Xem [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
và [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md) về giới hạn đo lường.

```text
AnnotaFlow/
  frontend/
    index.html
    src/
      app.js                    router, shell, event delegation
      core/                     state, API client, UI helpers, backend inference integration
      features/
        auth/ projects/ overview/ datasets/ annotation/ research/
        models/ evaluation/ quality/ versions/ exports/
        members/ project-settings/ account/
      styles/                   base, theme, auth, studio
    public/                     synthetic demo + Transformer model reports
  backend/
    config/                     Django settings, URLs, WSGI
    core/
      api/                      accounts, projects, ingestion, inference, research, evaluation
      jobs/                     runner, checkpoint, predict, training, benchmark, CSV, YouTube
      services/                 dispatch and local model loading
      management/commands/      setup/demo/recovery/dataset download
      models.py                 projects, members, sources, comments, jobs, audit
      migrations/
    studio/
      api/                      one module per application feature
      models/                   projects, annotations, accounts, versions
      services/                 schemas/guards, quality metrics, 16 exports
      migrations/
    integrations/
      providers/                base, Gemini, Ollama, OpenAI-compatible
      registry.py               uniform adapter interface, safe config snapshots
      secrets.py                Fernet key encryption
      models.py                 project provider connections
    experiments/
      algorithms/registry.py    allowed algorithms and validation grids
      training.py               split cleaning, fit, metrics, artifacts
      models.py                 model runs, benchmarks, references
    reviewing/                  time-budget sampling, blind review, adjudication
    artifacts/                  3 trained model versions, reports, predictions
    tests/                      business/security/export/job tests
    private_data/               runtime-only uploads/models/exports/emails (ignored)
  requirements/                 shared pinned packages + Windows variant
  scripts/                      env setup, native startup, build, model checks
  docs/                         architecture, extension, feature matrix, verification
  dist/                         generated deployable frontend; do not edit
  .github/workflows/            PostgreSQL 15 CI configuration
  RUN_NATIVE_WINDOWS.bat        native development entry point
  START_WINDOWS.bat             optional Docker entry point
```

`frontend` gọi `/api/*` qua cookie/session/CSRF. Backend chịu trách nhiệm kiểm tra quyền, nhãn, offsets, revision và transaction; không tin role hoặc dữ liệu từ trình duyệt. Browser demo dùng dữ liệu tổng hợp lưu localStorage, không xác thực tài khoản thật.

Một `Comment` giữ text gốc, source/context/metadata; `Annotation` là lớp riêng theo user; `GoldAnnotation` là quyết định phân xử; `Prediction` giữ lịch sử model/API. Lượt đầu nghiên cứu được đóng băng riêng, không ghi đè khi gán lại AI hoặc sửa annotation chung.

Job dispatch: native `threads` (2 worker) hoặc Docker `celery`+Redis. Checkpoint sau response/row, cancellation ở safe boundary; retry pin cấu hình model/API và schema để tránh trộn kết quả. YouTube lưu cursor trang gốc và trang/reply index. Restart native đánh dấu job bị ngắt để quản lý tiếp tục.

Thay đổi model/nhãn giữa các lượt cần xem lại tính tương thích. TF-IDF không tự chuyển nhãn nhị phân thành nhãn nhiều lớp; backend kiểm tra schema. Không load pickle do người dùng upload.

Phiên bản dữ liệu là snapshot lớp nhãn, không phải bản backup PostgreSQL. DB backup riêng bằng pg_dump khi vận hành thật.
