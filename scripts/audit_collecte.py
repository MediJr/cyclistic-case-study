"""Audit de cohérence de la collecte Cyclistic (lecture seule).

Usage : python -I scripts/audit_collecte.py data/raw data/extracted
Ne modifie aucun fichier ; écrit uniquement le rapport sur la sortie standard.
"""
import collections
import csv
import os
import sys
import zipfile
from datetime import datetime

EXPECTED_COLS = ["ride_id", "rideable_type", "started_at", "ended_at",
                 "start_station_name", "start_station_id", "end_station_name",
                 "end_station_id", "start_lat", "start_lng", "end_lat", "end_lng",
                 "member_casual"]
EXPECTED_MONTHS = ["202510", "202511", "202512", "202601", "202602", "202603",
                   "202604", "202605", "202606", "202607", "202608", "202609"]


def csv_for_zip(raw_dir, month):
    """Nom du CSV contenu dans l'archive du mois (le mois attendu vient du nom du ZIP)."""
    with zipfile.ZipFile(os.path.join(raw_dir, f"{month}-divvy-tripdata.zip")) as zf:
        names = [n for n in zf.namelist()
                 if n.lower().endswith(".csv") and not n.startswith("__MACOSX")]
    assert len(names) == 1, (month, names)
    return names[0]


def main(raw_dir, ext_dir):
    seen = {}                      # ride_id -> premier fichier où il apparaît
    cross = collections.Counter()  # (fichier_a, fichier_b) -> nb d'ids partagés
    cross_examples = []
    total = 0
    print("fichier | mois_attendu | lignes | min started_at | max started_at | "
          "dans_mois | hors_mois | non_parsables | ride_id_vides | ride_id_dupl_intra | "
          "lignes_mal_formées | schéma")
    for month in EXPECTED_MONTHS:
        name = csv_for_zip(raw_dir, month)
        path = os.path.join(ext_dir, name)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            print(f"{name} | MANQUANT OU VIDE")
            continue
        exp = f"{month[:4]}-{month[4:]}"
        rows = in_m = out_m = bad_dt = empty_id = malformed = 0
        out_months = collections.Counter()
        ids = collections.Counter()
        tmin = tmax = None
        with open(path, newline="", encoding="utf-8") as fh:
            r = csv.reader(fh)
            header = next(r)
            schema = "OK" if header == EXPECTED_COLS else f"DIFF {header}"
            i_id, i_st = header.index("ride_id"), header.index("started_at")
            for row in r:
                rows += 1
                if len(row) != len(header):
                    malformed += 1
                    continue
                rid, st = row[i_id].strip(), row[i_st]
                try:
                    dt = datetime.fromisoformat(st)
                except ValueError:
                    bad_dt += 1
                    dt = None
                if dt is not None:
                    tmin = dt if tmin is None or dt < tmin else tmin
                    tmax = dt if tmax is None or dt > tmax else tmax
                    if st[:7] == exp:
                        in_m += 1
                    else:
                        out_m += 1
                        out_months[st[:7]] += 1
                if not rid:
                    empty_id += 1
                    continue
                ids[rid] += 1
        dup_intra = sum(c - 1 for c in ids.values() if c > 1)
        for rid in ids:
            if rid in seen:
                cross[(seen[rid], name)] += 1
                if len(cross_examples) < 5:
                    cross_examples.append((rid, seen[rid], name))
            else:
                seen[rid] = name
        total += rows
        print(f"{name} | {exp} | {rows} | {tmin} | {tmax} | {in_m} | {out_m} "
              f"{dict(out_months)} | {bad_dt} | {empty_id} | {dup_intra} | {malformed} | {schema}")
    print(f"\nTOTAL lignes de données : {total}")
    print(f"ride_id distincts (tous fichiers) : {len(seen)}")
    print(f"ride_id partagés entre fichiers : {sum(cross.values())} {dict(cross)}")
    for ex in cross_examples:
        print("  exemple :", ex)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
