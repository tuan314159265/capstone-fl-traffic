# Dashboard giao thông và hai nhóm thu thập

Web riêng tư:
https://hcmc-traffic-observatory-tuan.tartclock12.chatgpt.site

Source giao diện ở thư mục bên cạnh repo:
`../traffic-observatory-site/`. Site ID được giữ trong `.openai/hosting.json`;
không tạo Site mới khi cập nhật giao diện này.

## Luồng dữ liệu

`TomTom → collector AWS → PostgreSQL/PostGIS → bridge chỉ đọc → Site riêng tư`.

AWS tiếp tục lấy mẫu mỗi 15 phút. Container `capstone-dashboard-sync` truy vấn
PostGIS mỗi 30 giây và gửi snapshot qua HTTPS. Web lưu bản mới nhất trong D1 và
tự đọc lại mỗi 30 giây. Đây là dữ liệu DB được đồng bộ, không phải truy vấn trực
tiếp từ browser vào PostgreSQL. Không chuyển API key TomTom hoặc mật khẩu DB sang
frontend. Không mở thêm cổng inbound AWS cho dashboard.

Bridge dùng role PostgreSQL `traffic_dashboard`, chỉ được SELECT các bảng cần
thiết, có `default_transaction_read_only=on` và statement timeout. Runtime env ở
`/opt/capstone-traffic/.dashboard.env`, mode 0600, không commit. Giới hạn container
là 192 MiB, 0.25 CPU; lần kiểm tra ban đầu dùng khoảng 34 MiB.

Site giữ quyền xem chỉ dành cho chủ sở hữu. Đồng bộ nền dùng credential dịch vụ
được Sites cấp, chỉ gửi tới chính Site này. Credential không có trong source hay
browser bundle. Trên AWS, dữ liệu gốc vẫn ở PostGIS; D1 chỉ giữ một snapshot đọc
cho dashboard, không thay thế database nguồn.

## Dữ liệu hiển thị

- Tất cả điểm đang thu thập, tọa độ truy vấn và hình học đoạn đường khi chọn điểm.
- Tốc độ hiện tại/thông thoáng, thời gian đi qua đoạn hiện tại/thông thoáng,
  confidence, road closure, cấp đường, số bản ghi và thời gian lấy mẫu.
- Biểu đồ 24 giờ, tìm kiếm, lọc nhóm, bảng dữ liệu và xuất CSV bản ghi mới nhất.
- Mốc giờ hiển thị theo `Asia/Ho_Chi_Minh`, dữ liệu lưu UTC.
- Điểm quá 30 phút chưa có quan sát mới được đánh dấu dữ liệu cũ. Bridge chậm hơn
  hai phút được hiển thị đồng bộ chậm; không giả lập giá trị mới.
- Trạng thái thông thoáng/chậm/ùn tắc là heuristic theo tỷ lệ tốc độ hiện tại /
  tốc độ thông thoáng (ngưỡng 0.8 và 0.5), không phải nhãn ùn tắc chuẩn.

## Hai tài khoản TomTom

`infra/aws/collection_groups.json` gán cố định mỗi nhóm cho một biến môi trường:

| Nhóm | Điểm | Key env | Counter |
| --- | --- | --- | --- |
| Bến Thành | 15 | `API_TOMTOM` | `request-budget.json` |
| Mở rộng TP.HCM | 15 | `API_TOMTOM_TRAFFIC` | `request-budget-traffic.json` |

Nhóm Bến Thành tiếp tục dùng các node ID và counter cũ. Nhóm mới có ID
`traffic_01` đến `traffic_15`; 15 geometry hash khác nhau đã được kiểm tra bằng API
và xác nhận khi ghi DB, không trùng 7 geometry hash của nhóm cũ. Tổng hiện có
30 điểm đang thu thập trên 22 đoạn đường khác nhau; thêm một điểm lịch sử có thể
xem bằng bộ lọc "Điểm cũ". Tọa độ là điểm lấy mẫu trên đường, không mặc định là
nút giao đã khảo sát hoặc tên đường đã xác minh.

