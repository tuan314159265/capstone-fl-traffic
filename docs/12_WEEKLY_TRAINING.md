# Lịch train tuần bằng AWS Lambda

## Lịch và kiến trúc

- Region: ap-southeast-2; giữ EC2 i-0b8aa823ebd3c885e và PostgreSQL hiện tại.
- EventBridge Scheduler `capstone-traffic-weekly-train`, cron `0 2 ? * MON *`,
  timezone `Asia/Ho_Chi_Minh`: thứ Hai 02:00 giờ Việt Nam.
- Lần chạy định kỳ đầu: 02/11/2026 lúc02:00. Lịch kết thúc
  23/11/2026 lúc20:38:58 giờ Việt Nam (13:38:58 UTC), cùng hạn dừng EC2.
- Scheduler gọi Lambda `capstone-traffic-weekly-train` (128MiB, timeout30s).
- Lambda gửi custom SSM document `capstone-traffic-weekly-train`, chạy đúng
  `/usr/bin/python3 /opt/capstone-traffic/fl-real/infra/aws/weekly/run_train.py`.
- Huấn luyện chạy trong Docker trên EC2, không chạy Torch trong Lambda.

Terraform: `infra/aws/weekly.tf`. EC2 được gắn instance profile SSM tại chỗ,
không thay máy/ổ đĩa và không mở cổng inbound. Lambda chỉ có SendCommand tới
instance/document này, DescribeInstances và ghi log của chính hàm. Scheduler
chỉ có quyền invoke hàm này. Không dùng SSH key, TomTom key hoặc DB password
trong Lambda. Hàm không nhận lệnh shell từ payload.

## Mỗi lần chạy

1. Kiểm tra hạn kết thúc và trạng thái running của EC2; không tự khởi động máy.
2. Khóa flock trên EC2; receipt theo tuần Việt Nam ngăn gọi lặp sau thành công.
3. Xuất CSV snapshot mới từ DB, gộp segment/slot, lọc confidence và khoảng trống.
4. Nếu thiếu mẫu hoặc snapshot không đổi thì bỏ qua, giữ báo cáo cũ.
5. Chạy `configs/fedavg_weekly.json`: GRU, dự báo+15phút từ8mốc, 10vòng FedAvg,
   2local epochs/vòng, CPU1, RAM768MiB, không network; timeout job15phút.
6. Lưu snapshot/config/manifest/model/metrics/log riêng theo run trong
   `/opt/capstone-traffic/fl-real/results/`.
7. Ghi báo cáo nhỏ bằng atomic rename vào
   `/var/lib/capstone-traffic/training.json`. Bridge đọc mỗi30giây, gửi lên web.

Receipt chỉ đánh dấu khi thành công. Job lỗi ghi trạng thái, giữ báo cáo thành
công gần nhất và có thể gọi lại. File training-schedule.json chứa lịch được đọc
và xác nhận từ AWS, không chỉ ghi một lịch dự kiến lên UI.

Mỗi snapshot có split train/validation/test theo thời gian riêng. Các test tuần
có thể chồng nhau giữa các run; đây là chỉ số giám sát thử nghiệm, không phải tập
test khóa cố định cho báo cáo nghiên cứu. Dashboard ghi rõ chưa triển khai dự
báo trực tiếp. Không tự promote checkpoint, kể cả khi một run thắng baseline.

## Đã kiểm chứng

- Terraform:11 resource mới,1 EC2 update in-place,0 xóa.
- SSM Agent Online; Lambda thực gửi lệnh; SSM trả Success/exit0.
- Run kiểm chứng: `fedavg_tomtom_weekly_20261026T185107Z`, dữ liệu thật mới.
- Kiểm tra loader chống trùng, gap, confidence và chia nhãn theo thời gian;
  kiểm tra Lambda bỏ qua máy dừng/hết hạn, không nhận lệnh từ payload.
- UI desktop/mobile đã kiểm tra API, lịch, MAE khớp báo cáo và Graph FL.

## Vận hành

```bash
# Xem lịch thực tế
aws scheduler get-schedule --name capstone-traffic-weekly-train --region ap-southeast-2
# Gọi kiểm tra; cùng tuần thành công sẽ bỏ qua
aws lambda invoke --function-name capstone-traffic-weekly-train \
  --region ap-southeast-2 --payload '{}' /tmp/weekly-trigger.json
# Đọc CommandId từ JSON rồi xem kết quả
aws ssm get-command-invocation --region ap-southeast-2 \
  --instance-id i-0b8aa823ebd3c885e --command-id COMMAND_ID
```

Log Lambda: `/aws/lambda/capstone-traffic-weekly-train`, giữ14ngày.
Trên EC2, xem `training.json` và file training.log trong thư mục run.

`python infra/aws/deploy_weekly.py` cập nhật code job và bridge, đọc lịch từ AWS,
giữ kết quả có sẵn. Trước Terraform plan/apply trên máy mới, tạo
`.state/weekly-trigger.zip` chứa `weekly/handler.py`, cùng biến
`weekly_training_end_date` từ hạn EC2 hiện có. Không kéo dài hạn thu thập ngầm.

Thu thập vẫn chịu budget TomTom18.000request/tháng/nhóm; 15điểm/15phút dùng
1.440request/ngày/nhóm. Lịch train không tăng budget và không gọi TomTom thêm.
