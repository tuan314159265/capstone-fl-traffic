# Capstone: Adaptive & Personalized Federated Learning cho Traffic Forecasting

Nghiên cứu và xây dựng phương pháp Federated Learning thích ứng và cá nhân hóa cho bài toán dự báo giao thông trong môi trường phân tán non-IID.

## Setup môi trường

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # điền giá trị thật
```

## Chạy thử

Pipeline thử hiện tại dùng Flower FedAvg, GRU nhỏ và dữ liệu giả, chạy trong
container CPU giới hạn RAM trên EC2 đã cấu hình:

```bash
python infra/aws/run_fl_smoke.py
```

Xem `docs/09_FEDAVG_SMOKE.md`. Kết quả dùng kiểm tra pipeline, chưa phải đánh giá
dự báo giao thông. Các config METR-LA/ST-GCN đang là thiết kế, chưa chạy được bằng
runner này.

## Thu thập traffic mẫu vào PostgreSQL/PostGIS

Prototype database và collector TomTom được hướng dẫn tại `docs/07_POSTGIS_PROTOTYPE.md`. Bước nhanh:

```bash
docker compose up -d db
python -m pip install 'psycopg[binary]>=3.2' requests
python data/scripts/collect_tomtom.py
```

Collector dùng các nút giao mẫu trong `data/sample_intersections.json`; key đọc từ `.env` và không được in ra log. Nút giao được gán nguồn riêng; Waze partner feed có collector riêng:

```bash
python data/scripts/collect_waze_feed.py
```

Google Routes chỉ được cấu hình làm nguồn đối chiếu tuyến; theo điều khoản mặc định, không lưu phản hồi Routes vào database/tập huấn luyện.

## Cấu trúc thư mục

```
capstone-fl-traffic/
├── configs/            # config YAML cho từng experiment
├── data/
│   ├── raw/            # dataset gốc (không commit)
│   ├── processed/      # đã tiền xử lý (không commit)
│   └── scripts/        # download_data.py, partition_noniid.py
├── src/
│   ├── metrics/        # heterogeneity.py, freshness.py, reliability.py
│   ├── models/         # backbone.py, head.py
│   ├── fl/             # server.py, client.py, strategies/
│   └── utils/          # tiện ích chung
├── experiments/        # entrypoint run_experiment.py
├── notebooks/          # EDA / thử nghiệm
├── results/            # log kết quả (không commit file lớn)
├── report/             # LaTeX báo cáo
├── docs/               # tài liệu + RULES (xem docs/00_*.md)
├── assets/             # examples, screenshots
├── requirements.txt
├── .env.example
└── README.md
```

Chi tiết xem `docs/00_PROJECT_STRUCTURE.md`.

## Quy ước

- Naming, branch, commit: xem `docs/01_NAMING_CONVENTION.md`
- Data schema: xem `docs/03_DATA_SCHEMA.md`
- API / config spec: xem `docs/02_API_SPEC.md`
- Thiết kế & luồng FL: xem `docs/04_PLAN_DESIGN.md`
- Nguồn compute & hiệu năng: xem `docs/05_COMPUTE_RESOURCES.md`
- Hướng dẫn sử dụng: xem `docs/USER_GUIDE.md`
- Dashboard bản đồ và hai nhóm TomTom: xem `docs/10_DASHBOARD.md`

## Git workflow

```bash
git checkout -b feat/<module>   # vd: feat/adaptive-aggregation
# commit theo chuẩn: [feat], [fix], [docs], [refactor], [style]
git commit -m "[feat] add adaptive aggregation"
git push -u origin feat/<module>
# tạo PR vào dev -> main
```

## License

TBD
