"""Install the private PostGIS-to-Sites bridge; receive Site credentials via hidden stdin."""

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tarfile
import termios


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "infra/aws/.state"


def read_env(path):
    result = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def main():
    os.umask(0o077)
    previous = termios.tcgetattr(sys.stdin) if sys.stdin.isatty() else None
    if previous:
        hidden = termios.tcgetattr(sys.stdin)
        hidden[3] &= ~termios.ECHO
        termios.tcsetattr(sys.stdin, termios.TCSANOW, hidden)
    print("Ready for dashboard configuration JSON on stdin (input is hidden).", flush=True)
    try:
        configuration = json.loads(sys.stdin.readline())
    finally:
        if previous:
            termios.tcsetattr(sys.stdin, termios.TCSANOW, previous)
    outputs = json.loads(subprocess.check_output([
        str(Path.home()/".local/bin/terraform"), f"-chdir={ROOT/'infra/aws'}", "output", "-json",
    ]))
    host = outputs["public_ip"]["value"]
    ssh = ["ssh", "-i", str(Path.home()/".ssh/capstone-traffic-aws"), "-o", "IdentitiesOnly=yes",
           "-o", f"UserKnownHostsFile={STATE/'known_hosts'}", "-o", "StrictHostKeyChecking=yes", f"ubuntu@{host}"]
    password_file = STATE / "dashboard-db-password"
    if not password_file.exists():
        password_file.write_text(secrets.token_urlsafe(32))
    password = password_file.read_text().strip()
    if not all(c.isalnum() or c in "_-" for c in password):
        raise SystemExit("Invalid generated database password")
    sql = f"""DO $$ BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='traffic_dashboard') THEN
        CREATE ROLE traffic_dashboard LOGIN;
      END IF;
    END $$;
    ALTER ROLE traffic_dashboard PASSWORD '{password}';
    ALTER ROLE traffic_dashboard SET default_transaction_read_only=on;
    GRANT CONNECT ON DATABASE capstone_traffic TO traffic_dashboard;
    GRANT USAGE ON SCHEMA public TO traffic_dashboard;
    GRANT SELECT ON sample_intersections, sample_query_points, data_source_assignments,
      road_segments, traffic_observations TO traffic_dashboard;
    """
    subprocess.run(ssh+["cd /opt/capstone-traffic && sudo docker compose exec -T db psql -X -q -v ON_ERROR_STOP=1 -U capstone -d capstone_traffic"], input=sql, text=True, check=True)
    archive = STATE / "dashboard-source.tar.gz"
    with tarfile.open(archive,"w:gz") as bundle:
        for name in ["dashboard/sync_site.py", "infra/aws/Dockerfile.dashboard", "infra/aws/compose.dashboard.yml", ".dockerignore"]:
            bundle.add(ROOT/name, arcname=name)
    subprocess.run(["scp",*ssh[1:-1],str(archive),f"ubuntu@{host}:/tmp/dashboard-source.tar.gz"],check=True)
    subprocess.run(ssh+["tar -xzf /tmp/dashboard-source.tar.gz -C /opt/capstone-traffic"],check=True)
    environment = {
        "DATABASE_URL": f"postgresql://traffic_dashboard:{password}@db:5432/capstone_traffic",
        "SITE_INGEST_URL": configuration["site_url"].rstrip("/")+"/api/ingest",
        "SITE_SERVICE_TOKEN": configuration["site_service_token"],
        "SYNC_INTERVAL_SECONDS": "30",
    }
    # The Site token is sent only over SSH stdin and stored as a private runtime
    # environment on AWS. It is never written to local source or printed.
    subprocess.run(ssh+["umask 077; cat > /opt/capstone-traffic/.dashboard.env"],
                   input="".join(f"{key}={value}\n" for key,value in environment.items()),text=True,check=True)
    subprocess.run(ssh+["cd /opt/capstone-traffic && sudo docker compose -f docker-compose.yml "
                       "-f infra/aws/compose.cloud.yml -f infra/aws/compose.dashboard.yml "
                       "up -d --build dashboard_sync --wait"],check=True)
    print("Dashboard bridge installed with a read-only database role and a 30-second interval.",flush=True)


if __name__ == "__main__":
    main()
