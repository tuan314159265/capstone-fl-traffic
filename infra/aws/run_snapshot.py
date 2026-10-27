"""Run one scheduled snapshot, reserving a conservative monthly request budget.

This counts attempted requests on this VM, not usage by other applications using
the same TomTom account. No retries occur until the next scheduled snapshot.
"""

import argparse
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess


def collect_group(root, state_dir, group, environment):
    group_id = group["id"]
    key = environment.get(group["key_env"])
    if not key:
        print(f"group={group_id} skipped: missing {group['key_env']}", flush=True)
        return 1
    budget = int(environment.get(group["budget_env"], "18000"))
    points = json.loads((root / group["points"]).read_text())
    requests = sum(p["assigned_provider"] == "tomtom" for p in points)
    filename = group["budget_state"]
    if Path(filename).name != filename or not filename.endswith(".json"):
        raise ValueError("Budget state must be a JSON filename")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    state_path = state_dir / filename
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    used = state.get(month, 0)
    if used + requests > budget:
        print(f"group={group_id} monthly budget reached: month={month} reserved={used} limit={budget}", flush=True)
        return 0
    state[month] = used + requests
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state) + "\n")
    temporary.chmod(0o600)
    temporary.replace(state_path)
    print(f"group={group_id} month={month} reserved_requests={state[month]} limit={budget}", flush=True)
    # Only the selected account's key enters this container. Keys are fixed to
    # groups; there is no failover or rotation to spend another account's quota.
    child_environment = dict(environment)
    child_environment["API_TOMTOM"] = key
    result = subprocess.run([
        "docker", "compose", "-f", "docker-compose.yml",
        "-f", "infra/aws/compose.cloud.yml", "--profile", "collect",
        "run", "--rm", "--no-deps", "collector", "--points", group["points"],
        "--workers", "4", "--max-cycles", "1",
    ], cwd=root, env=child_environment, check=False)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", help="Run one collection group; default runs all configured groups")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    for raw in (root / ".env").read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    groups = json.loads((root / "infra/aws/collection_groups.json").read_text())["groups"]
    if args.group:
        groups = [group for group in groups if group["id"] == args.group]
        if not groups:
            parser.error("Unknown collection group")
    state_dir = Path("/var/lib/capstone-traffic")
    state_dir.mkdir(mode=0o700, exist_ok=True)
    with (state_dir / "collection.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another snapshot is still running; skipped", flush=True)
            return 0
        failed = False
        for group in groups:
            try:
                failed = bool(collect_group(root, state_dir, group, os.environ)) or failed
            except Exception as exc:
                print(f"group={group['id']} failed={type(exc).__name__}", flush=True)
                failed = True
        return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
