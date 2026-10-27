# Data audit and comparison reports

AWS web: https://3.107.21.103 → Báo cáo. It displays frozen-snapshot statistics,
not continuously recomputed benchmark scores. Existing collectors and the Monday
FedAvg schedule are unchanged.

## Reproduce

```bash
python infra/aws/run_comparison.py
python experiments/export_obsidian_report.py \
  --report results/comparison_20261026T194246Z/reports.json \
  --vault-root /home/tuan/Documents/Notes/ObsidianVault
```

The runner uses `data/raw/tomtom_report_snapshot.csv`, exported from PostGIS,
with no raw API payload or credentials. It does not refresh that CSV or call
TomTom. Freeze a new CSV explicitly for a new comparison; never combine rows
from different snapshot hashes in a comparison table.

Code: `src/data/quality.py`, `experiments/run_comparison.py`,
`experiments/comparison_worker.py`, `src/metrics/evaluation.py`.
Configuration: `configs/comparison_pilot.json`.

Runs are isolated under `/opt/capstone-traffic/comparison/<run_id>` and copied
back to local `results/<run_id>`. Container limits:1CPU/768MiB/no network; workers
run one at a time with a separate process for each method/seed. The parent job
is bounded to20minutes. The job runs the Torch-dependent objective tests on AWS.
A successful report is atomically copied to `/var/lib/capstone-traffic/reports.json`.
The read-only bridge includes it in both Sites and AWS dashboard snapshots.

## Protocol

- Same frozen CSV, active points, deduplicated physical segment/slot, global
  chronological target cutoffs and eligible clients for every method.
- Input8slots, output+15min; normalized speed/80 plus cyclic time features.
- GRU16, Adam0.003, batch16,10rounds×2epochs, optimizer reset each round.
- Local/centralized/FedAvg/FedProx use the same initialization per seed42/43/44.
  Total example visits match; pooled minibatch step counts need not match FL.
- FedProx fixes the incoming global parameters during each local objective,
  adding mu/2 times squared parameter distance; mu0.01, not tuned on test.
- Global methods choose trained checkpoints by macro validation MAE; local
  selects validation checkpoint per client. Test evaluated only after selection.
- Metrics: macro/micro MAE, RMSE, worst-node/ceil(10%K)tail, per-node dispersion,
  local-relative negative transfer, seed SD, convergence and tensor payload.
- Confidence quality and collection age are not FL participant reliability or
  model-update freshness. JS is computed using observations in the train period.
- SCAFFOLD, Ditto/FedRep and adaptive personalization remain unimplemented.

## Initial measured pilot

Run `comparison_20261026T194246Z`:753raw rows,375distinct valid segment slots,
264same-segment/slot rows merged,108off-grid/future rows and6invalid
speed/confidence rows.6eligible clients;54train/18validation/21test windows.

Macro MAE(mean±sample SD between seeds), km/h:

| Method | MAE |
| --- | ---: |
| Persistence |0.458±0.000|
| Local GRU |2.450±1.290|
| Centralized GRU |3.434±1.088|
| FedAvg |3.674±1.894|
| FedProx |3.680±1.893|

These are pipeline observations, not research conclusions. One node has only
one test window. No method is automatically promoted to live forecasting.
The model has1025float32 parameters (4100tensor bytes); FedAvg/FedProx each
exchange738000logical tensor bytes per seed run, including validation broadcasts.
Network/TLS/protocol overhead and centralized raw-data upload are not measured.

## Obsidian

Study notes:
`/home/tuan/Documents/Notes/ObsidianVault/Project/Scl/DACN/Thực nghiệm/`.
Includes the experiment index, proposed S0–S5 scenarios/protocol, metric
interpretation, measured pilot note and6figures exported asSVG/PNG/PDF with
CSV/JSON. Wiki links are checked. Existing assignment/meeting notes are preserved.
