"""Forecasting head, currently aggregated with the backbone by FedAvg."""

from torch import nn


class ForecastHead(nn.Module):
    def __init__(self, hidden_dim: int, num_horizons: int):
        super().__init__()
        self.output = nn.Linear(hidden_dim, num_horizons)

    def forward(self, representation):
        return self.output(representation)
