# User Guide — capstone-fl-traffic

## 1. Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Chuẩn bị data

```bash
python data/scripts/download_data.py --dataset METR-LA
python data/scripts/partition_noniid.py --num-clients 10 --alpha 0.5
```

## 3. Chạy experiment

```bash
python experiments/run_experiment.py --config configs/baseline_fedavg.yaml
```

## 4. Quy ước Git

- Branch: `main` (ổn định), `dev` (phát triển), `feat/<module>`
- Commit: `[feat]`, `[fix]`, `[docs]`, `[refactor]`, `[style]`
- Xem `docs/01_NAMING_CONVENTION.md`

## 5. Lưu ý

- Không commit `data/raw/*`, `data/processed/*`, `.env`, `*.pt`
- Kết quả lớn để ở `results/` + wandb
