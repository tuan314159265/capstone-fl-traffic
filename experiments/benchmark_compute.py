"""
benchmark_compute.py — ước tính thời gian FL trên từng nguồn compute.

Chạy:
  python experiments/benchmark_compute.py --config configs/baseline_fedavg.yaml --rounds 2
  python experiments/benchmark_compute.py --dry-run  # không cần torch, chỉ tính toán lý thuyết

Đo thực tế nếu có torch + GPU:
  - t_epoch_shard: thời gian 1 epoch trên 1 shard (1/num_clients data)
"""
import argparse
import time
import yaml
from pathlib import Path

# Ước tính lý thuyết dựa trên §3.2 docs/05_COMPUTE_RESOURCES.md
THEORETICAL = {
    "rtx3060_6gb": {"t_epoch_shard_s": 18, "vram_gb": 6, "batch": 32},
    "t4_16gb": {"t_epoch_shard_s": 12, "vram_gb": 16, "batch": 64},
    "a100_40gb": {"t_epoch_shard_s": 7, "vram_gb": 40, "batch": 64},
}

def estimate_total_time(num_rounds, num_clients, fraction_fit, local_epochs, t_epoch_shard):
    clients_per_round = max(1, int(num_clients * fraction_fit))
    return num_rounds * (clients_per_round * local_epochs * t_epoch_shard + 5)  # +5s agg

def try_real_benchmark(batch_size=32, hist_len=12, num_nodes=207):
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        return None, "torch not installed"

    device = "cuda" if torch.cuda.is_available() else "cpu"
    # dummy ST-GCN-like op
    model = nn.Sequential(nn.Linear(num_nodes, 64), nn.ReLU(), nn.Linear(64, 1)).to(device)
    x = torch.randn(batch_size, hist_len, num_nodes).to(device)
    y = torch.randn(batch_size, 12, num_nodes).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    # warmup
    for _ in range(5):
        opt.zero_grad()
        out = model(x).mean(dim=1)  # dummy
        loss = (out - y.mean(dim=1)).pow(2).mean()
        loss.backward()
        opt.step()
    if device == "cuda":
        torch.cuda.synchronize()
    start = time.time()
    for _ in range(10):
        opt.zero_grad()
        out = model(x).mean(dim=1)
        loss = (out - y.mean(dim=1)).pow(2).mean()
        loss.backward()
        opt.step()
    if device == "cuda":
        torch.cuda.synchronize()
    elapsed = time.time() - start
    return elapsed / 10, f"device={device}, model dummy, batch={batch_size}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=str, default="configs/baseline_fedavg.yaml")
    ap.add_argument("--rounds", type=int, default=None, help="override num_rounds for quick test")
    ap.add_argument("--dry-run", action="store_true", help="only theoretical estimate")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    cfg = {}
    if cfg_path.exists():
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}
    fl_cfg = cfg.get("fl", {})
    num_clients = fl_cfg.get("num_clients", 10)
    num_rounds = args.rounds or fl_cfg.get("num_rounds", 50)
    fraction_fit = fl_cfg.get("client_fraction", 0.5)
    local_epochs = fl_cfg.get("local_epochs", 5)

    print(f"Config: {cfg_path} -> clients={num_clients}, rounds={num_rounds}, fraction={fraction_fit}, local_epochs={local_epochs}")
    print("\n=== Ước tính lý thuyết (docs/05_COMPUTE_RESOURCES.md §3.2) ===")
    for name, spec in THEORETICAL.items():
        total_s = estimate_total_time(num_rounds, num_clients, fraction_fit, local_epochs, spec["t_epoch_shard_s"])
        print(f"{name:12s} t_epoch_shard={spec['t_epoch_shard_s']:2d}s batch={spec['batch']:2d} VRAM={spec['vram_gb']:2d}GB -> total ~{total_s/3600:.2f}h ({total_s/60:.0f} phút)")

    if args.dry_run:
        return

    print("\n=== Đo thực tế (dummy model) ===")
    t, msg = try_real_benchmark()
    if t is None:
        print(f"Skip real benchmark: {msg}")
    else:
        print(f"Real t_epoch ~ {t*100:.1f}s/epoch dummy ({msg})")
        # so sánh
        total_s = estimate_total_time(num_rounds, num_clients, fraction_fit, local_epochs, t*50)  # scale dummy
        print(f"Scaled estimate (dummy*50) -> ~{total_s/3600:.2f}h")

if __name__ == "__main__":
    main()
