CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS sample_intersections (
    intersection_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    country_code CHAR(2) NOT NULL,
    assigned_provider TEXT NOT NULL DEFAULT 'tomtom'
        CHECK (assigned_provider IN ('tomtom', 'google_maps', 'waze')),
    location GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sample_intersections_location_gix
    ON sample_intersections USING GIST (location);

CREATE TABLE IF NOT EXISTS sample_query_points (
    query_point_id TEXT PRIMARY KEY,
    intersection_id TEXT NOT NULL REFERENCES sample_intersections(intersection_id),
    approach_label TEXT NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (intersection_id, approach_label)
);
CREATE INDEX IF NOT EXISTS sample_query_points_location_gix
    ON sample_query_points USING GIST (location);

CREATE TABLE IF NOT EXISTS data_source_assignments (
    intersection_id TEXT PRIMARY KEY REFERENCES sample_intersections(intersection_id),
    provider TEXT NOT NULL CHECK (provider IN ('tomtom', 'google_maps', 'waze')),
    acquisition_mode TEXT NOT NULL,
    access_status TEXT NOT NULL,
    provider_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Generic event storage for partner feeds such as Waze. Google Routes responses
-- are intentionally not persisted here under the standard Routes API terms.
CREATE TABLE IF NOT EXISTS provider_events (
    event_id BIGSERIAL PRIMARY KEY,
    intersection_id TEXT REFERENCES sample_intersections(intersection_id),
    provider TEXT NOT NULL CHECK (provider IN ('waze')),
    provider_event_id TEXT,
    event_type TEXT NOT NULL,
    observed_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    geometry GEOMETRY(Geometry, 4326),
    speed_kmh DOUBLE PRECISION,
    regular_speed_kmh DOUBLE PRECISION,
    reliability DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    raw_payload JSONB NOT NULL,
    UNIQUE (provider, provider_event_id, observed_at)
);
CREATE INDEX IF NOT EXISTS provider_events_geometry_gix
    ON provider_events USING GIST (geometry);
CREATE INDEX IF NOT EXISTS provider_events_time_idx
    ON provider_events (provider, observed_at DESC);

CREATE TABLE IF NOT EXISTS road_segments (
    segment_id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    segment_key TEXT NOT NULL,
    functional_road_class TEXT,
    geometry GEOMETRY(LineString, 4326) NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, segment_key)
);
CREATE INDEX IF NOT EXISTS road_segments_geometry_gix
    ON road_segments USING GIST (geometry);

CREATE TABLE IF NOT EXISTS traffic_observations (
    observation_id BIGSERIAL PRIMARY KEY,
    query_point_id TEXT NOT NULL REFERENCES sample_query_points(query_point_id),
    segment_id BIGINT NOT NULL REFERENCES road_segments(segment_id),
    provider TEXT NOT NULL,
    source_updated_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL,
    current_speed_kmh DOUBLE PRECISION,
    free_flow_speed_kmh DOUBLE PRECISION,
    current_travel_time_s DOUBLE PRECISION,
    free_flow_travel_time_s DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    road_closed BOOLEAN,
    raw_response JSONB NOT NULL,
    CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1)
);
CREATE INDEX IF NOT EXISTS traffic_observations_collected_at_idx
    ON traffic_observations (collected_at DESC);
CREATE INDEX IF NOT EXISTS traffic_observations_query_point_time_idx
    ON traffic_observations (query_point_id, collected_at DESC);
