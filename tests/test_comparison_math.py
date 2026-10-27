"""Quality/audit invariants and FedProx mathematics; Torch checks run on AWS."""
from datetime import datetime,timezone
import importlib.util
import math
import unittest
from src.data.quality import clean_observations,js_divergence
from src.metrics.evaluation import aggregate_nodes


class AuditMetrics(unittest.TestCase):
    def test_filters_and_js(self):
        base={'segment_key':'a','query_point_id':'a','collected_at':'2026-01-01T00:00:00+00:00',
              'current_speed_kmh':'20','confidence':'.9'}
        rows=[base,dict(base,confidence='1.5'),dict(base,confidence='nan'),dict(base,collected_at='2026-01-01T00:00:00')]
        accepted,rejected=clean_observations(rows,as_of=datetime(2026,1,2,tzinfo=timezone.utc).timestamp())
        self.assertEqual(len(accepted),1);self.assertEqual(sum(rejected.values()),3)
        self.assertEqual(js_divergence([1,0],[1,0]),0)
        self.assertEqual(js_divergence([1,0],[0,1]),1)
        self.assertIsNone(js_divergence([0,0],[1,0]))

    def test_macro_micro_rmse_and_worst_direction(self):
        result=aggregate_nodes([{'mae_kmh':2,'rmse_kmh':3,'samples':2},{'mae_kmh':4,'rmse_kmh':5,'samples':6}])
        self.assertEqual(result['macro_mae_kmh'],3);self.assertEqual(result['micro_mae_kmh'],3.5)
        self.assertAlmostEqual(result['rmse_kmh'],math.sqrt(21))
        self.assertEqual(result['worst_node_mae_kmh'],4);self.assertEqual(result['node_mae_std_kmh'],1)


@unittest.skipUnless(importlib.util.find_spec('torch'),'Torch only installed in AWS training image')
class FedProxMath(unittest.TestCase):
    def test_proximal_gradient_and_zero_mu_equivalence(self):
        import torch
        from torch.utils.data import DataLoader,TensorDataset
        from src.fl.strategies.fedprox import proximal_penalty
        from src.models.forecast import train_local
        parameter=torch.tensor([1.,2.],requires_grad=True)
        penalty=proximal_penalty([parameter],[torch.zeros(2)],.4)
        self.assertAlmostEqual(float(penalty.detach()),1.)
        penalty.backward();torch.testing.assert_close(parameter.grad,torch.tensor([.4,.8]))
        torch.manual_seed(42)
        left=torch.nn.Linear(3,1);right=torch.nn.Linear(3,1);right.load_state_dict(left.state_dict())
        dataset=TensorDataset(torch.randn(8,3),torch.randn(8,1))
        train_local(left,DataLoader(dataset,batch_size=4),2,.003)
        train_local(right,DataLoader(dataset,batch_size=4),2,.003,proximal_mu=0.)
        for x,y in zip(left.parameters(),right.parameters()):self.assertTrue(torch.equal(x,y))


if __name__=='__main__':unittest.main()
