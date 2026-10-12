-- =====================================================================================
-- sql/04_sensitivity.sql — Analyses de sensibilité (C5), LECTURE SEULE.
-- SENS-1 (D5) : population principale (A) contre A + trajets positifs < 60 s (B).
-- SENS-2 (D3) : population principale avec / sans les journées du 31/03 et du 01/04/2026.
-- Les durées négatives sont exclues des deux côtés (elles ne sont pas dans la vue).
-- =====================================================================================

-- name: sens1_summary
WITH pop AS (
  SELECT 'A_principale' AS scope, * FROM clean.v_sens1_population WHERE NOT is_under_60s
  UNION ALL
  SELECT 'B_avec_moins_60s', * FROM clean.v_sens1_population
)
SELECT scope, coalesce(rideable_type, 'TOUS'), coalesce(member_casual, 'TOUS'), count(*),
       round(percentile_cont(0.5)  WITHIN GROUP (ORDER BY ride_length_sec)::numeric, 1),
       round(avg(ride_length_sec), 1),
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY ride_length_sec)::numeric, 1),
       count(*) FILTER (WHERE is_under_60s)
FROM pop
GROUP BY GROUPING SETS ((scope, rideable_type, member_casual), (scope, rideable_type), (scope, member_casual), (scope))
ORDER BY 1, 2, 3;

-- name: sens1_dow
WITH pop AS (
  SELECT 'A_principale' AS scope, * FROM clean.v_sens1_population WHERE NOT is_under_60s
  UNION ALL
  SELECT 'B_avec_moins_60s', * FROM clean.v_sens1_population
)
SELECT scope, rideable_type, member_casual, (EXTRACT(DOW FROM started_at) + 1)::int, count(*)
FROM pop GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4;

-- name: sens1_hour
WITH pop AS (
  SELECT 'A_principale' AS scope, * FROM clean.v_sens1_population WHERE NOT is_under_60s
  UNION ALL
  SELECT 'B_avec_moins_60s', * FROM clean.v_sens1_population
)
SELECT scope, rideable_type, member_casual, EXTRACT(HOUR FROM started_at)::int, count(*)
FROM pop GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4;

-- name: sens2_summary
WITH pop AS (
  SELECT 'avec_31mars_1avril' AS scope, * FROM clean.trips
  UNION ALL
  SELECT 'sans_31mars_1avril', * FROM clean.trips
  WHERE started_at::date NOT IN (date '2026-03-31', date '2026-04-01')
)
SELECT scope, coalesce(member_casual, 'TOUS'), count(*),
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY ride_length_sec)::numeric, 1),
       round(avg(ride_length_sec), 1)
FROM pop GROUP BY GROUPING SETS ((scope, member_casual), (scope)) ORDER BY 1, 2;

-- name: sens2_hour
WITH pop AS (
  SELECT 'avec_31mars_1avril' AS scope, * FROM clean.trips
  UNION ALL
  SELECT 'sans_31mars_1avril', * FROM clean.trips
  WHERE started_at::date NOT IN (date '2026-03-31', date '2026-04-01')
)
SELECT scope, member_casual, start_hour, count(*) FROM pop GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
