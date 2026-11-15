# Xác minh AnnotaFlow Studio 3

## Sửa trạng thái model và tiếp tục gợi ý theo video — 15/11/2026

Lượt cuối: **147 tests, OK**, 72,979 giây, gồm ba luồng browser cách ly và vòng đời Chrome
trên Windows. **70 module source/build**, **16 converter** qua; migration dry-run không
có thay đổi. [Log hồi quy](../backend/private_data/verification/django-prediction-resume-full.log),
[browser theo nguồn](../backend/private_data/verification/source-scope-browser.json),
[ảnh gợi ý một nhánh](../backend/private_data/verification/hitl-resumed-local-suggestion.png).

Tái hiện trên PostgreSQL đang dùng: run #5 có job Local #38/API #39 đã failed sau khi
server dừng, nhưng JSON của từng cặp còn pending/running. Giao diện trước sửa chỉ đọc
JSON nên báo đang xử lý dù không còn worker. Trạng thái mới đối chiếu job với Prediction
đã lưu; kết quả hoàn tất vẫn giữ nguyên, thiếu kết quả sau khi dừng báo interrupted.

Thêm 5 test API/service: phân biệt queued/running/interrupted và giữ dự đoán đã hoàn tất;
tiếp tục đúng nguồn/nhánh thiếu, tham chiếu lại Prediction có sẵn; API chỉ tạo job khi
được yêu cầu; idempotency; quyền quản lý/nguồn/schema/job đang chạy; recovery lúc native
startup. Worker API chạy bằng mock và xác minh nhãn sửa của người/gold không bị thay đổi.

Browser mở video D có hai job failed: không báo đang chạy, hủy hộp thoại không tạo job,
Local được chọn sẵn còn API tắt. Gửi tạo đúng một job Local và chỉ hàng đợi D; reload
giữ run/video/note. Dùng response tổng hợp để mô phỏng worker chuyển running → complete:
gợi ý tự hiện, không mất note/focus và không tự chọn nhãn hay gọi là đồng thuận.
Luồng bất đồng vẫn phải lưu lựa chọn độc lập rồi bấm mở gợi ý; hồi quy browser xác minh.

Kiểm tra `resume_run` thực tế trên PostgreSQL bằng transaction **rollback toàn bộ**:
nguồn #10 chỉ chọn 50 mẫu thiếu Local, không tạo job API; dispatch không được gọi và số
bản ghi Job/Prediction/AutoLabelRun/Annotation/PairDecision trước/sau bằng nhau.
[Bằng chứng](../backend/private_data/verification/postgres-prediction-resume.json).
Đây là số lượng dữ liệu hiện có và kiểm thử kỹ thuật, không phải metrics mô hình.
Không chạy suy luận thật hoặc gọi API thương mại trong đợt sửa này.

## Ưu tiên Google Chrome cho launcher — 15/11/2026

Launcher tìm tất cả vị trí Chrome trước Edge, kể cả Chrome 64-bit khi Edge nằm trong
Program Files (x86). Máy kiểm tra chọn đúng `C:\Program Files\Google\Chrome\Application\chrome.exe`.
**7 test launcher, OK**, 19,505 giây: thêm test ưu tiên browser và chạy lại các tình huống
đóng web, reload, backend dừng, force-close launcher với Google Chrome thật ở chế độ headless.
[Log](../backend/private_data/verification/native-chrome-lifecycle.log).
Hành vi đóng cửa sổ app dừng backend và giữ các cửa sổ trình duyệt khác tiếp tục được xác minh.

## BAT tự mở web, đóng cửa sổ web dừng backend — 15/11/2026

Lượt cuối: **141 tests, OK**, 66,708 giây, gồm ba luồng Chromium của ứng dụng và ba test
vòng đời tiến trình trên **Windows thật với Edge headless đã cài**.
[Log toàn bộ](../backend/private_data/verification/django-native-window-full.log),
[log 6 test launcher riêng](../backend/private_data/verification/native-web-lifecycle.log).

