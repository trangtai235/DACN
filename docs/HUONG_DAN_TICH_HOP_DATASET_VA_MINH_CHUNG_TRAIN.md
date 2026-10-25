# Tích hợp dataset, mã train và hồ sơ đối chiếu 3 model

## 1. Kết luận sau khi kiểm tra ba ZIP

Các kết luận dưới đây dựa trên đọc và băm file thực tế, không dựa riêng vào lời
khẳng định trong các tài liệu đính kèm.

| File gửi vào | Đã kiểm tra thấy gì | Dùng cho việc gì |
|---|---|---|
| `1 - DU LIEU TRUOC KHI TRAIN.zip` | 5 CSV, 3 script Python, notebook Colab và hai tài liệu thông tin/lệnh | Nguồn dữ liệu và mã train |
| `datasets.zip` | 5 CSV giống từng byte với CSV ở ZIP thứ nhất | Một bản dataset; không cần giữ hai bản trùng |
| `2 - KET QUA SAU KHI TRAIN.zip` | Báo cáo, metrics và config của ba model | Đối chiếu kết quả được cung cấp; không chứa trọng số |

Đã xác minh:

- Dataset: 8.844 câu train, 1.106 dev, 1.106 test. Test có 1.266 span độc hại.
- Notebook có 13 ô code, 0 ô có `execution_count`, 0 output được lưu.
- Hai file code nhúng trong notebook khớp script rời sau khi bỏ khoảng trắng
  đầu/cuối; các bản rời được nhập giữ nguyên byte.
- Metrics và config của cả 3 model giống từng byte với bản ứng dụng đang dùng.
- Hash trọng số đang cài khớp tiền tố SHA-256 trong hồ sơ được cung cấp:

| Model | Tiền tố SHA-256 trọng số đã kiểm tra |
|---|---|
| PhoBERT-base | `23fe96ca2b2a87f7d9e101a460918f6c` |
| XLM-R base | `94d1d9920cd479d8b61765aa5a5278ad` |
| XLM-R large | `52d105d542a29ccb5a51cdd6a16a0b58` |

**Có thể kết luận:** Dataset, mã train và bộ báo cáo được cung cấp đã được tập
hợp vào source; báo cáo/config/trọng số của website khớp các tệp được đối chiếu.

**Chưa thể kết luận:** Ba trọng số cũ đã được train trên máy này hoặc từ commit
hiện tại. Metrics không có hash dataset, commit huấn luyện và thời gian chạy;
notebook không có output. Chép file hoặc tạo manifest hôm nay không tạo lại được
bằng chứng quá khứ. Nếu cần chứng minh một lần train từ đúng source hiện tại,
cần thực sự chạy train và giữ bằng chứng của lần chạy mới.

## 2. Các thư mục đã bổ sung vào dự án

Đã đặt vào đúng vị trí sau; không cần giải nén đè lần nữa:

```text
AnnotaFlow/
├── datasets/
│   └── ViHOS/
│       ├── README.md
│       └── data/
│           ├── Sequence_labeling_based_version/
│           │   ├── Syllable/
│           │   │   ├── train_BIO_syllable.csv
│           │   │   └── dev_BIO_syllable.csv
│           │   └── Word/
│           │       ├── train_BIO_Word.csv
│           │       └── dev_BIO_Word.csv
│           └── Test_data/
│               └── test.csv
├── training/
│   ├── README.md
│   ├── vihos/
│   │   ├── train_vihos.py
│   │   ├── vihos_data.py
│   │   └── eval_model.py
│   ├── configs/
│   │   └── three_models.json
│   ├── provenance/
│   │   └── import_manifest.json
│   ├── evidence/
│   │   ├── imported/
│   │   │   ├── before/
│   │   │   │   ├── THONG TIN DU LIEU.txt
│   │   │   │   └── LENH TRAIN.txt
│   │   │   └── after/
│   │   │       ├── metrics/{phobert-base,xlmr-base,xlmr-large}.json
│   │   │       ├── config/{phobert-base,xlmr-base,xlmr-large}.json
│   │   │       └── Các báo cáo DOCX/XLSX/JSON/TXT/MD nguyên bản
│   │   └── runs/                  Sinh khi chạy thực tế, chưa phải dữ liệu có sẵn
│   ├── runs/                      Model đầu ra của lần train mới, chưa được train
│   └── run_experiment.py
├── notebooks/
│   └── training/
│       └── Colab - Train ViHOS.ipynb
├── scripts/
│   └── verify_training_bundle.py
├── backend/artifacts/transformers/vihos-full/
│   ├── phobert-base/              Model website đang dùng, giữ nguyên
│   ├── xlmr-base/
│   └── xlmr-large/
└── .gitattributes                 Giữ nguyên line ending/byte của bản gốc
```

