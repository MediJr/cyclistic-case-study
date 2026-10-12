-- =====================================================================================
-- sql/03_qa_clean.sql — Contrôles qualité après nettoyage (C4), LECTURE SEULE.
-- Exécuté par scripts/run_qa_clean.py (session default_transaction_read_only=on).
-- Chaque bloc commence par « -- name: ». Variables psql : :'period_start' :'period_end'
-- :'trim_pattern' :'staff_pattern'
-- =====================================================================================

-- ---- Pré-contrôles (utilisables AVANT le nettoyage : ne lisent que raw et le catalogue) ----

-- name: preflight_schemas
SELECT to_regnamespace('clean') IS NOT NULL, to_regnamespace('audit') IS NOT NULL;

-- name: preflight_raw_rows
SELECT count(*) FROM raw.trips;

-- name: preflight_conflicts
-- R2.1 : ride_id présents avec des contenus différents (100 premiers)
SELECT ride_id, count(*) FROM raw.trips t
GROUP BY ride_id
HAVING count(DISTINCT md5(concat_ws(chr(31),
         coalesce(t.ride_id, '\N'), coalesce(t.rideable_type, '\N'), coalesce(t.started_at, '\N'),
         coalesce(t.ended_at, '\N'), coalesce(t.start_station_name, '\N'), coalesce(t.start_station_id, '\N'),
         coalesce(t.end_station_name, '\N'), coalesce(t.end_station_id, '\N'), coalesce(t.start_lat, '\N'),
         coalesce(t.start_lng, '\N'), coalesce(t.end_lat, '\N'), coalesce(t.end_lng, '\N'),
         coalesce(t.member_casual, '\N')))) > 1
ORDER BY ride_id LIMIT 100;

-- ---- Contrôles après nettoyage ----

-- name: counts
SELECT (SELECT count(*) FROM raw.trips), (SELECT count(*) FROM clean.trips), (SELECT count(*) FROM audit.excluded_rows);

-- name: reasons
SELECT reason, count(*), count(*) FILTER (WHERE n_criteria <> 1) FROM audit.excluded_rows GROUP BY reason ORDER BY reason;

-- name: orphans_and_overlaps
-- Q3 : lignes brutes dans aucun état / dans les deux états
SELECT (SELECT count(*) FROM raw.trips r
        WHERE NOT EXISTS (SELECT 1 FROM clean.trips c WHERE c.source_csv = r.source_csv AND c.source_line = r.source_line)
          AND NOT EXISTS (SELECT 1 FROM audit.excluded_rows e WHERE e.source_csv = r.source_csv AND e.source_line = r.source_line)),
       (SELECT count(*) FROM clean.trips c JOIN audit.excluded_rows e USING (source_csv, source_line));

-- name: period
SELECT min(started_at)::text, max(started_at)::text,
       count(*) FILTER (WHERE started_at < :'period_start'::timestamp OR started_at >= :'period_end'::timestamp)
FROM clean.trips;

-- name: months
SELECT to_char(ride_month, 'YYYY-MM'), count(*) FROM clean.trips GROUP BY ride_month ORDER BY ride_month;

-- name: members
SELECT member_casual, count(*) FROM clean.trips GROUP BY member_casual ORDER BY 1;

-- name: month_consistency
SELECT count(*) FILTER (WHERE ride_month <> date_trunc('month', started_at)::date) FROM clean.trips;

-- name: file_202501
-- Q7 : le CSV mal nommé ; aucun trajet de janvier 2025 ; mois réellement attribués
SELECT (SELECT count(*) FROM clean.trips WHERE ride_month = date '2025-01-01'),
       (SELECT string_agg(DISTINCT to_char(c.ride_month, 'YYYY-MM'), ',' ORDER BY to_char(c.ride_month, 'YYYY-MM'))
          FROM clean.trips c WHERE c.source_csv = '202501-divvy-tripdata.csv'),
       (SELECT file_month FROM raw.source_files WHERE csv_name = '202501-divvy-tripdata.csv');

-- name: uniqueness
SELECT count(*), count(DISTINCT ride_id) FROM clean.trips;

-- name: q10_timestamps
-- Q10 : comparaison de VALEURS temporelles (jamais de ::text) + contrôle de format sur 3 décimales
SELECT count(*) FILTER (WHERE c.started_at <> r.started_at::timestamp OR c.ended_at <> r.ended_at::timestamp),
       count(*) FILTER (WHERE to_char(c.started_at, 'YYYY-MM-DD HH24:MI:SS.MS') <> r.started_at
                           OR to_char(c.ended_at,   'YYYY-MM-DD HH24:MI:SS.MS') <> r.ended_at)
