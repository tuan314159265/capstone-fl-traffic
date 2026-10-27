"""Credential-free collection audit; distinguish raw points from road segments."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path
import statistics


def clean_observations(rows, interval=900, as_of=None):
    now = datetime.now(timezone.utc).timestamp() if as_of is None else as_of
    accepted, rejected = [], Counter()
    for row in rows:
        try:
            stamp = datetime.fromisoformat(row['collected_at'])
            if stamp.tzinfo is None:raise ValueError('Timezone required')
            timestamp=stamp.timestamp()
            speed, confidence=float(row['current_speed_kmh']),float(row['confidence'])
            slot=round(timestamp/interval)
            if not math.isfinite(speed) or speed<0 or not math.isfinite(confidence) or not .7<=confidence<=1:
                rejected['invalid_speed_or_confidence']+=1;continue
            if timestamp>now or abs(timestamp-slot*interval)>180:
                rejected['off_grid_or_future']+=1;continue
            accepted.append({'row':row,'timestamp':timestamp,'slot':slot,'speed':speed,'confidence':confidence,
                             'segment_key':row['segment_key'],'point_id':row.get('query_point_id','')})
        except (KeyError,ValueError,TypeError,OverflowError):rejected['invalid_fields']+=1
    return accepted,rejected


def histogram(values):
    counts=[0]*12
    for value in values:counts[min(11,max(0,int(value/10)))]+=1
    return counts


def js_divergence(left,right):
    a,b=sum(left),sum(right)
    if not a or not b:return None
    p,q=[v/a for v in left],[v/b for v in right]
    mid=[(x+y)/2 for x,y in zip(p,q)]
    return .5*sum(x*math.log2(x/m) if x else 0 for x,m in zip(p,mid))+.5*sum(x*math.log2(x/m) if x else 0 for x,m in zip(q,mid))


def audit(path, active_ids=None, manifest=None, as_of=None):
    content=Path(path).read_bytes()
    rows=list(csv.DictReader(content.decode().splitlines()))
    now=datetime.now(timezone.utc).timestamp() if as_of is None else as_of
    accepted,rejected=clean_observations(rows,as_of=now)
    active=set(active_ids) if active_ids is not None else {r['query_point_id'] for r in rows}
    chosen=[r for r in accepted if r['point_id'] in active]
    grouped=defaultdict(dict);points=defaultdict(set);names={};groups=defaultdict(set)
    duplicates=0
    for item in chosen:
        key=item['segment_key'];slot=item['slot'];row=item['row']
        points[key].add(item['point_id']);groups[key].add(row.get('collection_group','unknown'))
        names[item['point_id']]=row.get('name') or item['point_id']
        if slot in grouped[key]:duplicates+=1
        if slot not in grouped[key] or item['timestamp']>grouped[key][slot]['timestamp']:grouped[key][slot]=item
    train_cut=datetime.fromisoformat(manifest['train_targets_before']).timestamp()/900 if manifest else None
    train_hist={key:histogram(v['speed'] for slot,v in items.items() if train_cut is None or slot<train_cut)
                for key,items in grouped.items()}
    pooled=[sum(values[i] for values in train_hist.values()) for i in range(12)]
    eligibility={c['segment_key']:c for c in manifest['clients']} if manifest else {}
    excluded={c['segment_key']:c for c in manifest['excluded_clients']} if manifest else {}
    iso=lambda slot:datetime.fromtimestamp(slot*900,timezone.utc).isoformat()
    now_slot=math.floor(now/900)
    nodes=[]
    for key,items in sorted(grouped.items()):
        slots=sorted(items);first,last=slots[0],slots[-1]
        values=[items[s]['speed'] for s in slots]
        longest=current=1;runs=[];run_start=previous=first
        for slot in slots[1:]:
            if slot==previous+1:current+=1
            else:runs.append((run_start,previous));current=1;run_start=slot
            longest=max(longest,current);previous=slot
        runs.append((run_start,previous))
        start24=max(first,now_slot-95)
        expected=max(0,now_slot-first+1);expected24=max(0,now_slot-start24+1)
        received24=sum(start24<=slot<=now_slot for slot in slots)
        missing_ranges=[]
        for (_,end),(start,_) in zip(runs,runs[1:]):
            missing_ranges.append({'start':iso(end+1),'end':iso(start-1),'slots':start-end-1})
        if last<now_slot:missing_ranges.append({'start':iso(last+1),'end':iso(now_slot),'slots':now_slot-last})
        before=[items[s]['speed'] for s in slots if now_slot-95<=s<=now_slot-48]
        after=[items[s]['speed'] for s in slots if now_slot-47<=s<=now_slot]
        # A descriptive drift proxy is hidden unless both halves have >=12 observations.
        shift=js_divergence(histogram(before),histogram(after)) if min(len(before),len(after))>=12 else None
        participation=eligibility.get(key) or excluded.get(key)
        sizes=participation.get('sizes',{}) if participation else {}
        nodes.append({'segment_key':key,'name':names[sorted(points[key])[0]],'point_ids':sorted(points[key]),
            'groups':sorted(groups[key]),'valid_slots':len(slots),'expected_slots':expected,
            'coverage':min(1,len(slots)/expected) if expected else None,
            'coverage_24h':received24/expected24 if expected24 else None,
            'expected_slots_24h':expected24,'received_slots_24h':received24,
            'first_at':iso(first),'last_at':iso(last),'span_hours':(last-first)*.25,
            'age_minutes':max(0,(now-max(v['timestamp'] for v in items.values()))/60),
            'longest_run':longest,'largest_gap_slots':max((g['slots'] for g in missing_ranges),default=0),
            'missing_ranges':missing_ranges[:10], 'mean_speed_kmh':statistics.mean(values),
            'std_speed_kmh':statistics.pstdev(values),'mean_confidence':statistics.mean(v['confidence'] for v in items.values()),
            'train_js_divergence':js_divergence(train_hist[key],pooled) if train_cut is not None else None,
            'shift_js_12h':shift,'train_samples':sizes.get('train',0),'validation_samples':sizes.get('validation',0),
            'test_samples':sizes.get('test',0),'eligible':key in eligibility,
            'candidate_windows_15m':sum(max(0,end-start+1-8) for start,end in runs),
            'candidate_windows_60m':sum(max(0,end-start+1-11) for start,end in runs),
            'histogram_train':train_hist[key]})
    point_counts=Counter(r['query_point_id'] for r in rows)
    field_nulls={field:sum(not r.get(field) for r in rows) for field in
                 ['current_speed_kmh','free_flow_speed_kmh','confidence','road_closed']}
    return {'schema_version':1,'as_of':datetime.fromtimestamp(now,timezone.utc).isoformat(),
        'snapshot_sha256':hashlib.sha256(content).hexdigest(),'raw_rows':len(rows),
        'raw_points':len(point_counts),'active_points':len(active),'segments':len(nodes),
        'accepted_point_rows':len(accepted),'active_valid_point_rows':len(chosen),
        'distinct_segment_slots':sum(len(v) for v in grouped.values()),'duplicate_segment_slots':duplicates,
        'rejected':dict(rejected),'null_fields':field_nulls,'eligible_clients':len(eligibility),
        'train_only_distribution':True,'train_targets_before':manifest.get('train_targets_before') if manifest else None,
        'coverage_scope':'From first valid observation to audit time; 24h coverage starts no earlier than first observation. Not API uptime.',
        'freshness_scope':'Collection timestamp only, not provider source-update age.',
        'research_ready':False,'nodes':nodes}
