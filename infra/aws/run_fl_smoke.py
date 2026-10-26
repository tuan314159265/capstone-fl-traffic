"""Upload and run a bounded, offline FedAvg smoke job on the existing EC2.

No AWS/TomTom credentials or DB access are passed to the training container.
Results are copied back to the local repository after the job completes.
"""

from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import shlex
import subprocess
import tarfile


ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra/aws"


def main():
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
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_name = f"fedavg_smoke_{stamp}"
    remote = "/opt/capstone-traffic/fl-smoke"
    state = INFRA / ".state"
    archive = state / "fl-smoke-code.tar.gz"
    paths = [ROOT / "experiments/run_experiment.py", ROOT / "configs/fedavg_smoke.yaml"]
    paths.extend(sorted((ROOT / "src").rglob("*.py")))
    with tarfile.open(archive, "w:gz") as bundle:
        for path in paths:
            bundle.add(path, arcname=str(path.relative_to(ROOT)))
        for name in ["Dockerfile", "requirements.txt"]:
            bundle.add(INFRA / "fl-smoke" / name, arcname=f"build/{name}")
    subprocess.run(ssh + [f"mkdir -p {remote}/results"], check=True)
    subprocess.run(scp + [str(archive), f"ubuntu@{host}:/tmp/fl-smoke-code.tar.gz"], check=True)
    subprocess.run(ssh + [f"tar -xzf /tmp/fl-smoke-code.tar.gz -C {remote}"], check=True)
    print("Building CPU-only Flower/PyTorch image on AWS...", flush=True)
    subprocess.run(ssh + [
        "sudo docker build --memory=768m --memory-swap=1g --cpu-period=100000 --cpu-quota=100000 "
        f"-t capstone-fedavg:cpu {remote}/build",
    ], check=True)
    command = ["sudo", "docker", "run", "--rm", "--name", "capstone-fedavg-smoke",
               "--memory=768m", "--memory-swap=1g", "--cpus=1", "--pids-limit=128",
               "--network=none", "--read-only", "--cap-drop=ALL",
               "--security-opt=no-new-privileges:true", "--tmpfs=/tmp:rw,nosuid,size=64m",
               "--mount", f"type=bind,src={remote},dst=/app,readonly",
               "--mount", f"type=bind,src={remote}/results,dst=/app/results",
               "capstone-fedavg:cpu", "--config", "configs/fedavg_smoke.yaml",
               "--output-dir", f"results/{run_name}"]
    print(f"Running {run_name}: 1 CPU, 768 MiB RAM, no network...", flush=True)
    log_path = state / f"{run_name}.log"
    try:
        result = subprocess.run(ssh + [shlex.join(command)], text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=300)
    except subprocess.TimeoutExpired:
        subprocess.run(ssh + ["sudo docker rm -f capstone-fedavg-smoke"], check=False)
        raise SystemExit("Smoke job timed out and its container was stopped.") from None
    log_path.write_text(result.stdout)
    print(result.stdout, flush=True)
    if result.returncode:
        raise SystemExit(f"Smoke job failed with exit {result.returncode}; log: {log_path}")
    output = ROOT / "results" / run_name
    output.mkdir(parents=True, exist_ok=True)
    for name in ["metrics.json", "model.pt"]:
        subprocess.run(scp + [f"ubuntu@{host}:{remote}/results/{run_name}/{name}", str(output / name)], check=True)
    report = json.loads((output / "metrics.json").read_text())
    if report["status"] != "passed":
        raise SystemExit("Smoke report did not pass")
    subprocess.run(ssh + [
        "sudo systemctl show capstone-collector.service -p Result; "
        "cd /opt/capstone-traffic && sudo docker compose exec -T db psql -U capstone -d capstone_traffic "
        "-c 'SELECT count(*) AS observations, max(collected_at) AS latest_utc FROM traffic_observations;'",
    ], check=True)
    print(f"Results copied to {output}", flush=True)


if __name__ == "__main__":
    main()
