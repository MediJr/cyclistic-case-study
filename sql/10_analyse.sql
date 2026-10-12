-- =====================================================================================
-- sql/10_analyse.sql — Phase Analyze : agrégations membres / occasionnels (LECTURE SEULE)
-- Source : clean.trips (règles v3.2, 6 012 458 trajets du 2025-10-01 au 2026-09-30).
-- Exécuté par scripts/run_analyse.py (session default_transaction_read_only=on).
-- Unités : durées en minutes (ride_length_sec / 60), calculées sur les horodatages bruts
--          (ride_length_sec). La colonne corrigée DST n'est utilisée qu'en contrôle (a01).
-- Unité de compte : le TRAJET (aucun identifiant d'usager : pas de comptage de personnes).
-- day_of_week : 1 = dimanche … 7 = samedi ; week-end = 1 et 7. Heures locales de Chicago.
-- =====================================================================================

-- name: a00_controle
SELECT count(*), count(*) FILTER (WHERE member_casual = 'member'), count(*) FILTER (WHERE member_casual = 'casual'),
       min(started_at)::text, max(started_at)::text, count(DISTINCT ride_month)
FROM clean.trips;

-- name: a01_usagers
SELECT coalesce(member_casual, 'TOUS'), count(*),
       round(100.0 * count(*) / sum(count(*)) FILTER (WHERE member_casual IS NOT NULL) OVER (), 2),
       round(avg(ride_length_sec) / 60, 2),
       round((percentile_cont(0.50) WITHIN GROUP (ORDER BY ride_length_sec::float8) / 60)::numeric, 2),
       round((percentile_cont(0.25) WITHIN GROUP (ORDER BY ride_length_sec::float8) / 60)::numeric, 2),
       round((percentile_cont(0.75) WITHIN GROUP (ORDER BY ride_length_sec::float8) / 60)::numeric, 2),
       round((percentile_cont(0.90) WITHIN GROUP (ORDER BY ride_length_sec::float8) / 60)::numeric, 2),
       round((percentile_cont(0.99) WITHIN GROUP (ORDER BY ride_length_sec::float8) / 60)::numeric, 2),
       round(stddev(ride_length_sec) / 60, 2),
       count(*) FILTER (WHERE is_over_24h),
       round(100.0 * avg((ride_length_sec >= 1800)::int), 2),
       round(avg(ride_length_sec_dst_adj) / 60, 2),
       round((percentile_cont(0.50) WITHIN GROUP (ORDER BY ride_length_sec_dst_adj::float8) / 60)::numeric, 2)
FROM clean.trips
GROUP BY GROUPING SETS ((member_casual), ())
ORDER BY 1;

-- name: a02_durees_tranches
WITH b AS (
  SELECT member_casual,
         CASE WHEN ride_length_sec < 300   THEN '01: 1-5 min'
              WHEN ride_length_sec < 600   THEN '02: 5-10 min'
              WHEN ride_length_sec < 900   THEN '03: 10-15 min'
              WHEN ride_length_sec < 1200  THEN '04: 15-20 min'
              WHEN ride_length_sec < 1800  THEN '05: 20-30 min'
              WHEN ride_length_sec < 2700  THEN '06: 30-45 min'
              WHEN ride_length_sec < 3600  THEN '07: 45-60 min'
              WHEN ride_length_sec < 7200  THEN '08: 1-2 h'
              WHEN ride_length_sec <= 86400 THEN '09: 2-24 h'
              ELSE '10: > 24 h' END AS tranche
  FROM clean.trips
)
SELECT member_casual, tranche, count(*),
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY member_casual), 2)
FROM b GROUP BY 1, 2 ORDER BY 1, 2;

-- name: a03_jour
SELECT member_casual, day_of_week, count(*),
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY member_casual), 2),
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY ride_length_sec::float8) / 60)::numeric, 2),
       round(avg(ride_length_sec) / 60, 2)
FROM clean.trips GROUP BY 1, 2 ORDER BY 1, 2;

-- name: a04_mois
SELECT to_char(ride_month, 'YYYY-MM'), member_casual, count(*),
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY ride_month), 2),
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY ride_length_sec::float8) / 60)::numeric, 2),
       round(avg(ride_length_sec) / 60, 2)
FROM clean.trips GROUP BY ride_month, member_casual ORDER BY ride_month, member_casual;

-- name: a05_heure
SELECT member_casual, CASE WHEN day_of_week IN (1, 7) THEN 'week-end' ELSE 'semaine' END AS type_jour,
       start_hour, count(*),
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY member_casual,
             CASE WHEN day_of_week IN (1, 7) THEN 'week-end' ELSE 'semaine' END), 3)
FROM clean.trips GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

-- name: a06_velo
SELECT member_casual, rideable_type, count(*),
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY member_casual), 2),
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY ride_length_sec::float8) / 60)::numeric, 2),
       round(avg(ride_length_sec) / 60, 2)
FROM clean.trips GROUP BY 1, 2 ORDER BY 1, 2;

-- name: a07_interactions
SELECT member_casual, rideable_type, CASE WHEN day_of_week IN (1, 7) THEN 'week-end' ELSE 'semaine' END,
       count(*),
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY member_casual), 2),
       round((percentile_cont(0.5)  WITHIN GROUP (ORDER BY ride_length_sec::float8) / 60)::numeric, 2),
       round((percentile_cont(0.75) WITHIN GROUP (ORDER BY ride_length_sec::float8) / 60)::numeric, 2),
       round(avg(ride_length_sec) / 60, 2)
FROM clean.trips GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

-- name: a08_boucles
-- Trajets « aller-retour » : station de départ = station d'arrivée (ID normalisés), parmi les
-- trajets ayant les deux stations (couverture limitée : vélos électriques hors station exclus).
SELECT member_casual,
       count(*),
       count(*) FILTER (WHERE NOT start_station_missing AND NOT end_station_missing),
       count(*) FILTER (WHERE NOT start_station_missing AND NOT end_station_missing AND start_station_id = end_station_id),
       round(100.0 * count(*) FILTER (WHERE start_station_id = end_station_id)
             / nullif(count(*) FILTER (WHERE NOT start_station_missing AND NOT end_station_missing), 0), 2),
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY ride_length_sec::float8)
              FILTER (WHERE start_station_id = end_station_id) / 60)::numeric, 2)
FROM clean.trips GROUP BY 1 ORDER BY 1;

-- name: a09_contexte
-- Couverture des champs et indicateurs, par type d'usager (contexte d'interprétation)
SELECT member_casual, count(*),
       round(100.0 * avg(start_station_missing::int), 2),
       round(100.0 * avg(end_station_missing::int), 2),
       round(100.0 * avg((NOT has_end_location)::int), 3),
       round(100.0 * avg(is_over_24h::int), 3),
       count(*) FILTER (WHERE dst_adj_status = 'corrected'),
       count(*) FILTER (WHERE dst_fall_back_overlap)
FROM clean.trips GROUP BY 1 ORDER BY 1;

-- name: a10_jours
-- Série quotidienne (tendance) : trajets par date de départ et type d'usager
SELECT started_at::date::text, member_casual, count(*)
FROM clean.trips GROUP BY 1, 2 ORDER BY 1, 2;

-- name: a11_jour_heure
SELECT member_casual, day_of_week, start_hour, count(*)
FROM clean.trips GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
