"""Run one scheduled snapshot, reserving a conservative monthly request budget.

This counts attempted requests on this VM, not usage by other applications using
the same TomTom account. No retries occur until the next scheduled snapshot.
"""

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    for raw in (root / ".env").read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    budget = int(os.environ.get("TOMTOM_MONTHLY_REQUEST_BUDGET", "18000"))
    points = json.loads((root / "data/sample_tomtom_ben_thanh_15.json").read_text())
    requests = sum(p["assigned_provider"] == "tomtom" for p in points)
    state_dir = Path("/var/lib/capstone-traffic")
    state_dir.mkdir(mode=0o700, exist_ok=True)
    with (state_dir / "collection.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another snapshot is still running; skipped", flush=True)
            return 0
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        state_path = state_dir / "request-budget.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        used = state.get(month, 0)
        if used + requests > budget:
            print(f"Monthly request budget reached: month={month} reserved={used} limit={budget}; paused until next month", flush=True)
            return 0
        # Reserve BEFORE launching so failures/restarts cannot spend uncounted requests.
        state[month] = used + requests
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state) + "\n")
        temporary.chmod(0o600)
        temporary.replace(state_path)
        print(f"month={month} reserved_requests={state[month]} limit={budget}", flush=True)
        result = subprocess.run([
            "docker", "compose", "-f", "docker-compose.yml",
            "-f", "infra/aws/compose.cloud.yml", "--profile", "collect",
            "run", "--rm", "--no-deps", "collector",
        ], cwd=root, check=False)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