### Bảng chép từ đâu sang đâu

| Đường dẫn trong ZIP | Vị trí trong source |
|---|---|
| `datasets/data/...` | `datasets/ViHOS/data/...` |
| `code/train_vihos.py` | `training/vihos/train_vihos.py` |
| `code/vihos_data.py` | `training/vihos/vihos_data.py` |
| `code/eval_model.py` | `training/vihos/eval_model.py` |
| `notebooks/Colab - Train ViHOS.ipynb` | `notebooks/training/Colab - Train ViHOS.ipynb` |
| Hai TXT của ZIP trước train | `training/evidence/imported/before/` |
| Toàn bộ ZIP sau train | `training/evidence/imported/after/` |

Trong ZIP, CSV nằm ở `datasets/data`; lệnh trong tài liệu lại ghi
`datasets/ViHOS`. Việc thêm cấp `ViHOS` ở đây giải quyết khác biệt đường dẫn.
Không tạo nhầm `datasets/ViHOS/datasets/data/...`.

Không bỏ CSV BIO vào `backend/private_data/postgres18/`. PostgreSQL chứa dữ liệu
ứng dụng; dataset train là các file độc lập. Không cần import BIO vào màn hình
nhập bình luận của website để chạy trainer.

## 3. Ý nghĩa các file cần trình bày

| File/thư mục | Thể hiện điều gì |
|---|---|
| CSV train/dev/test | Dữ liệu đầu vào và cách chia tập |
| `training/vihos/train_vihos.py` | Thuật toán train, tokenizer, optimizer, scheduler, chọn best checkpoint |
| `training/vihos/vihos_data.py` | Đọc BIO, căn chỉnh và cách tính span F1 |
| `training/vihos/eval_model.py` | Chấm lại model trên test và xuất kết quả |
| `training/configs/three_models.json` | Tham số sẽ truyền cho ba lần chạy theo hồ sơ được cung cấp |
| `training/provenance/import_manifest.json` | Hash file và ghi nhận việc nhập tài liệu, không phải log train |
| `training/evidence/imported/after/metrics/` | Báo cáo cũ; đối chiếu với báo cáo của website |
| Notebook nguyên bản | Mã/thao tác Colab được cung cấp, chưa có output chạy |
| `training/evidence/runs/<id>/` | Log, manifest và báo cáo của lần thực thi mới |
| `training/runs/<id>/model/` | Trọng số và tokenizer thật được sinh sau khi train xong |

`.gitattributes` giữ nguyên byte các CSV, script gốc, notebook và báo cáo nhập.
Nếu Git đổi LF/CRLF khi checkout, hash có thể đổi dù nội dung nhìn tương tự;
do đó cần giữ file này khi chia sẻ source giữa Windows và Linux/Colab.

## 4. Kiểm tra ngay trên máy, chưa cần train

Mở terminal PowerShell tại thư mục dự án:

```powershell
cd C:\Users\taitr\Downloads\AnnotaFlow
```

### 4.1. Xác minh các file

```powershell
.venv/Scripts/python.exe -X utf8 scripts/verify_training_bundle.py
```

Kiểm tra thêm hash trọng số hiện tại (đọc khoảng 3,9 GB từ ổ đĩa):

```powershell
.venv/Scripts/python.exe -X utf8 scripts/verify_training_bundle.py --weights
```

Kết quả `OK` xác nhận file khớp bản đã nhập hoặc hash được đối chiếu. Nó không
xác nhận ai đã chạy train hoặc train ở máy nào. Nếu chưa cài trọng số, phần
website sẽ được báo `SKIP`; các file nhập vẫn được kiểm tra.

### 4.2. Kiểm tra dataset bằng chính mã gốc

```powershell
.venv/Scripts/python.exe -X utf8 training/vihos/train_vihos.py --check-data --data-root datasets/ViHOS
```

