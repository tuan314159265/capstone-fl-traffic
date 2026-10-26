# Kế hoạch thu thập dữ liệu giao thông cho FL

## 1. Quyết định nguồn dữ liệu

### Nguồn huấn luyện chính: TomTom Traffic Flow

TomTom Flow Segment API nhận một tọa độ và trả về đoạn đường gần nhất, tốc độ hiện tại/tốc độ thông thoáng, thời gian đi qua, confidence, road closure, loại đường và hình học đoạn. Việt Nam có trong danh sách độ phủ. Dữ liệu này phù hợp làm chuỗi tốc độ giao thông; đây là API chính thức, không cần cào giao diện bản đồ.

### Waze: bổ sung sự kiện nếu có quyền đối tác

Waze Data Feed trả về JSON/XML gồm jam, alerts và irregularities cho khu vực đã được phê duyệt; feed cập nhật khoảng 2 phút. Chỉ dùng khi nhóm có quyền Waze for Cities/Partner Hub và feed URL hợp lệ. Waze phù hợp bổ sung sự kiện và tình trạng ùn tắc, không thay thế chuỗi tốc độ cố định của TomTom.

### Google Maps Routes: đối chiếu tuyến, không đưa vào tập train

Routes API có thể trả ETA và các khoảng traffic-aware polyline với phân loại NORMAL/SLOW/TRAFFIC_JAM. Điều khoản Google Maps Platform hiện cấm cào/xuất dữ liệu Maps ra ngoài dịch vụ và cấm dùng nội dung Maps để train, test, validate hoặc fine-tune mô hình ML. Vì vậy không lưu phản hồi Routes vào PostGIS hay tập huấn luyện; chỉ xem xét đối chiếu trực tiếp, tạm thời nếu điều khoản của project cho phép. Không cần bật API này cho pipeline huấn luyện.

## 2. Thiết kế lấy mẫu TomTom

### Giai đoạn thử kết nối

- Lấy 10 điểm trên các đoạn đường khác nhau tại TP.HCM trong 7 ngày.
- Dùng chu kỳ 15 phút để kiểm tra độ phủ, confidence, tỷ lệ lỗi và mức tiêu thụ quota.
- Đặt tọa độ trên nhánh đường/đoạn đường cần đo, không đặt giữa tâm giao lộ. Một điểm API lấy đoạn gần nhất; xác minh hình học trả về có đúng đường và hướng cần nghiên cứu.

### Giai đoạn tạo chuỗi cho thực nghiệm

- Mục tiêu khởi đầu: 20–30 điểm đường, phủ các khu vực và loại đường khác nhau.
- Gom điểm thành 5–10 FL client theo khu vực; giữ nguyên thời gian và vị trí xuyên suốt đợt thu thập.
- Mục tiêu thời gian: tối thiểu 8 tuần. Ưu tiên lấy mẫu mỗi 5 phút nếu quota/chi phí tài khoản cho phép; nếu không, dùng 15 phút và ghi rõ độ phân giải trong protocol.
- Lấy các điểm theo cùng lịch để các client có thể so sánh trên các mốc thời gian chung.

Ước lượng request chỉ tính theo số điểm và chu kỳ, chưa tính retry:

| Điểm | Chu kỳ | Request/ngày | Request/30 ngày |
|---:|---:|---:|---:|
| 10 | 15 phút | 960 | 28.800 |
| 20 | 15 phút | 1.920 | 57.600 |
| 20 | 5 phút | 5.760 | 172.800 |
| 30 | 15 phút | 2.880 | 86.400 |
| 30 | 5 phút | 8.640 | 259.200 |

Trước khi tăng số điểm hoặc chạy dài ngày, kiểm tra quota, billing, entitlement và điều khoản retention/research của chính API key trong TomTom dashboard. Trang giá TomTom hiện liệt kê mốc miễn phí hàng tháng cho Traffic Flow Segment Data, nhưng quyền sử dụng và quota thực tế cần xác nhận trên tài khoản.

## 3. Trường dữ liệu cần lưu

Một bản ghi chuẩn tương ứng một đoạn đường tại một thời điểm lấy mẫu.

### Định danh và vị trí

- `provider`, `intersection_id`, `query_point_id`, `segment_key`
- `collected_at` UTC; `source_updated_at` nếu response có HTTP Date, nhưng không coi đây là timestamp đo trực tiếp của sensor
- tọa độ điểm truy vấn, hình học đoạn trả về, tên đường nếu có từ nguồn bản đồ độc lập, `functional_road_class`, hướng/nhánh lấy mẫu

### Tốc độ và trạng thái

