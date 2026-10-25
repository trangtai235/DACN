# Nguồn tham khảo và tài nguyên

- ViHOS: dataset và mã huấn luyện được người dùng cung cấp trong ba ZIP, giữ tại `datasets/ViHOS/`, `training/vihos/` và `notebooks/training/`. Notebook ghi nguồn dataset là https://github.com/phusroyal/ViHOS. Hash và nguồn từng tệp tại `training/provenance/import_manifest.json`; lần nhập này không tự đặt giấy phép mới hoặc xác nhận tác giả/thời điểm huấn luyện của các trọng số được cung cấp.

- AnnotaHub, Dinh-Hong Vu, Hoang-Duy Nguyen, Tuong Le: https://github.com/vdhong/AnnotaHub (Apache-2.0). Tham khảo quy trình; dự án này được cài đặt mới, không chứa toàn bộ mã AnnotaHub.
- UIT-ViCTSD, Luan Thanh Nguyen, Kiet Van Nguyen, Ngan Luu-Thuy Nguyen. Constructive and Toxic Speech Detection for Open-domain Social Media Comments in Vietnamese, 2021. https://github.com/tarudesu/ViCTSD. CSV gốc được tải bằng lệnh riêng; nguồn và hash được ghi khi train. Đọc điều kiện của nguồn khi tái sử dụng hoặc chia sẻ dữ liệu.
- Django (BSD), scikit-learn (BSD), PostgreSQL (PostgreSQL License), Celery (BSD), các thư viện theo giấy phép riêng trong phân phối của chúng.
- Font Be Vietnam Pro từ Google Fonts (SIL Open Font License); giao diện có fallback font hệ thống khi offline.
- Icon SVG trong giao diện được tạo từ các nét hình học cơ bản cho bản dựng này.

Model baseline được huấn luyện phục vụ nghiên cứu/đồ án. Báo cáo chỉ áp dụng tập dữ liệu và cấu hình đã đo, không phải chứng nhận độ đúng cho dữ liệu tùy ý.
