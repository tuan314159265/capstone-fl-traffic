"""Causal, segment-deduplicated TomTom windows; no gap interpolation."""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import math
from pathlib import Path
from src.data.quality import clean_observations

SPEED_SCALE = 80.0

@lru_cache(maxsize=4)
def prepare(path, history=8, horizons=(1,), sample_minutes=15, active_ids=None):
    content = Path(path).read_bytes()
    interval = sample_minutes * 60
    segments = defaultdict(dict)
    rows = list(csv.DictReader(content.decode().splitlines()))
    accepted, rejected = clean_observations(rows, interval)
    for item in accepted:
        row, timestamp, speed, slot = item['row'], item['timestamp'], item['speed'], item['slot']
        if active_ids is not None and item['point_id'] not in active_ids:
            rejected['inactive_query_point'] += 1
            continue
        previous = segments[row['segment_key']].get(slot)
        if previous is not None:
            rejected['duplicate_segment_slot'] += 1
        if previous is None or timestamp > previous[0]:
            segments[row['segment_key']][slot] = (timestamp, speed)
    candidates = {}
    for key, slots in sorted(segments.items()):
        windows = []
        for anchor in sorted(slots):
            required = range(anchor-history+1, anchor+max(horizons)+1)
            if all(step in slots for step in required):
                features = []
                for step in range(anchor-history+1, anchor+1):
                    phase = 2*math.pi*((step*interval+7*3600) % 86400)/86400
                    features.append([slots[step][1]/SPEED_SCALE, math.sin(phase), math.cos(phase)])
                targets = [anchor+h for h in horizons]
                windows.append((features, [slots[t][1]/SPEED_SCALE for t in targets], targets))
        candidates[key] = windows
    times = sorted({t for windows in candidates.values() for _,_,targets in windows for t in targets})
    if len(times) < 5:
        raise ValueError('Not enough distinct target times for chronological train/validation/test')
    train_cut, validation_cut = times[int(len(times)*.6)], times[int(len(times)*.8)]
    clients, excluded = [], []
    for key, windows in candidates.items():
        partitions = {'train': [], 'validation': [], 'test': []}
        for x,y,targets in windows:
            split = ('train' if max(targets)<train_cut else
                     'validation' if min(targets)>=train_cut and max(targets)<validation_cut else
                     'test' if min(targets)>=validation_cut else None)
            if split:
                partitions[split].append((x,y,targets))
        sizes = {name:len(rows) for name,rows in partitions.items()}
        if sizes['train'] >= 3 and sizes['validation'] >= 1 and sizes['test'] >= 1:
            clients.append({'segment_key':key, 'partitions':partitions})
        else:
            excluded.append({'segment_key':key, 'sizes':sizes, 'reason':'minimum train=3, validation=1, test=1 not met'})
    if len(clients)<2:
        raise ValueError('Fewer than two eligible segment clients; collect more continuous data')
    def iso(slot):
        return datetime.fromtimestamp(slot*interval,timezone.utc).isoformat()
    manifest = {'sha256':hashlib.sha256(content).hexdigest(), 'raw_rows':len(rows),
        'segment_count':len(segments), 'rejected':dict(rejected), 'excluded_clients':excluded,
        'train_targets_before':iso(train_cut), 'validation_targets_before':iso(validation_cut),
        'test_targets_from':iso(validation_cut), 'sample_minutes':sample_minutes,
        'history':history, 'horizons':list(horizons),
        'active_query_points':list(active_ids) if active_ids is not None else None,
        'split_policy':'Global chronological target boundaries; past context may cross a boundary. No target timestamp overlaps partitions. No interpolation.',
        'clients':[{'client_id':i,'segment_key':c['segment_key'],
             'sizes':{k:len(v) for k,v in c['partitions'].items()},
             'target_ranges':{k:[iso(min(t for _,_,ts in v for t in ts)),iso(max(t for _,_,ts in v for t in ts))] for k,v in c['partitions'].items()}}
            for i,c in enumerate(clients)]}
    return clients, manifest


def prepared(config):
    d = config['dataset']
    active=tuple(sorted(d['active_query_points'])) if d.get('active_query_points') is not None else None
    return prepare(d['path'], d['hist_len'], tuple(d['horizons']), d['sample_minutes'], active)


def client_loaders(config, client_id, round_id=0):
    import numpy as np
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    client = prepared(config)[0][client_id]
    return {name:DataLoader(TensorDataset(
        torch.tensor(np.asarray([x for x,_,_ in rows]),dtype=torch.float32),
        torch.tensor(np.asarray([y for _,y,_ in rows]),dtype=torch.float32)),
        batch_size=config['train']['batch_size'], shuffle=name=='train', num_workers=0,
        generator=torch.Generator().manual_seed(config['seed']+client_id*100+round_id))
        for name,rows in client['partitions'].items()}
