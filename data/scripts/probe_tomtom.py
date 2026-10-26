"""Make one TomTom Flow Segment request and print a safe summary (no database)."""

from __future__ import annotations

import argparse
import json
import os
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests


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
        os.environ.setdefault(key, value.strip().strip("\"'"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points", type=Path, default=DEFAULT_POINTS, help="JSON file of sample points")
    parser.add_argument("--point-id", help="intersection_id to query; defaults to the first TomTom point")
    args = parser.parse_args()

    load_env_file()
    api_key = os.environ.get("API_TOMTOM")
    if not api_key:
        raise SystemExit("API_TOMTOM is missing from .env")

    points = json.loads(args.points.read_text(encoding="utf-8"))
    eligible = [p for p in points if p.get("assigned_provider") == "tomtom"]
    point = next((p for p in eligible if p.get("intersection_id") == args.point_id), None) if args.point_id else (eligible[0] if eligible else None)
    if point is None:
        choices = ", ".join(p.get("intersection_id", "?") for p in eligible)
        raise SystemExit(f"TomTom point not found. Available point IDs: {choices or '(none)'}")

    try:
        response = requests.get(
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
        # The request URL contains the API key; never print the exception text.
        raise SystemExit(f"TomTom request failed ({type(exc).__name__}); check network and API key configuration") from None
    if response.status_code != 200:
        # Do not print response/request URLs or bodies, which may expose credentials.
        raise SystemExit(f"TomTom returned HTTP {response.status_code}; check API key, product access, and quota")

    try:
        flow = response.json().get("flowSegmentData")
    except (ValueError, AttributeError):
        flow = None
    if not isinstance(flow, dict):
        raise SystemExit("TomTom response did not include flowSegmentData")

    raw_coordinates = flow.get("coordinates", {}).get("coordinate", [])
    endpoints = []
    if raw_coordinates:
        endpoints.append({"latitude": raw_coordinates[0].get("latitude"), "longitude": raw_coordinates[0].get("longitude")})
        if len(raw_coordinates) > 1:
            endpoints.append({"latitude": raw_coordinates[-1].get("latitude"), "longitude": raw_coordinates[-1].get("longitude")})
    date_header = response.headers.get("Date")
    result = {
        "sample_id": point["intersection_id"],
        "sample_name": point.get("name"),
        "query_point": {"latitude": point["latitude"], "longitude": point["longitude"]},
        "http_status": response.status_code,
        "response_date_utc": parsedate_to_datetime(date_header).isoformat() if date_header else None,
        "segment": {
            "frc": flow.get("frc"),
            "coordinates_count": len(coordinates),
            "endpoints": endpoints,
        },
        "traffic": {
            "current_speed_kmh": flow.get("currentSpeed"),
            "free_flow_speed_kmh": flow.get("freeFlowSpeed"),
            "current_travel_time_s": flow.get("currentTravelTime"),
            "free_flow_travel_time_s": flow.get("freeFlowTravelTime"),
            "confidence": flow.get("confidence"),
            "road_closed": flow.get("roadClosure"),
        },
        "stored_in_database": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
