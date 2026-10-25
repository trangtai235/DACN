# Cấu trúc dự án

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