FROM clean.trips c JOIN raw.trips r USING (source_csv, source_line);

-- name: q11_derived
SELECT count(*) FILTER (WHERE ride_length_sec <> EXTRACT(EPOCH FROM ended_at - started_at)
                           OR ride_length <> ended_at - started_at),
       count(*) FILTER (WHERE day_of_week <> EXTRACT(DOW FROM started_at) + 1
                           OR start_hour <> EXTRACT(HOUR FROM started_at)),
       (EXTRACT(DOW FROM timestamp '2025-10-05 12:00') + 1)::int
FROM clean.trips;

-- name: q12_dst
SELECT count(*) FILTER (WHERE dst_fall_back_overlap),
       count(*) FILTER (WHERE dst_spring_forward_span),
       count(*) FILTER (WHERE dst_adj_status = 'corrected'),
       count(*) FILTER (WHERE dst_adj_status = 'span_not_confirmed'),
       count(*) FILTER (WHERE dst_adj_status = 'corrected' AND NOT dst_spring_forward_span),
       count(*) FILTER (WHERE dst_adj_status = 'corrected' AND started_at::date = date '2025-11-02'),
       count(*) FILTER (WHERE (dst_adj_status = 'corrected') <> (ride_length_sec <> ride_length_sec_dst_adj))
FROM clean.trips;

-- name: q13_durations
SELECT (SELECT min(ride_length_sec)::text FROM clean.trips),
       (SELECT count(*) FROM audit.excluded_rows WHERE reason = 'under_60s' AND ride_length_sec < 0),
       (SELECT count(*) FROM audit.excluded_rows WHERE reason = 'negative_duration' AND ride_length_sec >= 0),
       (SELECT count(*) FROM audit.excluded_rows WHERE reason = 'under_60s' AND ride_length_sec = 0);

-- name: flags
SELECT count(*) FILTER (WHERE NOT has_end_location),
       count(*) FILTER (WHERE is_over_24h),
       count(*) FILTER (WHERE start_station_missing),
       count(*) FILTER (WHERE end_station_missing),
       max(ride_length_sec)::text
FROM clean.trips;

-- name: subsets
SELECT 'v_trips_geo', count(*) FROM clean.v_trips_geo
UNION ALL SELECT 'v_trips_start_station', count(*) FROM clean.v_trips_start_station
UNION ALL SELECT 'v_trips_end_station', count(*) FROM clean.v_trips_end_station
UNION ALL SELECT 'v_trips_station_pair', count(*) FROM clean.v_trips_station_pair
UNION ALL SELECT 'v_sens1_population', count(*) FROM clean.v_sens1_population;

-- name: q17_stations
-- 0 chaîne vide ; paires nom/ID cohérentes ; clean = btrim(raw, ' ') (seule transformation autorisée)
SELECT count(*) FILTER (WHERE c.start_station_name = '' OR c.start_station_id = '' OR c.end_station_name = '' OR c.end_station_id = ''),
       count(*) FILTER (WHERE (c.start_station_name IS NULL) <> (c.start_station_id IS NULL)
                           OR (c.end_station_name IS NULL) <> (c.end_station_id IS NULL)),
       count(*) FILTER (WHERE c.start_station_name IS DISTINCT FROM btrim(r.start_station_name, ' ')
                           OR c.start_station_id   IS DISTINCT FROM btrim(r.start_station_id, ' ')
                           OR c.end_station_name   IS DISTINCT FROM btrim(r.end_station_name, ' ')
                           OR c.end_station_id     IS DISTINCT FROM btrim(r.end_station_id, ' '))
FROM clean.trips c JOIN raw.trips r USING (source_csv, source_line);

-- name: q20_trim
-- par colonne : valeurs brutes avec espace en bordure (lignes conservées), indicateurs, restes après, espaces doubles internes
SELECT x.col,
       count(*) FILTER (WHERE x.raw_v ~ '^ | $'),
       count(*) FILTER (WHERE x.flag),
       count(*) FILTER (WHERE x.clean_v ~ '^\s|\s$'),
       count(*) FILTER (WHERE position('  ' in x.clean_v) > 0),
       count(*) FILTER (WHERE position('  ' in btrim(x.raw_v, ' ')) > 0)
