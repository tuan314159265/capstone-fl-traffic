"""One method/seed per process; test is evaluated only after validation selection."""
import argparse
from copy import deepcopy
import csv
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import random
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import numpy as np
import torch
from torch.utils.data import ConcatDataset,DataLoader
from src.data.traffic import prepared,client_loaders,SPEED_SCALE
from src.metrics.evaluation import aggregate_nodes
from src.models.forecast import make_model,train_local,evaluate_model


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--method',required=True)
    parser.add_argument('--seed',type=int,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();started=time.monotonic()
    config=json.loads(args.config.read_text());config['seed']=args.seed
    clients,manifest=prepared(config);count=len(clients);config['fl']['num_clients']=count
    config['fl']['strategy']='fedprox' if args.method=='fedprox' else 'fedavg'
    args.output.mkdir(parents=True,exist_ok=True)
    random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    # Flower's runner sets inter-op threads itself; local-only worker sets it here.
    if args.method not in {'fedavg','fedprox'}:torch.set_num_interop_threads(1)
    initial=make_model(config).state_dict()
    histories=[];states={};selected={};logical_bytes=0
    rounds=config['fl']['num_rounds'];epochs=config['fl']['local_epochs']
    if args.method in {'fedavg','fedprox'}:
        from src.fl.server import run_fedavg
        report=run_fedavg(config,args.output)
        (args.output/'flower_metrics.json').write_text(json.dumps(report,indent=2)+'\n')
        final=torch.load(args.output/'model.pt',weights_only=True,map_location='cpu')['state_dict']
        states={i:final for i in range(count)};selected={'global':report['selected_round']}
        histories=[{'round':int(round_id),'validation_mae_kmh':float(np.mean([v['mae_kmh'] for v in rows]))}
                   for round_id,rows in report['validation_history'].items()]
        logical_bytes=report['logical_model_bytes']
    elif args.method in {'local','centralized'}:
        models={i:make_model(config) for i in (range(count) if args.method=='local' else [0])}
        for model in models.values():model.load_state_dict(initial)
        best={i:float('inf') for i in models};best_states={}
        for round_id in range(1,rounds+1):
            validations=[]
            if args.method=='centralized':
                datasets=[client_loaders(config,i,round_id)['train'].dataset for i in range(count)]
                pooled=DataLoader(ConcatDataset(datasets),batch_size=config['train']['batch_size'],shuffle=True,
                    generator=torch.Generator().manual_seed(args.seed+round_id),num_workers=0)
                torch.manual_seed(args.seed+round_id)
                train_local(models[0],pooled,epochs,config['train']['lr'])
                score=float(np.mean([evaluate_model(models[0],client_loaders(config,i)['validation'],config)['mae_kmh'] for i in range(count)]))
                validations.append(score)
                if score<best[0]:best[0]=score;best_states[0]=deepcopy(models[0].state_dict());selected['global']=round_id
            else:
                for i,model in models.items():
                    torch.manual_seed(args.seed+i*100+round_id)
                    train_local(model,client_loaders(config,i,round_id)['train'],epochs,config['train']['lr'])
                    score=evaluate_model(model,client_loaders(config,i)['validation'],config)['mae_kmh']
                    validations.append(score)
                    if score<best[i]:best[i]=score;best_states[i]=deepcopy(model.state_dict());selected[str(i)]=round_id
            histories.append({'round':round_id,'validation_mae_kmh':float(np.mean(validations))})
        states={i:best_states[i if args.method=='local' else 0] for i in range(count)}
        torch.save({'states':states,'config':config,'selected_rounds':selected},args.output/'model.pt')
    elif args.method!='persistence':raise ValueError('Unsupported method')
    nodes=[];prediction_rows=[]
    for i,client in enumerate(clients):
        test=client_loaders(config,i)['test'];errors=[];squared=[]
        model=None
        if args.method!='persistence':
            model=make_model(config);model.load_state_dict(states[i]);model.eval()
        offset=0
        with torch.no_grad():
            for x,y in test:
                prediction=x[:,-1,0:1].repeat(1,len(config['dataset']['horizons'])) if model is None else model(x)
                delta=(prediction-y)*SPEED_SCALE
                errors.extend(delta.abs().mean(dim=1).tolist());squared.extend(delta.square().mean(dim=1).tolist())
                for j in range(len(y)):
                    targets=client['partitions']['test'][offset+j][2]
                    for h,target in enumerate(targets):
                        prediction_rows.append({'client_id':i,'segment_key':client['segment_key'],
                            'target_at':datetime.fromtimestamp(target*config['dataset']['sample_minutes']*60,timezone.utc).isoformat(),
                            'horizon_minutes':config['dataset']['horizons'][h]*config['dataset']['sample_minutes'],
                            'actual_kmh':float(y[j,h]*SPEED_SCALE),'predicted_kmh':float(prediction[j,h]*SPEED_SCALE),
                            'persistence_kmh':float(x[j,-1,0]*SPEED_SCALE)})
                offset+=len(y)
        nodes.append({'client_id':i,'segment_key':client['segment_key'],'samples':len(errors),
            'train_samples':len(client['partitions']['train']),'mae_kmh':float(np.mean(errors)),
            'rmse_kmh':math.sqrt(float(np.mean(squared)))})
    with (args.output/'predictions.csv').open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(prediction_rows[0]));writer.writeheader();writer.writerows(prediction_rows)
    result={'method':args.method,'seed':args.seed,'snapshot_sha256':manifest['sha256'],
        'selected_rounds':selected,'validation_history':histories,'nodes':nodes,**aggregate_nodes(nodes),
        'logical_model_bytes':logical_bytes,'elapsed_seconds':time.monotonic()-started,
        'model_tensor_bytes':sum(t.numel()*t.element_size() for t in initial.values()),
        'model_parameters':sum(t.numel() for t in initial.values()),
        'train_download_bytes':logical_bytes//3,'train_upload_bytes':logical_bytes//3,
        'validation_download_bytes':logical_bytes//3,
        'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'trained_example_visits':sum(len(c['partitions']['train']) for c in clients)*rounds*epochs if args.method!='persistence' else 0,
        'runtime':'single_process_sequential_message_adapter' if args.method in {'fedavg','fedprox'} else 'single_process_cpu',
        'research_result':False}
    (args.output/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.output/'data_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'method':args.method,'seed':args.seed,'mae':result['macro_mae_kmh']}))


if __name__=='__main__':main()
