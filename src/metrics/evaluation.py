"""Forecast/fairness metrics. Larger worst-node MAE means worse performance."""
import math
import statistics


def aggregate_nodes(nodes):
    values=[node['mae_kmh'] for node in nodes]
    count=sum(node['samples'] for node in nodes)
    tail=sorted(values,reverse=True)[:max(1,math.ceil(len(values)*.1))]
    return {'macro_mae_kmh':statistics.mean(values),
        'micro_mae_kmh':sum(node['mae_kmh']*node['samples'] for node in nodes)/count,
        'rmse_kmh':math.sqrt(sum(node['rmse_kmh']**2*node['samples'] for node in nodes)/count),
        'worst_node_mae_kmh':max(values),'worst_decile_mae_kmh':statistics.mean(tail),
        'node_mae_std_kmh':statistics.pstdev(values),'test_samples':count,
        'worst_decile_nodes':len(tail)}
