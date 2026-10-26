"""Artificial traffic-like series for pipeline checks, not research evidence."""

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset


SPEED_SCALE = 80.0


def client_loaders(config: dict, client_id: int, round_id: int = 0):
    settings = config["dataset"]
    steps, history = settings["num_steps"], settings["hist_len"]
    horizons = np.asarray(settings["horizons"], dtype=np.int64)
    generator = np.random.default_rng(config["seed"] + client_id)
    time = np.arange(steps, dtype=np.float64)
    phase = 2 * np.pi * time * settings["sample_minutes"] / (24 * 60)
    mean, amplitude = 20.0 + client_id * 12.0, 5.0 + client_id * 2.0
    speed = np.clip(
        mean + amplitude * np.sin(phase + client_id * 0.6)
        + 0.3 * amplitude * np.cos(2 * phase)
        + generator.normal(0, 1.2, steps), 1, SPEED_SCALE,
    ).astype(np.float32)
    features = np.column_stack([speed / SPEED_SCALE, np.sin(phase), np.cos(phase)]).astype(np.float32)
    train_end, val_end = int(steps * 0.7), int(steps * 0.8)
    partitions = {"train": [], "validation": [], "test": []}
    for anchor in range(history - 1, steps - int(horizons.max())):
        target_steps = anchor + horizons
        if target_steps[-1] < train_end:
            split = "train"
        elif target_steps[0] >= train_end and target_steps[-1] < val_end:
            split = "validation"
        elif target_steps[0] >= val_end:
            split = "test"
        else:
            continue
        partitions[split].append((features[anchor-history+1:anchor+1], speed[target_steps] / SPEED_SCALE))
    # Quantity skew with shared time boundaries, in addition to different speeds.
    partitions["train"] = partitions["train"][::client_id + 1]
    loaders = {}
    for split, rows in partitions.items():
        if not rows:
            raise ValueError(f"No {split} windows; increase dataset.num_steps")
        x = torch.from_numpy(np.stack([row[0] for row in rows]))
        y = torch.from_numpy(np.stack([row[1] for row in rows]))
        loaders[split] = DataLoader(
            TensorDataset(x, y), batch_size=config["train"]["batch_size"],
            shuffle=split == "train", num_workers=0,
            generator=torch.Generator().manual_seed(config["seed"] + client_id * 100 + round_id),
        )
    return loaders
