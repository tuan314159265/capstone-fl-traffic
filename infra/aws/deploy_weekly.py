"""Install weekly job code and connect its public metrics to the dashboard."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT/'infra/aws'


def main():
    schedule = json.loads(subprocess.check_output(['aws','scheduler','get-schedule',
        '--name','capstone-traffic-weekly-train','--region','ap-southeast-2','--output','json']))
    outputs = json.loads(subprocess.check_output([str(Path.home()/'.local/bin/terraform'),
        f'-chdir={INFRA}','output','-json']))
    host = outputs['public_ip']['value']
    options = ['-i',str(Path.home()/'.ssh/capstone-traffic-aws'),'-o','IdentitiesOnly=yes',
        '-o','StrictHostKeyChecking=yes','-o',f'UserKnownHostsFile={INFRA/".state/known_hosts"}',
        '-o','ConnectTimeout=10','-o','ServerAliveInterval=15']
    ssh=['ssh',*options,f'ubuntu@{host}']
    archive=INFRA/'.state/weekly-code.tar.gz'
    paths=[*sorted((ROOT/'src').rglob('*.py')), *sorted((INFRA/'weekly').glob('*.py')),
        ROOT/'configs/fedavg_weekly.json', ROOT/'experiments/run_experiment.py']
    with tarfile.open(archive,'w:gz') as bundle:
        for path in paths: bundle.add(path,arcname=str(path.relative_to(ROOT)))
    subprocess.run(['scp',*options,str(archive),f'ubuntu@{host}:/tmp/weekly-code.tar.gz'],check=True)
    subprocess.run(ssh+['tar -xzf /tmp/weekly-code.tar.gz -C /opt/capstone-traffic/fl-real'],check=True)
    end = schedule['EndDate']
    deadline = datetime.fromtimestamp(end,timezone.utc) if isinstance(end,(int,float)) else datetime.fromisoformat(end)
    settings={'enabled':schedule['State']=='ENABLED','name':schedule['Name'],
        'expression':schedule['ScheduleExpression'],'timezone':schedule['ScheduleExpressionTimezone'],
        'end_date':deadline.astimezone(timezone.utc).isoformat(),
        'verified_at':datetime.now(timezone.utc).isoformat()}
    subprocess.run(ssh+['sudo tee /var/lib/capstone-traffic/training-schedule.json >/dev/null'],
        input=json.dumps(settings)+'\n',text=True,check=True)
    subprocess.run(ssh+['sudo python3 /opt/capstone-traffic/fl-real/infra/aws/weekly/run_train.py '
        '--seed-run fedavg_tomtom_20261026T183431Z'],check=True)
    subprocess.run(['scp',*options,str(ROOT/'dashboard/sync_site.py'),
        f'ubuntu@{host}:/opt/capstone-traffic/dashboard/sync_site.py'],check=True)
    subprocess.run(ssh+['cd /opt/capstone-traffic && sudo docker compose -f docker-compose.yml '
        '-f infra/aws/compose.cloud.yml -f infra/aws/compose.dashboard.yml '
        'up -d --build dashboard_sync --wait'],check=True)
    subprocess.run(ssh+['sudo systemctl restart snap.amazon-ssm-agent.amazon-ssm-agent.service'],check=True)
    print(json.dumps(settings,indent=2))


if __name__=='__main__': main()
