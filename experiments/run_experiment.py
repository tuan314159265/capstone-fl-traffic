"""Run a bounded synthetic smoke or real TomTom FedAvg pilot."""

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
    real = config["dataset"]["name"] == "tomtom-snapshot"
    if config["dataset"]["name"] not in {"synthetic-traffic-smoke", "tomtom-snapshot"} or config["fl"]["strategy"] != "fedavg":
        parser.error("Unsupported dataset or strategy")
    if real:
        from src.data.traffic import prepared
        clients, manifest = prepared(config)
        config["fl"]["num_clients"] = len(clients)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "data_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    if config["train"]["device"] != "cpu":
        parser.error("The bounded smoke runner currently supports CPU only.")
    if not 2 <= config["fl"]["num_clients"] <= 30 or not 1 <= config["fl"]["num_rounds"] <= 10:
        parser.error("Runs require 2-30 clients and 1-10 rounds.")
    print("REAL TOMTOM: small-data pilot, not a research benchmark." if real else "SYNTHETIC DATA: pipeline check only.", flush=True)
    from src.fl.server import run_fedavg
    report = run_fedavg(config, args.output_dir)
    (args.output_dir / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ["status", "data_source", "aggregation_rounds_verified",
                                                 "elapsed_seconds", "peak_process_rss_mib"]}), flush=True)


if __name__ == "__main__":
    main()