FROM clean.trips c JOIN raw.trips r USING (source_csv, source_line)
CROSS JOIN LATERAL (VALUES
  ('start_station_name', r.start_station_name, c.start_station_name, c.start_station_name_trimmed),
  ('start_station_id',   r.start_station_id,   c.start_station_id,   c.start_station_id_trimmed),
  ('end_station_name',   r.end_station_name,   c.end_station_name,   c.end_station_name_trimmed),
  ('end_station_id',     r.end_station_id,     c.end_station_id,     c.end_station_id_trimmed)
) AS x(col, raw_v, clean_v, flag)
GROUP BY x.col ORDER BY x.col;

-- name: q20_log
SELECT column_name, count(*), sum(n_rows), string_agg(normalized_value, ' | ' ORDER BY normalized_value) FILTER (WHERE merges_with_existing_value)
FROM audit.normalization_log GROUP BY column_name ORDER BY column_name;

-- name: q19_transform_log
SELECT step_no, coalesce(rows_before, -1), coalesce(rows_excluded, -1), rows_after FROM audit.transform_log ORDER BY step_no;

-- name: q21_march_april
SELECT count(*) FROM clean.trips WHERE ride_month = date '2026-03-01' AND ended_at >= timestamp '2026-04-01';

-- name: q22_dedup
SELECT count(*),
       string_agg(DISTINCT source_csv, ','),
       string_agg(DISTINCT kept_source_csv, ','),
       count(*) FILTER (WHERE content_md5 <> kept_content_md5),
       count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM clean.trips c
                                          WHERE c.source_csv = e.kept_source_csv AND c.source_line = e.kept_source_line))
FROM audit.excluded_rows e WHERE reason = 'duplicate_ride_id';

-- name: s1_summary
-- ID à plusieurs noms (après normalisation) ; « trivial » = même nom une fois casse et ponctuation retirées
WITH s AS (
  SELECT 'start' AS side, start_station_id AS id, start_station_name AS name FROM clean.trips WHERE NOT start_station_missing
  UNION ALL
  SELECT 'end', end_station_id, end_station_name FROM clean.trips WHERE NOT end_station_missing
), g AS (
  SELECT side, id, count(DISTINCT name) AS n_names,
         count(DISTINCT regexp_replace(lower(name), '[^a-z0-9]', '', 'g')) AS n_norm
  FROM s GROUP BY side, id
)
SELECT side, count(*), count(*) FILTER (WHERE n_names > 1), count(*) FILTER (WHERE n_names > 1 AND n_norm = 1)
FROM g GROUP BY side ORDER BY side;

-- name: s1_list
WITH s AS (
  SELECT 'start' AS side, start_station_id AS id, start_station_name AS name FROM clean.trips WHERE NOT start_station_missing
  UNION ALL
  SELECT 'end', end_station_id, end_station_name FROM clean.trips WHERE NOT end_station_missing
), n AS (SELECT side, id, name, count(*) AS rows FROM s GROUP BY 1, 2, 3),
   m AS (SELECT side, id FROM n GROUP BY side, id HAVING count(*) > 1)
SELECT n.side, n.id, n.name, n.rows FROM n JOIN m USING (side, id) ORDER BY n.side, n.id, n.rows DESC;

-- name: s2_summary
WITH s AS (
  SELECT 'start' AS side, start_station_id AS id, start_station_name AS name FROM clean.trips WHERE NOT start_station_missing
  UNION ALL
  SELECT 'end', end_station_id, end_station_name FROM clean.trips WHERE NOT end_station_missing
)
SELECT side, count(*) FILTER (WHERE k > 1) FROM (SELECT side, name, count(DISTINCT id) AS k FROM s GROUP BY 1, 2) x GROUP BY side ORDER BY side;

-- name: s2_list
WITH s AS (
  SELECT 'start' AS side, start_station_id AS id, start_station_name AS name FROM clean.trips WHERE NOT start_station_missing
  UNION ALL
  SELECT 'end', end_station_id, end_station_name FROM clean.trips WHERE NOT end_station_missing
), n AS (SELECT side, name, id, count(*) AS rows FROM s GROUP BY 1, 2, 3),
   m AS (SELECT side, name FROM n GROUP BY side, name HAVING count(*) > 1)
SELECT n.side, n.name, n.id, n.rows FROM n JOIN m USING (side, name) ORDER BY n.side, n.name, n.rows DESC;

