# Plan & Design — Adaptive & Personalized FL cho Traffic Forecasting

## 1. Mục tiêu

Xây dựng FL framework mô phỏng non-IID traffic, baseline FedAvg/FedProx/SCAFFOLD/FedRep/Ditto, rồi đề xuất Adaptive Aggregation có trọng số theo heterogeneity/freshness/reliability.

## 2. Luồng hệ thống

1. `download_data.py` -> `data/raw`
2. `partition_noniid.py` -> `data/processed`
3. `run_experiment.py` load YAML -> Flower simulation (server.py/client.py)
4. Strategy (`src/fl/strategies/*`) thực hiện aggregation
5. Log metrics -> `results/` + wandb

## 3. Kiến trúc

- `src/models/backbone.py`: ST-GCN / DCRNN
- `src/metrics/*`: tính trọng số adaptive
- `src/fl/strategies/adaptive.py` (sẽ thêm): weighted aggregation

## 4. Roadmap

Giai đoạn 1: repo, data, metrics, FL sim, baseline
Giai đoạn 2: adaptive aggregation + experiments + báo cáo

Chi tiết kiến trúc tham khảo `docs/04_PLAN_DESIGN.md.rule_example`.
