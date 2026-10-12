-- =====================================================================================
-- sql/05_stations_precontrole.sql — Contrôles S1–S6 et examen des 40 trajets du 08/03/2026
-- AVANT nettoyage, STRICTEMENT EN LECTURE SEULE (une seule requête SELECT).
-- Exécuté par scripts/run_stations_precheck.py (session default_transaction_read_only=on).
--
-- La population « conservée » est reconstituée à la volée selon les règles v3.2 (R2 première
-- occurrence par file_month puis source_line ; R1 période ; R4 durée ≥ seuil). Les stations sont
-- normalisées à la volée par btrim(·, ' ') (R8). Rien n'est écrit : ni table, ni table temporaire.
-- Autocontrôle : le total reconstitué doit égaler config/attendus_v3.2.json → kept.
-- Sortie : 11 colonnes texte, la 1re indique le type de ligne (total, agg, s3, s6, dst).
-- =====================================================================================

-- name: stations_precheck
WITH ranked AS (
  SELECT t.source_csv, t.source_line, t.ride_id, t.rideable_type, t.member_casual,
         t.start_station_name, t.start_station_id, t.end_station_name, t.end_station_id,
         t.start_lat, t.start_lng,
         t.started_at::timestamp AS s, t.ended_at::timestamp AS e,
         row_number() OVER (PARTITION BY t.ride_id ORDER BY f.file_month, t.source_line) AS occ
  FROM raw.trips t JOIN raw.source_files f ON f.zip_name = t.source_zip
), kept AS MATERIALIZED (
  SELECT source_csv, source_line, ride_id, rideable_type, member_casual, s, e,
         EXTRACT(EPOCH FROM e - s) AS dur,
         date_trunc('month', s)::date AS ride_month,
         start_station_name AS sn_raw, start_station_id AS si_raw,
         end_station_name AS en_raw, end_station_id AS ei_raw,
         btrim(start_station_name, :'trim_chars') AS sn, btrim(start_station_id, :'trim_chars') AS si,
         btrim(end_station_name, :'trim_chars') AS en, btrim(end_station_id, :'trim_chars') AS ei,
         start_lat::double precision AS lat, start_lng::double precision AS lng
  FROM ranked
  WHERE occ = 1
    AND s >= :'period_start'::timestamp AND s < :'period_end'::timestamp
    AND EXTRACT(EPOCH FROM e - s) >= :min_duration_sec
), side AS (
  SELECT 'start' AS side, si AS id, sn AS name, ride_month FROM kept WHERE si IS NOT NULL
  UNION ALL
  SELECT 'end', ei, en, ride_month FROM kept WHERE ei IS NOT NULL
), cls AS (
  SELECT si AS id, lat, lng FROM kept WHERE rideable_type = 'classic_bike' AND si IS NOT NULL
), med AS (
  SELECT id, count(*) AS n,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY lat) AS lat_m,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY lng) AS lng_m,
         greatest(max(lat) - min(lat), max(lng) - min(lng)) AS span_deg
  FROM cls GROUP BY id
), dist AS (
  SELECT c.id, sqrt(power((c.lng - m.lng_m) * cos(radians(m.lat_m)) * 111320, 2)
                  + power((c.lat - m.lat_m) * 110574, 2)) AS d
  FROM cls c JOIN med m USING (id)
), dst AS (
  SELECT k.*,
         ((k.s >= :'sf_start'::timestamp AND k.s < :'sf_end'::timestamp)
           OR (k.e >= :'sf_start'::timestamp AND k.e < :'sf_end'::timestamp)) AS in_gap,
         EXTRACT(EPOCH FROM (k.e AT TIME ZONE :'tz') - (k.s AT TIME ZONE :'tz')) AS tz_sec
  FROM kept k
  WHERE k.s < :'sf_start'::timestamp AND k.e >= :'sf_end'::timestamp
)
SELECT 'total', count(*)::text, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL FROM kept
UNION ALL
SELECT 'agg', side, id, name, to_char(ride_month, 'YYYY-MM'), count(*)::text, NULL, NULL, NULL, NULL, NULL
FROM side GROUP BY side, id, name, ride_month
UNION ALL
SELECT 's6',
       count(*) FILTER (WHERE (sn IS NULL) <> (si IS NULL) OR (en IS NULL) <> (ei IS NULL))::text,
       count(*) FILTER (WHERE si = '' OR ei = '' OR sn = '' OR en = '')::text,
       count(*) FILTER (WHERE sn_raw ~ '^ | $' OR si_raw ~ '^ | $' OR en_raw ~ '^ | $' OR ei_raw ~ '^ | $')::text,
       count(*) FILTER (WHERE si IS NULL)::text,
       count(*) FILTER (WHERE ei IS NULL)::text,
       NULL, NULL, NULL, NULL, NULL
FROM kept
UNION ALL
SELECT 's3', m.id, m.n::text, round(m.span_deg::numeric, 5)::text,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY d.d)::numeric, 1)::text,
       round(max(d.d)::numeric, 1)::text, NULL, NULL, NULL, NULL, NULL
FROM med m JOIN dist d USING (id) GROUP BY m.id, m.n, m.span_deg
UNION ALL
SELECT 'dst', source_csv, source_line::text, to_char(s, 'YYYY-MM-DD HH24:MI:SS.MS'), to_char(e, 'YYYY-MM-DD HH24:MI:SS.MS'),
       dur::text, in_gap::text, tz_sec::text,
       (NOT in_gap AND tz_sec = dur - :sf_correction_sec AND dur - :sf_correction_sec >= 0)::text,
       member_casual, rideable_type
FROM dst;
