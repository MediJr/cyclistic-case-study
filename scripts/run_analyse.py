"""Phase Analyze — extraction des agrégats depuis clean.trips (LECTURE SEULE).

Usage : python -I scripts/run_analyse.py [--out-dir results/analysis]
- Session PostgreSQL forcée en lecture seule ; requêtes de sql/10_analyse.sql.
- Un CSV par requête ; contrôles de cohérence immédiats (totaux, pourcentages) ; journal
  reports/logs/analyse_*.log. Aucune écriture en base.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cleanlib as cl  # noqa: E402
from pg import psql  # noqa: E402
from runlog import RunLog  # noqa: E402

SQL = os.path.join(cl.ROOT, "sql", "10_analyse.sql")
HEADERS = {
    "a00_controle": ["trajets", "member", "casual", "premier_depart", "dernier_depart", "mois"],
    "a01_usagers": ["member_casual", "trajets", "part_pct", "moyenne_min", "mediane_min", "p25_min", "p75_min",
                    "p90_min", "p99_min", "ecart_type_min", "trajets_plus_24h", "part_30min_plus_pct",
                    "moyenne_min_dst_corrigee", "mediane_min_dst_corrigee"],
    "a02_durees_tranches": ["member_casual", "tranche", "trajets", "part_pct"],
    "a03_jour": ["member_casual", "day_of_week", "trajets", "part_pct", "mediane_min", "moyenne_min"],
    "a04_mois": ["mois", "member_casual", "trajets", "part_du_mois_pct", "mediane_min", "moyenne_min"],
    "a05_heure": ["member_casual", "type_jour", "heure", "trajets", "part_pct"],
    "a06_velo": ["member_casual", "rideable_type", "trajets", "part_pct", "mediane_min", "moyenne_min"],
    "a07_interactions": ["member_casual", "rideable_type", "type_jour", "trajets", "part_pct", "mediane_min",
                         "p75_min", "moyenne_min"],
    "a08_boucles": ["member_casual", "trajets", "trajets_avec_2_stations", "trajets_boucle", "part_boucle_pct",
                    "mediane_boucle_min"],
    "a09_contexte": ["member_casual", "trajets", "depart_sans_station_pct", "arrivee_sans_station_pct",
                     "sans_coord_arrivee_pct", "plus_24h_pct", "corrections_dst", "chevauchement_heure_automne"],
    "a10_jours": ["date", "member_casual", "trajets"],
    "a11_jour_heure": ["member_casual", "day_of_week", "heure", "trajets"],
}


def main(argv=None):
    cl.utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=os.path.join(cl.ROOT, "results", "analysis"))
    ap.add_argument("--db", default=cl.DB)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    blocks = cl.load_blocks(SQL)
    with RunLog("analyse", files=[SQL, __file__, os.path.join(cl.ROOT, "scripts", "pg.py")]) as log:
        ro = psql(a.db, "SHOW default_transaction_read_only", read_only=True)[0][0]
        if ro != "on":
            sys.exit("ARRÊT : session non en lecture seule")
        res = {}
        for name, header in HEADERS.items():
            rows = psql(a.db, blocks[name], read_only=True, label=name)
            res[name] = rows
            with open(os.path.join(a.out_dir, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(rows)

        # Contrôles de cohérence (totaux et pourcentages)
        total, mem, cas = (int(x) for x in res["a00_controle"][0][:3])
        checks = [("total = member + casual", total == mem + cas)]
        for name, idx_n in (("a02_durees_tranches", 2), ("a03_jour", 2), ("a06_velo", 2), ("a07_interactions", 3),
                            ("a05_heure", 3), ("a11_jour_heure", 3)):
            checks.append((f"{name} : somme des trajets = total", sum(int(r[idx_n]) for r in res[name]) == total))
        for name, idx_n in (("a04_mois", 2), ("a10_jours", 2)):
            checks.append((f"{name} : somme des trajets = total", sum(int(r[idx_n]) for r in res[name]) == total))
        for name, key, pct in (("a02_durees_tranches", 0, 3), ("a03_jour", 0, 3), ("a06_velo", 0, 3), ("a07_interactions", 0, 4)):
            sums = {}
            for r in res[name]:
                sums[r[key]] = sums.get(r[key], 0) + float(r[pct])
            checks.append((f"{name} : pourcentages par usager ≈ 100", all(abs(s - 100) < 0.1 for s in sums.values())))
        u = {r[0]: r for r in res["a01_usagers"]}
        checks.append(("a01 : trajets member/casual = contrôle", (int(u["member"][1]), int(u["casual"][1])) == (mem, cas)))
        checks.append(("a08 : trajets = contrôle", sum(int(r[1]) for r in res["a08_boucles"]) == total))
        for label, ok in checks:
            log.info(f"[{'OK' if ok else 'ÉCHEC'}] {label}")
        log.info(f"trajets={total} member={mem} casual={cas} période={res['a00_controle'][0][3]} → {res['a00_controle'][0][4]}")
        log.info(f"CSV écrits dans {a.out_dir}")
        if not all(ok for _, ok in checks):
            sys.exit(1)


if __name__ == "__main__":
    main()
