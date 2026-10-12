# Methodology: data preparation, quality assurance and analysis

This document summarizes, in English, how the 6,012,458 analyzed rides were obtained from the 6,171,785 raw rows. The authoritative specification of the cleaning rules is the original plan, written in French, [`plan_nettoyage_v3.2.md`](plan_nettoyage_v3.2.md). It is kept unchanged because `scripts/run_clean.py` requires it and records its SHA-256 checksum in the audit tables of the database.

## 1. Pipeline overview

| Phase | What happens | Code | Output |
|---|---|---|---|
| Prepare | Download of the 12 monthly ZIP files, SHA-256 checksums, consistency audit (columns, dates, identifiers, duplicates) | `scripts/audit_collecte.py` | console report |
| Import | Raw import into PostgreSQL schema `raw`, all 13 columns as text, no filtering; provenance (file, line number, checksums) recorded; post-import checks | `scripts/run_import.py`, `load_raw.py`, `qa_import.py`, `audit_import.py`, `sql/01_create_raw.sql`, `sql/qa_import.sql`, `sql/audit_import.sql` | `raw.trips`, `raw.source_files` |
| Pre-checks | Read-only station checks (S1–S6) and daylight-saving-time criteria before cleaning | `scripts/run_stations_precheck.py`, `sql/05_stations_precontrole.sql` | CSV lists (not published) |
| Process | Cleaning rules v3.2 applied in **one transaction**; raw table fingerprint checked before and after | `scripts/run_clean.py`, `sql/02_clean.sql`, `config/regles_nettoyage_v3.2.json`, `config/attendus_v3.2.json` | `clean.trips`, `audit.*` |
| QA | 72 read-only quality checks | `scripts/run_qa_clean.py`, `sql/03_qa_clean.sql` | [`results/quality/qa_results.csv`](../results/quality/qa_results.csv) |
| Sensitivity | SENS-1 (rides < 60 s added back) and SENS-2 (31 March and 1 April 2026 removed) | `scripts/run_sensitivity.py`, `sql/04_sensitivity.sql` | [`results/quality/`](../results/quality/) |
| Analyze | Read-only aggregations by rider type, day, month, hour, bike type and round trips | `scripts/run_analyse.py`, `sql/10_analyse.sql` | [`results/analysis/`](../results/analysis/) |
| Share | Charts and report built from the CSV files only | `scripts/figures_analyse.py`, `scripts/build_latex_report.py` | [`visualizations/`](../visualizations/), [`reports/`](../reports/) |

Supporting, read-only measurement scripts (`scripts/mesure_espaces_limites.py`, `scripts/mesure_stations_durees.py`) read the extracted CSV files and produced the figures behind some cleaning decisions: leading and trailing spaces in station fields, rides crossing month boundaries, and test or staff stations.

## 2. Cleaning rules (v3.2)

Exclusions are applied in a fixed order; each excluded row receives exactly one reason.

| Order | Rule | Rows excluded | Rows remaining |
|---|---|---:|---:|
| – | Raw data (12 CSV files) | – | 6,171,785 |
| 1 | Duplicate `ride_id` (35 rides from 30 April to 1 May 2026 present in both the April and May files; the April copy is kept) | 35 | 6,171,750 |
| 2 | Ride started outside the period (period defined on `started_at`: 2025-10-01 00:00 to 2026-10-01 00:00, local time) | 71 | 6,171,679 |
| 3 | Negative duration (clock change) | 29 | 6,171,650 |
| 4 | Positive duration shorter than 60 seconds | 159,192 | **6,012,458** |
| | **Total excluded** | **159,327** | |

Other decisions:

- **60-second threshold.** Divvy's *System Data* page states that rides shorter than 60 seconds are removed from the published data. They were still present in the files, exclusively for e-bikes. Excluding them is a provisional choice, tested by the SENS-1 sensitivity analysis.
- **No global removal** of rides without stations (20.0% without a start station, 20.8% without an end station, mostly e-bikes), without end coordinates, or longer than 24 hours. These rides are flagged and left out only of the analyses that need the missing information.
- **Minimal normalization.** Only leading and trailing spaces are trimmed from station names and identifiers; stations are not merged and no values are imputed.
- **Daylight saving time.** Raw timestamps and durations are never modified. For the 40 rides spanning the skipped hour of 8 March 2026, a −3,600 s correction is stored in a separate column, after four criteria were checked ride by ride. When clocks go back in the fall, the 474 rides that overlap the repeated hour are flagged but not corrected.
- **Test or staff stations.** The 41 rides linked to test, warehouse or repair stations are kept and documented, not excluded.

## 3. Quality assurance

The 72 post-cleaning checks are listed in [`results/quality/qa_results.csv`](../results/quality/qa_results.csv). Check labels are in French; the status codes are:

| Status code | Meaning | Count |
|---|---|---:|
| `OK` | check passed | 62 |
| `INFO` | descriptive output (station lists, spatial spread, counts) | 8 |
| `ANOMALIE_CONNUE` | known anomaly of the source (Q21: no March ride ends in April) | 1 |
| `ÉCHEC` | failed check (Q16b, explained below) | 1 |

**Q16b, explained failure.** The maximum ride duration is 93,597.011 s, while the expected reference had been rounded to 93,597 s. The failure comes from the rounded reference value, not from the data: no rule caps durations. The result was documented and the reference was not edited after the fact.

Key reconciliations that passed include: raw = kept + excluded (6,171,785 = 6,012,458 + 159,327); every raw row in exactly one state; source file checksums unchanged; and the exhaustive fingerprint of `raw.trips` identical before and after cleaning.

## 4. Sensitivity analyses

| Analysis | Population | Median duration (s) | Effect |
|---|---|---:|---|
| SENS-1 | Casual riders, without / with rides < 60 s | 669.9 / 646.2 | gap between groups unchanged in direction |
| SENS-1 | Members, without / with rides < 60 s | 521.4 / 510.6 | |
| SENS-2 | All rides, with / without 31 March and 1 April 2026 | 567.4 / 568.0 | negligible |

Source: [`results/quality/sens1_ecarts.csv`](../results/quality/sens1_ecarts.csv), [`sens1_summary.csv`](../results/quality/sens1_summary.csv) and [`sens2_summary.csv`](../results/quality/sens2_summary.csv).

## 5. Known characteristics of the source

- The January 2026 archive (`202601`) contains a file named `202501-divvy-tripdata.csv`; its content does correspond to January 2026.
- No ride crosses the boundary from 31 March to 1 April 2026, whereas the other month boundaries have between 12 and 173 such rides. By analogy, a gap of about 28 to 102 rides is possible. This is an estimate, not a measurement.
- Rides started on 30 September 2026 and ended in October 2026 were not yet published when the data were downloaded.

## 6. Analysis conventions

- **Unit of analysis:** the ride. The data contain no rider identifier, so no statement is made about numbers of people.
- **Durations:** minutes, computed from the raw timestamps. The median is the main indicator.
- **Percentages:** computed on each group's rides, unless stated otherwise, and recomputed from counts with a single rounding (ROUND_HALF_UP).
- **Weekend:** Saturday and Sunday. **Peak hours:** weekday departures from 7:00 to 8:59 a.m. and from 4:00 to 6:59 p.m., Chicago local time.
- **Round trip:** a ride whose end station equals its start station, computed only on rides that have both stations.
