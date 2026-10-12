-- Contrôles qualité de l'import brut (lecture seule). Chaque bloc commence par « -- name: ».
-- Exécutés par scripts/qa_import.py, qui compare les résultats aux mesures des missions 1 à 3.

-- name: rows_per_file
SELECT f.csv_name, f.file_month, f.csv_data_rows, count(t.source_line),
       min(t.source_line), max(t.source_line)
FROM raw.source_files f LEFT JOIN raw.trips t ON t.source_zip = f.zip_name
GROUP BY f.csv_name, f.file_month, f.csv_data_rows ORDER BY f.file_month;

-- name: total_rows
SELECT count(*) FROM raw.trips;

-- name: source_csv_consistency
-- source_csv de raw.trips doit correspondre au CSV enregistré pour son ZIP
SELECT count(*) FROM raw.trips t JOIN raw.source_files f ON f.zip_name = t.source_zip
WHERE t.source_csv <> f.csv_name;

-- name: schema
SELECT column_name, data_type, ordinal_position FROM information_schema.columns
WHERE table_schema = 'raw' AND table_name = 'trips' ORDER BY ordinal_position;

-- name: missing_all_columns
-- NULL = champ vide non quoté dans le CSV ; '' = champ vide quoté (attendu : 0)
SELECT c.col, count(*) FILTER (WHERE c.val IS NULL), count(*) FILTER (WHERE c.val = '')
FROM raw.trips t
CROSS JOIN LATERAL (VALUES
  ('ride_id', t.ride_id), ('rideable_type', t.rideable_type), ('started_at', t.started_at),
  ('ended_at', t.ended_at), ('start_station_name', t.start_station_name),
  ('start_station_id', t.start_station_id), ('end_station_name', t.end_station_name),
  ('end_station_id', t.end_station_id), ('start_lat', t.start_lat), ('start_lng', t.start_lng),
  ('end_lat', t.end_lat), ('end_lng', t.end_lng), ('member_casual', t.member_casual)) AS c(col, val)
GROUP BY c.col ORDER BY c.col;

-- name: category_values
SELECT 'rideable_type', rideable_type, count(*) FROM raw.trips GROUP BY rideable_type
UNION ALL
SELECT 'member_casual', member_casual, count(*) FROM raw.trips GROUP BY member_casual
ORDER BY 1, 2;

-- name: timestamp_format
-- format texte attendu : AAAA-MM-JJ HH:MM:SS[.fff] (inspection seulement, aucune conversion stockée)
SELECT count(*) FILTER (WHERE started_at !~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d{1,6})?$'),
       count(*) FILTER (WHERE ended_at   !~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d{1,6})?$')
FROM raw.trips;

-- name: distinct_ride_id
SELECT count(*), count(DISTINCT ride_id) FROM raw.trips;

-- name: dup_within_file
SELECT count(*) FROM (
  SELECT source_csv, ride_id FROM raw.trips GROUP BY source_csv, ride_id HAVING count(*) > 1) d;

-- name: dup_cross_file
-- combinaison de fichiers, nombre d'identifiants partagés, nombre de lignes concernées
SELECT files, count(*), sum(n) FROM (
  SELECT ride_id, string_agg(source_csv, ' + ' ORDER BY source_csv) AS files, count(*) AS n
  FROM raw.trips GROUP BY ride_id HAVING count(DISTINCT source_csv) > 1) x
GROUP BY files;

-- name: ride_id_conflicts
-- même ride_id avec un contenu différent sur l'une des 13 colonnes sources (attendu : 0)
SELECT count(*) FROM (
  SELECT ride_id FROM raw.trips GROUP BY ride_id
  HAVING count(DISTINCT ROW(rideable_type, started_at, ended_at, start_station_name,
         start_station_id, end_station_name, end_station_id, start_lat, start_lng,
         end_lat, end_lng, member_casual)) > 1) c;

-- name: month_consistency
-- mois de départ (texte) comparé au mois du fichier déduit du nom du ZIP
SELECT f.csv_name, f.file_month, min(t.started_at), max(t.started_at),
       count(*) FILTER (WHERE left(t.started_at, 7) = f.file_month),
       count(*) FILTER (WHERE left(t.started_at, 7) <> f.file_month),
       count(*) FILTER (WHERE left(t.ended_at, 7) <> f.file_month)
FROM raw.trips t JOIN raw.source_files f ON f.zip_name = t.source_zip
GROUP BY f.csv_name, f.file_month ORDER BY f.file_month;
