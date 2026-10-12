-- Schéma brut Cyclistic : copie fidèle des 12 CSV, sans transformation.
-- Toutes les colonnes sources sont en texte ; un champ vide non quoté du CSV devient NULL (convention COPY CSV).
-- Aucune contrainte d'unicité sur ride_id : les doublons inter-fichiers restent présents.
-- Refuse de s'exécuter si les tables existent déjà (aucun écrasement silencieux).

CREATE SCHEMA raw;

CREATE TABLE raw.source_files (
    zip_name       text PRIMARY KEY,
    csv_name       text NOT NULL UNIQUE,
    file_month     text NOT NULL,          -- AAAA-MM déduit du nom du ZIP, jamais du nom du CSV
    zip_bytes      bigint NOT NULL,
    zip_sha256     text NOT NULL,
    csv_bytes      bigint NOT NULL,
    csv_sha256     text NOT NULL,
    csv_data_rows  bigint NOT NULL,        -- compté par Python (csv.reader) avant import
    loaded_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE raw.trips (
    source_zip          text    NOT NULL REFERENCES raw.source_files (zip_name),
    source_csv          text    NOT NULL,
    source_line         integer NOT NULL,  -- numéro de ligne physique dans le CSV (en-tête = 1)
    ride_id             text,
    rideable_type       text,
    started_at          text,
    ended_at            text,
    start_station_name  text,
    start_station_id    text,
    end_station_name    text,
    end_station_id      text,
    start_lat           text,
    start_lng           text,
    end_lat             text,
    end_lng             text,
    member_casual       text,
    PRIMARY KEY (source_csv, source_line)
);
