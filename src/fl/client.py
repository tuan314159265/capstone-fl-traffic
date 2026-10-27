"""Flower Message API handlers for isolated synthetic client partitions."""

import torch
from flwr.app import ArrayRecord, Message, MetricRecord, RecordDict
from flwr.clientapp import ClientApp

from src.data.loaders import client_loaders
from src.models.forecast import evaluate_model, make_model, train_local


def make_client_app(config):
    app = ClientApp()

    @app.train()
    def train(message, context):
        client_id = int(context.node_config["partition-id"])
        round_id = int(message.content["config"]["server-round"])
        torch.manual_seed(config["seed"] + client_id * 100 + round_id)
        model = make_model(config)
        model.load_state_dict(message.content["arrays"].to_torch_state_dict())
        loader = client_loaders(config, client_id, round_id)["train"]
        mu = config['fl'].get('proximal_mu', 0.0) if config['fl']['strategy'] == 'fedprox' else 0.0
        loss = train_local(model, loader, config["fl"]["local_epochs"], float(message.content["config"]["lr"]), proximal_mu=mu)
        return Message(content=RecordDict({
            "arrays": ArrayRecord(model.state_dict()),
            "metrics": MetricRecord({"train_loss": loss, "num-examples": len(loader.dataset)}),
        }), reply_to=message)

    @app.evaluate()
    def evaluate(message, context):
        client_id = int(context.node_config["partition-id"])
        model = make_model(config)
        model.load_state_dict(message.content["arrays"].to_torch_state_dict())
        loader = client_loaders(config, client_id)["validation"]
        metrics = evaluate_model(model, loader, config)
        metrics["num-examples"] = len(loader.dataset)
        return Message(content=RecordDict({"metrics": MetricRecord(metrics)}), reply_to=message)

    return app
