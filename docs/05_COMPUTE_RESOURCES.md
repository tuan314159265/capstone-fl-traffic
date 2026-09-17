# 05 — Khảo sát & Chốt nguồn Compute — FL Traffic Forecasting

**Ngày:** 2026-09-17 | **Tác giả:** Tuấn | **Trạng thái:** chốt phương án

## 1. Mục tiêu compute

- Dataset: **METR-LA** (207 nodes, 34k steps) và **PeMS-BAY** (325 nodes, 52k steps), `hist_len=12 pred_len=12`.
- Model backbone: **ST-GCN / DCRNN** (~300K–1.2M params), loss MAE, optimizer Adam.
- FL setup: `num_clients=10`, `num_rounds=50`, `local_epochs=5`, `fraction_fit=0.5` → tổng ~1250 local epochs tương đương central 50 epochs x 10 shards.
- Tracking: wandb, log `results/*.json`.

Yêu cầu tối thiểu: chạy 1 experiment end-to-end <6h, grid 10–15 config <3 ngày, VRAM >=8GB để batch 32–64 với graph 207–325 nodes.

## 2. Hạ tầng khảo sát (09/2026)

| Nguồn | Cấu hình thực đo / công bố | VRAM/RAM | Thời lượng | Chi phí | Phù hợp |
|---|---|---|---|---|---|
| **A. GPU cá nhân (máy Tuấn)** | `NVIDIA GeForce RTX 3060 Laptop GPU 6GB` + `Intel i9-12900H 14C/20T` + `15.6GB RAM` + `473GB NVMe (46% used)` <br> Driver 610.57.04, CUDA 13.3 (kiểm tra `nvidia-smi 2026-09-17`) | 6GB / 15GB | Không giới hạn, điện nhà | 0đ | Dev local, debug, chạy 1–2 exp nhỏ, Flower simulation `ray` sequential (không fit 10 clients // trên GPU 6GB) |
| **B. Google Colab Pro** | Pro: `T4 16GB` hoặc `L4 24GB` (2025-2026), Pro+: `A100 40GB`. RAM 12–25GB, runtime 12–24h/session, background execution | 16–40GB | ~100 compute units/tháng (~50h T4) | ~11$/tháng (Pro, giá 2026) | Burst khi cần A100, dễ mount Drive/GCS, nhưng queue + timeout, không ổn định cho long-run FL |
| **C. Kaggle GPU** | `T4 x2 16GB` hoặc `P100 16GB`, CPU 4c/30GB RAM, disk 20GB + dataset 50GB, Internet off default | 16GB (x2) | **30h GPU/week** (quota user báo), 20h extra nếu verify phone. Note: Kaggle reset Chủ nhật 00:00 UTC | 0đ | Grid search, chạy 5–8 exp song song theo tuần, code phải checkpoint `results/` → commit dataset |
| **D. Server trường (nếu có)** | *Chưa xác nhận — cần hỏi khoa/phòng lab xem có cấp GPU không*. Nếu có thường là `RTX 3090/4090 24GB` hoặc `A5000 24GB` qua SSH/Slurm | 24GB+ / 64GB+ | Theo slot đăng ký (thường 48h/job) | 0đ (nội bộ) | Chỉ tính nếu trường cấp; không thì dùng Vast.ai thuê ngoài |

> **Kết luận chốt (đề xuất):** Dùng **A cá nhân** cho dev/debug + unit test + 1 baseline nhỏ. Dùng **C Kaggle 30h/w** làm worker chính cho sweep 10 configs/tuần. Dùng **B Colab Pro** làm backup khi Kaggle hết quota hoặc cần A100 40GB cho DCRNN 325 nodes. **D Server trường** chỉ là optional — nếu không có thì chốt Vast.ai `RTX4090 24GB ~0.5$/h` cho final run.

## 3. Ước tính hiệu năng có thể đạt được

### 3.1 Baseline central (không FL) — tham chiếu paper

| Dataset | Model | MAE@12 (central) | Thời gian train central (1 GPU) |
|---|---|---|---|
| METR-LA | DCRNN | ~3.60 | ~1.2h trên T4 16GB (50 epochs, batch 64) |
| METR-LA | ST-GCN | ~3.45 | ~0.9h trên T4 |
| PeMS-BAY | DCRNN | ~1.86 | ~1.8h trên T4 |
| PeMS-BAY | GraphWaveNet | ~1.72 | ~2.5h trên T4 |

> FL thường giảm 3–8% so với central do non-IID (FedAvg), kỳ vọng MAE@12 FL: METR-LA ~3.7–3.9, PeMS-BAY ~1.95–2.05 trước khi adaptive.

### 3.2 Ước tính thời gian FL simulation (Flower, sequential trên 1 GPU)

Công thức: `T ≈ num_rounds * (fraction_fit*num_clients*local_epochs*t_epoch_shard + t_agg)`

- `t_epoch_shard` (METR-LA shard 1/10): ~18s trên RTX3060 6GB (batch 32), ~12s trên T4 16GB (batch 64), ~7s trên A100
- `num_rounds=50, local_epochs=5, 5 clients/round` → ~250 local epochs

| Nguồn | Thời gian / exp (50 rounds) | Grid 10 exp | Ghi chú |
|---|---|---|---|
| **A RTX3060 6GB** | **4.5–6h** (batch 32, sequential, RAM 15GB đủ, VRAM sát nút) | 45–60h (~1 tuần, không sleep) | Batch >32 dễ OOM với 325 nodes → phải giảm batch 16, thời gian x1.5 |
| **T4 16GB (Kaggle/Colab)** | **2.5–3.5h** (batch 64) | 25–35h → vừa trong 30h Kaggle/tuần nếu tối ưu 5–7 exp | T4x2 Kaggle có thể chạy 2 exp // nếu RAM đủ |
| **A100 40GB (Colab Pro+ / Server trường)** | **1.2–1.8h** | 12–18h | Đủ VRAM chạy 10 clients // bằng `ray` hoặc `flwr simulation` với concurrency |

**Suy ra hiệu năng đạt được với combo A+C+B:**
- Với 30h Kaggle + cá nhân không giới hạn: **~7–10 exp hoàn chỉnh / tuần** (đủ cho baseline FedAvg/FedProx/SCAFFOLD/FedRep/Ditto = 5 exp + 3 ablation).
- Nếu có server trường 24GB: **~20–25 exp / tuần**, đủ cho sweep hyperparam adaptive (lr, weight heterogeneity/freshness).

### 3.3 Giới hạn & rủi ro

- **RTX3060 6GB OOM:** PeMS-BAY 325 nodes + ST-GCN batch 64 → ~9GB, bắt buộc batch 16–32 hoặc `torch.cuda.amp`. Cần implement gradient accumulation.
- **Kaggle 30h/w:** Không cumulable, reset Chủ nhật. Job >9h sẽ bị kill. Phải checkpoint mỗi round → `results/checkpoints/`.
- **Colab timeout:** 12h idle, cần `wandb` + Drive sync.
- **Server trường chưa chốt:** Nếu trường không cấp GPU trước tháng 10, phương án fallback là thuê Vast.ai `RTX4090 24GB ~0.5$/h` cho final run (~20h ≈10$).

### 3.4 Khuyến nghị config để fit 6GB

```yaml
# configs/fedavg_6gb.yaml — dùng cho máy cá nhân
dataset: {name: METR-LA, hist_len: 12, pred_len: 12}
fl: {strategy: fedavg, num_clients: 10, num_rounds: 20, local_epochs: 2, client_fraction: 0.3}
model: {backbone: stgcn, hidden_dim: 32}
train: {batch_size: 32, amp: true, grad_accum: 2}
```

Với config này 1 exp chỉ ~1.2h trên RTX3060, dùng để debug trước khi scale 50 rounds trên Kaggle/Colab/server trường.

## 4. Kế hoạch chốt nguồn (action items)

- [x] Đo máy cá nhân: RTX3060 6GB / i9-12900H / 15GB RAM (done 2026-09-17)
- [x] Xác nhận Kaggle 30h GPU/week (user báo) — tạo notebook `capstone-fl-traffic-kaggle.ipynb` với checkpoint
- [ ] **Tuấn: hỏi khoa/phòng lab** xem có server GPU trường cấp cho đồ án không (specs, Slurm queue, thời hạn) — ESC là công ty nên bỏ khỏi phạm vi đồ án
- [ ] Đăng ký Colab Pro (11$/th) — chỉ active khi Kaggle cạn hoặc cần A100
- [ ] Viết script benchmark `experiments/benchmark_compute.py` (đã tạo skeleton) để đo `t_epoch_shard` thực tế trên từng nguồn và cập nhật bảng §3
- [ ] Thống nhất lưu kết quả: `results/` + wandb project `capstone-fl-traffic`, không commit file >10MB (theo `.gitignore`)

## 5. Tài liệu liên quan

- `docs/03_DATA_SCHEMA.md` — schema partition non-IID ảnh hưởng đến t_epoch_shard
- `docs/04_PLAN_DESIGN.md` — luồng FL, chỗ adaptive aggregation tiêu tốn thêm ~10% compute
- `configs/baseline_fedavg.yaml` — config gốc, sẽ tạo thêm `configs/*_6gb.yaml` cho máy cá nhân
- `experiments/benchmark_compute.py` — script đo hiệu năng thực tế (chạy `python experiments/benchmark_compute.py --config configs/baseline_fedavg.yaml --rounds 2`)

## 6. Phụ lục: lệnh kiểm tra nhanh

```bash
nvidia-smi --query-gpu=name,memory.total --format=csv
free -h; lscpu | grep "Tên mô hình"
python experiments/benchmark_compute.py --dry-run  # ước tính không cần GPU
```

> Cập nhật tiếp khi có phản hồi server trường và kết quả benchmark thực tế trên Kaggle/Colab.
