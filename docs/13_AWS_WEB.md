# Web tĩnh trên EC2 và graph tương tác

URL: https://3.107.21.103
Tài khoản: tuan. Mật khẩu được tạo ngẫu nhiên, lưu riêng ở
`infra/aws/.state/web-login.json` (mode0600, Git ignore). Không commit hoặc đưa
mật khẩu lên browser bundle. Server đăng nhập giữ PBKDF2 hash, không lưu password plaintext trên AWS. HTTPS dùng chứng chỉ
IP công khai của Let's Encrypt, ACME shortlived, Caddy tự gia hạn.

## Thành phần

- Cùng EC2 hiện tại, không tạo máy mới, load balancer, RDS hoặc domain trả phí.
- UI dùng chung source `../traffic-observatory-site/app/dashboard.tsx`.
- Vite SPA build riêng bằng `vite.aws.config.ts`; không cần Node/SSR chạy trên EC2.
- Caddy2.11.7-alpine giới hạn96MiB/0.25CPU, phục vụ file tĩnh và snapshot JSON.
- Tại lần đo: Caddy13.2MiB, bridge31.4MiB. JS75.3KB gzip + CSS5.5KB gzip.
- Mở80 (HTTPS redirect) và443; database vẫn không có cổng public.
- Trang `/login` riêng; form POST, phiên cookie Secure/HttpOnly/SameSite=Lax.
- Giữ đăng nhập7ngày nếu chọn; nếu bỏ chọn thì8giờ. Có nút đăng xuất trên dashboard.
- API và dữ liệu yêu cầu cookie hợp lệ; chưa đăng nhập API trả401, trang chuyển về/login.
- Form kiểm tra Origin, giới hạn8lần sai/15phút/IP. Auth server stdlib chạy container64MiB/0.25CPU; không mở thêm cổng public.
- /api/ingest không được mở trên bản AWS. Bản này chỉ đọc snapshot.

Bridge SELECT từ PostGIS bằng role read-only, ghi atomic snapshot vào
`/var/lib/capstone-traffic/web-snapshot/traffic-snapshot.json` mỗi30giây.
Container phục vụ dữ liệu chỉ mount thư mục này read-only; không có key TomTom, credential
Sites hay mật khẩu database. Bridge vẫn đồng bộ website Sites riêng tư.

`Referrer-Policy: strict-origin-when-cross-origin` và URL tile chuẩn
`https://tile.openstreetmap.org/{z}/{x}/{y}.png` cho phép trình duyệt gửi Referer
đúng chính sách OSM. Không proxy tile hoặc thêm header giả. Cấu hình same-origin
trước đây đã chặn Referer và gây ảnh báo403.

Caddy có default_sni là IP public để hỗ trợ trình duyệt/curl không gửi SNI cho
IP. Chứng chỉ, account ACME được giữ trong `/var/lib/capstone-traffic/caddy-data`.
Khi EC2 stop/start, IP có thể thay đổi; cần deploy lại theo IP mới. Không tự tạo
Elastic IP. Hạn dừng EC2 vẫn23/11/2026.

## Graph FL

Mô phỏng lực chạy trong trình duyệt: lực đẩy tránh chồng node, lò xo về FedAvg,
chuyển động nhẹ. Hover dừng node đang xem; kéo node để đổi vị trí, kéo nền để pan,
cuộn hoặc nút +/- để zoom. Có tạm dừng và đặt lại. FedAvg giữ ở giữa đồ thị.

Màu vẫn theo độ lệch phân bố JS; dấu tick chỉ node tham gia run thật. Tooltip
hiện dữ liệu quan sát, MAE và trọng số tổng hợp theo số mẫu của run. Bố cục không
biểu thị khoảng cách địa lý hay quan hệ đường sá. Không giả lập dự báo trực tiếp.

## Cập nhật

```bash
cd ../traffic-observatory-site
./node_modules/.bin/vite build --config vite.aws.config.ts
cd ../capstone-fl-traffic
python infra/aws/deploy_web.py --static-dir ../traffic-observatory-site/dist/aws-client
```

Terraform `infra/aws/web.tf` quản lý cổng80/443. Deploy giữ mật khẩu sẵn có;
muốn đổi, sửa password trong file local riêng rồi chạy lại deploy. Deploy tự tạo hash mới,
đổi khóa ký phiên khi mật khẩu đổi và khởi động lại các container web.
File `.state/web-auth.json` và `/opt/capstone-traffic/web/auth.json` chứa hash và
khóa phiên, mode0600, không đưa vào frontend/Git. Tài khoản hiện tại được giữ nguyên.