Đã chạy kiểm tra này với dữ liệu được nhập và thấy đủ 8.844/1.106/1.106 câu.
Mã `load_all()` đọc cả năm CSV, nên vẫn phải giữ thư mục `Word` dù các cấu hình
đối chiếu ba model đang dùng `--variant syllable`.

Lần kiểm tra hiện tại ghi nhận `torch 2.14.1+cpu`, `transformers 5.20.2`,
`cuda: False`. Đây là môi trường PyTorch CPU hiện tại; không suy ra máy vật lý
chắc chắn không có GPU. Để dùng GPU cần môi trường PyTorch/CUDA phù hợp.

### 4.3. Xem trước lệnh sẽ chạy

```powershell
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model phobert-base --dry-run
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model xlmr-base --dry-run
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model xlmr-large --dry-run
```

`--dry-run` chỉ in lệnh, không tải model, không train và không tạo bằng chứng
chạy thực tế. Không sử dụng output dry-run làm minh chứng đã huấn luyện.

## 5. Chốt source bằng Git trước lần train mới

Đây là bước gắn một lần chạy với đúng phiên bản mã nguồn. Tại terminal dự án:

```powershell
git branch --show-current
git add .gitattributes .gitignore datasets/ViHOS training notebooks/training scripts/verify_training_bundle.py docs/HUONG_DAN_TICH_HOP_DATASET_VA_MINH_CHUNG_TRAIN.md
git diff --cached --stat
git commit -m "Bo sung dataset ViHOS va pipeline huan luyen ba model"
git rev-parse HEAD
```

Ghi lại commit hiển thị. Nếu chia sẻ lên nhánh hiện tại:

```powershell
git push origin huong-moi
```

Wrapper mặc định từ chối khi các file code/dataset/cấu hình cần thiết chưa được
commit hoặc đã thay đổi sau commit. `--allow-dirty` chỉ dành cho thử nghiệm có
ghi rõ source chưa chốt; không dùng chế độ đó để khẳng định một commit sạch.

Các file Word/Markdown phân tích hệ thống tạo trước đó là tài liệu riêng, có
thể commit thêm nếu muốn. Không thêm `.env.local`, database hoặc `.venv` vào Git.

## 6. Chạy train thật và lưu bằng chứng tự động

Các lệnh sau **thực sự huấn luyện**, có thể tải model gốc từ Hugging Face, cần
RAM/VRAM và thời gian đáng kể. Hiện chưa tự chạy các lệnh này. Bản CPU có thể
rất chậm với XLM-R large; không cam kết thời lượng trong các TXT là thời gian
đã đo trên máy hiện tại.

Nếu còn thiếu thư viện, dùng môi trường Python phù hợp và cài theo
`requirements/transformers.txt`; khi dùng GPU, kiểm tra lại
`torch.cuda.is_available()` trước khi chạy. Phiên bản thư viện thực tế sẽ được
ghi trong manifest của lần chạy.

### 6.1. PhoBERT-base

```powershell
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model phobert-base
```

Tham số: `vinai/phobert-base`, syllable, 5 epoch, batch 32, learning rate
`2e-5`, gradient accumulation 1, max length 128, seed 42, có chấm test.

### 6.2. XLM-R base

```powershell
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model xlmr-base
```

Tham số: `xlm-roberta-base`, syllable, 5 epoch, batch 16, learning rate
`3e-5`, gradient accumulation 1, max length 128, seed 42, có chấm test.

### 6.3. XLM-R large

```powershell
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model xlmr-large
```

Tham số: `xlm-roberta-large`, syllable, 4 epoch, batch 8, learning rate
`1e-5`, gradient accumulation 2, max length 128, seed 42, có chấm test.

Chạy tuần tự từng lệnh, không đồng thời cả ba trên môi trường RAM/VRAM hạn chế.
Các tham số trên được lấy từ lệnh/tài liệu được cung cấp và giá trị mặc định
trong mã; metadata cũ không ghi đầy đủ mọi tham số để xác minh lịch sử.

### 6.4. Đầu ra của một lần chạy mới

```text
training/evidence/runs/<run-id>/
  manifest.json     Commit, hash code/data, tham số, môi trường, thiết bị,
                    thời gian thực thi, exit code và hash đầu ra
  process.log       Output thật của tiến trình train/evaluate
  metrics.json      Bản sao metrics của lần train nếu được sinh ra

training/runs/<run-id>/model/
  model.safetensors
  config.json
  metrics.json
  tokenizer files...
```

