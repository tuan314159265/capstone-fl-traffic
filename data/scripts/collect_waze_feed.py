"""Collect approved Waze partner-feed events assigned to the sample Waze node."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import requests
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[2]
POINTS_FILE = ROOT / "data" / "sample_intersections.json"


def load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.removeprefix("export ").strip(), value.strip().strip("\"'"))


def as_timestamp(record: dict) -> datetime | None:
    value = record.get("pubMillis") or record.get("detectionDateMillis") or record.get("updateDateMillis")
    if value is not None:
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    return None


def line_wkt(record: dict) -> str | None:
    points = record.get("line") or record.get("turnLine")
    if not points or len(points) < 2:
        return None
    return "LINESTRING(" + ",".join(f"{float(p['x'])} {float(p['y'])}" for p in points) + ")"


def point_wkt(record: dict) -> str | None:
    location = record.get("location")
    if not location or "x" not in location or "y" not in location:
        return None
    return f"POINT({float(location['x'])} {float(location['y'])})"


def sync_assignment(conn: psycopg.Connection, point: dict, status: str) -> None:
    query_point_id = f"{point['intersection_id']}:{point['approach_label']}"
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO sample_intersections
                   (intersection_id, name, city, country_code, assigned_provider, location)
               VALUES (%s, %s, %s, %s, 'waze', ST_SetSRID(ST_MakePoint(%s, %s), 4326))
               ON CONFLICT (intersection_id) DO UPDATE SET
                   name = EXCLUDED.name, city = EXCLUDED.city,
                   country_code = EXCLUDED.country_code,
                   assigned_provider = EXCLUDED.assigned_provider,
                   location = EXCLUDED.location""",
            (point["intersection_id"], point["name"], point["city"], point["country_code"], point["longitude"], point["latitude"]),
        )
        cur.execute(
            """INSERT INTO sample_query_points (query_point_id, intersection_id, approach_label, location)
               VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
               ON CONFLICT (query_point_id) DO UPDATE SET location = EXCLUDED.location""",
            (query_point_id, point["intersection_id"], point["approach_label"], point["longitude"], point["latitude"]),
        )
        cur.execute(
            """INSERT INTO data_source_assignments
                   (intersection_id, provider, acquisition_mode, access_status, provider_config)
               VALUES (%s, 'waze', 'partner_data_feed', %s, %s)
               ON CONFLICT (intersection_id) DO UPDATE SET
                   provider = EXCLUDED.provider,
                   acquisition_mode = EXCLUDED.acquisition_mode,
                   access_status = EXCLUDED.access_status,
                   provider_config = EXCLUDED.provider_config,
                   updated_at = now()""",
            (point["intersection_id"], status, Jsonb(point.get("provider_config", {}))),
        )


def main() -> int:
    load_env_file()
    feed_url = os.environ.get("WAZE_DATA_FEED_URL")
    if not feed_url:
        raise SystemExit("WAZE_DATA_FEED_URL is missing; this must be an approved Partner Hub feed URL")
    database_url = os.environ.get("DATABASE_URL", "postgresql://capstone:change_me_locally@localhost:54329/capstone_traffic")
    points = json.loads(POINTS_FILE.read_text(encoding="utf-8"))
    waze_points = [point for point in points if point.get("assigned_provider") == "waze"]
    if not waze_points:
        raise SystemExit("No sample intersection is assigned to Waze")

    try:
        response = requests.get(feed_url, timeout=30)
    except requests.RequestException as exc:
        # Feed URLs contain a unique partner token; never print the URL.
        raise SystemExit(f"Waze feed request failed ({type(exc).__name__})") from None
    if response.status_code != 200:
        raise SystemExit(f"Waze feed returned HTTP {response.status_code}; feed URL is not printed")
    payload = response.json()

    with psycopg.connect(database_url) as conn:
        for point in waze_points:
            sync_assignment(conn, point, "partner_feed_present_unverified")
        inserted = 0
        with conn.cursor() as cur:
            for collection_name in ("jams", "alerts", "irregularities"):
                for record in payload.get(collection_name, []):
                    wkt = line_wkt(record) or point_wkt(record)
                    if not wkt:
                        # Without geometry the event cannot be assigned to a sample junction.
                        continue
                    observed_at = as_timestamp(record)
                    event_key = record.get("uuid") or record.get("id")
                    # Keep this sample focused on events nearest the assigned Waze intersection.
                    cur.execute(
                        """INSERT INTO provider_events
                               (intersection_id, provider, provider_event_id, event_type,
                                observed_at, geometry, speed_kmh, regular_speed_kmh,
                                reliability, confidence, raw_payload)
                           SELECT i.intersection_id, 'waze', %s, %s, %s,
                                  ST_GeomFromText(%s, 4326),
                                  %s, %s, %s, %s, %s
                           FROM sample_intersections i
                           WHERE i.assigned_provider = 'waze'
                             AND ST_DWithin(i.location::geography, ST_GeomFromText(%s, 4326)::geography, 1000)
                           ORDER BY ST_Distance(i.location::geography, ST_GeomFromText(%s, 4326)::geography)
                           LIMIT 1
                           ON CONFLICT (provider, provider_event_id, observed_at) DO NOTHING""",
                        (
                            str(event_key) if event_key is not None else None,
                            str(record.get("type") or collection_name),
                            observed_at,
                            wkt,
                            record.get("speedKMH", record.get("speedKPH")) or (float(record["speed"]) * 3.6 if record.get("speed") is not None and collection_name == "jams" else record.get("speed")),
                            record.get("regularSpeed"),
                            record.get("reliability"),
                            record.get("confidence"),
                            Jsonb(record),
                            wkt,
                            wkt,
                        ),
                    )
                    inserted += cur.rowcount
        conn.commit()
    print(f"waze_events_inserted={inserted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
