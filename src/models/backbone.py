"""Small shared temporal backbone for the first FedAvg pipeline check."""

from torch import nn


class GRUBackbone(nn.Module):
    def __init__(self, input_dim: int = 3, hidden_dim: int = 16):
        super().__init__()
        self.gru = nn.GRU(input_dim, hidden_dim, batch_first=True)

    def forward(self, inputs):
        sequence, _ = self.gru(inputs)
        return sequence[:, -1, :]
