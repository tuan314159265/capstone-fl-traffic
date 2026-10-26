"""Use Flower's real FedAvg and check sample-weighted model aggregation."""

import numpy as np
from flwr.serverapp.strategy import FedAvg


class CheckedFedAvg(FedAvg):
    def __init__(self, num_clients):
        super().__init__(fraction_train=1.0, fraction_evaluate=1.0,
                         min_train_nodes=num_clients, min_evaluate_nodes=num_clients,
                         min_available_nodes=num_clients)
        self.num_clients = num_clients
        self.checked_rounds = []

    def aggregate_train(self, server_round, replies):
        replies = list(replies)
        if len(replies) != self.num_clients or any(reply.has_error() for reply in replies):
            raise RuntimeError("A client update is missing or failed")
        weights = [float(reply.content["metrics"]["num-examples"]) for reply in replies]
        updates = [{name: tensor.detach().clone()
                    for name, tensor in reply.content["arrays"].to_torch_state_dict().items()}
                   for reply in replies]
        arrays, metrics = super().aggregate_train(server_round, replies)
        if arrays is None:
            raise RuntimeError("FedAvg did not return model weights")
        for name, actual in arrays.to_torch_state_dict().items():
            expected = np.average(np.stack([state[name].numpy() for state in updates]), axis=0, weights=weights)
            np.testing.assert_allclose(actual.numpy(), expected, rtol=1e-5, atol=1e-7)
        self.checked_rounds.append(server_round)
        return arrays, metrics
