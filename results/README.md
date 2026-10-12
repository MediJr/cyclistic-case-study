# Results: aggregated tables

All files are **aggregates** computed from the cleaned table `clean.trips` (6,012,458 rides, 1 October 2025 to 30 September 2026). They contain no ride identifiers, no coordinates and no row-level data. Column names are the ones produced by the SQL queries (mostly in French); this page translates them.

Common values:
- `member_casual`: `member` = annual member, `casual` = casual rider, `TOUS` = all rides.
- `day_of_week`: 1 = Sunday … 7 = Saturday.
- `type_jour`: `semaine` = weekday, `week-end` = weekend.
- `rideable_type`: `classic_bike`, `electric_bike`.
- Durations are in minutes (`_min`), or in seconds (`_s`) in the sensitivity files.

## `analysis/` — produced by `scripts/run_analyse.py` (`sql/10_analyse.sql`)

| File | Content | Main columns |
|---|---|---|
| `a00_controle.csv` | Control totals | `trajets` (rides), `member`, `casual`, `premier_depart` / `dernier_depart` (first / last start), `mois` (months) |
| `a01_usagers.csv` | Summary by rider type | `trajets` (rides), `part_pct` (share %), `moyenne_min` (mean), `mediane_min` (median), `p25_min`…`p99_min` (percentiles), `ecart_type_min` (std. dev.), `trajets_plus_24h` (rides > 24 h), `part_30min_plus_pct` (share ≥ 30 min), `*_dst_corrigee` (with the 8 March DST correction) |
| `a02_durees_tranches.csv` | Distribution by duration band | `tranche` (band), `trajets`, `part_pct` |
| `a03_jour.csv` | By day of week | `day_of_week`, `trajets`, `part_pct`, `mediane_min`, `moyenne_min` |
| `a04_mois.csv` | By month of departure | `mois` (YYYY-MM), `trajets`, `part_du_mois_pct` (share of the month's rides), `mediane_min`, `moyenne_min` |
| `a05_heure.csv` | By hour of departure and type of day | `type_jour`, `heure` (hour 0–23), `trajets`, `part_pct` (share of the group's rides on that type of day) |
| `a06_velo.csv` | By bike type | `rideable_type`, `trajets`, `part_pct`, `mediane_min`, `moyenne_min` |
| `a07_interactions.csv` | Bike type × type of day | `rideable_type`, `type_jour`, `trajets`, `part_pct`, `mediane_min`, `p75_min`, `moyenne_min` |
| `a08_boucles.csv` | Round trips | `trajets_avec_2_stations` (rides with both stations), `trajets_boucle` (round trips), `part_boucle_pct`, `mediane_boucle_min` |
| `a09_contexte.csv` | Data coverage | `depart_sans_station_pct` / `arrivee_sans_station_pct` (% without start / end station), `sans_coord_arrivee_pct` (% without end coordinates), `plus_24h_pct`, `corrections_dst`, `chevauchement_heure_automne` (fall-back overlap) |
| `a10_jours.csv` | Daily series | `date`, `member_casual`, `trajets` |
| `a11_jour_heure.csv` | Day of week × hour | `day_of_week`, `heure`, `trajets` |

## `quality/` — produced by `scripts/run_qa_clean.py` and `scripts/run_sensitivity.py`

| File | Content |
|---|---|
| `qa_results.csv` | The 72 post-cleaning checks: `controle` (check id), `libelle` (label, French), `attendu` (expected), `mesure` (measured), `statut` (status; see [`docs/methodology.md`](../docs/methodology.md#3-quality-assurance)) |
| `sens1_summary.csv` | SENS-1: population `A_principale` (analyzed rides) vs `B_avec_moins_60s` (rides < 60 s added back), by bike type and rider type: rides, median / mean / 95th percentile duration (s) |
| `sens1_ecarts.csv` | SENS-1 differences (B − A): ride counts, median and mean (s) |
| `sens2_summary.csv` | SENS-2: with / without 31 March and 1 April 2026 (`avec_` / `sans_31mars_1avril`): rides, median and mean (s) |

The station-level check lists (S1–S4) and run logs are not published: they are working outputs, and the logs contain machine-specific information.
