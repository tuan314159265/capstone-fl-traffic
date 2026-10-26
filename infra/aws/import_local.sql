-- Executed after temporary source tables have been populated in one transaction.
-- Protect current node identities: do not silently move an existing query point.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM imported_sample_query_points s
    JOIN public.sample_query_points t USING (query_point_id)
    WHERE s.intersection_id IS DISTINCT FROM t.intersection_id
       OR s.approach_label IS DISTINCT FROM t.approach_label
       OR NOT ST_Equals(s.location, t.location)
  ) THEN
    RAISE EXCEPTION 'Source query point metadata differs from the cloud point';
  END IF;
  IF EXISTS (
    SELECT 1 FROM imported_sample_intersections s
    JOIN public.sample_intersections t USING (intersection_id)
    WHERE NOT ST_Equals(s.location, t.location)
       OR s.assigned_provider IS DISTINCT FROM t.assigned_provider
  ) THEN
    RAISE EXCEPTION 'Source intersection metadata differs from the cloud intersection';
  END IF;
END $$;

INSERT INTO public.sample_intersections
  (intersection_id, name, city, country_code, assigned_provider, location, created_at)
SELECT intersection_id, name, city, country_code, assigned_provider, location, created_at
FROM imported_sample_intersections
ON CONFLICT (intersection_id) DO NOTHING;

INSERT INTO public.sample_query_points
  (query_point_id, intersection_id, approach_label, location, created_at)
SELECT query_point_id, intersection_id, approach_label, location, created_at
FROM imported_sample_query_points
ON CONFLICT (query_point_id) DO NOTHING;

INSERT INTO public.data_source_assignments
  (intersection_id, provider, acquisition_mode, access_status, provider_config, updated_at)
SELECT intersection_id, provider, acquisition_mode, access_status, provider_config, updated_at
FROM imported_data_source_assignments
ON CONFLICT (intersection_id) DO NOTHING;

INSERT INTO public.road_segments AS target
  (provider, segment_key, functional_road_class, geometry, first_seen_at, last_seen_at)
SELECT provider, segment_key, functional_road_class, geometry, first_seen_at, last_seen_at
FROM imported_road_segments
ON CONFLICT (provider, segment_key) DO UPDATE SET
  first_seen_at = LEAST(target.first_seen_at, EXCLUDED.first_seen_at),
  last_seen_at = GREATEST(target.last_seen_at, EXCLUDED.last_seen_at);

-- Local numeric segment/observation IDs cannot be reused on the cloud DB.
-- Resolve segments by their provider and stable geometry hash instead.
LOCK TABLE public.traffic_observations IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE import_counts ON COMMIT DROP AS
SELECT count(*) AS target_before FROM public.traffic_observations;

INSERT INTO public.traffic_observations
  (query_point_id, segment_id, provider, source_updated_at, collected_at,
   current_speed_kmh, free_flow_speed_kmh, current_travel_time_s,
   free_flow_travel_time_s, confidence, road_closed, raw_response)
SELECT s.query_point_id, target.segment_id, s.provider,
       s.source_updated_at, s.collected_at, s.current_speed_kmh,
       s.free_flow_speed_kmh, s.current_travel_time_s,
       s.free_flow_travel_time_s, s.confidence, s.road_closed, s.raw_response
FROM imported_traffic_observations s
JOIN imported_road_segments source ON source.segment_id = s.segment_id
JOIN public.road_segments target ON target.provider = source.provider
  AND target.segment_key = source.segment_key
WHERE NOT EXISTS (
  SELECT 1 FROM public.traffic_observations existing
  WHERE existing.query_point_id = s.query_point_id
    AND existing.segment_id = target.segment_id
    AND existing.provider = s.provider
    AND existing.collected_at = s.collected_at
    AND existing.source_updated_at IS NOT DISTINCT FROM s.source_updated_at
);

-- Compare every imported field, including raw JSON, against the source snapshot.
-- Any missing or conflicting record aborts the entire import.
CREATE TEMP TABLE import_verification ON COMMIT DROP AS
SELECT count(*) AS source_rows,
       count(*) FILTER (WHERE EXISTS (
         SELECT 1 FROM public.traffic_observations existing
         WHERE existing.query_point_id = s.query_point_id
           AND existing.segment_id = target.segment_id
           AND existing.provider = s.provider
           AND existing.collected_at = s.collected_at
           AND existing.source_updated_at IS NOT DISTINCT FROM s.source_updated_at
           AND existing.current_speed_kmh IS NOT DISTINCT FROM s.current_speed_kmh
           AND existing.free_flow_speed_kmh IS NOT DISTINCT FROM s.free_flow_speed_kmh
           AND existing.current_travel_time_s IS NOT DISTINCT FROM s.current_travel_time_s
           AND existing.free_flow_travel_time_s IS NOT DISTINCT FROM s.free_flow_travel_time_s
           AND existing.confidence IS NOT DISTINCT FROM s.confidence
           AND existing.road_closed IS NOT DISTINCT FROM s.road_closed
           AND existing.raw_response = s.raw_response
       )) AS matched_rows
FROM imported_traffic_observations s
LEFT JOIN imported_road_segments source ON source.segment_id = s.segment_id
LEFT JOIN public.road_segments target ON target.provider = source.provider
  AND target.segment_key = source.segment_key;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM import_verification WHERE source_rows <> matched_rows) THEN
    RAISE EXCEPTION 'Import verification failed: missing or conflicting observations';
  END IF;
END $$;

SELECT json_build_object(
  'source_rows', v.source_rows,
  'matched_rows', v.matched_rows,
  'inserted_rows', (SELECT count(*) FROM public.traffic_observations) - c.target_before,
  'target_rows', (SELECT count(*) FROM public.traffic_observations),
  'source_points', (SELECT count(DISTINCT query_point_id) FROM imported_traffic_observations),
  'first_source_utc', (SELECT min(collected_at) FROM imported_traffic_observations),
  'last_source_utc', (SELECT max(collected_at) FROM imported_traffic_observations)
) FROM import_verification v CROSS JOIN import_counts c;