- `current_speed_kmh` — mục tiêu dự báo chính
- `free_flow_speed_kmh`
- `current_travel_time_s`, `free_flow_travel_time_s`
- `confidence`, `road_closed`
- `congestion_ratio = current_speed_kmh / free_flow_speed_kmh` sau kiểm tra mẫu số hợp lệ

TomTom Flow không trả số xe đi qua hoặc occupancy. Không diễn giải tốc độ thành lưu lượng xe. Nếu sau này cần dự báo counts/flow thì phải có nguồn đếm xe riêng (camera/sensor) và pipeline nhãn riêng.

### Đặc trưng thời gian và chất lượng

- Tạo `local_time`, giờ trong ngày, thứ trong tuần, cuối tuần/ngày lễ từ timestamp UTC; giữ UTC làm khóa thời gian chuẩn.
- Lưu cờ thiếu dữ liệu, lỗi truy vấn, giá trị bất thường và confidence thấp để phục vụ QC.
- Không dùng API key trong log, URL lưu trữ hoặc bảng dữ liệu. Raw response chỉ giữ trong phạm vi được điều khoản tài khoản cho phép.

## 4. Tạo bộ train/validation/test

- Cố định mục tiêu: dự báo `current_speed_kmh` sau 15, 30, 60 phút.
- Chu kỳ 5 phút: 12 bước lịch sử (1 giờ) dự báo các horizon 3/6/12 bước. Chu kỳ 15 phút: horizon 1/2/4 bước.
- Chia theo thời gian theo thứ tự: 70% train, 10% validation, 20% test; dùng cùng mốc ngày cho tất cả client. Không shuffle ngẫu nhiên các timestamp.
- Chỉ fit scaler bằng phần train. Các target của cửa sổ phải nằm trong đúng split; không cho nhãn tương lai đi qua ranh giới split.
- Báo cáo MAE/RMSE và per-client MAE; báo worst-client. Chỉ báo worst-decile khi có đủ số client để phân vị này có ý nghĩa.

## 5. Kịch bản non-IID và so sánh

Tạo client từ các vùng/nhóm điểm TomTom, không gán một nhà cung cấp cho mỗi client. Mô tả và đo rõ các mức:

- **Spatial/feature skew:** client khác nhau về khu vực, road class, mức tốc độ và congestion ratio.
- **Quantity skew:** số điểm hoặc số thời điểm quan sát giữa client khác nhau.
- **Temporal skew / distribution shift:** một số client thiếu giai đoạn hoặc có thay đổi theo thời gian; vẫn giữ test là giai đoạn tương lai.

Trên cùng dữ liệu, split và kiến trúc dự báo, so sánh local-only, centralized upper-bound và FedAvg, FedProx, SCAFFOLD, Ditto cùng phương pháp adaptive đề xuất. Kiến trúc dự báo (ví dụ GRU làm baseline trước, ST-GCN/DCRNN nếu đồ thị đủ tốt) là phần riêng với thuật toán FL.

## 6. Kiểm tra chất lượng trước khi huấn luyện

1. Tỷ lệ điểm trả về đúng đoạn đường, theo từng điểm.
2. Tỷ lệ thành công API, missingness theo điểm/giờ/ngày và độ liên tục của cadence.
3. Phân bố `confidence`, tốc độ 0/thiếu, outlier và tỷ lệ đoạn bị đóng.
4. Segment ID/geometry có ổn định qua thời gian không; nhiều điểm có bị map vào cùng một đoạn không.
5. Số timestamp hữu dụng sau khi tạo lookback/horizon và phân chia client.
6. Kiểm tra retention, attribution, quota và khả năng công bố dữ liệu dẫn xuất theo điều khoản TomTom.

Không bắt đầu huấn luyện dựa trên snapshot đơn lẻ. Chạy pipeline thử trước, sau đó quyết định giữa tập 20–30 điểm live và/hoặc dataset giao thông lịch sử có giấy phép phù hợp.

## Tài liệu API

- [TomTom Flow Segment Data](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data)
- [TomTom Traffic API Market Coverage](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/product-information/market-coverage)
- [TomTom Pricing](https://docs.tomtom.com/pricing)
- [Waze Data Feed](https://support.google.com/waze/partners/answer/10618035?hl=en)
- [Waze Data Feed specifications](https://support.google.com/waze/partners/answer/13458165?hl=en)
- [Apply for Waze for Cities](https://support.google.com/waze/partners/answer/10453062?hl=en)
- [Google Routes traffic-aware polylines](https://developers.google.com/maps/documentation/routes/traffic_on_polylines)
- [Google Maps Platform Terms](https://cloud.google.com/maps-platform/terms)
- [Google Routes API service terms](https://cloud.google.com/maps-platform/terms/maps-service-terms)
