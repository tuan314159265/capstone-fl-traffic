"""CPU forecasting model and shared train/evaluation functions."""

import torch
from torch import nn

from src.data.synthetic import SPEED_SCALE
from src.models.backbone import GRUBackbone
from src.models.head import ForecastHead


def make_model(config):
    hidden = config["model"]["hidden_dim"]
    return nn.Sequential(GRUBackbone(hidden_dim=hidden), ForecastHead(hidden, len(config["dataset"]["horizons"])))


def train_local(model, loader, epochs: int, learning_rate: float, proximal_mu: float = 0.0):
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    reference = [p.detach().clone() for p in model.parameters()] if proximal_mu else None
    total, examples = 0.0, 0
    for _ in range(epochs):
        for x, y in loader:
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.mse_loss(model(x), y)
            if reference is not None:
                from src.fl.strategies.fedprox import proximal_penalty
                loss = loss + proximal_penalty(model.parameters(), reference, proximal_mu)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite training loss")
            loss.backward()
            optimizer.step()
            total += loss.item() * len(y)
            examples += len(y)
    return total / examples


def evaluate_model(model, loader, config):
    model.eval()
    squared, absolute, examples = 0.0, torch.zeros(len(config["dataset"]["horizons"])), 0
    with torch.no_grad():
        for x, y in loader:
            error = model(x) - y
            squared += float(error.square().mean()) * len(y)
            absolute += error.abs().sum(dim=0) * SPEED_SCALE
            examples += len(y)
    values = absolute / examples
    metrics = {"loss": squared / examples, "mae_kmh": float(values.mean())}
    for horizon, mae in zip(config["dataset"]["horizons"], values.tolist()):
        minutes = horizon * config["dataset"]["sample_minutes"]
        metrics[f"mae_{minutes}m_kmh"] = mae
    return metrics
