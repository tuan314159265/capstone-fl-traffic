"""SSM entrypoint: export a frozen snapshot, train offline, publish only metrics."""
import argparse
import csv
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

from summary import summarize

ROOT = Path('/opt/capstone-traffic/fl-real')
STATE = Path('/var/lib/capstone-traffic')
STATUS = STATE/'training.json'
SCHEDULE = STATE/'training-schedule.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def read_status():
    return json.loads(STATUS.read_text()) if STATUS.exists() else {}


def write_status(state):
    state['updated_at'] = now()
    state['schedule'] = json.loads(SCHEDULE.read_text()) if SCHEDULE.exists() else {'enabled': False}
    temporary = STATUS.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(state, separators=(',', ':'))+'\n')
    temporary.chmod(0o644)
    temporary.replace(STATUS)


def seed(run_id):
    if read_status().get('latest_run'):
        write_status(read_status())
        return
    output = ROOT/'results'/run_id
    report = json.loads((output/'metrics.json').read_text())
    manifest = json.loads((output/'data_manifest.json').read_text())
    completed = datetime.fromtimestamp((output/'metrics.json').stat().st_mtime, timezone.utc).isoformat()
    item = summarize(run_id, report, manifest, completed)
    write_status({'status':'succeeded', 'latest_run':item, 'history':[item]})


def run():
    os.chdir(ROOT)
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE/'weekly-training.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('skipped: another training job is running')
            return
        state = read_status()
        schedule = json.loads(SCHEDULE.read_text())
        if datetime.now(timezone.utc) >= datetime.fromisoformat(schedule['end_date'].replace('Z','+00:00')):
            state.update(status='skipped', reason='collection_deadline_reached')
            write_status(state)
            return
        week = datetime.now(timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%G-W%V')
        receipt = STATE/f'weekly-training-{week}.done'
        if receipt.exists():
            print('skipped: this week already completed')
            return
        run_id = 'fedavg_tomtom_weekly_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        output = ROOT/'results'/run_id
        output.mkdir(parents=True)
        os.chown(output,1000,1000)
        state.update(status='running', active_run=run_id, started_at=now(), reason=None)
        write_status(state)
        container = 'capstone-fedavg-weekly'
        try:
            sql = """COPY (SELECT o.observation_id,o.query_point_id,r.segment_key,o.collected_at,
              o.current_speed_kmh,o.free_flow_speed_kmh,o.confidence,o.road_closed
              FROM traffic_observations o JOIN road_segments r USING(segment_id)
              WHERE o.provider='tomtom' ORDER BY o.collected_at,o.observation_id)
              TO STDOUT WITH CSV HEADER"""
            snapshot = subprocess.check_output(['docker','compose','exec','-T','db','psql','-X',
                '-v','ON_ERROR_STOP=1','-U','capstone','-d','capstone_traffic','-c',sql],
                cwd='/opt/capstone-traffic', timeout=60)
            (output/'snapshot.csv').write_bytes(snapshot)
            config = json.loads((ROOT/'configs/fedavg_weekly.json').read_text())
            config['dataset']['path'] = str((output/'snapshot.csv').relative_to(ROOT))
            sys.path.insert(0,str(ROOT))
            from src.data.traffic import prepared
            try:
                _, manifest = prepared(config)
            except ValueError as error:
                state.update(status='skipped',reason=str(error),active_run=None)
                write_status(state)
                return
            if manifest['sha256'] == state.get('latest_run',{}).get('snapshot_sha256'):
                state.update(status='skipped', reason='no_new_data',active_run=None)
                write_status(state)
                return
            (output/'config.json').write_text(json.dumps(config,indent=2)+'\n')
            command = ['docker','run','--rm','--name',container,'--memory=768m','--memory-swap=1g',
                '--cpus=1','--pids-limit=128','--network=none','--read-only','--cap-drop=ALL',
                '--security-opt=no-new-privileges:true','--tmpfs=/tmp:rw,nosuid,size=64m',
                '--mount',f'type=bind,src={ROOT},dst=/app,readonly',
                '--mount',f'type=bind,src={ROOT}/results,dst=/app/results',
                'capstone-fedavg:cpu','--config',str((output/'config.json').relative_to(ROOT)),
                '--output-dir',str(output.relative_to(ROOT))]
            with (output/'training.log').open('w') as log:
                subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=900,check=True)
            metrics = json.loads((output/'metrics.json').read_text())
            manifest = json.loads((output/'data_manifest.json').read_text())
            if metrics.get('status') != 'passed':
                raise RuntimeError('Training report failed integrity checks')
            item = summarize(run_id,metrics,manifest,now())
            history = [*state.get('history',[]),item][-8:]
            state.update(status='succeeded',latest_run=item,history=history,reason=None,active_run=None)
            write_status(state)
            receipt.write_text(run_id+'\n')
            print(json.dumps({'status':'succeeded','run_id':run_id,'test_mae_kmh':item['test_mae_kmh']}))
        except Exception as error:
            subprocess.run(['docker','rm','-f',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            state.update(status='failed',reason=type(error).__name__,active_run=None)
            write_status(state)
            raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-run')
    args=parser.parse_args()
    if args.seed_run:
        seed(args.seed_run)
    else:
        run()
