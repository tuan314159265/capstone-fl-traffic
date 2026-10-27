"""Data integrity checks for the real-data forecasting split (stdlib only)."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from src.data.traffic import prepare

class TrafficWindows(unittest.TestCase):
    def test_segment_dedup_and_global_target_split(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'snapshot.csv'
            rows=[]
            origin=round(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()/900)
            for segment in ['a','b']:
                for index in range(19):
                    row={'segment_key':segment,'collected_at':datetime.fromtimestamp((origin+index)*900,timezone.utc).isoformat(),
                         'current_speed_kmh':20+index,'confidence':.9}
                    rows.extend([row,row.copy()])
            # Discontinuous series must not be interpolated to eligible windows.
            rows.extend([dict(row,segment_key='gap') for row in rows if int(datetime.fromisoformat(row['collected_at']).timestamp()/900)%2==0])
            rows.append(dict(rows[0], confidence=.2))
            rows.append(dict(rows[0], collected_at='2026-01-01T00:05:00+00:00'))
            with path.open('w') as handle:
                writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            clients,manifest=prepare(str(path))
            self.assertEqual(len(clients),2)
            self.assertGreater(manifest['rejected']['duplicate_segment_slot'],0)
            self.assertEqual(manifest['rejected']['invalid_speed_or_confidence'],1)
            self.assertEqual(manifest['rejected']['off_grid_or_future'],1)
            self.assertEqual(len(manifest['excluded_clients']),1)
            for client in clients:
                self.assertEqual({k:len(v) for k,v in client['partitions'].items()},{'train':6,'validation':2,'test':3})
                target_sets=[{t for _,_,ts in client['partitions'][k] for t in ts} for k in ['train','validation','test']]
                self.assertLess(max(target_sets[0]),min(target_sets[1]))
                self.assertLess(max(target_sets[1]),min(target_sets[2]))
                for partition in client['partitions'].values():
                    for x,y,targets in partition:
                        self.assertEqual(len(x),8)
                        self.assertAlmostEqual(y[0]-x[-1][0],1/80)

if __name__=='__main__': unittest.main()
