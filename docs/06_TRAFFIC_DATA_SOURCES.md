# Traffic Data Sources — TomTom, Google Maps, Waze

## Recommendation

Use TomTom Traffic Flow as the primary live traffic source and Traffic Incidents as supplementary event labels. Treat Google Maps Routes as a limited cross-check for route ETA/traffic categories, not as a source for a stored training dataset. Treat Waze as optional unless the project obtains Waze for Cities partner access.

For the initial three-node wiring sample, `data/sample_intersections.json` assigns Ben Thanh to TomTom, Turtle Lake to Google Routes, and Dinh Tien Hoang/Le Duan to Waze. This demonstrates source allocation per node. Since provider and location are confounded in this layout, it is not a fair provider comparison; for that, use overlapping locations and timestamps where the provider licenses permit it.

The current `.env` contains `API_TOMTOM`; `GOOGLE_MAPS_API_KEY` and `WAZE_DATA_FEED_URL` are placeholders without values. Real keys/feed URLs belong only in `.env`; `.env.example` lists variable names without secrets.

## Data needed by this project

The existing model/data schema expects time-series traffic features split among clients/nodes. For a traffic-provider collector, persist a normalized observation with at least:

| Field | Purpose |
|---|---|
| `provider`, `provider_record_id` | Provenance and deduplication; record ID may be unavailable, so use a geometry-derived ID where permitted. |
| `observed_at`, `fetched_at` | Distinguish provider observation time from collection time; use UTC. |
| `segment_geometry`, `road_name`, `road_class` | Spatial matching and partitioning; preserve coordinates only as allowed by the provider terms. |
| `current_speed_kmh`, `free_flow_speed_kmh` | Main flow features and congestion ratio. |
| `current_travel_time_s`, `free_flow_travel_time_s`, `confidence` | Additional flow features / quality indicators when returned. |
| `incident_type`, `severity`, `delay_s`, `incident_geometry`, `is_road_closed` | Optional incident labels; null when there is no incident. |
| `units`, `raw_schema_version`, `request_area` | Make parsing, auditing, and reproducibility possible. |

Before modeling, choose a bounded study area, fixed sampling cadence, and stable segment-to-node mapping. Aggregate segments into node/zone features such as mean/median speed, congestion ratio, incident count, and missingness. The resulting data can then be reshaped into the existing `[samples, hist_len, N, F]` input format. A single live snapshot is not enough for forecasting: a time series must be collected over time or obtained through a historical-data product.

## Provider comparison

| Provider | Useful traffic data | Access / setup | Fit for this project |
|---|---|---|---|
| **TomTom Traffic Flow** | Current and free-flow speed, travel times, confidence/quality, road geometry/class. Traffic Flow updates about once per minute. | Existing `API_TOMTOM`; query by area/road location. Coverage and the enabled product/plan must be checked for the selected study area. | Best available primary source for live segment observations. Build a collector and accumulate a time series. Confirm the account's license permits the intended retention, research use, and any publication or redistribution before committing a dataset. |
| **TomTom Traffic Incidents** | Jam/incident location, road name, type, delay, significance/severity, distance and geometry. Also updated about once per minute. | Same provider family/key, subject to product entitlement and area coverage. | Useful as labels/context, not a substitute for dense sensor speed observations. |
| **Google Maps Routes API** | Route duration/distance and traffic-aware route polyline intervals with categories such as normal/slow/jam. Needs `TRAFFIC_AWARE`/`TRAFFIC_AWARE_OPTIMAL` and a field mask for traffic intervals. | Separate Google Cloud project, enabled Routes API, API key, and billing. | Useful to compare ETA/traffic along chosen routes. It does not provide the same general segment-speed feed as TomTom. Google policy restricts prefetching, storage, and caching of most Routes content, so do not collect its responses into the training corpus without an applicable license/exception. |
| **Waze Data Feed** | Jams, unusual traffic, and user-reported incidents/alerts; feed can be JSON/XML and is refreshed every 2 minutes. | Partner Hub feed available to approved Waze for Cities partners and approved managed areas. It is not a public API key that any student can self-issue. | Optional event/incident comparison if the project or collaborating organization is eligible. Feed limits include up to 5,000 events; normalize speed units carefully (`speedKMH` versus `speed`). Follow Waze attribution and sharing terms. |
| **HCMC Traffic Information Portal** | Public UI documents road closures, incidents, traffic conditions, congestion alerts, cameras, and traffic diversions. | Public pages reviewed do not publish a data-feed/API specification. The City open-data portal points to a separate public catalog, but its content could not be inspected in this session. | Do not scrape undocumented endpoints or copy portal content into PostGIS yet. The portal terms restrict copying/reuse without prior written permission. Request an official API/open-data dataset and reuse permission first. |

## HCMC portal check

The portal's user guide confirms that the web map displays closures, incidents, traffic status, congestion alerts, cameras, and traffic diversions. It does not document an API/feed contract for these layers. Its terms permit viewing/downloading/printing only for personal noncommercial use and state that copying, publication, or reuse requires prior written permission. The public home page also shows a `LIVE` traffic status label, but the indexed status timestamp is stale, so it should not be treated as a reliable freshness guarantee.

Using the browser-resolved IP and non-sensitive browser headers, the public home HTML and its linked page script loaded successfully. The script indicates that the map renders traffic as a visual overlay and loads layer metadata through the site's AJAX proxy; it does not expose a documented tabular sensor feed. Its legend presents speed bands over 15- and 30-minute periods, so this source would be categorical/aggregated map data rather than TomTom-style per-segment numeric observations. No internal AJAX method or map tile was called, and no portal content was written to PostGIS.

The city's separate open-data landing page says shared datasets and technical access instructions are available in its open-data catalog. The catalog presented a human-verification challenge during this review, so no matching traffic dataset or API was confirmed.

## Current implementation gap

This repository currently has no data collector or non-IID partition implementation; `data/scripts/download_data.py` and `partition_noniid.py` are empty. `docs/03_DATA_SCHEMA.md` describes sensor tensors but does not yet define provider observation records or stable road-segment/node mapping. Add the collector, normalized storage format, and provider-specific terms/attribution before using these feeds in experiments.

## Official references

- [TomTom Traffic API overview](https://developer.tomtom.com/traffic-api/documentation/product-information/introduction)
- [Google Routes API: traffic-aware polylines](https://developers.google.com/maps/documentation/routes/traffic_on_polylines)
- [Google Routes API policies and attributions](https://developers.google.com/maps/documentation/routes/policies)
- [Waze Data Feed](https://support.google.com/waze/partners/answer/10618035?hl=en)
- [Waze Data Feed specifications](https://support.google.com/waze/partners/answer/13458165?hl=en)
- [Waze for Cities eligibility and program](https://support.google.com/waze/partners/answer/10618477?hl=en)
- [HCMC Traffic Portal user guide](https://giaothong.hochiminhcity.gov.vn/Userguide/)
- [HCMC Traffic Portal terms of use](https://giaothong.hochiminhcity.gov.vn/TermOfUse/)
- [HCMC Open Data landing page](https://data.hochiminhcity.gov.vn/)
