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

```bash
python experiments/run_experiment.py --config configs/baseline_fedavg.yaml
```

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
- Hướng dẫn sử dụng: xem `docs/USER_GUIDE.md`

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
