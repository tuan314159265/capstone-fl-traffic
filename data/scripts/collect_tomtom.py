"""Collect one TomTom Traffic Flow snapshot for each configured sample point."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import psycopg
import requests
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POINTS = ROOT / "data" / "sample_intersections.json"
FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"


def load_env_file(path: Path = ROOT / ".env") -> None:
    """Load simple KEY=value entries without printing secrets or overriding env."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        value = value.strip().strip("\"'")
        os.environ.setdefault(key, value)


def read_points(path: Path) -> list[dict]:
    points = json.loads(path.read_text(encoding="utf-8"))
    if not points:
        raise ValueError("Sample point file has no entries")
    for point in points:
        if not all(k in point for k in ("intersection_id", "name", "city", "country_code", "latitude", "longitude", "approach_label", "assigned_provider", "acquisition_mode")):
            raise ValueError("Each sample requires intersection metadata and latitude/longitude")
    return points


def register_sample_assignments(
    conn: psycopg.Connection,
    points: list[dict],
    tomtom_key_present: bool,
    google_key_present: bool,
    waze_feed_present: bool,
) -> None:
    statuses = {
        "tomtom": "credential_present_unverified" if tomtom_key_present else "needs_api_key",
        "google_maps": "credential_present_unverified" if google_key_present else "needs_api_key",
        "waze": "partner_feed_present_unverified" if waze_feed_present else "needs_approved_partner_feed",
    }
    with conn.cursor() as cur:
        for point in points:
            cur.execute(
                """INSERT INTO sample_intersections
                       (intersection_id, name, city, country_code, assigned_provider, location)
                   VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                   ON CONFLICT (intersection_id) DO UPDATE SET
                       name = EXCLUDED.name, city = EXCLUDED.city,
                       country_code = EXCLUDED.country_code,
                       assigned_provider = EXCLUDED.assigned_provider,
                       location = EXCLUDED.location""",
                (point["intersection_id"], point["name"], point["city"], point["country_code"], point["assigned_provider"], point["longitude"], point["latitude"]),
            )
            cur.execute(
                """INSERT INTO data_source_assignments
                       (intersection_id, provider, acquisition_mode, access_status, provider_config)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (intersection_id) DO UPDATE SET
                       provider = EXCLUDED.provider,
                       acquisition_mode = EXCLUDED.acquisition_mode,
                       access_status = EXCLUDED.access_status,
                       provider_config = EXCLUDED.provider_config,
                       updated_at = now()""",
                (point["intersection_id"], point["assigned_provider"], point["acquisition_mode"], statuses[point["assigned_provider"]], Jsonb(point.get("provider_config", {}))),
            )


