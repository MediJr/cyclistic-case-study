"""Contrôles qualité de l'import brut (lecture seule) et comparaison aux mesures précédentes.

Usage : python -I scripts/qa_import.py
Écrit le détail dans reports/qa_import_output.txt ; code de sortie 1 si un contrôle échoue.
Valeurs attendues : missions 1-2 (scripts/audit_collecte.py) et mission 3 (profilage).
"""
import csv
import hashlib
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pg import psql  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "data", "extracted")
COLS = ["ride_id", "rideable_type", "started_at", "ended_at", "start_station_name",
        "start_station_id", "end_station_name", "end_station_id", "start_lat",
        "start_lng", "end_lat", "end_lng", "member_casual"]

# Mission 2 : lignes, min/max started_at (à la seconde), trajets hors du mois du fichier.
EXP_FILES = {
    "2025-10": (646039, "2025-09-30 08:37:53", "2025-10-31 23:56:47", 71),
    "2025-11": (356628, "2025-10-31 01:24:38", "2025-11-30 23:51:43", 128),
    "2025-12": (140534, "2025-11-30 16:02:08", "2025-12-31 23:53:24", 12),
    "2026-01": (137787, "2025-12-31 10:30:49", "2026-01-31 23:56:54", 23),
    "2026-02": (201450, "2026-01-31 11:08:07", "2026-02-28 23:57:54", 18),
    "2026-03": (317037, "2026-02-28 10:48:22", "2026-03-31 23:55:56", 22),
    "2026-04": (448252, "2026-04-01 00:01:42", "2026-04-30 23:58:56", 0),
    "2026-05": (653704, "2026-04-30 00:24:47", "2026-05-31 23:57:08", 35),
    "2026-06": (762550, "2026-05-31 01:07:54", "2026-06-30 23:58:47", 78),
    "2026-07": (869051, "2026-06-29 23:11:19", "2026-07-31 23:58:05", 123),
    "2026-08": (868191, "2026-07-30 23:01:41", "2026-08-31 23:55:36", 173),
    "2026-09": (770562, "2026-08-31 00:53:20", "2026-09-30 23:59:38", 51),
}
EXP_TOTAL = 6171785
# Mission 3 : valeurs manquantes (lignes brutes).
EXP_MISSING = {c: 0 for c in COLS}
EXP_MISSING.update(start_station_name=1289486, start_station_id=1289486,
                   end_station_name=1355487, end_station_id=1355487, end_lat=5451, end_lng=5451)
REQUIRED = ["ride_id", "rideable_type", "started_at", "ended_at", "member_casual",
            "start_lat", "start_lng"]
EXP_CATEGORIES = {("rideable_type", "classic_bike"): 1784432, ("rideable_type", "electric_bike"): 4387353,
                  ("member_casual", "casual"): 2189024, ("member_casual", "member"): 3982761}

results = []
out_lines = []


def log(s=""):
    print(s)
    out_lines.append(s)


def check(name, expected, measured):
    ok = expected == measured
    results.append((name, ok))
    log(f"[{'OK ' if ok else 'ÉCHEC'}] {name} : attendu={expected} mesuré={measured}")


