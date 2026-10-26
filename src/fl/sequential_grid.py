"""In-process message adapter for small CPU smoke runs.

This exercises Flower's ClientApp handlers and built-in strategy. It does not
test SuperLink, Ray scheduling, network transport, TLS, or separate machines.
"""

import copy
import time
import uuid

from flwr.app import Context, Message, Metadata, RecordDict
from flwr.supercore.task_identity import TaskIdentity


class SequentialGrid:
    def __init__(self, app, num_clients, seed):
        # In a deployment, the Flower runtime sets this process-local identity.
        # This pinned-version smoke adapter supplies it for its single process.
        TaskIdentity.run_id = 1
        TaskIdentity.node_id = 1
        TaskIdentity.task_id = 1
        self.app = app
        self.contexts = {
            node_id: Context(run_id=1, node_id=node_id,
                             node_config={"partition-id": node_id - 100},
                             state=RecordDict(), run_config={"seed": seed})
            for node_id in range(100, 100 + num_clients)
        }
        self.logical_model_bytes = 0
        self.calls = []

    def get_node_ids(self):
        return list(self.contexts)

    @staticmethod
    def array_bytes(message):
        if "arrays" not in message.content:
            return 0
        return sum(tensor.numel() * tensor.element_size()
                   for tensor in message.content["arrays"].to_torch_state_dict().values())

    def send_and_receive(self, messages, *, timeout=None):
        replies = []
        started = time.monotonic()
        for message in messages:
            if timeout is not None and time.monotonic() - started > timeout:
                raise TimeoutError("Sequential smoke run exceeded round timeout")
            source = message.metadata
            node_id = source.dst_node_id
            metadata = Metadata(
                run_id=source.run_id, message_id=str(uuid.uuid4()),
                src_node_id=source.src_node_id, dst_node_id=node_id,
                reply_to_message_id=source.reply_to_message_id,
                group_id=source.group_id, created_at=source.created_at,
                ttl=source.ttl, message_type=source.message_type,
                src_task_id=source.src_task_id, dst_task_id=node_id,
            )
            request = Message(content=copy.deepcopy(message.content), metadata=metadata)
            self.logical_model_bytes += self.array_bytes(request)
            TaskIdentity.node_id, TaskIdentity.task_id = node_id, node_id
            try:
                reply = self.app(request, self.contexts[node_id])
            finally:
                TaskIdentity.node_id, TaskIdentity.task_id = 1, 1
            if reply.has_error():
                raise RuntimeError(f"Client {node_id} returned an error")
            self.logical_model_bytes += self.array_bytes(reply)
            self.calls.append({"node_id": node_id, "type": request.metadata.message_type,
                               "round": int(request.content["config"]["server-round"]),
                               "metrics": dict(reply.content["metrics"])})
            replies.append(reply)
        return replies