`RUN_NATIVE_WINDOWS.bat` gọi supervisor mới: đợi HTTP backend sẵn sàng, mở cửa sổ Edge/Chrome
app riêng và theo dõi các page target thuộc cửa sổ đó. Profile riêng theo
[quy định DevTools của Chrome](https://developer.chrome.com/blog/remote-debugging-port)
được giữ ở private_data; cổng DevTools ngẫu nhiên chỉ dùng loopback.

Đã kiểm:

- Đóng trang app: launcher thoát, server HTTP test và tiến trình con đã dừng, cổng được giải phóng.
- Trang tự reload và đổi hash route: backend vẫn chạy. Một browser fixture riêng vẫn sống khi app đóng.
- Backend bị dừng: cửa sổ app được dọn, launcher báo lỗi và không để sót process.
- Force-close launcher: Windows Job Object dừng server và descendants, kể cả tiến trình con thử nghiệm.
- Backend/browser khởi động lỗi được dọn; endpoint profile cũ được xóa khi stale nhưng giữ dữ liệu login;
  profile đang chạy bị từ chối để tránh nối nhầm cửa sổ.

Đã chạy **BAT thật** sau khi kiểm tra server cũ không có job queued/running. PostgreSQL sẵn sàng,
không có migration mới; recovery ghi nhận 0 job bị ngắt. Backend trả HTTP 200 và tự mở cửa sổ app
tại localhost:8000. [Log BAT](../backend/private_data/verification/native-bat-live.log).
Cửa sổ thật được để mở cho người dùng; thao tác đóng/kill tự động được kiểm trên các fixture
HTTP/browser riêng, không dùng bình luận hay job của người dùng để thử dừng tiến trình.

Các phần dưới ghi nhận các đợt trước thay đổi launcher.

## Gán nhãn riêng theo video / nguồn — 15/11/2026

Lượt cuối: **135 tests, OK**, 37,544 giây, gồm ba luồng Chromium trên SQLite cách ly.
Build mới qua kiểm tra **70 module source/build**, **16 converter**, migration dry-run không
có thay đổi. [Log hồi quy](../backend/private_data/verification/django-video-scope-full.log),
[browser theo nguồn](../backend/private_data/verification/source-scope-browser.json),
[ảnh HITL theo video](../backend/private_data/verification/hitl-video-only.png).

Thêm 7 test API và một test browser cho nguồn: dashboard/queue/count đúng nguồn, cặp chi tiết
khác nguồn bị từ chối, không lưu nhầm nguồn hoặc nguồn dự án khác, tạo run/idempotency theo nguồn,
manual queue hết mẫu không lấy nguồn khác, lượt tự động/CSV/retry không nhận run trộn nguồn,
snapshot chạy mới chỉ có bình luận video chọn.

Browser bấm Gán nhãn từ thẻ video A/B, xác minh run cũ trộn A+B chỉ hiện hai mẫu A;
bản nháp A/B riêng, qua Quản lý nhãn và reload không đổi nguồn hoặc mất nháp. Gán hết A
không nhảy B; manual của A hiển thị hết mẫu. Chuyển manual B/A/B và reload giữ note/nhãn
của B. Video C chưa có dự đoán không mở hàng đợi chung; tạo lượt từ màn tự động vẫn giữ C.
Trong lúc tải nguồn mới, thao tác gán được khóa đến khi giao diện cập nhật.

Đã đọc API trên PostgreSQL **18.6** bằng transaction rollback và trên server localhost sau
khi khởi động lại (không có job queued/running). Run cũ #5 có 365 cặp: nguồn #8 trả riêng
115, #9 trả 200, #10 trả 50, mọi row đúng source_id. Đây là số lượng dữ liệu hiện có, không
phải kết quả đánh giá model. [Kiểm tra PostgreSQL](../backend/private_data/verification/postgres-video-scope.json),
[kiểm tra HTTP server đang chạy](../backend/private_data/verification/live-video-scope.json).
Không sửa nhãn, seed/migrate hoặc chạy model/API thật trên database làm việc trong bước xác minh.

Các phần sau giữ lịch sử trước khi thêm phạm vi nguồn.

## Sửa lỗi lưu HITL trên PostgreSQL và backend cũ — 15/11/2026

Tái hiện trên PostgreSQL **18.6** đang dùng: `NotSupportedError: FOR UPDATE cannot be applied
to the nullable side of an outer join`. `AutoLabelRun.schema` cho phép null để đọc run cũ;
truy vấn khóa cả phần join khi lưu nhãn bị PostgreSQL từ chối. Đã giới hạn khóa ở
PredictionPair, vẫn giữ khóa preferences/comment và kiểm tra revision như trước.
Các test SQLite của đợt trước không phát hiện lỗi riêng của PostgreSQL này.

Backend localhost lúc nhận ảnh lỗi chạy `--noreload` và còn giữ code cũ: GET detail trả 200
nhưng thiếu comment_id/author/tokens. Đã xác nhận không có job queued/running và khởi động lại
đúng server cổng 8000, không seed/migrate lại hoặc chạy model. Sau khởi động, API thật trả
workspace_version=1, comment_id hợp lệ, source/author/tokens và annotation_revision.

- [Kiểm tra PostgreSQL](../backend/private_data/verification/postgres-hitl-fix.json): gọi API lưu
  trong transaction, HTTP **200 application/json**, status confirmed, không tạo gold;
  rollback và đối chiếu annotation/decision/history/events giữ nguyên dữ liệu ban đầu.
- [Kiểm tra backend đang chạy](../backend/private_data/verification/live-hitl-backend.json).
- [Log hồi quy](../backend/private_data/verification/django-hitl-postgres-fix.log):
  **127 tests, OK**, 41,009 giây, trên SQLite cách ly và hai luồng Chromium.
- Browser mô phỏng API cũ: thông báo cần cập nhật backend, không hiện undefined hoặc cho
  nộp nhãn với dữ liệu thiếu; tải lại được sau khi API tương thích.
- Lỗi API bất ngờ được ghi stack trace trong log server, trả JSON 500 với thông báo an toàn;
  404 cũng trả JSON. Frontend chỉ rõ HTTP status nếu gặp phản hồi HTML.
- Build, **68 module source/build** và **16 converter** đều qua kiểm tra.

Đây là xác minh có mục tiêu trên PostgreSQL thật, chưa phải toàn bộ bộ test hoặc thử
concurrency trên PostgreSQL. Không có kết quả model/human study mới. Các mục dưới giữ lịch sử.

## HITL rút gọn theo giao diện AnnotaFlow — 15/11/2026

Lượt cuối: **124 tests, OK**, 37,656 giây, gồm hai luồng Chromium trên HTTP Django thật
và database SQLite tạm. Build mới qua kiểm tra **68 module source/build** và **16 converter**.
[Log](../backend/private_data/verification/django-hitl-simple.log),
[báo cáo browser](../backend/private_data/verification/browser-smoke.json),
[ảnh desktop](../backend/private_data/verification/hitl-simple-1366.png),
[ảnh 768px](../backend/private_data/verification/hitl-simple-768.png),
[ảnh 360px](../backend/private_data/verification/hitl-simple-360.png).

Màn hình dùng thẻ bình luận có chế độ compact và palette/control AnnotaFlow sẵn có.
Đã kiểm mặc định thu gọn công cụ, đổi lượt và hàng đợi; các nút gán nhãn/điều hướng nằm
trong khung nhìn đầu tiên ở desktop 1366×950 với fixture bình luận ngắn. Cả ba chiều rộng
không tràn ngang. Nội dung bình luận dài vẫn được hiển thị đầy đủ và có thể cuộn trang.

Tiến độ lấy từ các quyết định đã xác nhận của chính người dùng: kiểm tra tăng từ 0/4 đến 3/4
trong fixture. Nút Bỏ qua ghi skipped và nhãn rỗng, không tạo lớp nội dung. Mở công cụ,
chọn rồi bỏ chọn từ không làm công cụ tự đóng. Luồng tự lưu, lỗi mạng/giữ nháp sau reload,
ghi chú/spans, nhãn theo dự án, kiểm tra mù và phân xử vẫn qua hồi quy.

Số 0/4 và 3/4 là dữ liệu kiểm thử tổng hợp, không phải kết quả nghiên cứu người dùng.
Model/API dùng fixture/mock; không có suy luận thật hoặc migration database làm việc mới.
Các phần sau giữ lịch sử thay đổi và kết quả trước đó.

## Bấm nhãn để tự lưu HITL — 15/11/2026

Lượt cuối: **124 tests, OK**, 35,295 giây, gồm hai luồng Chromium với model/API mock.
Build đã cập nhật; **68 module source/build** và **16 converter** đều qua kiểm tra.
[Log tự lưu](../backend/private_data/verification/django-hitl-autosave.log) và
[báo cáo browser](../backend/private_data/verification/browser-smoke.json).

- Bấm nhãn hoặc Dùng gợi ý lưu qua API và tự chuyển sau khi server xác nhận.
- Ghi chú và cụm từ đang soạn được lưu kèm, được đọc lại từ dữ liệu xuất scope human.
- Mẫu bất đồng: lần bấm đầu lưu lựa chọn độc lập, giữ mẫu và chưa lộ dự đoán;
  sau khi mở gợi ý, bấm nhãn để xác nhận và tiếp tục.
- Chủ động ngắt request lưu: giữ đúng bình luận và bản nháp nhãn/note/spans sau reload;
  thử lại lưu thành công. Hai lần bấm liên tiếp chỉ tạo một request lưu.
- Nhãn đã tự lưu vẫn đúng sau reload. Chỉ hiển thị đồng thuận không tự ghi annotation.
- Luồng Quản lý nhãn, giữ bản nháp, phân quyền, xuất dữ liệu và kiểm tra mù tiếp tục qua hồi quy.

Các mục phía dưới ghi nhận hành vi và kết quả của các phiên bản trước.

## HITL dạng workspace gán nhãn — 15/11/2026

Lượt cuối: **124 tests, OK**, 32,680 giây, gồm hai test Chromium trên HTTP Django/SQLite
cách ly. Build mới kiểm tra **68 module source/build** và **16 converter** đều qua;
system check không có lỗi, migration dry-run không phát sinh thay đổi.

- [Log Django](../backend/private_data/verification/django-hitl-workspace.log).
- [Báo cáo browser](../backend/private_data/verification/browser-smoke.json).
- [Gợi ý đồng thuận](../backend/private_data/verification/hitl-consensus.png).
- [HITL 360px](../backend/private_data/verification/hitl-workspace-360.png),
  [768px](../backend/private_data/verification/hitl-workspace-768.png),
  [1366px](../backend/private_data/verification/hitl-workspace-1366.png).

Đã kiểm các luồng trên trang chính, không dùng popup quyết định:

- Đồng thuận tự hiện gợi ý với exposure đúng Prediction ID, không tự chọn/lưu nhãn hoặc chạy inference.
- Dùng gợi ý chỉ điền bản nháp; người duyệt có thể sửa cả khi hai model cùng sai.
- Chưa chọn nhãn: báo lỗi và giữ mẫu; Lưu giữ nguyên mẫu và đọc lại sau reload;
  Lưu & tiếp tục chỉ chuyển sau khi lưu thành công.
- Bất đồng giữ bước chọn độc lập; thiếu/lỗi nhánh không hiển thị đồng thuận giả.
- Reload và qua lại trang nhãn giữ đúng bình luận, nhãn, note và spans; spans tiếp tục được giữ
  qua bước lưu độc lập và được xác minh trong dữ liệu xuất sau xác nhận.
- Ba test API bổ sung kiểm metadata nguồn/tác giả và Unicode tokens, lưu/bảo toàn/xóa spans
  có chủ ý, từ chối offsets hoặc nhãn spans sai/ngừng dùng mà không ghi annotation.
- Không tràn ngang ở 360/768/1366px. Luồng giám sát/duyệt phản hồi, kiểm tra mù theo ngân sách,
  phân xử người thứ ba và xuất nhãn người tiếp tục qua kiểm thử.

Lượt đầu phát hiện spans bản nháp mất qua bước lưu độc lập; đã sửa và chạy lại toàn bộ.
Các kết quả model/API trong tình huống browser là fixture/mock, không phải thực nghiệm thật.
Không gọi API thương mại hoặc chạy lại Transformer lớn; không thay database PostgreSQL làm việc.
Các mục dưới giữ kết quả lịch sử của những đợt trước.

## Quản lý nhãn riêng theo dự án — 15/11/2026

Lượt hồi quy cuối: **121 tests, OK**, 35,268 giây; bao gồm hai test Chromium.
9 test API mới và browser test trang nhãn kiểm tra CRUD/reload, revision, bảo vệ lịch sử,
phân quyền, cùng mã ở hai dự án, giữ bản nháp manual và cặp HITL sau khi thay đổi bộ nhãn.
Các số 111/107 phía dưới là kết quả lịch sử của các đợt trước.

- [Log Django](../backend/private_data/verification/django-label-management.log).
- [Browser report](../backend/private_data/verification/label-management-browser.json).
- [Ảnh 360px](../backend/private_data/verification/label-management-360.png),
  [768px](../backend/private_data/verification/label-management-768.png),
  [1366px](../backend/private_data/verification/label-management-1366.png).

Chromium chạy HTTP frontend/backend thật trên SQLite cách ly, có reload ở cả trang quản lý
và workspace. Đã kiểm lựa chọn/note/spans giữ nguyên; tắt nhãn làm bản nháp không hợp lệ
nhưng không xóa nội dung; kích hoạt lại khôi phục khả năng lưu. Gợi ý AI đóng băng không
được diễn giải lại khi thêm nhãn; quyết định người có schema riêng. Lỗi 409 giữ nội dung form.
Reader không có nút thay đổi và API từ chối POST; dự án khác không xem/sửa nhãn dự án này.
Ở ba chiều rộng không tràn ngang; ảnh được chụp sau khi sidebar hoàn tất transition.

Build từ frontend/src đã chạy; `npm run check` qua **64 module source/build**,
`npm run test:exports` qua **16 converter**, migration dry-run không thiếu thay đổi.
Migration `studio.0010_projectlabel_revision` được chạy trong database test, chưa áp dụng
vào PostgreSQL làm việc. Không có model/API inference thật hoặc human study mới trong đợt này.
Hướng dẫn chạy: [LABEL_MANAGEMENT_VI.md](LABEL_MANAGEMENT_VI.md).

## Kiểm tra bổ sung Human-in-the-loop

Lượt cuối sau khi nối router và luồng thao tác: **111 tests, OK**, 23,693 giây,
gồm browser smoke test chạy HTTP Django thật. [Log HITL](../backend/private_data/verification/django-hitl.log).
Các dòng 107 tests bên dưới là kết quả đợt trước, không bao gồm phần nối đầy đủ này.

Đã kiểm bằng Chromium:

- Menu chính `#human-review` và `#manual-annotation` hiện và mở được.
- Chạy tự động với checkbox HITL mặc định tạo run và chuyển sang đúng hàng đợi người duyệt.
- Gợi ý → lựa chọn độc lập khi bất đồng → xem gợi ý → xác nhận/sửa; hai model cùng sai vẫn sửa được.
- Quản lý xem/duyệt phản hồi; giám sát không tự tạo thêm annotation.
- Gán nhãn thủ công: chọn lớp chưa ghi DB; chỉ lưu sau nút Lưu & tiếp tục.
- Xuất scope human chứa nhãn đã sửa và nhãn thủ công, không thay bằng dự đoán máy.
- Pause/resume, kiểm tra mù và phân xử người thứ ba vẫn chạy; không có page error.

Test API bổ sung chặn giám sát khi đang mù, loại người đã xem nhãn khỏi kiểm tra độc lập,
thể hiện phản hồi cần duyệt lại khi quyết định đổi revision, và tách run HITL khỏi danh sách tự gán cũ.
Frontend build/check 60 module và 16 converter vẫn qua. Không phát sinh migration mới trong phần nối HITL.
Các hạn chế về model/API thật, PostgreSQL concurrency và human study ở phần dưới vẫn giữ nguyên.

## Kết quả đợt M1–M3, 14/11/2026

Base `5e24ba55ad200bef45246f56f6f8d37d09ac9e8c`, branch `feat/code-update-20261114`.

| Kiểm tra thực chạy | Kết quả |
|---|---|
| `manage.py test tests --settings=config.settings_test --noinput --verbosity 1`, có cấu hình Playwright | **107 tests, OK**, 16,323 giây ở lượt cuối; gồm 86 test cũ, 20 regression/API/model/migration mới và 1 browser smoke test. |
| `manage.py makemigrations --check --dry-run --settings=config.settings_test` | Không thiếu migration. |
| `manage.py check --settings=config.settings_test` | Không có lỗi system check. |
| `python scripts/build_frontend.py` | Build thành công từ frontend/src sang dist; thông báo console tương thích Windows cp1258. |
| `npm run check` | Syntax và relative import targets của **60 module source/build** qua. |
| `npm run test:exports` | 16 converter sinh output, fixture Unicode/BIO qua. |
| `python -m pip check` | Không có dependency bị hỏng. |
| `git -c core.whitespace=cr-at-eol diff --check` | Qua; có thông báo chuẩn hóa LF/CRLF của Git Windows, không thay cấu hình Git. |

Browser test chạy Chromium headless với Django test server và database SQLite cách ly,
không mock HTTP frontend/backend. API model trong dữ liệu demo là mock cố định;
sklearn train artifact thực từ dữ liệu tổng hợp. Đã chạy các thao tác đồng thuận,
preliminary trước exposure khi bất đồng, người sửa hai model cùng sai, API lỗi,
review mù, pause/resume và người thứ ba phân xử. `pageErrors=[]`.

Bằng chứng local (ignored, không publish dữ liệu runtime):

- [Log toàn bộ test](../backend/private_data/verification/django-final.log).
- [Browser summary](../backend/private_data/verification/browser-smoke.json).
- [Ảnh màn hình phối hợp](../backend/private_data/verification/collaboration.png).
- [Ảnh màn hình ngân sách](../backend/private_data/verification/budget.png).

Lệnh browser ở máy kiểm tra:

```powershell
$env:ANNOTAFLOW_PLAYWRIGHT_MODULE = 'C:\Users\taitr\AppData\Local\npm-cache\_npx\e41f203b7505f1fb\node_modules\playwright'
$env:ANNOTAFLOW_BROWSER_EXECUTABLE = 'C:\Users\taitr\AppData\Local\ms-playwright\chromium_headless_shell-1223\chrome-headless-shell-win64\chrome-headless-shell.exe'
.venv\Scripts\python.exe backend\manage.py test tests --settings=config.settings_test --noinput --verbosity 1
```

Playwright package thực dùng 1.65.1; executable Chromium đã có trên máy được chỉ định rõ,
không tải browser hoặc checkpoint lớn. Trên máy khác thay hai đường dẫn bằng cài đặt tương ứng.
Nếu không đặt `ANNOTAFLOW_PLAYWRIGHT_MODULE`, bộ test vẫn chạy phần backend và báo skip
browser, không được mô tả là đã chạy browser. Không có dev dependency Node bắt buộc cho runtime web.

Các lượt kiểm tra đầu có lỗi đã được sửa: sandbox chặn Temp/child process (đã chạy lại với
quyền phù hợp), ký tự console Windows trong build, chốt test sau feedback prompt và
điều kiện chờ bất đồng bộ của smoke test. Chỉ lấy lượt cuối OK làm kết quả.
Test log có warning staticfiles chưa collect và deprecation multiclass liblinear của
dependency hiện cài; không phải lỗi test. Log `Job ... failed (ValueError)` là tình huống
lỗi được test chủ động kiểm tra, không phải kết quả API thất bại bị che.

**Chưa chạy thật trong đợt này:** API thương mại/Ollama, suy luận lại Transformer lớn,
human study, PostgreSQL/Redis/Celery concurrency hoặc production load. Migration đã
kiểm tra nâng từ dữ liệu cũ trong test; database PostgreSQL làm việc của người dùng chưa bị sửa.
Xem [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), [DEMO_SCRIPT_VI.md](DEMO_SCRIPT_VI.md)
và [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md). Các mục phía dưới giữ lịch sử bàn giao cũ.

Ngày tạo bản dựng: 24–25/10/2026 (UTC và giờ Việt Nam).

## Kiểm tra bổ sung trên Windows ngày 25/10/2026

- Đã tạo database PostgreSQL 18.6 UTF-8 trong `backend/private_data/postgres18` với provider `builtin`, locale `C.UTF-8`, các mục `LC_*` là `C` và múi giờ UTC sau khi installer gặp lỗi encoding.
- Đã chạy toàn bộ migrations và seed demo trên PostgreSQL thật; kiểm tra cả ba tài khoản demo, đăng nhập HTTP và tải workspace thành công.
- Trang chủ, JavaScript và CSS trả HTTP 200; truy vấn tiếng Việt qua database giữ nguyên nội dung.
- Đã dừng database và kiểm tra helper khởi động lại thành công, kết nối được bằng tài khoản ứng dụng. Native startup ưu tiên `.env.local` để tránh biến `DEBUG` của terminal làm mất tài nguyên giao diện.
- Các kết quả bên dưới ghi nhận bản dựng ban đầu; kiểm tra bổ sung này không thay thế toàn bộ integration tests hoặc thử tải production.

## Đã chạy

- **56 kiểm thử backend** qua trên profile SQLite **chỉ dành cho test**: tài khoản/CSRF/quyền dự án, nghiên cứu mù/người thứ ba/ngân sách, Unicode spans, optimistic revision, redundancy, skip/undo, sticky AI exposure, khóa dự án, nhãn chỉ dùng trong spans, đồng thuận/gold, phiên bản/backup/null gold/monotonic revision, 16 exports/XLSX, mã hóa key, endpoint allowlist, mocked Ollama, invitation/revoke/email/reset, real local prediction job không Redis, pin cấu hình, mocked YouTube resume giữa reply page và thay đổi khóa khi request đang chạy.
- Pipeline train thật cho cả 3 thuật toán; test bổ sung train đủ 3 lớp cho mỗi thuật toán.
- Seed dữ liệu idempotent và đăng ký 3 model theo dự án; tạo mới không ghi đè password cũ.
- Bộ model hiện tại: PhoBERT-base, XLM-R base và XLM-R large từ ZIP ViHOS. Kiểm tra nạp trọng số và suy luận thật bằng `import_transformers --verify`; điểm test là báo cáo được cung cấp, chưa đo lại.
- 16 browser export converters sinh được output; Unicode/partial-token BIO đúng fixture; XLSX của browser được đọc lại bằng openpyxl, đủ 3 sheets.
- Django system check không có lỗi; migration check không thiếu thay đổi; Python compile, JS syntax và pip check qua.
- Windows CPython 3.12 x86_64 dependency resolution được kiểm tra bằng pip dry-run/only-binary; không cần biên dịch scientific packages bằng C trên máy Windows.
- Compose YAML được parse/kiểm tra: PostgreSQL 15, Redis, web/worker, worker chờ web healthy, cổng web localhost. Không chạy daemon.
- Browser QA: mở login/demo, chuyển vai, tạo/chuyển dự án, lưu cấu hình, chọn model, dự đoán câu mới, hiển thị đánh giá, chọn token/span, lưu nhãn và chuyển mẫu. Ảnh giao diện từ trình duyệt được giữ làm bằng chứng phiên làm việc; không phải kết quả human study.

## Chưa chạy

- Không có PostgreSQL 15 hoặc Docker daemon hoạt động trong môi trường tạo bản dựng. Chưa kiểm tra transaction/concurrency trên PostgreSQL thật. CI PostgreSQL 15 đã cấu hình, **chưa có kết quả workflow chạy**.
- Chưa thực thi installer trên Windows thật. Dry-run package resolution không thay thế thử toàn bộ startup PostgreSQL/migrations/threads trên Windows.
- Chưa gọi Gemini/Ollama/OpenAI-compatible/YouTube thật bằng tài khoản có khóa, chưa kiểm tra quota/phí/provider model ID. API tests dùng mocks. Email dùng local backend; SMTP chưa gửi thật.
- Chưa thử tải production, nhiều worker tranh chấp, thiết bị di động thật, backup PostgreSQL/restore máy mới hoặc human study độc lập.
- Bản Site online chỉ host static demo. Dữ liệu demo lưu trong browser; không có PostgreSQL/backend/API host kèm. Source native/Docker là bản backend để nhóm tự chạy.

## Lệnh kiểm tra lại

Từ thư mục backend:

```bash
python manage.py test tests --settings=config.settings_test
python manage.py makemigrations --check --dry-run --settings=config.settings_test
```

Từ root:

```bash
python scripts/build_frontend.py
node scripts/check_exports.mjs
npm run check
```

Node chỉ dùng cho kiểm tra cú pháp/converter, không bắt buộc để build hoặc chạy web.

Sau khi có PostgreSQL thật: dùng cấu hình development riêng và `python manage.py test tests` không dùng settings_test; role test cần quyền tạo test database. Thử multi-user cùng sửa 1 record, hủy/tiếp tục job đang gọi API, restart server, khóa và thu hồi quyền giữa job, sau đó kiểm tra dữ liệu/history.
