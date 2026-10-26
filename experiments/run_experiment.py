"""Run the explicitly synthetic FedAvg CPU smoke configuration."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/fedavg_smoke.yaml")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/fedavg_smoke")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text())
    if config["dataset"]["name"] != "synthetic-traffic-smoke" or config["fl"]["strategy"] != "fedavg":
        parser.error("Only the synthetic FedAvg smoke config is implemented; real-data experiments are not ready.")
    if config["train"]["device"] != "cpu":
        parser.error("The bounded smoke runner currently supports CPU only.")
    if not 2 <= config["fl"]["num_clients"] <= 5 or not 1 <= config["fl"]["num_rounds"] <= 10:
        parser.error("Smoke runs require 2-5 clients and 1-10 rounds.")
    print("SYNTHETIC DATA: testing pipeline execution, not traffic forecast quality.", flush=True)
    from src.fl.server import run_fedavg
    report = run_fedavg(config, args.output_dir)
    (args.output_dir / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ["status", "data_source", "aggregation_rounds_verified",
                                                 "elapsed_seconds", "peak_process_rss_mib"]}), flush=True)


if __name__ == "__main__":
    main()
