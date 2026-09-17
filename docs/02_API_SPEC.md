# API / Config Spec — FL Traffic Forecasting

Base: `experiments/run_experiment.py --config configs/<name>.yaml`

## Config YAML

```yaml
experiment: adaptive_agg_v1
seed: 42
dataset:
  name: METR-LA
  hist_len: 12
  pred_len: 12
fl:
  strategy: fedavg  # fedavg | fedprox | scaffold | fedrep | ditto | adaptive
  num_clients: 10
  num_rounds: 50
  client_fraction: 0.5
  local_epochs: 5
model:
  backbone: stgcn
  hidden_dim: 64
metrics:
  heterogeneity: emd
  freshness: enabled
```

## Endpoints (nếu chạy Flower server thật)

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | /api/fl/start | khởi tạo run |
| GET | /api/fl/status | trạng thái round |
| GET | /api/metrics/heterogeneity | độ dị biệt |

Xem template REST đầy đủ ở `docs/02_API_SPEC.md.rule_example`.
