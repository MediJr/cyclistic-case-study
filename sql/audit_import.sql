-- Audit de l'import brut (mission 4.1) — LECTURE SEULE.
-- Exécuté par scripts/audit_import.py avec default_transaction_read_only=on.
-- Chaque bloc commence par « -- name: ».

-- name: objects
-- objets créés dans la base (hors schémas système) : attendu raw.source_files + raw.trips
SELECT table_schema, table_name, table_type FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY 1, 2;

-- name: schemas
SELECT nspname FROM pg_namespace
WHERE nspname NOT LIKE 'pg\_%' AND nspname <> 'information_schema' ORDER BY 1;

-- name: table_stats
-- compteurs cumulés depuis la création : insertions, mises à jour, suppressions
SELECT relname, n_tup_ins, n_tup_upd, n_tup_del, n_tup_hot_upd, n_live_tup, n_dead_tup
FROM pg_stat_user_tables WHERE schemaname = 'raw' ORDER BY relname;

-- name: source_files
SELECT zip_name, csv_name, file_month, zip_bytes, csv_bytes, csv_data_rows, loaded_at
FROM raw.source_files ORDER BY file_month;

-- name: id_arithmetic
-- total, distincts, identifiants répétés, occurrences excédentaires
SELECT (SELECT count(*) FROM raw.trips),
       (SELECT count(DISTINCT ride_id) FROM raw.trips),
       count(*), sum(n - 1), max(n)
FROM (SELECT ride_id, count(*) AS n FROM raw.trips GROUP BY ride_id HAVING count(*) > 1) d;

-- name: dup_rows
-- les lignes des identifiants répétés, avec empreinte du contenu des 13 colonnes
SELECT t.ride_id, t.source_csv, t.source_line, t.started_at, t.ended_at,
       md5(concat_ws(chr(31), t.ride_id, t.rideable_type, t.started_at, t.ended_at,
           coalesce(t.start_station_name, '\N'), coalesce(t.start_station_id, '\N'),
           coalesce(t.end_station_name, '\N'), coalesce(t.end_station_id, '\N'),
           t.start_lat, t.start_lng, coalesce(t.end_lat, '\N'), coalesce(t.end_lng, '\N'),
           t.member_casual)) AS content_md5
FROM raw.trips t
WHERE t.ride_id IN (SELECT ride_id FROM raw.trips GROUP BY ride_id HAVING count(*) > 1)
ORDER BY t.ride_id, t.source_csv;

-- name: dup_content_distinct
-- par identifiant répété : nombre de contenus distincts (attendu : 1 pour chacun)
SELECT count(*) FILTER (WHERE k = 1), count(*) FILTER (WHERE k > 1) FROM (
  SELECT ride_id, count(DISTINCT md5(concat_ws(chr(31), ride_id, rideable_type, started_at, ended_at,
           coalesce(start_station_name, '\N'), coalesce(start_station_id, '\N'),
           coalesce(end_station_name, '\N'), coalesce(end_station_id, '\N'),
           start_lat, start_lng, coalesce(end_lat, '\N'), coalesce(end_lng, '\N'),
           member_casual))) AS k
  FROM raw.trips GROUP BY ride_id HAVING count(*) > 1) x;

-- name: april_end_may_vs_dups
-- lignes de 202604 terminées hors avril, comparées à l'ensemble des identifiants répétés
WITH a AS (SELECT ride_id FROM raw.trips
           WHERE source_zip = '202604-divvy-tripdata.zip' AND left(ended_at, 7) <> '2026-04'),
     d AS (SELECT ride_id FROM raw.trips GROUP BY ride_id HAVING count(*) > 1)
SELECT (SELECT count(*) FROM a), (SELECT count(*) FROM d),
       (SELECT count(*) FROM a JOIN d USING (ride_id)),
       (SELECT count(*) FROM a WHERE ride_id NOT IN (SELECT ride_id FROM d)),
       (SELECT count(*) FROM d WHERE ride_id NOT IN (SELECT ride_id FROM a));

-- name: may_start_april_vs_dups
-- lignes de 202605 commencées hors mai, comparées à l'ensemble des identifiants répétés
WITH b AS (SELECT ride_id FROM raw.trips
           WHERE source_zip = '202605-divvy-tripdata.zip' AND left(started_at, 7) <> '2026-05'),
     d AS (SELECT ride_id FROM raw.trips GROUP BY ride_id HAVING count(*) > 1)