def fetch_flow(session: requests.Session, api_key: str, point: dict) -> tuple[dict, datetime | None]:
    try:
        response = session.get(
            FLOW_URL,
            params={
                "key": api_key,
                "point": f"{point['latitude']},{point['longitude']}",
                "unit": "kmph",
                "thickness": 10,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        # Requests exceptions can include the full URL, including its API key.
        raise RuntimeError(f"TomTom request failed for sample {point['intersection_id']} ({type(exc).__name__})") from None
    if response.status_code != 200:
        # Avoid printing request URLs: the key is passed as a query parameter.
        raise RuntimeError(f"TomTom returned HTTP {response.status_code} for sample {point['intersection_id']}")
    payload = response.json()
    flow = payload.get("flowSegmentData")
    if not isinstance(flow, dict):
        raise RuntimeError(f"TomTom response has no flowSegmentData for sample {point['intersection_id']}")
    date_header = response.headers.get("Date")
    source_updated_at = parsedate_to_datetime(date_header).astimezone(timezone.utc) if date_header else None
    return flow, source_updated_at


def flow_coordinates(flow: dict) -> list[tuple[float, float]]:
    coordinates = flow.get("coordinates", {}).get("coordinate", [])
    line = [(float(item["longitude"]), float(item["latitude"])) for item in coordinates]
    if len(line) < 2:
        raise RuntimeError("TomTom returned fewer than two coordinates for the road segment")
    return line


def stable_segment_key(line: list[tuple[float, float]]) -> str:
    canonical = json.dumps([[round(lon, 6), round(lat, 6)] for lon, lat in line], separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_observation(conn: psycopg.Connection, point: dict, flow: dict, source_updated_at: datetime | None) -> None:
    line = flow_coordinates(flow)
    segment_key = stable_segment_key(line)
    wkt = "LINESTRING(" + ",".join(f"{lon} {lat}" for lon, lat in line) + ")"
    collected_at = datetime.now(timezone.utc)
    query_point_id = f"{point['intersection_id']}:{point['approach_label']}"

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO sample_intersections
                   (intersection_id, name, city, country_code, assigned_provider, location)
               VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
               ON CONFLICT (intersection_id) DO UPDATE SET
                   name = EXCLUDED.name, city = EXCLUDED.city,
                   country_code = EXCLUDED.country_code,
                   assigned_provider = EXCLUDED.assigned_provider,
                   location = EXCLUDED.location""",
            (point["intersection_id"], point["name"], point["city"], point["country_code"], point["assigned_provider"], point["longitude"], point["latitude"]),
        )
        cur.execute(
            """INSERT INTO sample_query_points (query_point_id, intersection_id, approach_label, location)
               VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
               ON CONFLICT (query_point_id) DO UPDATE SET
                   intersection_id = EXCLUDED.intersection_id,
                   approach_label = EXCLUDED.approach_label, location = EXCLUDED.location""",
            (query_point_id, point["intersection_id"], point["approach_label"], point["longitude"], point["latitude"]),
        )
        cur.execute(
            """INSERT INTO road_segments (provider, segment_key, functional_road_class, geometry)
               VALUES ('tomtom', %s, %s, ST_GeomFromText(%s, 4326))
               ON CONFLICT (provider, segment_key) DO UPDATE SET
                   functional_road_class = EXCLUDED.functional_road_class,
                   geometry = EXCLUDED.geometry, last_seen_at = now()
               RETURNING segment_id""",
            (segment_key, flow.get("frc"), wkt),
        )
        segment_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO traffic_observations (
                   query_point_id, segment_id, provider, source_updated_at, collected_at,
                   current_speed_kmh, free_flow_speed_kmh, current_travel_time_s,
                   free_flow_travel_time_s, confidence, road_closed, raw_response
               ) VALUES (%s, %s, 'tomtom', %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                query_point_id,
                segment_id,
                source_updated_at,
                collected_at,
                flow.get("currentSpeed"),
                flow.get("freeFlowSpeed"),
                flow.get("currentTravelTime"),
                flow.get("freeFlowTravelTime"),
                flow.get("confidence"),
                flow.get("roadClosure"),
                Jsonb(flow),
            ),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points", type=Path, default=DEFAULT_POINTS, help="JSON file of sample junction coordinates")
    parser.add_argument("--interval-seconds", type=int, default=0, help="Repeat collection at this interval; 0 means one snapshot")
    parser.add_argument("--max-cycles", type=int, default=1, help="Number of cycles when interval is enabled; 0 means until interrupted")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent TomTom requests per cycle; DB writes remain on one connection")
    args = parser.parse_args()

    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")

    load_env_file()
    api_key = os.environ.get("API_TOMTOM")
    if not api_key:
        raise SystemExit("API_TOMTOM is missing from .env")
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://capstone:change_me_locally@localhost:54329/capstone_traffic",
    )
    points = read_points(args.points)
    tomtom_points = [point for point in points if point["assigned_provider"] == "tomtom"]
    if not tomtom_points:
        raise SystemExit("No sample intersections are assigned to TomTom")
    cycles = 0
    def fetch_point(point: dict) -> tuple[dict, datetime | None]:
        # Use a separate Session per worker; never share requests.Session across threads.
        with requests.Session() as session:
            return fetch_flow(session, api_key, point)

    with ThreadPoolExecutor(max_workers=args.workers) as executor, psycopg.connect(database_url) as conn:
        register_sample_assignments(
            conn,
            points,
            bool(api_key),
            bool(os.environ.get("GOOGLE_MAPS_API_KEY")),
            bool(os.environ.get("WAZE_DATA_FEED_URL")),
        )
        conn.commit()
        while args.max_cycles == 0 or cycles < args.max_cycles:
            cycle_started = time.monotonic()
            saved = 0
            failed = 0
            # Requests run concurrently; a single DB connection writes results in point order.
            futures = [executor.submit(fetch_point, point) for point in tomtom_points]
            for point, future in zip(tomtom_points, futures):
                try:
                    flow, source_updated_at = future.result()
                    # Commit each point independently so one failed request or
                    # invalid segment does not roll back the other observations.
                    with conn.transaction():
                        write_observation(conn, point, flow, source_updated_at)
                    saved += 1
                except (RuntimeError, ValueError, psycopg.Error, requests.RequestException) as exc:
                    failed += 1
                    # Exception types are safe; request/connection URLs may contain secrets.
                    print(f"sample={point['intersection_id']} failed={type(exc).__name__}", flush=True)
            cycles += 1
            print(f"cycle={cycles} observations={saved} failed={failed}", flush=True)
            if not saved:
                return 1
            if args.interval_seconds <= 0 or (args.max_cycles and cycles >= args.max_cycles):
                break
            remaining = args.interval_seconds - (time.monotonic() - cycle_started)
            if remaining > 0:
                time.sleep(remaining)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
