# Dataset ViHOS trong source AnnotaFlow

Bộ dữ liệu được nhập nguyên byte từ `datasets.zip`, đối chiếu giống hoàn toàn
với các CSV trong `1 - DU LIEU TRUOC KHI TRAIN.zip` do người dùng cung cấp.
Manifest nguồn, hash đầy đủ và thống kê tại `training/provenance/import_manifest.json`.

```text
data/
  Sequence_labeling_based_version/
    Syllable/train_BIO_syllable.csv
    Syllable/dev_BIO_syllable.csv
    Word/train_BIO_Word.csv
    Word/dev_BIO_Word.csv
  Test_data/test.csv
```

Train có 8.844 câu; dev và test mỗi tập 1.106 câu. Các tệp BIO có các cột
`Word`, `Tag`, `sentence_id` và thêm cột chỉ mục từ nguồn. Không xóa cột/chỉnh
line ending vì sẽ thay đổi hash. Test có `content`, `index_spans` và cột chỉ mục;
`index_spans` là danh sách vị trí ký tự độc hại, được mã đọc chuyển thành spans.

Nguồn được notebook đi kèm ghi là ViHOS, kho `https://github.com/phusroyal/ViHOS`.
Các điều khoản/ghi nhận nguồn gốc của dataset gốc vẫn áp dụng; lần nhập này không
tự đặt một giấy phép mới cho dữ liệu. Giữ ghi nhận nguồn khi sử dụng trong báo cáo.

Cấu hình đối chiếu ba model hiện tại dùng `variant=syllable`, kể cả PhoBERT,
vì metadata được cung cấp ghi như vậy. Vẫn giữ cả tệp Word do `load_all()` trong
mã gốc đọc đủ năm CSV trước khi chọn biến thể.

Đây là dataset huấn luyện/đánh giá, không phải database bình luận người dùng
trong PostgreSQL. Không cần import các CSV BIO vào website để train.

Xem `docs/HUONG_DAN_TICH_HOP_DATASET_VA_MINH_CHUNG_TRAIN.md`.
