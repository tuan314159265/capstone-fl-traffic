"""Frozen-snapshot pilot comparison; no synthetic substitution or test tuning."""
import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.data.traffic import prepared
from src.data.quality import audit


def mean_std(values):
    return {'mean':statistics.mean(values),'std':statistics.stdev(values) if len(values)>1 else 0.0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();config=json.loads(args.config.read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    if not 1<=len(config['seeds'])<=5 or not 1<=config['fl']['num_rounds']<=10:
        raise ValueError('Pilot limited to 1-5 seeds, 1-10 rounds')
    active=[]
    for group in json.loads((ROOT/'infra/aws/collection_groups.json').read_text())['groups']:
        for point in json.loads((ROOT/group['points']).read_text()):
            active.append(point['intersection_id']+':'+point['approach_label'])
    config['dataset']['active_query_points']=sorted(active)
    _,manifest=prepared(config)
    quality=audit(config['dataset']['path'],active,manifest)
    (args.output/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (args.output/'data_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (args.output/'quality.json').write_text(json.dumps(quality,indent=2)+'\n')
    runs=[]
    for method in config['methods']:
        for seed in config['seeds']:
            output=args.output/f'{method}_seed{seed}'
            with (args.output/f'{method}_seed{seed}.log').open('w') as log:
                subprocess.run([sys.executable,'experiments/comparison_worker.py','--config',str(args.output/'config.json'),
                    '--method',method,'--seed',str(seed),'--output',str(output)],stdout=log,stderr=subprocess.STDOUT,
                    timeout=180,check=True,cwd=ROOT)
            item=json.loads((output/'metrics.json').read_text())
            if item['snapshot_sha256']!=manifest['sha256']:raise RuntimeError('Worker snapshot changed')
            runs.append(item)
            print(json.dumps({'method':method,'seed':seed,'macro_mae':item['macro_mae_kmh']}),flush=True)
    metric_keys=['macro_mae_kmh','micro_mae_kmh','rmse_kmh','worst_node_mae_kmh','worst_decile_mae_kmh','node_mae_std_kmh']
    names={'persistence':'Persistence','local':'Local GRU','centralized':'Centralized GRU','fedavg':'FedAvg','fedprox':'FedProx'}
    methods=[];curves=[]
    for method in config['methods']:
        selected=[r for r in runs if r['method']==method]
        methods.append({'id':method,'name':names[method],'status':'measured_pilot','seeds':len(selected),
            'metrics':{key:mean_std([r[key] for r in selected]) for key in metric_keys},
            'logical_model_bytes':mean_std([r['logical_model_bytes'] for r in selected]),
            'train_upload_bytes':selected[0]['train_upload_bytes'],
            'train_download_bytes':selected[0]['train_download_bytes'],
            'validation_download_bytes':selected[0]['validation_download_bytes'],
            'elapsed_seconds':mean_std([r['elapsed_seconds'] for r in selected]),
            'trained_example_visits':selected[0]['trained_example_visits']})
        rounds=defaultdict(list)
        for item in selected:
            for point in item['validation_history']:rounds[point['round']].append(point['validation_mae_kmh'])
        curves.append({'method':method,'points':[{'round':round_id,**mean_std(values)} for round_id,values in sorted(rounds.items())]})
    per_node=[]
    quality_by_key={n['segment_key']:n for n in quality['nodes']}
    for client in manifest['clients']:
        key=client['segment_key'];stats=quality_by_key[key]
        entries={method:mean_std([next(n['mae_kmh'] for n in item['nodes'] if n['segment_key']==key)
                                 for item in runs if item['method']==method]) for method in config['methods']}
        per_node.append({'segment_key':key,'name':stats['name'],'point_ids':stats['point_ids'],
            'train_samples':client['sizes']['train'],'test_samples':client['sizes']['test'],
            'train_js_divergence':stats['train_js_divergence'],'methods':entries,
            'fedavg_minus_local_kmh':entries['fedavg']['mean']-entries['local']['mean']})
    source_hash=hashlib.sha256()
    for folder in ['src','experiments']:
        for path in sorted((ROOT/folder).rglob('*.py')):
            source_hash.update(str(path.relative_to(ROOT)).encode());source_hash.update(path.read_bytes())
    benchmark={'run_id':args.output.name,'generated_at':datetime.now(timezone.utc).isoformat(),
        'snapshot_sha256':manifest['sha256'],'source_sha256':source_hash.hexdigest(),
        'research_result':False,'scenario':'natural_non_iid_observation_only','seeds':config['seeds'],
        'clients':len(manifest['clients']),'sizes':{k:sum(c['sizes'][k] for c in manifest['clients']) for k in ['train','validation','test']},
        'hist_len':config['dataset']['hist_len'],'horizons_minutes':[h*config['dataset']['sample_minutes'] for h in config['dataset']['horizons']],
        'rounds':config['fl']['num_rounds'],'local_epochs':config['fl']['local_epochs'],
        'proximal_mu':config['fl']['proximal_mu'],'model_parameters':runs[0]['model_parameters'],
        'model_tensor_bytes':runs[0]['model_tensor_bytes'],
        'train_targets_before':manifest['train_targets_before'],'test_targets_from':manifest['test_targets_from'],
        'methods':methods,'per_node':per_node,'curves':curves,
        'planned_methods':[{'id':name,'status':'not_implemented'} for name in ['SCAFFOLD','Ditto / FedRep','Adaptive + personalization']],
        'communication_scope':'Logical model tensors, train down/up and validation down. Not measured network bytes. Centralized raw data transfer excluded.',
        'validation_policy':'Global methods select minimum macro validation MAE across trained rounds; Local selects its own best validation checkpoint per client. Test evaluated only after selection.',
        'optimizer_policy':'Adam reset each round for every learned method; same architecture, initialization per seed, learning rate, total epochs and eligible windows.',
        'versions':{name:importlib.metadata.version(name) for name in ['torch','flwr','numpy']},
        'runs':runs}
    report={'schema_version':1,'generated_at':benchmark['generated_at'],'quality':quality,'benchmark':benchmark}
    (args.output/'reports.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Report saved: '+str(args.output/'reports.json'),flush=True)


if __name__=='__main__':main()
