-- =====================================================================================
-- sql/02_clean.sql — Nettoyage Cyclistic selon docs/plan_nettoyage_v3.2.md (C3)
--
-- NE PAS EXÉCUTER DIRECTEMENT. Lancé uniquement par `scripts/run_clean.py --execute`,
-- en UNE SEULE transaction (psql -1, ON_ERROR_STOP), avec les variables psql définies à
-- partir de config/regles_nettoyage_v3.2.json et config/attendus_v3.2.json.
--
-- Garanties :
--   * raw.trips et raw.source_files sont uniquement LUS (aucune écriture, aucun ALTER) ;
--   * seconde exécution refusée si un schéma `clean` ou `audit` existe déjà ;
--   * toute assertion en échec lève une exception : la transaction entière est annulée,
--     rien n'est créé ;
--   * chaque ligne de raw.trips aboutit à exactement un état : clean.trips OU audit.excluded_rows,
--     avec un motif principal unique ; les deux tables portent une clé étrangère vers raw.trips.
-- =====================================================================================

-- 0. Outils et garde-fous ---------------------------------------------------------------
CREATE FUNCTION pg_temp.assert(ok boolean, msg text) RETURNS void LANGUAGE plpgsql AS $f$
BEGIN
  IF ok IS NOT TRUE THEN
    RAISE EXCEPTION 'CONTRÔLE BLOQUANT : %', msg;
  END IF;
END
$f$;

-- Empreinte du contenu source (13 colonnes) ; NULL écrit \N. Même convention que l'audit 4.1.
CREATE FUNCTION pg_temp.content_md5(r raw.trips) RETURNS text LANGUAGE sql IMMUTABLE AS $f$
  SELECT md5(concat_ws(chr(31),
    coalesce(r.ride_id, '\N'), coalesce(r.rideable_type, '\N'), coalesce(r.started_at, '\N'),
    coalesce(r.ended_at, '\N'), coalesce(r.start_station_name, '\N'), coalesce(r.start_station_id, '\N'),
    coalesce(r.end_station_name, '\N'), coalesce(r.end_station_id, '\N'), coalesce(r.start_lat, '\N'),
    coalesce(r.start_lng, '\N'), coalesce(r.end_lat, '\N'), coalesce(r.end_lng, '\N'),
    coalesce(r.member_casual, '\N')))
$f$;

SELECT pg_temp.assert(to_regnamespace('clean') IS NULL AND to_regnamespace('audit') IS NULL,
  'un schéma clean ou audit existe déjà : seconde exécution refusée (appliquer d''abord la procédure de retour arrière)');

SELECT pg_temp.assert(n = :expected_raw_rows, format('raw.trips : %s lignes, %s attendues', n, :expected_raw_rows))
FROM (SELECT count(*) AS n FROM raw.trips) x;

SELECT pg_temp.assert(n = :expected_source_files, format('raw.source_files : %s fichiers, %s attendus', n, :expected_source_files))
FROM (SELECT count(*) AS n FROM raw.source_files) x;