SELECT (SELECT count(*) FROM b), (SELECT count(*) FROM b JOIN d USING (ride_id)),
       (SELECT count(*) FROM b WHERE ride_id NOT IN (SELECT ride_id FROM d));

-- name: month_crossings
-- trajets dont le mois de départ diffère du mois d'arrivée, par fichier source
SELECT left(started_at, 7), left(ended_at, 7), source_csv, count(*),
       min(started_at), max(ended_at)
FROM raw.trips WHERE left(started_at, 7) <> left(ended_at, 7)
GROUP BY 1, 2, 3 ORDER BY 1, 3;

-- name: march_april_boundary
-- trajets commencés le 31/03/2026 : répartition par fichier et mois d'arrivée
SELECT source_csv, left(ended_at, 7), count(*), max(started_at), max(ended_at)
FROM raw.trips WHERE started_at >= '2026-03-31' AND started_at < '2026-04-01'
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: empty_representations
-- par colonne : NULL, '', espaces seuls, espaces en bordure, jetons de valeur manquante
SELECT c.col,
       count(*) FILTER (WHERE c.val IS NULL),
       count(*) FILTER (WHERE c.val = ''),
       count(*) FILTER (WHERE c.val <> '' AND c.val ~ '^\s+$'),
       count(*) FILTER (WHERE c.val ~ '^\s|\s$'),
       count(*) FILTER (WHERE upper(btrim(c.val)) IN ('NULL', 'NA', 'N/A', 'NAN', 'NONE', '\N', '-', '?', 'UNKNOWN'))
FROM raw.trips t
CROSS JOIN LATERAL (VALUES
  ('ride_id', t.ride_id), ('rideable_type', t.rideable_type), ('started_at', t.started_at),
  ('ended_at', t.ended_at), ('start_station_name', t.start_station_name),
  ('start_station_id', t.start_station_id), ('end_station_name', t.end_station_name),
  ('end_station_id', t.end_station_id), ('start_lat', t.start_lat), ('start_lng', t.start_lng),
  ('end_lat', t.end_lat), ('end_lng', t.end_lng), ('member_casual', t.member_casual)) AS c(col, val)
GROUP BY c.col ORDER BY c.col;

-- name: null_pairs
-- cohérence des NULL : nom et ID de station, latitude et longitude d'arrivée
SELECT count(*) FILTER (WHERE (start_station_name IS NULL) <> (start_station_id IS NULL)),
       count(*) FILTER (WHERE (end_station_name IS NULL) <> (end_station_id IS NULL)),
       count(*) FILTER (WHERE (end_lat IS NULL) <> (end_lng IS NULL))
FROM raw.trips;

-- name: timestamp_text_roundtrip
-- l'aller-retour texte -> timestamp -> texte restitue-t-il le texte source ? (lecture seule)
SELECT count(*) FILTER (WHERE started_at::timestamp::text <> started_at),
       count(*) FILTER (WHERE ended_at::timestamp::text <> ended_at),
       count(*) FILTER (WHERE started_at !~ '\.\d{3}$'),
       min(started_at) FILTER (WHERE started_at::timestamp::text <> started_at)
FROM raw.trips;

-- name: fingerprint
-- empreinte exhaustive par fichier : somme d'un hachage 60 bits de (source_line + 13 valeurs)
SELECT source_csv, count(*),
       sum(('x' || left(md5(source_line::text || chr(31) || concat_ws(chr(31),
           coalesce(ride_id, '\N'), coalesce(rideable_type, '\N'), coalesce(started_at, '\N'),
           coalesce(ended_at, '\N'), coalesce(start_station_name, '\N'),
           coalesce(start_station_id, '\N'), coalesce(end_station_name, '\N'),
           coalesce(end_station_id, '\N'), coalesce(start_lat, '\N'), coalesce(start_lng, '\N'),
           coalesce(end_lat, '\N'), coalesce(end_lng, '\N'), coalesce(member_casual, '\N'))), 15))::bit(60)::bigint)
FROM raw.trips GROUP BY source_csv ORDER BY source_csv;
