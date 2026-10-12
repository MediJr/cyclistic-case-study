# Data

**No trip data are stored in this repository.** The scripts expect the original Divvy files, which you must download yourself.

## Source

- **Publisher:** Divvy, Chicago's bike-share system. "Cyclistic" is the fictional company name used by the Google Data Analytics case study.
- **Download page:** <https://divvy-tripdata.s3.amazonaws.com/index.html>
- **License:** [Divvy Data License Agreement](https://divvybikes.com/data-license-agreement), checked on 11 October 2026. It names Lyft Bikes and Scooters, LLC as the operator and the City of Chicago as the owner of the data. The case study brief describes the data as made available by Motivate International Inc.
- **Documentation:** [Divvy System Data](https://divvybikes.com/system-data), which describes the fields and the removal of rides shorter than 60 seconds.

## Why the data are not redistributed

The license allows the data to be used as source material in analyses and reports. It does **not** allow hosting, publishing or distributing the data as a stand-alone data set. This repository therefore publishes only:

- aggregated result tables ([`../results/`](../results/));
- charts ([`../visualizations/`](../visualizations/));
- the report ([`../reports/`](../reports/)).

The license also forbids attempting to link the data to individual customers. The analysis does not do so: the data contain no rider identifier, and every result is aggregated.

## Files used

The 12 monthly archives covering rides **started from 1 October 2025 to 30 September 2026**:

```
202510-divvy-tripdata.zip  202511-divvy-tripdata.zip  202512-divvy-tripdata.zip
202601-divvy-tripdata.zip  202602-divvy-tripdata.zip  202603-divvy-tripdata.zip
202604-divvy-tripdata.zip  202605-divvy-tripdata.zip  202606-divvy-tripdata.zip
202607-divvy-tripdata.zip  202608-divvy-tripdata.zip  202609-divvy-tripdata.zip
```

They contain 6,171,785 data rows in total. Each ZIP holds one CSV with 13 columns: `ride_id`, `rideable_type`, `started_at`, `ended_at`, `start_station_name`, `start_station_id`, `end_station_name`, `end_station_id`, `start_lat`, `start_lng`, `end_lat`, `end_lng`, `member_casual`.

The `202601` archive contains a CSV named `202501-divvy-tripdata.csv`; its content does correspond to January 2026. The scripts handle this.

## Expected layout

```
data/
├── raw/         the 12 ZIP files, unchanged
└── extracted/   the 12 CSV files extracted from them
```

Both folders are excluded from Git by [`../.gitignore`](../.gitignore).

The publisher may update files after publication. The cleaning step therefore checks the files against reference values:

- `scripts/run_clean.py` compares the SHA-256 checksums recorded at import time;
- it also compares the exhaustive fingerprint of the raw table with the one stored in [`../config/attendus_v3.2.json`](../config/attendus_v3.2.json).

If you download different versions of the files, these checks will fail and cleaning will be refused. This is intended: the published results are only valid for the files that were audited.

## Reproducing the analysis

See [Reproducibility](../README.md#reproducibility) in the main README.