def queries():
    text = open(os.path.join(ROOT, "sql", "qa_import.sql"), encoding="utf-8").read()
    blocks = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    return {blocks[i]: blocks[i + 1] for i in range(1, len(blocks), 2)}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    Q = queries()
    run = lambda n: psql("cyclistic", Q[n])  # noqa: E731

    log("== 1. Lignes par fichier et total ==")
    for csv_name, month, py_rows, db_rows, lmin, lmax in run("rows_per_file"):
        exp = EXP_FILES[month][0]
        check(f"lignes {csv_name} (mois ZIP {month}) vs mission 2", exp, int(db_rows))
        check(f"lignes {csv_name} vs comptage Python pré-import", int(py_rows), int(db_rows))
        check(f"source_line {csv_name} contiguës 2..n+1", (2, exp + 1), (int(lmin), int(lmax)))
    check("total général", EXP_TOTAL, int(run("total_rows")[0][0]))
    check("source_csv cohérent avec le ZIP", 0, int(run("source_csv_consistency")[0][0]))

    log("\n== 2. Schéma ==")
    schema = run("schema")
    names = [r[0] for r in schema]
    check("colonnes de raw.trips", ["source_zip", "source_csv", "source_line"] + COLS, names)
    check("colonnes sources en texte", ["text"] * 13, [r[1] for r in schema[3:]])
    log("  (l'en-tête de chaque CSV a aussi été validé par COPY ... HEADER MATCH lors de l'import)")

    log("\n== 3. Valeurs manquantes ==")
    miss = {c: (int(n), int(e)) for c, n, e in run("missing_all_columns")}
    for c in COLS:
        tag = "indispensable" if c in REQUIRED else "facultatif"
        check(f"NULL {c} ({tag}) vs mission 3", EXP_MISSING[c], miss[c][0])
    check("chaînes vides '' (toutes colonnes)", 0, sum(e for _, e in miss.values()))
    cats = {(k, v): int(n) for k, v, n in run("category_values")}
    check("valeurs de rideable_type / member_casual vs mission 3", EXP_CATEGORIES, cats)
    check("horodatages au format ISO (started_at, ended_at)", ["0", "0"], run("timestamp_format")[0])

    log("\n== 4. Identifiants ==")
    total, distinct = map(int, run("distinct_ride_id")[0])
    check("ride_id distincts vs mission 2", 6171750, distinct)
    check("doublons à l'intérieur d'un fichier", 0, int(run("dup_within_file")[0][0]))
    cross = [(f, int(i), int(r)) for f, i, r in run("dup_cross_file")]
    check("doublons inter-fichiers (fichiers, ids, lignes) — conservés",
          [("202604-divvy-tripdata.csv + 202605-divvy-tripdata.csv", 35, 70)], cross)
    check("ride_id en conflit (contenu différent)", 0, int(run("ride_id_conflicts")[0][0]))

    log("\n== 5. Cohérence fichier / période ==")
    for csv_name, month, smin, smax, in_m, out_m, end_out in run("month_consistency"):
        exp_rows, exp_min, exp_max, exp_out = EXP_FILES[month]
        check(f"{csv_name} (mois ZIP {month}) min/max started_at vs mission 2",
              (exp_min, exp_max), (smin[:19], smax[:19]))
        check(f"{csv_name} hors mois (started_at) vs mission 2", (exp_rows - exp_out, exp_out),
              (int(in_m), int(out_m)))
        log(f"  info {csv_name} : ended_at hors du mois du fichier = {end_out}")

    log("\n== 6. Provenance et fidélité des valeurs (échantillon ligne à ligne) ==")
    rng = random.Random(20261011)
    files = psql("cyclistic", "SELECT csv_name, csv_data_rows, csv_sha256, zip_name, zip_sha256 "
                 "FROM raw.source_files ORDER BY file_month")
    mism = sampled = quoted_empty = 0
    for csv_name, n, csv_sha, zip_name, zip_sha in files:
        check(f"empreinte {zip_name} inchangée", zip_sha, sha256(os.path.join(ROOT, "data", "raw", zip_name)))
        n = int(n)
        lines = sorted({2, n + 1} | {rng.randint(2, n + 1) for _ in range(20)})
        want = {}
        path = os.path.join(EXT, csv_name)
        with open(path, newline="", encoding="utf-8") as f:
            for lineno, row in enumerate(csv.reader(f), start=1):
                if lineno in lines:
                    want[lineno] = [v if v != "" else None for v in row]
        with open(path, "rb") as f:
            quoted_empty += sum(len(re.findall(rb'(?:^|,)""(?=,|\r?\n|$)', ln)) for ln in f)
        got = psql("cyclistic", f"SELECT source_line, {', '.join(COLS)} FROM raw.trips "
                   f"WHERE source_csv = '{csv_name}' AND source_line IN ({','.join(map(str, lines))}) "
                   "ORDER BY source_line")
        # psql -At affiche NULL comme chaîne vide ; l'équivalence est sûre car la section 3
        # vérifie qu'aucune valeur '' n'existe dans raw.trips.
        for r in got:
            ln = int(r[0])
            db = [v if v != "" else None for v in r[1:]]
            sampled += 1
            if db != want[ln]:
                mism += 1
                log(f"  écart {csv_name}:{ln} fichier={want[ln]} base={db}")
        check(f"empreinte {csv_name} inchangée", csv_sha, sha256(path))
    check(f"lignes échantillonnées identiques au fichier ({sampled} lignes)", 0, mism)
    check("champs vides quotés \"\" dans les CSV (NULL fidèle)", 0, quoted_empty)

    failed = [n for n, ok in results if not ok]
    log(f"\nBILAN : {len(results) - len(failed)}/{len(results)} contrôles OK")
    for n in failed:
        log(f"  ÉCHEC : {n}")
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "reports", "qa_import_output.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
