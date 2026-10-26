"""Deploy collector files and a private environment over SSH after Terraform apply.

Only a small allowlist of project files is uploaded. AWS credentials and the
project's original .env are never uploaded; .state/cloud.env contains only the
TomTom key and separate database credentials. Run this from the repository root.
"""

from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time


ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra/aws"
STATE = INFRA / ".state"


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    os.umask(0o077)
    terraform = Path.home() / ".local/bin/terraform"
    outputs = json.loads(subprocess.check_output([
        str(terraform), f"-chdir={INFRA}", "output", "-json",
    ]))
    ip = str(ipaddress.IPv4Address(outputs["public_ip"]["value"]))
    key = Path.home() / ".ssh/capstone-traffic-aws"
    target = f"ubuntu@{ip}"
    options = ["-i", str(key), "-o", "IdentitiesOnly=yes",
               "-o", "StrictHostKeyChecking=accept-new",
               "-o", f"UserKnownHostsFile={STATE / 'known_hosts'}",
               "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15"]

    def ssh(command):
        return run(["ssh", *options, target, command])

    print(f"Waiting for SSH on {ip}...", flush=True)
    for attempt in range(60):
        ready = subprocess.run(["ssh", *options, target, "true"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ready.returncode == 0:
            break
        time.sleep(5)
    else:
        raise SystemExit("SSH is not ready; check the instance and SSH source IP.")

    print("Waiting for Ubuntu bootstrap...", flush=True)
    ssh("sudo cloud-init status --wait; sudo test -f /var/lib/capstone-traffic/bootstrap-complete")

    expiry = STATE / "stop-at-utc.txt"
    if not expiry.exists():
        expiry.write_text((datetime.now(timezone.utc) + timedelta(days=28)).strftime("%Y-%m-%d %H:%M:%S"))
    stop_at = expiry.read_text().strip()
    timer = STATE / "capstone-expiry.timer"
    timer.write_text(
        "[Unit]\nDescription=Stop EC2 after the four-week collection period\n\n"
        f"[Timer]\nOnCalendar={stop_at} UTC\nPersistent=true\n"
        "Unit=capstone-expiry.service\n\n[Install]\nWantedBy=timers.target\n"
    )

    files = [ROOT / "docker-compose.yml", ROOT / "data/scripts/collect_tomtom.py",
             ROOT / "data/sample_tomtom_ben_thanh_15.json"]
    files.extend(sorted((ROOT / "database/init").glob("*.sql")))
    files.extend(INFRA / name for name in [
        "Dockerfile.collector", "requirements-collector.txt", "compose.cloud.yml",
        "run_snapshot.py", "backup.sh", "capstone-collector.service",
        "capstone-collector.timer", "capstone-backup.service", "capstone-backup.timer",
        "capstone-expiry.service",
    ])
    archive = STATE / "deploy.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for path in files:
            bundle.add(path, arcname=str(path.relative_to(ROOT)))

    print("Uploading deployment files and private cloud configuration...", flush=True)
    run(["scp", *options, str(archive), f"{target}:/tmp/capstone-deploy.tar.gz"])
    ssh("tar -xzf /tmp/capstone-deploy.tar.gz -C /opt/capstone-traffic")
    run(["scp", *options, str(STATE / "cloud.env"), f"{target}:/opt/capstone-traffic/.env"])
    run(["scp", *options, str(timer), f"{target}:/opt/capstone-traffic/infra/aws/capstone-expiry.timer"])

    print("Starting PostGIS and building the collector image...", flush=True)
    ssh("cd /opt/capstone-traffic && chmod 600 .env && "
        "sudo docker compose -f docker-compose.yml -f infra/aws/compose.cloud.yml up -d db --wait && "
        "sudo docker compose -f docker-compose.yml -f infra/aws/compose.cloud.yml --profile collect build collector")
    ssh("sudo install -m 0644 /opt/capstone-traffic/infra/aws/capstone-*.service "
        "/opt/capstone-traffic/infra/aws/capstone-*.timer /etc/systemd/system/ && "
        "sudo systemctl daemon-reload && "
        "sudo systemctl enable --now capstone-collector.timer capstone-backup.timer capstone-expiry.timer")
    print("Collecting the first snapshot and checking stored data...", flush=True)
    ssh("sudo systemctl start capstone-collector.service && sudo systemctl start capstone-backup.service")
    ssh("cd /opt/capstone-traffic && "
        "sudo docker compose exec -T db psql -U capstone -d capstone_traffic -c "
        "\"SELECT count(*) AS observations, count(DISTINCT query_point_id) AS points, "
        "max(collected_at) AS latest_utc FROM traffic_observations;\" && "
        "sudo systemctl list-timers 'capstone-*' --no-pager")
    print(f"Deployment complete: {ip}; scheduled stop at {stop_at} UTC", flush=True)


if __name__ == "__main__":
    main()
