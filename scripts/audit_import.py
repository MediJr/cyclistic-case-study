"""Audit de l'import brut (mission 4.1) — LECTURE SEULE.

Usage : python -I scripts/audit_import.py
- La session PostgreSQL est forcée en lecture seule (default_transaction_read_only=on) :
  toute écriture serait refusée par le serveur.
- Recalcule côté fichiers (Python) une empreinte exhaustive par CSV et la compare à celle
  calculée côté base sur les 6 171 785 lignes ; compte aussi les champs vides des fichiers.
- Écrit les résultats bruts dans reports/audit_import_output.txt (aucune donnée personnelle :
  identifiants anonymes de trajets et horodatages uniquement).
"""
import collections
import csv
import hashlib
import os
import re
import sys

os.environ["PGOPTIONS"] = "-c default_transaction_read_only=on"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pg import psql  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "data", "extracted")
COLS = ["ride_id", "rideable_type", "started_at", "ended_at", "start_station_name",
        "start_station_id", "end_station_name", "end_station_id", "start_lat",
        "start_lng", "end_lat", "end_lng", "member_casual"]
out = []


def log(s=""):
    print(s)
    out.append(str(s))


def section(title, rows):
    log(f"\n## {title}")
    for r in rows:
        log("  " + " | ".join(r))


def main():
    text = open(os.path.join(ROOT, "sql", "audit_import.sql"), encoding="utf-8").read()
    blocks = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    Q = {blocks[i]: blocks[i + 1] for i in range(1, len(blocks), 2)}

    ro = psql("cyclistic", "SHOW default_transaction_read_only")[0][0]
    log(f"session lecture seule (default_transaction_read_only) = {ro}")
    if ro != "on":
        sys.exit("ARRÊT : la session n'est pas en lecture seule.")

    db_fp = {}
    for name in Q:
        rows = psql("cyclistic", Q[name])
        if name == "fingerprint":
            db_fp = {r[0]: (int(r[1]), int(r[2])) for r in rows}
        section(name, rows)

    log("\n## fichiers : empreinte exhaustive, champs vides, lignes physiques")
    files = psql("cyclistic", "SELECT csv_name FROM raw.source_files ORDER BY file_month")
    empties = collections.Counter()
    all_ok = True
    for (csv_name,) in files:
        n = s = multiline = 0
        with open(os.path.join(EXT, csv_name), newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            next(r)
            for rec_no, row in enumerate(r, start=2):
                if r.line_num != rec_no:      # un champ sur plusieurs lignes décalerait la numérotation
                    multiline += 1
                vals = [v if v != "" else "\\N" for v in row]
                for c, v in zip(COLS, row):
                    if v == "":
                        empties[c] += 1
                key = f"{rec_no}\x1f" + "\x1f".join(vals)
                s += int(hashlib.md5(key.encode("utf-8")).hexdigest()[:15], 16)
                n += 1
        ok = db_fp.get(csv_name) == (n, s)
        all_ok &= ok
        log(f"  {csv_name} | fichier n={n} somme={s} | base={db_fp.get(csv_name)} | "
            f"{'IDENTIQUE' if ok else 'DIFFÉRENT'} | décalages de ligne physique={multiline}")
    log(f"  EMPREINTES EXHAUSTIVES : {'toutes identiques' if all_ok else 'ÉCART'}")
    log("  champs vides dans les fichiers (csv.reader, quotés ou non) : "
        + ", ".join(f"{c}={empties[c]}" for c in COLS))

    with open(os.path.join(ROOT, "reports", "audit_import_output.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
