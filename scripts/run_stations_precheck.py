"""Contrôles de stations S1–S6 et examen des trajets du 08/03/2026 AVANT nettoyage — LECTURE SEULE.

Usage : python -I scripts/run_stations_precheck.py
- Session PostgreSQL forcée en lecture seule ; une seule requête SELECT (sql/05_stations_precontrole.sql).
- Aucune correction de durée n'est appliquée : les critères de l'heure d'été sont seulement évalués.
- Sorties : reports/stations_precheck/<horodatage>/ (CSV) + journal reports/logs/controles_stations_*.log.
- S5 est publié sous forme agrégée (aucun détail ligne à ligne).
"""
import collections
import csv
import datetime as dt
import os
import re
import statistics
from decimal import Decimal
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cleanlib as cl  # noqa: E402
from pg import psql  # noqa: E402
from runlog import RunLog  # noqa: E402

SQL = os.path.join(cl.ROOT, "sql", "05_stations_precontrole.sql")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    cl.utf8_console()
    rules, exp = cl.load_json(cl.RULES_PATH), cl.load_json(cl.EXPECTED_PATH)
    out = os.path.join(cl.REPORTS, "stations_precheck", dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out, exist_ok=True)
    with RunLog("controles_stations", files=[SQL, __file__, cl.RULES_PATH, cl.EXPECTED_PATH,
                                             os.path.join(cl.ROOT, "scripts", "pg.py")]) as log:
        ro = psql(cl.DB, "SHOW default_transaction_read_only", read_only=True)[0][0]
        log.info(f"session lecture seule = {ro}")
        if ro != "on":
            sys.exit("ARRÊT : session non en lecture seule")
        rows = psql(cl.DB, cl.load_blocks(SQL)["stations_precheck"], read_only=True,
                    variables=cl.rules_variables(rules), label="stations_precheck")
        by = collections.defaultdict(list)
        for r in rows:
            by[r[0]].append(r[1:])

        total = int(by["total"][0][0])
        ok_total = total == exp["kept"]
        log.info(f"AUTOCONTRÔLE population conservée reconstituée = {total} (attendu {exp['kept']}) : "
                 f"{'OK' if ok_total else 'ÉCHEC'}")

        # S1, S2, S4 à partir des agrégats (côté, ID, nom, mois, lignes)
        agg = [(s, i, n, m, int(c)) for s, i, n, m, c, *_ in by["agg"]]
        names = collections.defaultdict(collections.Counter)
        ids = collections.defaultdict(collections.Counter)
        for s, i, n, m, c in agg:
            names[(s, i)][n] += c
            ids[(s, n)][i] += c
        s1 = [(s, i, n, c) for (s, i), ns in sorted(names.items()) if len(ns) > 1 for n, c in ns.most_common()]
        s2 = [(s, n, i, c) for (s, n), is_ in sorted(ids.items()) if len(is_) > 1 for i, c in is_.most_common()]
        multi_ids = {k for k, ns in names.items() if len(ns) > 1}
        s4 = sorted((s, i, m, n, c) for s, i, n, m, c in agg if (s, i) in multi_ids)
        for side in ("start", "end"):
            multi = [ns for (s, _), ns in names.items() if s == side and len(ns) > 1]
            triv = sum(1 for ns in multi if len({norm(n) for n in ns}) == 1)
            nmi = sum(1 for (s, _), is_ in ids.items() if s == side and len(is_) > 1)
            n_ids = sum(1 for (s, _) in names if s == side)
            log.info(f"S1 {side} : {len(multi)} ID à plusieurs noms dont {triv} triviaux, sur {n_ids} ID "
                     f"(référence lignes brutes : {exp['reference_info_raw_rows']['S1_ids_with_several_names'][side]})")
            log.info(f"S2 {side} : {nmi} noms à plusieurs ID "
                     f"(référence lignes brutes : {exp['reference_info_raw_rows']['S2_names_with_several_ids'][side]})")

        # S3 dispersion
        s3 = sorted(by["s3"], key=lambda r: -float(r[3]))
        s3 = [r[:5] for r in s3]
        log.info("S3 ID (vélos classiques) : étendue > 0,005° = %d ; p95 > 100 m = %d ; p95 > 250 m = %d ; sur %d ID"
                 % (sum(float(r[2]) > 0.005 for r in s3), sum(float(r[3]) > 100 for r in s3),
                    sum(float(r[3]) > 250 for r in s3), len(s3)))

        # S5 agrégé
        pat = re.compile(rules["staff_or_test_stations"]["name_pattern"], re.I)
        s5 = collections.Counter()
        for s, i, n, m, c in agg:
            if pat.search(n):
                s5[(s, i, n)] += c
        log.info(f"S5 occurrences (départ + arrivée) de stations « internes » : {sum(s5.values())} "
                 f"(aucune exclusion ; référence lignes conservées : {exp['reference_info_raw_rows']['S5_staff_or_test_rows_kept']})")

        # S6
        pair_bad, empty, bordered, s_missing, e_missing = map(int, by["s6"][0][:5])
        log.info(f"S6 paires nom/ID incohérentes = {pair_bad} ; valeurs vides après btrim = {empty} "
                 f"(attendu 0 / 0) — {'OK' if (pair_bad, empty) == (0, 0) else 'ÉCHEC'}")
        log.info(f"   lignes conservées avec au moins un espace en bordure = {bordered} ; "
                 f"stations manquantes départ/arrivée = {s_missing}/{e_missing} "
                 f"(attendu {exp['flags']['start_station_missing']}/{exp['flags']['end_station_missing']})")

        # Heure d'été du 08/03/2026 : critères individuels, AUCUNE correction appliquée
        dst = [r[:10] for r in by["dst"]]
        n = len(dst)
        conf = [r for r in dst if r[7] == "true"]
        gap = sum(r[5] == "true" for r in dst)
        tz_ok = sum(Decimal(r[6]) == Decimal(r[4]) - 3600 for r in dst)  # décimales exactes (pas de flottants)
        nonneg = sum(Decimal(r[4]) - 3600 >= 0 for r in dst)
        log.info(f"DST 08/03 : critère 1 (enjambe 02:00–03:00) = {n} (attendu {exp['flags']['dst_spring_forward_span']}) ; "
                 f"critère 2 (aucun horodatage dans l'heure inexistante) = {n - gap} ; critère 3 (durée fuseau = brute − 3600) = {tz_ok} ; "
                 f"critère 4 (corrigée ≥ 0) = {nonneg} ; confirmés (2+3+4) = {len(conf)}")
        raw = [float(r[4]) for r in dst]
        adj = [float(r[4]) - 3600 if r[7] == "true" else float(r[4]) for r in dst]
        if raw:
            log.info(f"   sensibilité (non appliquée) : médiane brute {statistics.median(raw):.0f} s → corrigée "
                     f"{statistics.median(adj):.0f} s ; moyenne {statistics.mean(raw):.0f} → {statistics.mean(adj):.0f} s ; "
                     f"corrigées < 60 s : {sum(a < 60 for a in adj)} ; > 24 h brutes : {sum(x > 86400 for x in raw)}")
            for mc in ("member", "casual"):
                sub = [(x, y) for x, y, r in zip(raw, adj, dst) if r[8] == mc]
                if sub:
                    log.info(f"   {mc} : n={len(sub)} médiane {statistics.median([x for x, _ in sub]):.0f} → "
                             f"{statistics.median([y for _, y in sub]):.0f} s")

        write(os.path.join(out, "s1_id_plusieurs_noms.csv"), ["cote", "id", "nom", "lignes"], s1)
        write(os.path.join(out, "s2_nom_plusieurs_id.csv"), ["cote", "nom", "id", "lignes"], s2)
        write(os.path.join(out, "s3_dispersion_id.csv"), ["id", "n_classiques", "etendue_deg", "p95_m", "max_m"], s3)
        write(os.path.join(out, "s4_noms_par_mois.csv"), ["cote", "id", "mois", "nom", "lignes"], s4)
        write(os.path.join(out, "s5_stations_internes_agrege.csv"), ["cote", "id", "nom", "occurrences"],
              [(*k, c) for k, c in s5.most_common()])
        write(os.path.join(out, "s6_presence.csv"), ["paires_incoherentes", "vides_apres_btrim", "lignes_espace_bordure",
                                                     "depart_manquant", "arrivee_manquante"], [by["s6"][0][:5]])
        write(os.path.join(out, "dst_2026-03-08_criteres.csv"),
              ["source_csv", "source_line", "started_at", "ended_at", "duree_brute_s", "horodatage_dans_heure_inexistante",
               "duree_fuseau_s", "correction_confirmee", "member_casual", "rideable_type"], dst)
        log.info(f"Résultats : {out}")
        if not ok_total or (pair_bad, empty) != (0, 0):
            sys.exit(1)


if __name__ == "__main__":
    main()