Mỗi nhóm mặc định có budget riêng 18.000 request/tháng UTC. 22 request khảo sát
ban đầu của tài khoản thứ hai đã được cộng vào counter đúng một lần bằng receipt.
Không reset counter cũ, không đổi key giữa các nhóm khi hết quota. Một nhóm lỗi
hoặc hết budget không ngăn nhóm còn lại chạy. 15 điểm/15 phút vẫn cần khoảng
43.200 request/30 ngày **cho mỗi tài khoản**, nên ngưỡng 18.000 không bảo đảm lấy
mẫu liên tục suốt bốn tuần; cần xác nhận allowance thực tế hoặc chỉnh cadence.

## Graph FL và mức sẵn sàng dữ liệu

Tab Graph FL đặt máy chủ FedAvg ở giữa, mặc định gộp các điểm trả về cùng
`segment_key` thành node đoạn đường. Có thể bỏ gộp để xem từng điểm truy vấn.
Màu thể hiện Jensen–Shannon divergence của histogram tốc độ (hoặc tỷ lệ tốc độ /
thông thoáng) so với phân bố gộp trong 24 giờ; kích thước theo số mốc hợp lệ.
Đây là mô tả khác biệt dữ liệu quan sát, chưa chứng minh non-IID ổn định.

Chỉ dùng mốc có confidence >= 0.7, gần lưới 15 phút trong 3 phút, không ở tương
lai; khử trùng theo đoạn và mốc. Cửa sổ tham khảo gồm 12 mốc liên tiếp (8 đầu vào,
4 đầu ra). α tham khảo = số cửa sổ node / tổng cửa sổ; chưa phải trọng số của một
run. Dashboard hiện đã đọc kết quả train thật: MAE, baseline, số mẫu, lịch sử và
trọng số FedAvg thực tế theo từng đoạn. Dấu ✓ chỉ các node tham gia run gần nhất.
Dự báo trực tiếp chưa triển khai. α tham khảo 8→4 vẫn được phân biệt với α của run +15 phút.

Lịch tự động đã được cài bằng Scheduler → Lambda → SSM → EC2 (xem tài liệu12).
Đề xuất thu thập: chạy kiểm tra pipeline khi đủ
cửa sổ liên tiếp; thử nghiệm sau 3–7 ngày liên tục, đánh giá lại hằng tuần khi có
dữ liệu mới. Các mốc này cần điều chỉnh theo độ phủ và kết quả validation.
Chia tập theo thời gian, tạo cửa sổ trong từng tập và giữ test cuối kỳ riêng.
Không dùng tổng số dòng thay cho kiểm tra khoảng trống hoặc số đoạn độc lập.

## Lệnh vận hành

Sau khi SSH vào AWS:

```bash
sudo journalctl -u capstone-collector.service -n 40 --no-pager
sudo docker logs --tail 10 capstone-dashboard-sync
sudo docker stats --no-stream capstone-dashboard-sync capstone-traffic-db
```

Kiểm tra một nhóm thủ công (sẽ dùng request thật):

```bash
cd /opt/capstone-traffic
sudo python3 infra/aws/run_snapshot.py --group traffic
```

`python infra/aws/deploy.py` cập nhật collector và merge các traffic key từ `.env`
vào env cloud riêng, giữ nguyên DB password và các counter. Script
`infra/aws/deploy_dashboard.py` cài bridge, nhận cấu hình Site qua stdin được ẩn;
không truyền token trên command line hoặc in log. Khi cập nhật collector, giữ
bridge đang chạy; khi cập nhật website, dùng lại Site ID và quyền xem hiện có.

EC2 vẫn có lịch tự dừng ngày 23/11/2026. Nếu EC2 dừng hoặc nguồn bị gián đoạn,
web vẫn giữ snapshot cuối và báo độ cũ của dữ liệu.
