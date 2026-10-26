# Thử pipeline Flower FedAvg trên AWS

Đây là bản thử thực thi pipeline với dữ liệu giả, chưa phải thực nghiệm dự báo
giao thông. Job dùng Flower `FedAvg` thật qua Message API, mô hình PyTorch GRU và
ba client có phân bố tốc độ/số mẫu khác nhau.

## Chạy ở đâu

Với EC2 `t3.small` hiện tại, chỉ chạy bản thử nhỏ: ba client chạy tuần tự trong
một process. Container giới hạn một CPU, RAM 768 MiB, tổng RAM và swap 1 GiB,
không có network và không nhận credentials hay kết nối DB. Máy AWS vẫn chạy
PostGIS và timer thu thập riêng. Không tạo thêm EC2 hoặc GPU cho bản thử này.

Adapter `SequentialGrid` gọi các handler `ClientApp` và chiến lược Flower trong
cùng process. Nó chưa kiểm tra mạng, TLS, SuperLink, Ray hoặc nhiều máy vật lý.
Khi cần thử runtime phân tán thật hay thực nghiệm lớn, dùng máy train riêng với
cùng dataset snapshot, giữ máy thu thập chuyên thu thập dữ liệu.

## Cách chạy

Trên máy bạn, từ thư mục gốc repo, với AWS/SSH đã cấu hình:

```bash
python infra/aws/run_fl_smoke.py
```

Script upload một danh sách file cho phép, build image CPU, chạy job trên AWS,
sau đó tải `metrics.json` và `model.pt` về
`results/fedavg_smoke_<timestamp>/`. Image được cache cho lần chạy tiếp theo.
Đầu ra này được Git ignore. Không upload `.env`, AWS credentials, dataset thật,
Terraform state hoặc SSH private key vào container train.

Config: `configs/fedavg_smoke.yaml`:

- Ba client, ba vòng FedAvg, một local epoch mỗi vòng.
- GRU hidden dimension 16; cả backbone và head được tổng hợp ở baseline này.
- Dữ liệu giả 512 mốc mỗi client, khoảng cách mô phỏng 15 phút, lịch sử tám bước.
- Dự báo sau 1/2/4 bước, tương ứng 15/30/60 phút.
- Chia theo thời gian 70/10/20, cùng mốc giữa các client. Chỉ giữ cửa sổ có toàn
  bộ nhãn thuộc đúng split. Input có thể chứa lịch sử đã xảy ra trước split.
- Chuẩn hóa bằng hằng số định trước cho dữ liệu giả, không fit bằng tập test.
- Validation dùng trong các vòng, test chỉ đánh giá một lần ở cuối.
- Số mẫu train lệch nhau do các client lấy thưa khác nhau trên phần train.

## Những gì bản thử kiểm tra

- Đủ update từ tất cả client ở mỗi vòng.
- Flower tổng hợp trọng số đúng theo `num-examples`, đối chiếu bằng phép tính độc lập.
- Đủ ba vòng và đầy đủ cả train/validation call.
- Trọng số thực sự thay đổi sau train, loss/trọng số không NaN/Inf.
- Lưu và đọc lại checkpoint giữ nguyên tensor.
- Ghi phiên bản thư viện, seed, config, số mẫu mỗi split, metric từng client và
  RSS cao nhất của process. `logical_model_bytes` chỉ là kích thước tensor logic,
  chưa phải số byte truyền qua mạng thực tế.
- Kiểm tra collector và DB sau job.

Môi trường chạy là Python 3.12, Flower 1.42 và PyTorch 2.10 CPU. Các venv và driver
GPU trên máy cá nhân không tham gia chạy job AWS này. Các config METR-LA/ST-GCN
cũ vẫn là thiết kế; runner hiện từ chối chúng thay vì chạy bằng dữ liệu giả.

Tài liệu chính thức:

- [Flower Message API và PyTorch](https://flower.ai/docs/framework/tutorial-series-write-your-first-flower-app-pytorch.html)
- [Flower FedAvg](https://flower.ai/docs/framework/main/en/ref-api/flwr.serverapp.strategy.FedAvg.html)
