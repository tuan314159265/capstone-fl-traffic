# FedAvg trên dữ liệu TomTom thật

Run chính thức đầu tiên: `fedavg_tomtom_20261026T183431Z` trên EC2 hiện tại, CPU.
Dữ liệu là snapshot 603 dòng từ PostgreSQL/PostGIS, không sinh thêm dữ liệu giả.
`data_manifest.json` lưu SHA-256 CSV, mốc chia tập và các đoạn bị loại.

## Phạm vi thử nghiệm

- Khử trùng theo segment_key và slot 15 phút (lấy bản mới nhất); confidence >=0.7.
- Loại mốc lệch lưới >3 phút; không nội suy qua khoảng trống.
- 8 mốc quá khứ, 3 đặc trưng: tốc độ/80, sin/cos giờ trong ngày Việt Nam.
- Dự báo duy nhất +15 phút. Chưa chạy +30 hoặc +60 phút vì thiếu chuỗi liên tục.
- 6 đoạn đường đủ điều kiện, mỗi đoạn một client logic; 16 đoạn bị loại.
- Train/validation/test =36/12/18 cửa sổ. Nhãn được chia theo thời gian chung
  cho mọi client, không trùng timestamp giữa các tập; lịch sử đầu vào được phép
  dùng dữ liệu đã biết ở tập trước.
- GRU hidden16, Flower FedAvg 10 vòng, mỗi vòng 2 local epochs, seed42.
- Client chạy tuần tự trong một container, không phải 6 máy phân tán.
- Bộ chọn checkpoint xét validation của vòng1..10; checkpoint chọn vòng10.

## Kết quả

| Phép đo | km/h |
| --- | ---: |
| MAE validation trước train | 3.0698 |
| MAE validation checkpoint đã train | 4.1374 |
| MAE test checkpoint đã train | 3.9210 |
| MAE test giữ nguyên tốc độ hiện tại | 1.2778 |

Mô hình hiện kém baseline và validation kém khởi tạo. Chưa đủ cơ sở dùng mô hình
này để dự báo vận hành hoặc kết luận chất lượng FedAvg. Test chỉ gồm 3 thời điểm
trên 6 đoạn. Không điều chỉnh tham số theo test này để tuyên bố chất lượng.

Cả 10 phép tổng hợp theo số mẫu đã được kiểm tra, checkpoint đọc lại trùng trọng
số, không lỗi số học. Peak RSS 335.4 MiB;
thời gian trong hàm train/evaluate 5.01 giây (không gồm khởi
động Docker/import/upload). Giới hạn container 1CPU/768MiB, không có network.
Collector tiếp tục chạy và DB tăng lên633 dòng sau snapshot.

Run trước `fedavg_tomtom_20261026T183322Z` đã chạy train nhưng bộ chọn
chọn vòng0 chưa train. Không dùng model.pt của run đó làm mô hình đã huấn luyện.
Run hiện tại giữ nguyên cấu hình, chỉ sửa quy tắc xuất checkpoint đã train.

## Chạy lại

```bash
# Giữ nguyên snapshot để tái lập
python infra/aws/run_fl_real.py
# Lấy snapshot mới từ PostgreSQL rồi chạy thử
python infra/aws/run_fl_real.py --refresh-snapshot
```

Dữ liệu CSV, metrics, manifest và model nằm trong thư mục bị Git ignore.
Kết quả giữ cả trên AWS `/opt/capstone-traffic/fl-real/results/` và local
`results/`. Không có API key hoặc thông tin đăng nhập DB trong dataset/container.
Không tự triển khai checkpoint để dự báo trực tiếp. Kết quả và trọng số đã được
đồng bộ lên dashboard; lịch retrain tuần được mô tả trong tài liệu12.

Kiểm tra loader (không cần Torch):

```bash
python -m unittest discover -s tests -v
```
