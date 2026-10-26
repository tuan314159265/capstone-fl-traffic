"""Back up and merge a local collection day into AWS over SSH without replacing data.

Dates use Asia/Ho_Chi_Minh. Source data is read in a single database snapshot.
Only the selected observations and their referenced metadata are imported.
Local/remote IDs are remapped, original timestamps and raw JSON are preserved,
and a second import can be checked to ensure it inserts no duplicate records.
"""

import argparse
import csv
from datetime import date, datetime, timedelta
import io
import ipaddress
import json
import os
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra/aws"
TABLE_COLUMNS = {
    "sample_intersections": "intersection_id name city country_code assigned_provider location created_at",
    "sample_query_points": "query_point_id intersection_id approach_label location created_at",
    "data_source_assignments": "intersection_id provider acquisition_mode access_status provider_config updated_at",
    "road_segments": "segment_id provider segment_key functional_road_class geometry first_seen_at last_seen_at",
    "traffic_observations": "observation_id query_point_id segment_id provider source_updated_at collected_at current_speed_kmh free_flow_speed_kmh current_travel_time_s free_flow_travel_time_s confidence road_closed raw_response",
}


def write_capture(path, command):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        subprocess.run(command, stdout=handle, check=True)


def build_import_sql(payload):
    output = io.StringIO()
    output.write("BEGIN;\nSET LOCAL lock_timeout = '30s';\nSET LOCAL statement_timeout = '120s';\n")
    for table, names in TABLE_COLUMNS.items():
        columns = names.split()
        output.write(f"CREATE TEMP TABLE imported_{table} (LIKE public.{table}) ON COMMIT DROP;\n")
        output.write(f"COPY imported_{table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv, NULL '\\N');\n")
        writer = csv.writer(output, lineterminator="\n")
        for row in payload[table]:
            values = []
            for column in columns:
                value = row[column]
                if value is None:
                    value = "\\N"
                elif isinstance(value, bool):
                    value = "true" if value else "false"
                elif isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                values.append(value)
            writer.writerow(values)
        output.write("\\.\n")
    output.write((INFRA / "import_local.sql").read_text())
    output.write("\nCOMMIT;\n")
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date() - timedelta(days=1))
    parser.add_argument("--verify-idempotency", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    state = INFRA / ".state" / f"import-{args.date}-{stamp}"
    state.mkdir(parents=True, mode=0o700)
    outputs = json.loads(subprocess.check_output([
        str(Path.home() / ".local/bin/terraform"), f"-chdir={INFRA}", "output", "-json",
    ]))
    host = str(ipaddress.IPv4Address(outputs["public_ip"]["value"]))
    ssh = ["ssh", "-i", str(Path.home() / ".ssh/capstone-traffic-aws"),
           "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
           "-o", f"UserKnownHostsFile={INFRA / '.state/known_hosts'}",
           "-o", "ConnectTimeout=10", f"ubuntu@{host}"]
    source_db = ["docker", "exec", "-i", "capstone-traffic-db", "psql",
                 "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", "capstone", "-d", "capstone_traffic"]
    target_db = ssh + ["cd /opt/capstone-traffic && sudo docker compose exec -T db "
                       "psql -X -qAt -v ON_ERROR_STOP=1 -U capstone -d capstone_traffic"]

    print(f"Backing up local database before exporting {args.date}...", flush=True)
    write_capture(state / "local-before.dump", ["docker", "exec", "capstone-traffic-db",
                  "pg_dump", "-U", "capstone", "-d", "capstone_traffic", "-Fc"])
    query = f"""
    WITH observations AS (
      SELECT * FROM traffic_observations
      WHERE (collected_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = DATE '{args.date}'
    ), points AS (
      SELECT p.* FROM sample_query_points p
      WHERE EXISTS (SELECT 1 FROM observations o WHERE o.query_point_id = p.query_point_id)
    ), intersections AS (
      SELECT s.* FROM sample_intersections s
      WHERE EXISTS (SELECT 1 FROM points p WHERE p.intersection_id = s.intersection_id)
    )
    SELECT jsonb_build_object(
      'sample_intersections', COALESCE((SELECT jsonb_agg(to_jsonb(s) || jsonb_build_object('location', s.location::text) ORDER BY intersection_id) FROM intersections s), '[]'::jsonb),
      'sample_query_points', COALESCE((SELECT jsonb_agg(to_jsonb(p) || jsonb_build_object('location', p.location::text) ORDER BY query_point_id) FROM points p), '[]'::jsonb),
      'data_source_assignments', COALESCE((SELECT jsonb_agg(to_jsonb(a) ORDER BY intersection_id) FROM data_source_assignments a WHERE EXISTS (SELECT 1 FROM intersections s WHERE s.intersection_id=a.intersection_id)), '[]'::jsonb),
      'road_segments', COALESCE((SELECT jsonb_agg(to_jsonb(s) || jsonb_build_object('geometry', s.geometry::text) ORDER BY segment_id) FROM road_segments s WHERE EXISTS (SELECT 1 FROM observations o WHERE o.segment_id=s.segment_id)), '[]'::jsonb),
      'traffic_observations', COALESCE((SELECT jsonb_agg(to_jsonb(o) ORDER BY observation_id) FROM observations o), '[]'::jsonb)
    );
    """
    exported = subprocess.check_output(source_db, input=query, text=True)
    payload = json.loads(exported)
    (state / "source.json").write_text(exported)
    counts = {name: len(rows) for name, rows in payload.items()}
    print("Exported rows: " + json.dumps(counts), flush=True)
    if not payload["traffic_observations"]:
        raise SystemExit(f"No local observations on {args.date}; nothing imported.")

    print("Backing up cloud database before merge...", flush=True)
    write_capture(state / "cloud-before.dump", ssh + [
        "cd /opt/capstone-traffic && sudo docker compose exec -T db "
        "pg_dump -U capstone -d capstone_traffic -Fc",
    ])
    sql = build_import_sql(payload)
    (state / "import.sql").write_text(sql)
    print("Merging historical data in one transaction...", flush=True)
    result = subprocess.check_output(target_db, input=sql, text=True)
    summary = json.loads(result.strip())
    assert summary["matched_rows"] == counts["traffic_observations"]
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if args.verify_idempotency:
        print("Checking a repeated import inserts zero duplicates...", flush=True)
        repeated = json.loads(subprocess.check_output(target_db, input=sql, text=True).strip())
        assert repeated["inserted_rows"] == 0, repeated
        assert repeated["matched_rows"] == counts["traffic_observations"]
        summary["idempotency_verified"] = True
        print(json.dumps(repeated, ensure_ascii=False), flush=True)
    summary.update({"date_vn": str(args.date), "host": host, "source_counts": counts})
    (state / "receipt.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    subprocess.run(ssh + ["sudo systemctl start capstone-backup.service"], check=True)
    write_capture(state / "cloud-after.dump", ssh + [
        "cd /opt/capstone-traffic && sudo docker compose exec -T db "
        "pg_dump -U capstone -d capstone_traffic -Fc",
    ])
    print(f"Import verified. Backups and receipt: {state}", flush=True)


if __name__ == "__main__":
    main()
