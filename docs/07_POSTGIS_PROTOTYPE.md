# PostgreSQL/PostGIS Traffic Data Prototype

## Scope

This first pass stores the sample intersections, the nearest TomTom road segment returned for each query point, and timestamped Flow Segment observations. TomTom documents the Flow Segment endpoint as returning the closest road fragment to a WGS84 point, with speed, travel time, confidence, road class, closure flag, and segment coordinates. Vietnam is listed in the Traffic Flow and Traffic Incidents coverage table.

The starter file `data/sample_intersections.json` contains three approximate central Ho Chi Minh City sample points, assigned one source per intersection: Ben Thanh → TomTom, Turtle Lake → Google Routes, Dinh Tien Hoang/Le Duan → Waze. Each TomTom point queries the nearest road fragment once per collection cycle. It is a wiring sample, not a complete survey of all incoming/outgoing arms at each junction. Add separate approach points after checking the intended junction geometry on a map.

`data_source_assignments` records the provider/method and whether credentials or partner access are configured. `provider_events` is for Waze event and jam geometries. Google Routes responses are deliberately not written to PostGIS under the standard API terms; its assignment is a live route cross-check only, not a training-data source.

## Start the database and collect a snapshot

Keep `API_TOMTOM` and the local database settings in `.env`. Do not commit `.env`.

```bash
docker compose up -d db
python -m pip install 'psycopg[binary]>=3.2' requests
python data/scripts/collect_tomtom.py
```

For Waze, first place an approved JSON feed URL from Partner Hub in `WAZE_DATA_FEED_URL`, then run:

```bash
python data/scripts/collect_waze_feed.py
```

The Waze collector stores jam/alert/irregularity geometry and selected event fields in `provider_events`, assigning each event to the nearest Waze-assigned sample intersection within 1 km. Waze feed URLs contain a private token; they are read from `.env` and never printed. The feed is restricted to approved managed areas.

Repeat collection every five minutes for a bounded initial run:

```bash
python data/scripts/collect_tomtom.py --interval-seconds 300 --max-cycles 12
```

Use `--max-cycles 0` to keep collecting until interrupted. TomTom requests are sent sequentially, and the API key is not written into the database or printed to output.

## Tables

- `sample_intersections`: sample junction point, city, and assigned provider.
- `sample_query_points`: exact point queried for each intersection/approach.
- `data_source_assignments`: provider allocation, acquisition mode, and credential/access status.
- `road_segments`: deduplicated TomTom segment geometry and functional road class.
- `traffic_observations`: speed, free-flow speed, travel times, confidence, road closure, capture time, provider response JSON.
- `provider_events`: Waze jams/incidents/irregularities with source geometry and selected normalized fields.

All geometries use SRID 4326 and have GiST indexes. `collected_at` records when this collector fetched the sample. TomTom's HTTP `Date` header is stored separately as `source_updated_at`; it is not treated as a sensor measurement timestamp.

Inspect the newest data:

```bash
docker compose exec db psql -U capstone -d capstone_traffic -c \
  "SELECT q.query_point_id, o.collected_at, o.current_speed_kmh, o.free_flow_speed_kmh, o.confidence, s.functional_road_class FROM traffic_observations o JOIN sample_query_points q USING (query_point_id) JOIN road_segments s USING (segment_id) ORDER BY o.collected_at DESC;"
```

## Before using it for forecasting

Collect over multiple periods, verify the points match the intended road approaches, and check missingness and confidence. The current sampling layout does not provide a sensor's flow/occupancy or a complete fixed road graph. It is enough to validate storage and build an initial time series, but model choice and training should wait until the sample's temporal coverage and data quality are reviewed. Confirm TomTom account-specific terms allow the desired retention and research publication/distribution. Google Routes returns route-level traffic intervals, not the same point-based speed series; its standard terms restrict storage of most response content. Waze data requires an approved Partner Hub feed for its managed area.

## Reference

- [TomTom Flow Segment Data](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data)
- [TomTom Traffic API Market Coverage](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/product-information/market-coverage)
