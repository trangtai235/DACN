# MINH CHỨNG HUẤN LUYỆN MÔ HÌNH

**Đề tài:** AnnotaHub — nền tảng gán nhãn bình luận YouTube có trợ giúp mô hình

**Nội dung:** Hồ sơ chứng minh 3 mô hình đã huấn luyện bằng bộ dữ liệu và mã nguồn nào.

---

## 1. BẰNG CHỨNG 1 — BỘ DỮ LIỆU

| Thông tin | Giá trị |
|---|---|
| Tên bộ dữ liệu | **ViHOS** — Vietnamese Hate and Offensive Spans |
| Nguồn | Bộ dữ liệu công khai kèm bài báo khoa học ViHOS |
| Ngôn ngữ | Tiếng Việt |
| Bài toán | Nhận diện **cụm từ độc hại** (span detection) |
| Số câu train | **8.844** |
| Số câu dev | **1.106** |
| Số câu test | **1.106** |
| Tổng số cụm độc hại trong test | **1.266** |

### Dấu vân tay SHA-256 từng file dữ liệu

| File | Dung lượng | SHA-256 (32 ký tự đầu) |
|---|---:|---|
| `train_BIO_syllable.csv` | 2,803,673 byte | `036ef6afa5efbe1dc0a0826e4c41e512` |
| `dev_BIO_syllable.csv` | 323,710 byte | `70406f825964ec73bb2e52b430e6807f` |
| `train_BIO_Word.csv` | 2,717,454 byte | `e7c0242d526b7303bb2acd898ba12470` |
| `dev_BIO_Word.csv` | 314,759 byte | `e9346bcdf40a834b9647aa2f14cdb44c` |
| `test.csv` | 121,774 byte | `0c8d09f1e9d649ac206619a717610e80` |

> **SHA-256 là gì?** Là "dấu vân tay" của file. Chỉ cần băm lại file là biết
> có đúng file gốc hay không. Không thể sửa file mà giữ nguyên dấu vân tay.

### Cấu trúc file nhãn

| Cột | Nghĩa |
|---|---|
| `Word` | âm tiết tiếng Việt đã tách |
| `Tag` | nhãn BIO của âm tiết đó |
| `sentence_id` | câu thứ mấy |

**Bộ nhãn: 1 loại — `TOXIC`, viết dưới 3 tag BIO:**

| Tag | Nghĩa |
|---|---|
| `O` | không độc hại (**O**utside) |
| `B-T` | bắt đầu cụm độc hại (**B**egin–**T**oxic) |
| `I-T` | trong cụm độc hại (**I**nside–**T**oxic) |

---

## 2. BẰNG CHỨNG 2 — MÃ NGUỒN HUẤN LUYỆN

| File | Vai trò | Dung lượng | SHA-256 (32 ký tự đầu) |
|---|---|---:|---|
| `train_vihos.py` | script huấn luyện chính | 24,627 byte | `fa326834404e2779627d3b1e4c630f3e` |
| `vihos_data.py` | đọc và xử lý dữ liệu ViHOS | 7,251 byte | `34cc8471e1c83ea9030c40ea34e4b091` |
| `eval_model.py` | chấm điểm trên tập test | 13,388 byte | `9d8724b6dcc5b52e2c99f23fc0c0946f` |

### Lệnh huấn luyện đã dùng (ghi trong đầu file `train_vihos.py`)

```bash
# XLM-R base
python train_vihos.py --variant syllable --model xlm-roberta-base \
  --epochs 5 --batch-size 16 --lr 3e-5 --test --out models/xlmr-base

# XLM-R large
python train_vihos.py --variant syllable --model xlm-roberta-large \
  --epochs 4 --batch-size 8 --lr 1e-5 --grad-accum 2 --test --out models/xlmr-large

# PhoBERT base
python train_vihos.py --variant syllable --model vinai/phobert-base \
  --epochs 5 --batch-size 32 --lr 2e-5 --out models/phobert-base
```

---

## 3. BẰNG CHỨNG 3 — SIÊU THAM SỐ (ghi trong `metrics.json`)

| Mô hình | Mô hình gốc | epoch | batch | learning rate | grad-accum | seed | câu train |
|---|---|---:|---:|---:|---:|---:|---:|
| **XLM-R large** | `xlm-roberta-large` | 4 | 8 | 1e-05 | — | 42 | 8,844 |
| **XLM-R base** | `xlm-roberta-base` | 5 | 16 | 3e-05 | — | 42 | 8,844 |
| **PhoBERT base** | `vinai/phobert-base` | 5 | 32 | 2e-05 | — | 42 | 8,844 |

> `grad-accum 2` chỉ dùng cho XLM-R large (mô hình lớn, cần chia nhỏ batch).

---

## 4. BẰNG CHỨNG 4 — NHẬT KÝ TỪNG EPOCH

Đây là **bằng chứng mạnh nhất**. Số liệu F1 theo từng epoch chỉ có được
khi thật sự chạy huấn luyện — không thể bịa ra.

### XLM-R large

| Epoch | Train loss | Dev — Precision | Dev — Recall | **Dev — F1** |
|---:|---:|---:|---:|---:|
| 1 | 0.5313 | 0.7218 | 0.7773 | **0.7485** |
| 2 | 0.3207 | 0.7980 | 0.7465 | **0.7714** |
| 3 | 0.2562 | 0.7959 | 0.7788 | **0.7873** |
| 4 | 0.2120 | 0.7713 | 0.7796 | **0.7754** |

**Epoch tốt nhất (chọn làm mô hình cuối): F1 dev = 0.7873**

### XLM-R base

