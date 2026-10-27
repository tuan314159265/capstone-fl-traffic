"""Read PostGIS with a read-only role and publish a private dashboard snapshot."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row
import requests


ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    active = set()
    groups = json.loads((ROOT / "infra/aws/collection_groups.json").read_text())["groups"]
    for group in groups:
        for p in json.loads((ROOT / group["points"]).read_text()):
            active.add(p["intersection_id"] + ":" + p["approach_label"])
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row,
                         options="-c default_transaction_read_only=on -c statement_timeout=10000") as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT count(*) AS observations, count(DISTINCT query_point_id) AS query_points,
                                  count(DISTINCT segment_id) AS distinct_segments, max(collected_at) AS latest_utc
                           FROM traffic_observations""")
            stats = dict(cur.fetchone())
            cur.execute("""SELECT q.query_point_id AS id, q.intersection_id, i.name,
                      ST_Y(q.location) AS latitude, ST_X(q.location) AS longitude,
                      COALESCE(a.provider_config->>'collection_group', 'legacy') AS "group",
                      o.provider, o.current_speed_kmh, o.free_flow_speed_kmh,
                      o.current_travel_time_s, o.free_flow_travel_time_s,
                      o.confidence, o.road_closed, o.collected_at, o.source_updated_at,
                      r.segment_key, r.functional_road_class, ST_AsGeoJSON(r.geometry) AS geometry,
                      c.observation_count
               FROM sample_query_points q
               JOIN sample_intersections i USING (intersection_id)
               LEFT JOIN data_source_assignments a USING (intersection_id)
               LEFT JOIN LATERAL (SELECT * FROM traffic_observations t
                   WHERE t.query_point_id=q.query_point_id ORDER BY collected_at DESC LIMIT 1) o ON true
               LEFT JOIN road_segments r ON r.segment_id=o.segment_id
               LEFT JOIN LATERAL (SELECT count(*) AS observation_count FROM traffic_observations t
                   WHERE t.query_point_id=q.query_point_id) c ON true
               ORDER BY q.query_point_id""")
            points = [dict(row) for row in cur.fetchall()]
            for point in points:
                point["is_active"] = point["id"] in active
                point["geometry"] = json.loads(point["geometry"]) if point["geometry"] else None
            stats["active_points"] = sum(p["is_active"] for p in points)
            cur.execute("""SELECT query_point_id, collected_at, current_speed_kmh,
                                   free_flow_speed_kmh, confidence
                            FROM traffic_observations
                            WHERE collected_at >= now() - interval '24 hours'
                            ORDER BY collected_at""")
            history = {}
            for row in cur.fetchall():
                history.setdefault(row["query_point_id"], []).append([
                    row["collected_at"].isoformat(), row["current_speed_kmh"],
                    row["free_flow_speed_kmh"], row["confidence"],
                ])
    now = datetime.now(timezone.utc)
    budgets = []
    for group in groups:
        path = Path(os.environ.get("STATE_DIR", "/state")) / group["budget_state"]
        state = json.loads(path.read_text()) if path.exists() else {}
        budgets.append({"id": group["id"], "month": now.strftime("%Y-%m"),
                        "reserved": state.get(now.strftime("%Y-%m"), 0),
                        "limit": int(os.environ.get(group["budget_env"], "18000"))})
    training_path = Path(os.environ.get("STATE_DIR", "/state")) / "training.json"
    try:
        training = json.loads(training_path.read_text()) if training_path.exists() else None
    except (OSError, ValueError):
        training = None
    reports_path = Path(os.environ.get("STATE_DIR", "/state")) / "reports.json"
    try:
        reports = json.loads(reports_path.read_text()) if reports_path.exists() else None
    except (OSError, ValueError):
        reports = None
    return {"schema_version": 1, "generated_at": now.isoformat(),
            "stats": stats, "points": points, "history": history, "budgets": budgets,
            "training": training, "reports": reports}


def main():
    endpoint = os.environ["SITE_INGEST_URL"]
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".chatgpt.site") or parsed.path != "/api/ingest":
        raise SystemExit("Only the configured HTTPS Sites ingest endpoint is allowed")
    token = os.environ["SITE_SERVICE_TOKEN"]
    interval = max(15, int(os.environ.get("SYNC_INTERVAL_SECONDS", "30")))
    with requests.Session() as session:
        while True:
            try:
                payload = snapshot()
                publish_dir = os.environ.get("WEB_SNAPSHOT_DIR")
                if publish_dir:
                    published = {**payload, "synced_at": datetime.now(timezone.utc).isoformat()}
                    temporary = Path(publish_dir) / "traffic-snapshot.tmp"
                    temporary.write_text(json.dumps(published, default=lambda value: value.isoformat(), separators=(",", ":")))
                    temporary.chmod(0o644)
                    temporary.replace(Path(publish_dir) / "traffic-snapshot.json")
                body = json.dumps(payload, default=lambda value: value.isoformat(), separators=(",", ":"))
                if len(body.encode()) > 900000:
                    raise RuntimeError("Snapshot exceeds the dashboard size limit")
                response = session.post(endpoint, data=body, headers={
                    "Content-Type": "application/json", "OAI-Sites-Authorization": "Bearer " + token,
                    "X-Traffic-Sync-Token": token,
                }, timeout=20, allow_redirects=False)
                if response.status_code != 200:
                    print(f"sync_failed=HTTP_{response.status_code}", flush=True)
                else:
                    print(f"synced points={len(payload['points'])} observations={payload['stats']['observations']} bytes={len(body.encode())}", flush=True)
            except Exception as exc:
                # Never log connection strings, request headers or tokens.
                print(f"sync_failed={type(exc).__name__}", flush=True)
            time.sleep(interval)


if __name__ == "__main__":
    main()
