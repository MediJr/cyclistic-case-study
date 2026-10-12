"""Import brut des 12 CSV Cyclistic dans PostgreSQL (base `cyclistic`, schéma `raw`).

Usage : python -I scripts/load_raw.py
- Crée la base `cyclistic` si elle n'existe pas, puis le schéma `raw` (échoue s'il existe déjà).
- Copie chaque CSV tel quel (COPY CSV HEADER MATCH) : colonnes en texte, aucune conversion,
  aucun filtre, aucune suppression ; les doublons de ride_id restent présents.
- Enregistre la provenance : ZIP, CSV, numéro de ligne physique, empreintes SHA-256.
- Tout l'import se fait dans une seule transaction (tout ou rien).
- Vérifie que les fichiers sources sont inchangés après l'import.
"""
import csv
import hashlib
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pg import psql  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
EXT = os.path.join(ROOT, "data", "extracted")
MONTHS = ["202510", "202511", "202512", "202601", "202602", "202603",
          "202604", "202605", "202606", "202607", "202608", "202609"]
COLS = ["ride_id", "rideable_type", "started_at", "ended_at", "start_station_name",
        "start_station_id", "end_station_name", "end_station_id", "start_lat",
        "start_lng", "end_lat", "end_lng", "member_casual"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sources():
    out = []
    for m in MONTHS:
        zip_name = f"{m}-divvy-tripdata.zip"
        zpath = os.path.join(RAW, zip_name)
        with zipfile.ZipFile(zpath) as zf:
            names = [n for n in zf.namelist()
                     if n.lower().endswith(".csv") and not n.startswith("__MACOSX")]
        assert len(names) == 1, (zip_name, names)
        cpath = os.path.join(EXT, names[0])
        with open(cpath, newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            header = next(r)
            assert header == COLS, (names[0], header)
            rows = sum(1 for _ in r)
        out.append(dict(zip_name=zip_name, csv_name=names[0], file_month=f"{m[:4]}-{m[4:]}",
                        zpath=zpath, cpath=cpath,
                        zip_bytes=os.path.getsize(zpath), zip_sha256=sha256(zpath),
                        csv_bytes=os.path.getsize(cpath), csv_sha256=sha256(cpath),
                        csv_data_rows=rows))
    return out


def q(s):
    return "'" + s.replace("'", "''") + "'"


def main():
    files = sources()
    print("Sources vérifiées (en-têtes, empreintes, lignes) :", len(files))

    if not psql("postgres", "SELECT 1 FROM pg_database WHERE datname = 'cyclistic'"):
        psql("postgres", "CREATE DATABASE cyclistic ENCODING 'UTF8' TEMPLATE template0")
        print("Base `cyclistic` créée.")
    else:
        print("Base `cyclistic` déjà existante.")

    cols = ", ".join(COLS)
    script = ["BEGIN;", open(os.path.join(ROOT, "sql", "01_create_raw.sql"), encoding="utf-8").read()]
    for f in files:
        script.append(
            "INSERT INTO raw.source_files (zip_name, csv_name, file_month, zip_bytes, zip_sha256, "
            "csv_bytes, csv_sha256, csv_data_rows) VALUES "
            f"({q(f['zip_name'])}, {q(f['csv_name'])}, {q(f['file_month'])}, {f['zip_bytes']}, "
            f"{q(f['zip_sha256'])}, {f['csv_bytes']}, {q(f['csv_sha256'])}, {f['csv_data_rows']});")
        # Table temporaire : l'identité numérote les lignes dans l'ordre de lecture du fichier.
        script.append(
            "CREATE TEMP TABLE stg (line_no bigint GENERATED ALWAYS AS IDENTITY, "
            + ", ".join(f"{c} text" for c in COLS) + ");")
        path = f["cpath"].replace("\\", "/")
        script.append(f"\\copy stg ({cols}) FROM {q(path)} WITH (FORMAT csv, HEADER match, ENCODING 'UTF8')")
        script.append(
            f"INSERT INTO raw.trips (source_zip, source_csv, source_line, {cols}) "
            f"SELECT {q(f['zip_name'])}, {q(f['csv_name'])}, line_no + 1, {cols} FROM stg ORDER BY line_no;")
        script.append("DROP TABLE stg;")
    script.append("ANALYZE raw.trips;")
    script.append("COMMIT;")
    psql("cyclistic", stdin="\n".join(script) + "\n")
    print("Import terminé.")

    for f in files:
        assert sha256(f["zpath"]) == f["zip_sha256"], f["zip_name"]
        assert sha256(f["cpath"]) == f["csv_sha256"], f["csv_name"]
    print("Empreintes SHA-256 des 24 fichiers sources inchangées après import.")


if __name__ == "__main__":
    main()