`manifest.json` phân biệt `mode=train`, `mode=smoke`, `mode=evaluate` và trạng
thái completed/failed/interrupted. Wrapper kiểm tra hash code/dataset trước và
sau tiến trình để nhận diện thay đổi giữa lúc chạy. Khi full train hoàn tất
đủ 8.844 câu và input không đổi, `full_data_training_complete` mới là `true`.

Đây là hồ sơ kiểm chứng được theo file/commit, không phải chứng thực chống mọi
khả năng sửa tay. Giữ log/notebook chạy thực tế, commit và checkpoint gốc để
bằng chứng thuyết phục hơn. Không đổi ngày file hay chép log cũ thành log mới.

Model đầu ra nằm ở thư mục mới, không ghi đè ba model website đang sử dụng.
Sau khi có ba run hoàn tất, có thể commit bằng chứng nhẹ:

```powershell
git add training/evidence/runs
git commit -m "Luu log va manifest cac lan huan luyen thuc te"
```

`.gitignore` bỏ qua `training/runs/` để không đẩy trọng số lớn lên Git, nhưng
cho phép log của `training/evidence/runs/`. Lưu trọng số trên nơi bàn giao
riêng và giữ hash để đối chiếu.

## 7. Chạy thử và chấm lại: hai việc khác với full train

### Smoke test pipeline

```powershell
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model xlmr-base --mode smoke
```

Mã gốc chỉ dùng 300 câu train, tối đa 200 câu dev và 1 epoch ở chế độ này.
Nó tạo trọng số thử riêng, không thay website. Đây là minh chứng pipeline
chạy được, không chứng minh đã full train cả ba model trên toàn dataset.

### Đánh giá lại trọng số hiện tại

```powershell
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model phobert-base --mode evaluate
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model xlmr-base --mode evaluate
.venv/Scripts/python.exe -X utf8 training/run_experiment.py --model xlmr-large --mode evaluate
```

Các lệnh evaluate dùng model hiện tại, không train, không thay trọng số và ghi
`evaluation.json` riêng. Kết quả mới phải được giữ riêng với `metrics.json`
cũ. Khác phiên bản thư viện, thiết bị, độ chính xác số hoặc giao thức tokenizer
có thể làm điểm khác; không chỉnh số mới để ép bằng báo cáo cũ.

`eval_model.py` dùng giao thức của bộ code được cung cấp, mặc định max length
160. Adapter trên website xử lý bình luận dài bằng cửa sổ; không xem lượt gán
nhãn website trên dữ liệu mới là phép chấm lại cùng điều kiện trên test ViHOS.

## 8. Nếu train bằng Colab

Để chứng minh chạy từ source này, cách rõ ràng là push commit đã chốt, clone
repo trên Colab, checkout đúng commit rồi chạy `training/run_experiment.py`
với cùng dataset trong repo. Lưu notebook có output thực thi và thư mục
`training/evidence/runs/<run-id>/` về cùng checkpoint.

Notebook nguyên bản hiện được giữ để tham khảo, nhưng các ô `%%writefile`
và tải dataset từ nhánh `master` không tự gắn với Git commit của website.
Nếu dùng các ô đó phải đối chiếu lại hash code/data. Không đổi các ô Colab
chưa chạy thành output giả.

Train trên Colab có thể chứng minh dùng cùng code/dataset/commit nếu ghi nhận
đầy đủ; không được gọi đó là huấn luyện trên máy Windows này. Nếu yêu cầu
bắt buộc là “train trên máy này”, phải có lần train thực sự trên máy này.

## 9. Liên kết model mới với website

Đối với trọng số cũ, việc đối chiếu đã xác nhận chúng khớp hồ sơ được cung cấp;
không cần sao chép lại hay sửa database chỉ để thêm dataset.

Nếu muốn đưa **model của lần train mới** vào website sau khi train xong:

1. Kiểm tra manifest ở trạng thái hoàn tất và lưu hash đầu ra.
2. Dừng server/tác vụ trước khi thay trọng số đang dùng.
3. Sao lưu thư mục model hiện tại sang nơi lưu artifact riêng.
4. Chép đủ trọng số, config, tokenizer và metrics của output mới vào đúng
   thư mục `backend/artifacts/transformers/vihos-full/<model-key>/`.
