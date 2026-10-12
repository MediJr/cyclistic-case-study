"""Analyses de sensibilité SENS-1 et SENS-2 (C5) — LECTURE SEULE.

Usage : python -I scripts/run_sensitivity.py [--out-dir ...]
Écrit des CSV (pas de verdict automatique) : l'interprétation est faite dans reports/anomalies.md.
SENS-1 : écarts entre A (principale) et B (+ positifs < 60 s) par type de vélo × type d'usager.
SENS-2 : écarts avec / sans les 31/03 et 01/04/2026.
"""
import argparse
import csv
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cleanlib as cl  # noqa: E402
from pg import psql  # noqa: E402
from runlog import RunLog  # noqa: E402

SQL = os.path.join(cl.ROOT, "sql", "04_sensitivity.sql")
HEADERS = {
    "sens1_summary": ["population", "rideable_type", "member_casual", "trajets", "mediane_s", "moyenne_s", "p95_s", "dont_moins_60s"],
    "sens1_dow": ["population", "rideable_type", "member_casual", "day_of_week", "trajets"],
    "sens1_hour": ["population", "rideable_type", "member_casual", "heure", "trajets"],
    "sens2_summary": ["population", "member_casual", "trajets", "mediane_s", "moyenne_s"],
    "sens2_hour": ["population", "member_casual", "heure", "trajets"],
}


def main(argv=None):
    cl.utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--db", default=cl.DB)
    a = ap.parse_args(argv)
    out = a.out_dir or os.path.join(cl.REPORTS, "sensitivity", dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out, exist_ok=True)
    blocks = cl.load_blocks(SQL)
    with RunLog("sensibilite", files=[SQL, __file__, os.path.join(cl.ROOT, "scripts", "pg.py")]):
        results = {}
        for name, header in HEADERS.items():
            rows = psql(a.db, blocks[name], read_only=True, label=name)
            results[name] = rows
            with open(os.path.join(out, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(rows)
            print(f"{name}: {len(rows)} lignes")
        # Tableau d'écarts SENS-1 : A contre B pour chaque (type de vélo, type d'usager)
        s = {(r[0], r[1], r[2]): r for r in results["sens1_summary"]}
        deltas = []
        for (scope, rt, mc), ra in sorted(s.items()):
            if scope != "A_principale":
                continue
            rb = s.get(("B_avec_moins_60s", rt, mc))
            if rb:
                deltas.append([rt, mc, ra[3], rb[3], int(rb[3]) - int(ra[3]),
                               ra[4], rb[4], round(float(rb[4]) - float(ra[4]), 1),
                               ra[5], rb[5], round(float(rb[5]) - float(ra[5]), 1)])
        with open(os.path.join(out, "sens1_ecarts.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["rideable_type", "member_casual", "n_A", "n_B", "ecart_n", "mediane_A", "mediane_B",
                        "ecart_mediane_s", "moyenne_A", "moyenne_B", "ecart_moyenne_s"])
            w.writerows(deltas)
        for d in deltas:
            print("SENS-1", d)
        print(f"Résultats dans {out}")


if __name__ == "__main__":
    main()
