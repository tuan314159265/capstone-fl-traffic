"""Run a bounded Flower FedAvg smoke workflow and save reproducible artifacts."""

import importlib.metadata
import math
from pathlib import Path
import random
import resource
import time

import numpy as np
import torch
from flwr.app import ArrayRecord, ConfigRecord, MetricRecord

from src.data.loaders import client_loaders
from src.fl.client import make_client_app
from src.fl.sequential_grid import SequentialGrid
from src.fl.strategies.fedavg import CheckedFedAvg
from src.models.forecast import evaluate_model, make_model


def run_fedavg(config, output_dir):
    started = time.monotonic()
    seed = config["seed"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    model = make_model(config)
    initial = {name: tensor.detach().clone() for name, tensor in model.state_dict().items()}
    count = config["fl"]["num_clients"]
    grid = SequentialGrid(make_client_app(config), count, seed)
    strategy = CheckedFedAvg(count)
    validation_history = {}
    real = config['dataset']['name'] == 'tomtom-snapshot'
    best = {'mae': float('inf'), 'round': None, 'state': None}

    def evaluate_global(round_id, arrays):
        model.load_state_dict(arrays.to_torch_state_dict())
        per_client = [evaluate_model(model, client_loaders(config, i)["validation"], config)
                      for i in range(count)]
        validation_history[round_id] = per_client
        score = float(np.mean([item['mae_kmh'] for item in per_client]))
        if round_id > 0 and score < best['mae']:
            best.update(mae=score, round=round_id,
                        state={k: v.detach().clone() for k, v in model.state_dict().items()})
        return MetricRecord({"mae_kmh": score})

    result = strategy.start(
        grid=grid, initial_arrays=ArrayRecord(initial),
        num_rounds=config["fl"]["num_rounds"], timeout=120,
        train_config=ConfigRecord({"lr": config["train"]["lr"]}),
        evaluate_fn=evaluate_global,
    )
    expected_rounds = list(range(1, config["fl"]["num_rounds"] + 1))
    if strategy.checked_rounds != expected_rounds:
        raise RuntimeError("Not all aggregation rounds completed")
    if len(grid.calls) != count * len(expected_rounds) * 2:
        raise RuntimeError("A training or validation client call is missing")
    final = result.arrays.to_torch_state_dict()
    if not any(not torch.equal(initial[name], final[name]) for name in initial):
        raise RuntimeError("Training did not change any model weights")
    if any(not torch.isfinite(tensor).all() for tensor in final.values()):
        raise RuntimeError("Model contains non-finite weights")
    if real:
        final = best['state']
    model.load_state_dict(final)
    final_test = []
    partition_sizes = []
    for client_id in range(count):
        loaders = client_loaders(config, client_id)
        final_test.append({"client_id": client_id,
                           **evaluate_model(model, loaders["test"], config)})
        if real:
            from src.data.traffic import SPEED_SCALE
            errors = []
            for x, y in loaders['test']:
                errors.extend(((x[:, -1, 0:1] - y).abs() * SPEED_SCALE).tolist())
            final_test[-1]['persistence_mae_kmh'] = float(np.mean(errors))
        partition_sizes.append({"client_id": client_id,
                                **{name: len(loader.dataset) for name, loader in loaders.items()}})
    if not all(math.isfinite(item["mae_kmh"]) for item in final_test):
        raise RuntimeError("Non-finite test metrics")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / "model.pt"
    torch.save({"state_dict": final, "config": config, "synthetic_data": not real,
                "selected_round": best['round'] if real else expected_rounds[-1]}, checkpoint)
    restored = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if not all(torch.equal(final[name], restored["state_dict"][name]) for name in final):
        raise RuntimeError("Checkpoint round-trip changed model weights")
    return {
        "status": "passed", "experiment": config["experiment"],
        "data_source": "tomtom_postgis_snapshot" if real else "synthetic_only_not_tomtom", "research_result": False,
        "selected_round": best['round'] if real else expected_rounds[-1],
        "selection": "lowest macro validation MAE among trained rounds (1..N)" if real else "last round",
        "initial_validation_mae_kmh": float(np.mean([m['mae_kmh'] for m in validation_history[0]])),
        "selected_validation_mae_kmh": best['mae'] if real else None,
        "test_mae_kmh": float(np.mean([m['mae_kmh'] for m in final_test])),
        "persistence_test_mae_kmh": float(np.mean([m['persistence_mae_kmh'] for m in final_test])) if real else None,
        "runtime": "single_process_sequential_message_adapter", "device": "cpu",
        "versions": {name: importlib.metadata.version(name) for name in ["flwr", "torch", "numpy", "PyYAML"]},
        "config": config, "partition_sizes": partition_sizes,
        "aggregation_rounds_verified": strategy.checked_rounds,
        "model_parameters": sum(tensor.numel() for tensor in final.values()),
        "logical_model_bytes": grid.logical_model_bytes,
        "logical_bytes_note": "Tensor payload sizes only; no network or protocol overhead measured",
        "client_calls": grid.calls, "validation_history": validation_history,
        "final_test": final_test, "checkpoint": "model.pt",
        "elapsed_seconds": time.monotonic() - started,
        "peak_process_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }
