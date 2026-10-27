"""Run a frozen comparison on the current EC2; publish only credential-free metrics."""
from datetime import datetime,timezone
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[2]
INFRA=ROOT/'infra/aws'


def main():
    outputs=json.loads(subprocess.check_output([str(Path.home()/'.local/bin/terraform'),f'-chdir={INFRA}','output','-json']))
    host=outputs['public_ip']['value']
    options=['-i',str(Path.home()/'.ssh/capstone-traffic-aws'),'-o','IdentitiesOnly=yes',
        '-o','StrictHostKeyChecking=yes','-o',f'UserKnownHostsFile={INFRA/".state/known_hosts"}',
        '-o','ConnectTimeout=10','-o','ServerAliveInterval=15']
    ssh=['ssh',*options,f'ubuntu@{host}'];scp=['scp',*options]
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');run_id='comparison_'+stamp
    remote=f'/opt/capstone-traffic/comparison/{run_id}'
    archive=INFRA/'.state/comparison-code.tar.gz'
    paths=[*sorted((ROOT/'src').rglob('*.py')),
        ROOT/'experiments/run_comparison.py',ROOT/'experiments/comparison_worker.py',
        ROOT/'configs/comparison_pilot.json',ROOT/'data/raw/tomtom_report_snapshot.csv',
        ROOT/'infra/aws/collection_groups.json',ROOT/'data/sample_tomtom_ben_thanh_15.json',
        ROOT/'data/sample_tomtom_traffic_15.json',ROOT/'tests/test_comparison_math.py']
    with tarfile.open(archive,'w:gz') as bundle:
        for path in paths:bundle.add(path,arcname=str(path.relative_to(ROOT)))
    subprocess.run(ssh+[f'mkdir -p {remote}/results'],check=True)
    subprocess.run(scp+[str(archive),f'ubuntu@{host}:/tmp/comparison-code.tar.gz'],check=True)
    subprocess.run(ssh+[f'tar -xzf /tmp/comparison-code.tar.gz -C {remote}'],check=True)
    base=['sudo','docker','run','--rm','--name','capstone-comparison','--memory=768m','--memory-swap=1g',
        '--cpus=1','--pids-limit=128','--network=none','--read-only','--cap-drop=ALL',
        '--security-opt=no-new-privileges:true','--tmpfs=/tmp:rw,nosuid,size=64m',
        '--mount',f'type=bind,src={remote},dst=/app,readonly',
        '--mount',f'type=bind,src={remote}/results,dst=/app/results',
        '--entrypoint','python','capstone-fedavg:cpu']
    subprocess.run(ssh+[shlex.join(base+['-m','unittest','discover','-s','tests','-p','test_comparison_math.py','-v'])],check=True,timeout=180)
    command=base+['experiments/run_comparison.py','--config','configs/comparison_pilot.json','--output',f'results/{run_id}']
    try:subprocess.run(ssh+[shlex.join(command)],check=True,timeout=1200)
    except subprocess.TimeoutExpired:
        subprocess.run(ssh+['sudo docker rm -f capstone-comparison'],check=False)
        raise SystemExit('Bounded comparison job timed out and was stopped') from None
    subprocess.run(scp+['-r',f'ubuntu@{host}:{remote}/results/{run_id}',str(ROOT/'results')],check=True)
    subprocess.run(ssh+[f'sudo install -m 644 {remote}/results/{run_id}/reports.json '
        '/var/lib/capstone-traffic/reports.json.tmp && '
        'sudo mv /var/lib/capstone-traffic/reports.json.tmp /var/lib/capstone-traffic/reports.json'],check=True)
    print(f'Comparison saved to {ROOT/"results"/run_id}',flush=True)


if __name__=='__main__':main()