5. Không giữ `verified.json` cũ làm bằng chứng cho trọng số mới. Chạy xác minh
   lại bằng lệnh sau; lệnh sẽ sinh marker mới sau khi suy luận thành công:

```powershell
$env:ANNOTAFLOW_ENV_FILE = Join-Path (Get-Location) '.env.local'
.venv/Scripts/python.exe -X utf8 backend/manage.py import_transformers --verify
```

6. Đối chiếu hash `model.safetensors` của model website với hash output trong
   manifest của run mới, ghi lại run nào đã được triển khai rồi khởi động lại.
7. Báo cáo kiểm tra với bộ nhập cũ có thể báo khác hash/metrics sau khi thay
   bằng model mới; đây là hai phiên bản artifact khác nhau, không sửa manifest
   nhập cũ để che khác biệt.

Các bước thay model chưa được tự thực hiện trong lần tích hợp tài liệu này.

## 10. Các điểm phải sửa trong cách trình bày minh chứng

- Một số báo cáo nhập vẫn ghi tên AnnotaHub. Chúng được giữ nguyên như tài liệu
  nguồn, không đổi tiêu đề để suy ra đã train từ source AnnotaFlow hiện tại.
- Không dùng câu trong báo cáo cũ rằng số liệu epoch “không thể bịa ra” như
  một chứng minh kỹ thuật. JSON/bảng có thể được sửa; cần log, commit, hash và
  quá trình chạy thật để đối chiếu.
- Mã gốc chọn `best_state` theo dev F1 nhưng ghi `dev_best = history[-1]['dev']`.
  Với PhoBERT và XLM-R large, `dev_best` là dev của epoch cuối, không nhất thiết
  là dev của checkpoint tốt nhất. Dùng `best_dev_span_f1_partial` và `history`
  để tìm epoch tốt nhất. Bản code nhập được giữ nguyên; sửa lỗi nên có commit
  riêng và phải ghi rõ đó là phiên bản mới.
- Số `grad_accum` và `max_len` không có đầy đủ trong metrics cũ; cấu hình mới
  ghi rõ tham số sẽ chạy, không giả định đó là chứng cứ lịch sử.
- Script gốc không khóa revision của model nền trên Hugging Face; muốn tái lập
  nghiêm ngặt hơn cần ghi/pin thêm revision và môi trường. Cùng seed không bảo
  đảm mọi thiết bị/phiên bản cho kết quả giống từng bit.
- F1 trong bộ báo cáo là F1 span, không phải accuracy phân loại câu của website.
- Dữ liệu YouTube đã nhập trong PostgreSQL và dataset ViHOS phục vụ train là
  hai tập khác nhau, không gọi dữ liệu ứng dụng là dataset train gốc.

## 11. Khi trình bày, mở file nào theo thứ tự nào?

1. `datasets/ViHOS/data/Sequence_labeling_based_version/Syllable/train_BIO_syllable.csv`:
   cho xem các cột Word/Tag/sentence_id và ví dụ BIO.
2. `training/vihos/vihos_data.py`: giải thích cách ghép token theo câu và span.
3. `training/vihos/train_vihos.py`: giải thích train/dev, optimizer và chọn best.
4. `training/configs/three_models.json`: cho xem tham số của từng model.
5. Chạy `verify_training_bundle.py --weights`: đối chiếu dữ liệu/mã/báo cáo và
   trọng số đang được website nạp.
6. Nếu có lần train mới, mở `training/evidence/runs/<run-id>/manifest.json`,
   `process.log`, `metrics.json`, commit tương ứng và checkpoint.
7. Mở website Mô hình & API, rồi gán nhãn thử để thể hiện phần triển khai.

Cách mô tả đúng với hồ sơ hiện có:

> Source đã tích hợp dataset ViHOS, mã huấn luyện và cấu hình của ba model.
> Trọng số và báo cáo đang dùng khớp bộ được cung cấp. Các lần chạy mới sẽ lưu
> commit, hash dữ liệu/mã, thiết bị và log để chứng minh quá trình thực thi.

Chỉ sau khi có đủ bằng chứng thực tế mới bổ sung “đã full train ba model từ
commit X trên môi trường Y”.
