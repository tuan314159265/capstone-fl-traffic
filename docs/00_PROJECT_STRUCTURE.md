# Project Structure — capstone-fl-traffic

```
capstone-fl-traffic/
├── configs/                        # YAML cho từng experiment
│   ├── baseline_fedavg.yaml
│   ├── baseline_fedprox.yaml
│   └── adaptive_agg.yaml
├── data/
│   ├── raw/                        # dataset gốc (PeMS, METR-LA...) — không commit, giữ .gitkeep
│   ├── processed/                  # sau tiền xử lý / chia non-IID — không commit
│   └── scripts/
│       ├── download_data.py        # tải dataset
│       └── partition_noniid.py     # chia non-IID theo không gian/thời gian
├── src/
│   ├── metrics/
│   │   ├── heterogeneity.py        # đo độ dị biệt client
│   │   ├── freshness.py            # độ tươi dữ liệu
│   │   └── reliability.py          # độ tin cậy client
│   ├── models/
│   │   ├── backbone.py             # ST-GNN / GRU backbone
│   │   └── head.py                 # forecasting head
│   ├── fl/
│   │   ├── server.py
│   │   ├── client.py
│   │   └── strategies/
│   │       ├── fedavg.py
│   │       ├── fedprox.py
│   │       ├── scaffold.py
│   │       ├── fedrep.py
│   │       └── ditto.py
│   └── utils/
│       ├── seed.py
│       └── logging.py
├── experiments/
│   ├── run_experiment.py           # entrypoint: load config -> chạy FL simulation
│   └── benchmark_compute.py        # đo t_epoch_shard, ước tính thời gian FL
├── notebooks/                      # EDA, phân tích
├── results/                        # log csv/json, wandb — không commit file lớn
├── report/                         # LaTeX báo cáo (Overleaf sync)
├── docs/
│   ├── 00_PROJECT_STRUCTURE.md     # file này
│   ├── 01_NAMING_CONVENTION.md     # quy tắc đặt tên, branch, commit
│   ├── 02_API_SPEC.md              # spec config / API FL (nếu có server)
│   ├── 03_DATA_SCHEMA.md           # schema dữ liệu traffic
│   ├── 04_PLAN_DESIGN.md           # thiết kế adaptive aggregation
│   ├── 05_COMPUTE_RESOURCES.md     # khảo sát nguồn compute & hiệu năng
│   ├── USER_GUIDE.md               # hướng dẫn chạy experiment
│   └── model_card.md               # model card
├── assets/
│   ├── examples/                   # sample config / sample data nhỏ
│   └── screenshots/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

> Bản petri-analyzer gốc được lưu ở `docs/*.rule_example` để tham khảo template.