-- name: s3_spatial
-- Dispersion des coordonnées de départ des VÉLOS CLASSIQUES par ID (indicatif, pas une règle) :
-- point médian, distance au médian en mètres (approximation équirectangulaire), p95 et max ;
-- étendue en degrés pour comparaison avec le repère 0,005°.
WITH p AS (
  SELECT start_station_id AS id, start_lat AS lat, start_lng AS lng
  FROM clean.trips WHERE rideable_type = 'classic_bike' AND NOT start_station_missing
), med AS (
  SELECT id, count(*) AS n,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY lat) AS lat_m,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY lng) AS lng_m,
         greatest(max(lat) - min(lat), max(lng) - min(lng)) AS span_deg
  FROM p GROUP BY id
), d AS (
  SELECT p.id, sqrt(power((p.lng - m.lng_m) * cos(radians(m.lat_m)) * 111320, 2)
                  + power((p.lat - m.lat_m) * 110574, 2)) AS dist_m
  FROM p JOIN med m USING (id)
)
SELECT m.id, m.n, round(m.span_deg::numeric, 5)::text,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY d.dist_m)::numeric, 1)::text,
       round(max(d.dist_m)::numeric, 1)::text
FROM med m JOIN d USING (id)
GROUP BY m.id, m.n, m.span_deg
ORDER BY percentile_cont(0.95) WITHIN GROUP (ORDER BY d.dist_m) DESC;

-- name: s4_names_by_month
-- nom par ID et par mois, pour les ID à plusieurs noms (renommage daté ou coexistence)
WITH s AS (
  SELECT 'start' AS side, start_station_id AS id, start_station_name AS name, ride_month FROM clean.trips WHERE NOT start_station_missing
  UNION ALL
  SELECT 'end', end_station_id, end_station_name, ride_month FROM clean.trips WHERE NOT end_station_missing
), m AS (SELECT side, id FROM s GROUP BY side, id HAVING count(DISTINCT name) > 1)
SELECT s.side, s.id, to_char(s.ride_month, 'YYYY-MM'), s.name, count(*)
FROM s JOIN m USING (side, id) GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 5 DESC;

-- name: s5_staff_test
-- suivi agrégé et non nominatif des stations dont le nom évoque un usage interne (aucune exclusion)
WITH s AS (
  SELECT start_station_id AS id, start_station_name AS name FROM clean.trips WHERE start_station_name ~* :'staff_pattern'
  UNION ALL
  SELECT end_station_id, end_station_name FROM clean.trips WHERE end_station_name ~* :'staff_pattern'
)
SELECT id, name, count(*) FROM s GROUP BY 1, 2 ORDER BY 3 DESC;

-- name: s5_rows
SELECT count(*) FROM clean.trips WHERE start_station_name ~* :'staff_pattern' OR end_station_name ~* :'staff_pattern';

-- name: s6_presence
SELECT count(*) FILTER (WHERE (start_station_name IS NULL) <> (start_station_id IS NULL)
                           OR (end_station_name IS NULL) <> (end_station_id IS NULL)),
       count(*) FILTER (WHERE btrim(start_station_id) = '' OR btrim(end_station_id) = '')
FROM clean.trips;

-- name: source_files
SELECT csv_name, zip_name, csv_sha256, zip_sha256 FROM raw.source_files ORDER BY file_month;

-- name: raw_fingerprint
-- Q1 : empreinte exhaustive de raw.trips (même formule que sql/audit_import.sql)
SELECT source_csv, count(*),
       sum(('x' || left(md5(source_line::text || chr(31) || concat_ws(chr(31),
           coalesce(ride_id, '\N'), coalesce(rideable_type, '\N'), coalesce(started_at, '\N'),
           coalesce(ended_at, '\N'), coalesce(start_station_name, '\N'),
           coalesce(start_station_id, '\N'), coalesce(end_station_name, '\N'),
           coalesce(end_station_id, '\N'), coalesce(start_lat, '\N'), coalesce(start_lng, '\N'),
           coalesce(end_lat, '\N'), coalesce(end_lng, '\N'), coalesce(member_casual, '\N'))), 15))::bit(60)::bigint)
FROM raw.trips GROUP BY source_csv ORDER BY source_csv;

-- name: run
SELECT run_id::text, rules_version, rules_sha256, plan_sha256, raw_rows, kept_rows, excluded_rows FROM audit.run;