-- R2.1 — contrôle bloquant des conflits (le pré-contrôle Python les a déjà listés s'il y en a)
SELECT pg_temp.assert(NOT EXISTS (
         SELECT 1 FROM raw.trips t GROUP BY t.ride_id HAVING count(DISTINCT pg_temp.content_md5(t)) > 1),
       'ride_id présent avec des contenus différents (R2.1) : arrêt sans arbitrage');

-- 1. Classification de chaque ligne brute (table temporaire, détruite à la validation) ---
CREATE TEMP TABLE stage ON COMMIT DROP AS
WITH base AS (
  SELECT t.source_csv, t.source_line, t.ride_id, f.file_month,
         pg_temp.content_md5(t)  AS content_md5,
         t.started_at::timestamp AS s_ts,
         t.ended_at::timestamp   AS e_ts,
         t.member_casual, t.rideable_type
  FROM raw.trips t
  JOIN raw.source_files f ON f.zip_name = t.source_zip
), ranked AS (
  SELECT b.*,
         row_number()             OVER w AS occurrence,
         first_value(source_csv)  OVER w AS first_source_csv,
         first_value(source_line) OVER w AS first_source_line,
         first_value(content_md5) OVER w AS first_content_md5,
         EXTRACT(EPOCH FROM e_ts - s_ts) AS dur_sec
  FROM base b
  WINDOW w AS (PARTITION BY ride_id ORDER BY file_month, source_line)
), flagged AS (
  SELECT r.*,
         (occurrence > 1)                                                             AS c_duplicate,
         NOT (s_ts >= :'period_start'::timestamp AND s_ts < :'period_end'::timestamp) AS c_out_of_period,
         (dur_sec < 0)                                                                AS c_negative,
         (dur_sec >= 0 AND dur_sec < :min_duration_sec)                               AS c_under_min
  FROM ranked r
)
SELECT f.*,
       CASE WHEN c_duplicate     THEN 'duplicate_ride_id'      -- ordre fixe : R2 → R1 → R4a → R4b
            WHEN c_out_of_period THEN 'out_of_period'
            WHEN c_negative      THEN 'negative_duration'
            WHEN c_under_min     THEN 'under_60s' END                                 AS reason,
       (c_duplicate::int + c_out_of_period::int + c_negative::int + c_under_min::int) AS n_criteria
FROM flagged f;

-- Comptes par motif : contrôles bloquants contre config/attendus_v3.2.json
SELECT pg_temp.assert(n = :exp_duplicate, format('R2 duplicate_ride_id : %s, %s attendus', n, :exp_duplicate))
FROM (SELECT count(*) AS n FROM stage WHERE reason = 'duplicate_ride_id') x;
SELECT pg_temp.assert(n = :exp_out_of_period, format('R1 out_of_period : %s, %s attendus', n, :exp_out_of_period))
FROM (SELECT count(*) AS n FROM stage WHERE reason = 'out_of_period') x;
SELECT pg_temp.assert(n = :exp_negative, format('R4a negative_duration : %s, %s attendus', n, :exp_negative))
FROM (SELECT count(*) AS n FROM stage WHERE reason = 'negative_duration') x;
SELECT pg_temp.assert(n = :exp_under_60s, format('R4b under_60s : %s, %s attendus', n, :exp_under_60s))
FROM (SELECT count(*) AS n FROM stage WHERE reason = 'under_60s') x;
SELECT pg_temp.assert(n = :exp_kept, format('lignes conservées : %s, %s attendues', n, :exp_kept))
FROM (SELECT count(*) AS n FROM stage WHERE reason IS NULL) x;
SELECT pg_temp.assert(NOT EXISTS (SELECT 1 FROM stage WHERE c_duplicate AND content_md5 <> first_content_md5),
       'R2 : une copie exclue diffère de la copie gardée');

-- 2. Schémas et journaux d'audit -----------------------------------------------------
CREATE SCHEMA audit;
CREATE SCHEMA clean;

CREATE TABLE audit.transform_log (
  step_no       integer PRIMARY KEY,
  step          text    NOT NULL,
  rule          text,
  rows_before   bigint,
  rows_excluded bigint,
  rows_after    bigint  NOT NULL,
  logged_at     timestamptz NOT NULL DEFAULT clock_timestamp()
);

WITH c AS (
  SELECT count(*) AS n0,
         count(*) FILTER (WHERE reason = 'duplicate_ride_id') AS d,
         count(*) FILTER (WHERE reason = 'out_of_period')     AS p,
         count(*) FILTER (WHERE reason = 'negative_duration') AS ng,
         count(*) FILTER (WHERE reason = 'under_60s')         AS u
  FROM stage)
INSERT INTO audit.transform_log (step_no, step, rule, rows_before, rows_excluded, rows_after)
SELECT v.* FROM c CROSS JOIN LATERAL (VALUES
  (0, 'source : raw.trips',  NULL::text, NULL::bigint,      NULL::bigint, c.n0),
  (1, 'duplicate_ride_id',   'R2',       c.n0,              c.d,          c.n0 - c.d),
  (2, 'out_of_period',       'R1',       c.n0 - c.d,        c.p,          c.n0 - c.d - c.p),
  (3, 'negative_duration',   'R4a',      c.n0 - c.d - c.p,  c.ng,         c.n0 - c.d - c.p - c.ng),
  (4, 'under_60s',           'R4b',      c.n0 - c.d - c.p - c.ng, c.u,    c.n0 - c.d - c.p - c.ng - c.u)
) AS v(step_no, step, rule, rows_before, rows_excluded, rows_after);

CREATE TABLE audit.excluded_rows (
  source_csv       text     NOT NULL,
  source_line      integer  NOT NULL,
  ride_id          text     NOT NULL,
  reason           text     NOT NULL CHECK (reason IN ('duplicate_ride_id', 'out_of_period', 'negative_duration', 'under_60s')),
  rule             text     NOT NULL,
  n_criteria       smallint NOT NULL,          -- nombre de critères remplis (1 attendu : motifs disjoints)
  member_casual    text,
  rideable_type    text,
  started_at       timestamp,
  ended_at         timestamp,
  ride_length_sec  numeric,
  content_md5      text     NOT NULL,
  kept_source_csv  text,                       -- doublons : ligne gardée
  kept_source_line integer,
  kept_content_md5 text,
  PRIMARY KEY (source_csv, source_line),
  FOREIGN KEY (source_csv, source_line) REFERENCES raw.trips (source_csv, source_line),
  CHECK ((reason = 'duplicate_ride_id') = (kept_source_csv IS NOT NULL))
);

INSERT INTO audit.excluded_rows
SELECT source_csv, source_line, ride_id, reason,
       CASE reason WHEN 'duplicate_ride_id' THEN 'R2' WHEN 'out_of_period' THEN 'R1'
                   WHEN 'negative_duration' THEN 'R4a' ELSE 'R4b' END,
       n_criteria, member_casual, rideable_type, s_ts, e_ts, dur_sec, content_md5,
       CASE WHEN c_duplicate THEN first_source_csv END,
       CASE WHEN c_duplicate THEN first_source_line END,
       CASE WHEN c_duplicate THEN first_content_md5 END
FROM stage WHERE reason IS NOT NULL;

-- 3. Table nettoyée (valeurs brutes laissées dans raw.trips ; lien par clé étrangère) -----
CREATE TABLE clean.trips (
  source_csv                 text     NOT NULL,
  source_line                integer  NOT NULL,
  ride_id                    text     NOT NULL UNIQUE,
  rideable_type              text     NOT NULL CHECK (rideable_type IN ('classic_bike', 'electric_bike')),
  member_casual              text     NOT NULL CHECK (member_casual IN ('member', 'casual')),
  started_at                 timestamp NOT NULL,
  ended_at                   timestamp NOT NULL,
  ride_length                interval NOT NULL,
  ride_length_sec            numeric  NOT NULL CHECK (ride_length_sec >= :min_duration_sec),
  ride_length_sec_dst_adj    numeric  NOT NULL,
  dst_adj_status             text     NOT NULL CHECK (dst_adj_status IN ('not_applicable', 'corrected', 'span_not_confirmed')),
  dst_fall_back_overlap      boolean  NOT NULL,
  dst_spring_forward_span    boolean  NOT NULL,
  day_of_week                smallint NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
  start_hour                 smallint NOT NULL CHECK (start_hour BETWEEN 0 AND 23),
  ride_month                 date     NOT NULL,
  start_station_name         text,
  start_station_id           text,
  end_station_name           text,
  end_station_id             text,
  start_station_name_trimmed boolean  NOT NULL,
  start_station_id_trimmed   boolean  NOT NULL,
  end_station_name_trimmed   boolean  NOT NULL,
  end_station_id_trimmed     boolean  NOT NULL,
  start_station_missing      boolean  NOT NULL,
  end_station_missing        boolean  NOT NULL,
  start_lat                  double precision NOT NULL,
  start_lng                  double precision NOT NULL,
  end_lat                    double precision,
  end_lng                    double precision,
  has_end_location           boolean  NOT NULL,
  is_over_24h                boolean  NOT NULL,
  PRIMARY KEY (source_csv, source_line),
  FOREIGN KEY (source_csv, source_line) REFERENCES raw.trips (source_csv, source_line),
  CHECK (start_station_name <> '' AND start_station_id <> '' AND end_station_name <> '' AND end_station_id <> ''),
  CHECK ((start_station_name IS NULL) = (start_station_id IS NULL)),
  CHECK ((end_station_name IS NULL) = (end_station_id IS NULL)),
  CHECK ((end_lat IS NULL) = (end_lng IS NULL)),
  CHECK (start_lat BETWEEN :lat_min AND :lat_max AND start_lng BETWEEN :lng_min AND :lng_max),
  CHECK (end_lat IS NULL OR (end_lat BETWEEN :lat_min AND :lat_max AND end_lng BETWEEN :lng_min AND :lng_max)),
  CHECK (dst_adj_status <> 'corrected' OR ride_length_sec - ride_length_sec_dst_adj = :sf_correction_sec),
  CHECK (dst_adj_status = 'corrected' OR ride_length_sec = ride_length_sec_dst_adj)
);

INSERT INTO clean.trips
SELECT s.source_csv, s.source_line, s.ride_id, r.rideable_type, r.member_casual,
       s.s_ts, s.e_ts, s.e_ts - s.s_ts, s.dur_sec,
       CASE WHEN d.confirmed THEN s.dur_sec - :sf_correction_sec ELSE s.dur_sec END,
       CASE WHEN d.confirmed THEN 'corrected' WHEN d0.span THEN 'span_not_confirmed' ELSE 'not_applicable' END,
       (s.s_ts < :'fb_end'::timestamp AND s.e_ts >= :'fb_start'::timestamp),
       d0.span,
       (EXTRACT(DOW FROM s.s_ts) + 1)::smallint,
       EXTRACT(HOUR FROM s.s_ts)::smallint,
       date_trunc('month', s.s_ts)::date,
       btrim(r.start_station_name, :'trim_chars'), btrim(r.start_station_id, :'trim_chars'),
       btrim(r.end_station_name, :'trim_chars'),   btrim(r.end_station_id, :'trim_chars'),
       r.start_station_name IS DISTINCT FROM btrim(r.start_station_name, :'trim_chars'),
       r.start_station_id   IS DISTINCT FROM btrim(r.start_station_id, :'trim_chars'),
       r.end_station_name   IS DISTINCT FROM btrim(r.end_station_name, :'trim_chars'),
       r.end_station_id     IS DISTINCT FROM btrim(r.end_station_id, :'trim_chars'),
       r.start_station_id IS NULL, r.end_station_id IS NULL,
       r.start_lat::double precision, r.start_lng::double precision,
       r.end_lat::double precision,   r.end_lng::double precision,
       r.end_lat IS NOT NULL,
       s.dur_sec > :long_trip_sec
FROM stage s
JOIN raw.trips r USING (source_csv, source_line)
CROSS JOIN LATERAL (
  SELECT (s.s_ts < :'sf_start'::timestamp AND s.e_ts >= :'sf_end'::timestamp) AS span,
         ((s.s_ts >= :'sf_start'::timestamp AND s.s_ts < :'sf_end'::timestamp)
           OR (s.e_ts >= :'sf_start'::timestamp AND s.e_ts < :'sf_end'::timestamp)) AS in_gap,
         EXTRACT(EPOCH FROM (s.e_ts AT TIME ZONE :'tz') - (s.s_ts AT TIME ZONE :'tz')) AS tz_sec
) d0
CROSS JOIN LATERAL (
  -- correction de l'heure d'été seulement si les 4 critères individuels sont vérifiés (R3)
  SELECT d0.span AND NOT d0.in_gap
         AND d0.tz_sec = s.dur_sec - :sf_correction_sec
         AND s.dur_sec - :sf_correction_sec >= 0 AS confirmed
) d
WHERE s.reason IS NULL;

-- 4. Journal de normalisation des stations (R8), au niveau des valeurs -----------------
CREATE TABLE audit.normalization_log AS
WITH t AS (
  SELECT x.column_name, x.raw_value, x.normalized_value, count(*) AS n_rows
  FROM clean.trips c
  JOIN raw.trips r USING (source_csv, source_line)
  CROSS JOIN LATERAL (VALUES
    ('start_station_name', r.start_station_name, c.start_station_name, c.start_station_name_trimmed),
    ('start_station_id',   r.start_station_id,   c.start_station_id,   c.start_station_id_trimmed),
    ('end_station_name',   r.end_station_name,   c.end_station_name,   c.end_station_name_trimmed),
    ('end_station_id',     r.end_station_id,     c.end_station_id,     c.end_station_id_trimmed)
  ) AS x(column_name, raw_value, normalized_value, trimmed)
  WHERE (c.start_station_name_trimmed OR c.start_station_id_trimmed
         OR c.end_station_name_trimmed OR c.end_station_id_trimmed)
    AND x.trimmed
  GROUP BY 1, 2, 3
)
SELECT t.*,
       CASE t.column_name
         WHEN 'start_station_name' THEN EXISTS (SELECT 1 FROM clean.trips c WHERE c.start_station_name = t.normalized_value AND NOT c.start_station_name_trimmed)
         WHEN 'start_station_id'   THEN EXISTS (SELECT 1 FROM clean.trips c WHERE c.start_station_id   = t.normalized_value AND NOT c.start_station_id_trimmed)
         WHEN 'end_station_name'   THEN EXISTS (SELECT 1 FROM clean.trips c WHERE c.end_station_name   = t.normalized_value AND NOT c.end_station_name_trimmed)
         WHEN 'end_station_id'     THEN EXISTS (SELECT 1 FROM clean.trips c WHERE c.end_station_id     = t.normalized_value AND NOT c.end_station_id_trimmed)
       END AS merges_with_existing_value
FROM t;
ALTER TABLE audit.normalization_log ADD PRIMARY KEY (column_name, raw_value);

SELECT pg_temp.assert(NOT EXISTS (SELECT 1 FROM audit.normalization_log WHERE normalized_value = ''),
       'R8 : une normalisation a produit une chaîne vide');

-- 5. Vues d'analyse : sous-ensembles propres à certaines analyses (pas des exclusions) ----
CREATE VIEW clean.v_trips_geo           AS SELECT * FROM clean.trips WHERE has_end_location;
CREATE VIEW clean.v_trips_start_station AS SELECT * FROM clean.trips WHERE NOT start_station_missing;
CREATE VIEW clean.v_trips_end_station   AS SELECT * FROM clean.trips WHERE NOT end_station_missing;
CREATE VIEW clean.v_trips_station_pair  AS SELECT * FROM clean.trips WHERE NOT start_station_missing AND NOT end_station_missing;
-- SENS-1 (D5) : population principale + trajets positifs < 60 s, sans les durées négatives
CREATE VIEW clean.v_sens1_population AS
  SELECT source_csv, source_line, member_casual, rideable_type, started_at, ride_length_sec, false AS is_under_60s
  FROM clean.trips
  UNION ALL
  SELECT source_csv, source_line, member_casual, rideable_type, started_at, ride_length_sec, true
  FROM audit.excluded_rows WHERE reason = 'under_60s';

CREATE TABLE audit.analysis_subsets (
  subset     text PRIMARY KEY,
  object     text NOT NULL,
  filter     text NOT NULL,
  scope      text NOT NULL
);
INSERT INTO audit.analysis_subsets VALUES
  ('global',        'clean.trips',                 'aucun',                                       'exclusions de base uniquement (R1, R2, R4a, R4b)'),
  ('geo',           'clean.v_trips_geo',           'has_end_location',                            'distances et cartes ; les trajets sans arrivée restent dans clean.trips'),
  ('start_station', 'clean.v_trips_start_station', 'NOT start_station_missing',                   'analyses par station de départ ; trajets sans station conservés ailleurs'),
  ('end_station',   'clean.v_trips_end_station',   'NOT end_station_missing',                     'analyses par station d''arrivée'),
  ('station_pair',  'clean.v_trips_station_pair',  'les deux stations présentes',                 'itinéraires station à station'),
  ('sens1',         'clean.v_sens1_population',    'clean.trips + motif under_60s',               'sensibilité D5 uniquement ; jamais l''analyse principale');

-- 6. Réconciliation finale (bloquante) -----------------------------------------------
SELECT pg_temp.assert(k + e = r, format('réconciliation : %s conservées + %s exclues ≠ %s brutes', k, e, r))
FROM (SELECT (SELECT count(*) FROM clean.trips) AS k,
             (SELECT count(*) FROM audit.excluded_rows) AS e,
             (SELECT count(*) FROM raw.trips) AS r) x;
SELECT pg_temp.assert(NOT EXISTS (SELECT 1 FROM clean.trips c JOIN audit.excluded_rows e USING (source_csv, source_line)),
       'une ligne est à la fois conservée et exclue');
SELECT pg_temp.assert((SELECT rows_after FROM audit.transform_log WHERE step_no = 4) = (SELECT count(*) FROM clean.trips),
       'journal des étapes incohérent avec clean.trips');

-- 7. Enregistrement de l'exécution ----------------------------------------------------
CREATE TABLE audit.run (
  run_id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  run_started    timestamptz NOT NULL,
  sql_finished   timestamptz NOT NULL DEFAULT clock_timestamp(),
  rules_version  text        NOT NULL,
  rules_sha256   text        NOT NULL,
  plan_sha256    text        NOT NULL,
  scripts        jsonb       NOT NULL,
  parameters     jsonb       NOT NULL,
  preflight      jsonb       NOT NULL,
  raw_rows       bigint      NOT NULL,
  kept_rows      bigint      NOT NULL,
  excluded_rows  bigint      NOT NULL,
  db_user        text        NOT NULL DEFAULT current_user,
  server_version text        NOT NULL DEFAULT current_setting('server_version')
);
INSERT INTO audit.run (run_started, rules_version, rules_sha256, plan_sha256, scripts, parameters, preflight,
                       raw_rows, kept_rows, excluded_rows)
VALUES (:'run_started'::timestamptz, :'rules_version', :'rules_sha256', :'plan_sha256',
        :'scripts_json'::jsonb, :'params_json'::jsonb, :'preflight_json'::jsonb,
        (SELECT count(*) FROM raw.trips), (SELECT count(*) FROM clean.trips), (SELECT count(*) FROM audit.excluded_rows));

ANALYZE clean.trips;
ANALYZE audit.excluded_rows;

-- Sortie récapitulative (lue par run_clean.py)
SELECT 'run', run_id::text, rules_version, kept_rows::text, excluded_rows::text FROM audit.run;
SELECT 'step', step_no::text, step, coalesce(rows_excluded::text, ''), rows_after::text FROM audit.transform_log ORDER BY step_no;
