"""Upload and run a bounded, offline FedAvg real-data pilot on the existing EC2.

A frozen, credential-free TomTom CSV snapshot is mounted read-only; no DB access.
Results are copied back to the local repository after the job completes.
"""

from datetime import datetime, timezone
import argparse
import ipaddress
import json
from pathlib import Path
import shlex
import subprocess
import tarfile


ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra/aws"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-snapshot', action='store_true',
                        help='Read a new frozen CSV from PostGIS before training')
    args = parser.parse_args()
    outputs = json.loads(subprocess.check_output([
        str(Path.home() / ".local/bin/terraform"), f"-chdir={INFRA}", "output", "-json",
    ]))
    host = str(ipaddress.IPv4Address(outputs["public_ip"]["value"]))
    options = ["-i", str(Path.home() / ".ssh/capstone-traffic-aws"),
               "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", f"UserKnownHostsFile={INFRA / '.state/known_hosts'}",
               "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15"]
    ssh = ["ssh", *options, f"ubuntu@{host}"]
    scp = ["scp", *options]
    snapshot = ROOT / 'data/raw/tomtom_training_snapshot.csv'
    if args.refresh_snapshot:
        sql = """COPY (SELECT o.observation_id,o.query_point_id,r.segment_key,
          o.collected_at,o.current_speed_kmh,o.free_flow_speed_kmh,o.confidence,o.road_closed
          FROM traffic_observations o JOIN road_segments r USING(segment_id)
          WHERE o.provider='tomtom' ORDER BY o.collected_at,o.observation_id)
          TO STDOUT WITH CSV HEADER"""
        export = ['sudo', 'docker', 'compose', 'exec', '-T', 'db', 'psql',
                  '-U', 'capstone', '-d', 'capstone_traffic', '-c', sql]
        content = subprocess.check_output(ssh + [
            'cd /opt/capstone-traffic && ' + shlex.join(export)])
        temporary = snapshot.with_suffix('.csv.tmp')
        temporary.write_bytes(content)
        temporary.replace(snapshot)
    if not snapshot.is_file():
        parser.error('Snapshot missing; use --refresh-snapshot')
    print('Using frozen real-data snapshot: ' + str(snapshot), flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_name = f"fedavg_tomtom_{stamp}"
    remote = "/opt/capstone-traffic/fl-real"
    state = INFRA / ".state"
    archive = state / "fl-real-code.tar.gz"
    paths = [ROOT / "experiments/run_experiment.py", ROOT / "configs/fedavg_tomtom.yaml"]
    paths.extend(sorted((ROOT / "src").rglob("*.py")))
    paths.append(ROOT / "data/raw/tomtom_training_snapshot.csv")
    with tarfile.open(archive, "w:gz") as bundle:
        for path in paths:
            bundle.add(path, arcname=str(path.relative_to(ROOT)))
        for name in ["Dockerfile", "requirements.txt"]:
            bundle.add(INFRA / "fl-smoke" / name, arcname=f"build/{name}")
    subprocess.run(ssh + [f"mkdir -p {remote}/results"], check=True)
    subprocess.run(scp + [str(archive), f"ubuntu@{host}:/tmp/fl-real-code.tar.gz"], check=True)
    subprocess.run(ssh + [f"tar -xzf /tmp/fl-real-code.tar.gz -C {remote}"], check=True)
    print("Checking CPU-only Flower/PyTorch image on AWS...", flush=True)
    subprocess.run(ssh + [
        "sudo docker image inspect capstone-fedavg:cpu >/dev/null 2>&1 || sudo docker build --memory=768m --memory-swap=1g --cpu-period=100000 --cpu-quota=100000 "
        f"-t capstone-fedavg:cpu {remote}/build",
    ], check=True)
    command = ["sudo", "docker", "run", "--rm", "--name", "capstone-fedavg-real",
               "--memory=768m", "--memory-swap=1g", "--cpus=1", "--pids-limit=128",
               "--network=none", "--read-only", "--cap-drop=ALL",
               "--security-opt=no-new-privileges:true", "--tmpfs=/tmp:rw,nosuid,size=64m",
               "--mount", f"type=bind,src={remote},dst=/app,readonly",
               "--mount", f"type=bind,src={remote}/results,dst=/app/results",
               "capstone-fedavg:cpu", "--config", "configs/fedavg_tomtom.yaml",
               "--output-dir", f"results/{run_name}"]
    print(f"Running {run_name}: 1 CPU, 768 MiB RAM, no network...", flush=True)
    log_path = state / f"{run_name}.log"
    try:
        result = subprocess.run(ssh + [shlex.join(command)], text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=300)
    except subprocess.TimeoutExpired:
        subprocess.run(ssh + ["sudo docker rm -f capstone-fedavg-real"], check=False)
        raise SystemExit("Real-data pilot timed out and its container was stopped.") from None
    log_path.write_text(result.stdout)
    print(result.stdout, flush=True)
    if result.returncode:
        raise SystemExit(f"Real-data pilot failed with exit {result.returncode}; log: {log_path}")
    output = ROOT / "results" / run_name
    output.mkdir(parents=True, exist_ok=True)
    for name in ["metrics.json", "model.pt", "data_manifest.json"]:
        subprocess.run(scp + [f"ubuntu@{host}:{remote}/results/{run_name}/{name}", str(output / name)], check=True)
    report = json.loads((output / "metrics.json").read_text())
    if report["status"] != "passed":
        raise SystemExit("Real-data report did not pass")
    subprocess.run(ssh + [
        "sudo systemctl show capstone-collector.service -p Result; "
        "cd /opt/capstone-traffic && sudo docker compose exec -T db psql -U capstone -d capstone_traffic "
        "-c 'SELECT count(*) AS observations, max(collected_at) AS latest_utc FROM traffic_observations;'",
    ], check=True)
    print(f"Results copied to {output}", flush=True)


if __name__ == "__main__":
    main()
