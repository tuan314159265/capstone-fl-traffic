# DATA SCHEMA — FL Traffic Forecasting

## 1. Input chuẩn hoá

Mỗi client giữ time-series giao thông dạng:

```json
{
  "client_id": "sensor_001",
  "num_nodes": 207,
  "time_steps": 288,
  "features": ["flow", "speed", "occupancy"],
  "data": "float32 [N, T, F]",
  "timestamps": ["2024-01-01T00:00:00", "..."],
  "adjacency": "float32 [N, N] (optional)"
}
```

File `data/processed/client_<id>.npz` chứa `x: [samples, hist_len, N, F]`, `y: [samples, pred_len, N]`.

## 2. Partition non-IID

`data/scripts/partition_noniid.py` hỗ trợ:
- Dirichlet theo phân bố không gian (sensor cluster)
- Temporal shift (freshness khác nhau)
- Lượng data lệch (quantity skew)

Output: `data/processed/partition.json` map `client_id -> indices`.

## 3. Metrics

- `heterogeneity.py`: EMD / CKA giữa phân bố client
- `freshness.py`: age-of-data, staleness
- `reliability.py`: dropout rate, noise level

## 4. Chuẩn đánh giá

MAE / RMSE / MAPE trên horizon 3/6/12. Log vào `results/<exp_id>.json`.

Tham khảo template petri ở `docs/03_DATA_SCHEMA.md.rule_example`.