| Epoch | Train loss | Dev — Precision | Dev — Recall | **Dev — F1** |
|---:|---:|---:|---:|---:|
| 1 | 0.4910 | 0.8175 | 0.7089 | **0.7594** |
| 2 | 0.3328 | 0.7940 | 0.7757 | **0.7848** |
| 3 | 0.2578 | 0.7693 | 0.8118 | **0.7900** |
| 4 | 0.1910 | 0.7785 | 0.8018 | **0.7900** |
| 5 | 0.1539 | 0.7902 | 0.8041 | **0.7971** |

**Epoch tốt nhất (chọn làm mô hình cuối): F1 dev = 0.7971**

### PhoBERT base

| Epoch | Train loss | Dev — Precision | Dev — Recall | **Dev — F1** |
|---:|---:|---:|---:|---:|
| 1 | 0.5550 | 0.7130 | 0.6797 | **0.6960** |
| 2 | 0.3576 | 0.7794 | 0.7203 | **0.7487** |
| 3 | 0.3050 | 0.7724 | 0.7517 | **0.7619** |
| 4 | 0.2627 | 0.7693 | 0.7487 | **0.7588** |
| 5 | 0.2438 | 0.7614 | 0.7556 | **0.7585** |

**Epoch tốt nhất (chọn làm mô hình cuối): F1 dev = 0.7619**

---

## 5. BẰNG CHỨNG 5 — KẾT QUẢ TRÊN TẬP TEST

| Mô hình | Precision | Recall | **F1 (trùng nhau)** | F1 (đúng cả 2 đầu) | F1 (mức ký tự) | Mức bình luận | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **XLM-R large** | 0.7792 | 0.7859 | **0.7825** | 0.5505 | 0.7023 | — | 995 | 282 | 271 |
| **XLM-R base** | 0.7661 | 0.7915 | **0.7786** | 0.5400 | 0.6848 | — | 1002 | 306 | 264 |
| **PhoBERT base** | 0.7358 | 0.7480 | **0.7419** | 0.5006 | 0.6559 | — | 947 | 340 | 319 |

**Giải thích cách chấm:**

| Cách chấm | Nghĩa |
|---|---|
| Trùng nhau (partial) | cụm đoán **chồng lên** cụm đúng là tính đúng — chỉ số chính |
| Đúng cả 2 đầu (strict) | phải khớp **chính xác cả đầu và cuối** |
| Mức ký tự (char) | so từng ký tự |
| Mức bình luận | cả câu có cụm độc hại nào không — đúng / sai |

---

## 6. CÁCH TÁI LẬP — CHỨNG MINH TRƯỚC HỘI ĐỒNG

Có thể chạy ngay tại chỗ để chứng minh:

```bash
# 1. Chấm lại mô hình trên tập test — ra đúng con số trong báo cáo
python tools/eval_model.py --model models/xlmr-large --data-root datasets/ViHOS

# 2. Cho xem mô hình đoán 10 câu thật
python tools/eval_model.py --model models/xlmr-large --data-root datasets/ViHOS --show 10

# 3. Cho xem mô hình đoán 1 câu bất kỳ
python tools/eval_model.py --model models/xlmr-large --text "Thằng này ngu vãi"

# 4. Chạy thử huấn luyện nhanh (1 phút) để chứng minh pipeline chạy được
python tools/train_vihos.py --variant syllable --model xlm-roberta-base --smoke
```

**Kết quả mong đợi ở lệnh 1:** F1 = 0.7825 (XLM-R large).

Lệch khoảng 0,0004 là bình thường: bản gốc chạy trên GPU dùng số thực 16-bit,
máy tính để bàn dùng 32-bit. Lệch đúng **1 cụm từ** trên tổng 1.266 cụm.

---

## 7. BẰNG CHỨNG 6 — TỆP TRỌNG SỐ ĐÃ LƯU

| Mô hình | `model.safetensors` | SHA-256 (32 ký tự đầu) |
|---|---:|---|
| **XLM-R large** | 2,235,424,156 byte | `52d105d542a29ccb5a51cdd6a16a0b58` |
| **XLM-R base** | 1,109,845,500 byte | `94d1d9920cd479d8b61765aa5a5278ad` |
| **PhoBERT base** | 537,663,868 byte | `23fe96ca2b2a87f7d9e101a460918f6c` |

Mỗi thư mục mô hình còn có:

| File | Nghĩa |
|---|---|
| `config.json` | kiến trúc mạng và bộ nhãn |
| `tokenizer.json` / `vocab.txt` | bộ tách từ |
| `metrics.json` | toàn bộ siêu tham số + nhật ký + kết quả |

---

## 8. CẦN BỔ SUNG THÊM GÌ

| # | Việc | Vì sao | Trạng thái |
|---|---|---|---|
| 1 | Chụp ảnh màn hình Colab lúc đang train | Bằng chứng trực quan | ☐ cần làm |
| 2 | Lưu notebook Colab **kèm kết quả chạy** | Hiện chưa lưu kết quả | ☐ cần làm |
| 3 | Ghi lại ngày huấn luyện, thời gian chạy | Hội đồng hay hỏi | ☐ cần làm |
| 4 | Chạy `--smoke` trước hội đồng | Chứng minh pipeline chạy được | ☐ làm khi bảo vệ |

> **Lưu ý:** hội đồng thường hỏi *"dữ liệu nào, code nào, tham số nào"* —
> cả ba đều đã có trong hồ sơ này. Việc train ở máy nào **không** phải
> câu hỏi thường gặp, nhưng nên chuẩn bị ảnh chụp để chắc chắn.

---

*Hồ sơ sinh tự động từ chính các tệp trong thư mục dự án.*