"""Contrôles qualité après nettoyage (C4) — LECTURE SEULE.

Usage : python -I scripts/run_qa_clean.py [--rules ...] [--expected ...] [--data-dir data] [--out-dir ...]
- Session PostgreSQL forcée en lecture seule ; aucune écriture en base.
- Résultats : <out-dir>/qa_results.csv + listes S1–S5, et journal reports/logs/qa_nettoyage_*.log.
- Statuts : OK, ÉCHEC (bloquant), INFO, ANOMALIE_CONNUE, NON_APPLICABLE. Code de sortie 1 si au moins un ÉCHEC.
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

SQL = os.path.join(cl.ROOT, "sql", "03_qa_clean.sql")


class QA:
    def __init__(self):
        self.rows = []

    def add(self, cid, label, expected, measured, status=None):
        if status is None:
            status = "OK" if expected == measured else "ÉCHEC"
        self.rows.append((cid, label, str(expected), str(measured), status))
        print(f"[{status:<15}] {cid:<5} {label} : attendu={expected} mesuré={measured}")

    @property
    def failed(self):
        return [r for r in self.rows if r[4] == "ÉCHEC"]


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main(argv=None):
    cl.utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default=cl.RULES_PATH)
    ap.add_argument("--expected", default=cl.EXPECTED_PATH)
    ap.add_argument("--data-dir", default=os.path.join(cl.ROOT, "data"))
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--db", default=cl.DB)
    a = ap.parse_args(argv)
    out = a.out_dir or os.path.join(cl.REPORTS, "qa_clean", dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out, exist_ok=True)

    rules, exp = cl.load_json(a.rules), cl.load_json(a.expected)
    variables = cl.rules_variables(rules)
    blocks = cl.load_blocks(SQL)

    def q(name):
        return psql(a.db, blocks[name], read_only=True, variables=variables, label=name)

    files = [SQL, a.rules, a.expected, __file__, os.path.join(cl.ROOT, "scripts", "cleanlib.py"),
             os.path.join(cl.ROOT, "scripts", "pg.py")]
    with RunLog("qa_nettoyage", files=files):
        qa = QA()
        ro = psql(a.db, "SHOW default_transaction_read_only", read_only=True)[0][0]
        qa.add("RO", "session en lecture seule", "on", ro)

        # Q1 — sources et raw intacts
        problems = cl.check_sources(q("source_files"), a.data_dir)
        qa.add("Q1a", "SHA-256 des fichiers sources = raw.source_files", [], problems)
        ok, got, ref = cl.fingerprint_matches(q("raw_fingerprint"), exp["raw_fingerprint"])
        qa.add("Q1b", "empreinte exhaustive de raw.trips = référence audit 4.1", "identique", "identique" if ok else got)

        # Q2, Q3 — réconciliation
        r, k, e = map(int, q("counts")[0])
        qa.add("Q2", "raw = clean + exclusions", (exp["raw_rows"], exp["kept"], sum(exp["excluded"].values())), (r, k, e))
        qa.add("Q2b", "raw − clean − exclusions", 0, r - k - e)
        orph, both = map(int, q("orphans_and_overlaps")[0])
        qa.add("Q3", "lignes brutes sans état / dans deux états", (0, 0), (orph, both))

        # Q4–Q7 — période et mois
        mn, mx, outp = q("period")[0]
        qa.add("Q4", "lignes hors période dans clean", 0, int(outp))
        qa.add("Q4b", "min/max started_at dans la période",
               True, mn >= rules["period"]["start_inclusive"][:10] and mx < rules["period"]["end_exclusive"][:10])
        qa.add("Q5", "conservés par mois", exp["kept_by_month"], {m: int(n) for m, n in q("months")})
        qa.add("Q5b", "conservés par type d'usager", exp["kept_by_member"], {m: int(n) for m, n in q("members")})
        qa.add("Q6", "ride_month ≠ date_trunc(started_at)", 0, int(q("month_consistency")[0][0]))
        jan25, months_202501, fm = (q("file_202501")[0] + ["", "", ""])[:3]
        if fm:
            qa.add("Q7", "CSV 202501 : file_month / trajets en 2025-01 / mois attribués ⊆ {2025-12, 2026-01}",
                   ("2026-01", 0, True), (fm, int(jan25), set(months_202501.split(",")) <= {"2025-12", "2026-01"}))
        else:
            qa.add("Q7", "CSV 202501", "—", "absent de raw.source_files", "NON_APPLICABLE")

        # Q8, Q9 — unicité et motifs
        n, nd = map(int, q("uniqueness")[0])
        qa.add("Q8", "ride_id uniques dans clean", n, nd)
        reasons = {rr[0]: int(rr[1]) for rr in q("reasons")}
        multi = sum(int(rr[2]) for rr in q("reasons"))
        qa.add("Q9", "exclusions par motif", exp["excluded"], reasons)
        qa.add("Q9b", "lignes exclues remplissant plusieurs critères (motifs disjoints attendus)", 0, multi,
               "OK" if multi == 0 else "INFO")

        # Q10–Q13 — horodatages, champs dérivés, changements d'heure, durées
        v1, v2 = map(int, q("q10_timestamps")[0])
        qa.add("Q10", "horodatages clean ≠ raw (comparaison de valeurs)", 0, v1)
        qa.add("Q10b", "format AAAA-MM-JJ HH24:MI:SS.MS ≠ texte source", 0, v2)
        d1, d2, dow = map(int, q("q11_derived")[0])
        qa.add("Q11", "durées / jour / heure recalculés différents", (0, 0), (d1, d2))
        qa.add("Q11b", "2025-10-05 (dimanche) → day_of_week", 1, dow)
        fb, sf, corr, nconf, corr_nospan, corr_fb, incons = map(int, q("q12_dst")[0])
        fl = exp["flags"]
        qa.add("Q12", "indicateurs d'heure d'automne / d'heure d'été",
               (fl["dst_fall_back_overlap"], fl["dst_spring_forward_span"]), (fb, sf))
        qa.add("Q12b", "corrigés + non confirmés = trajets enjambant l'heure sautée", sf, corr + nconf)
        qa.add("Q12c", "corrections hors heure sautée / le 02/11/2025 / statut incohérent", (0, 0, 0), (corr_nospan, corr_fb, incons))
        qa.add("Q12d", "trajets corrigés (heure d'été)", "≤ " + str(sf), corr, "INFO")
        mind, u_neg, n_pos, zero = q("q13_durations")[0]
        qa.add("Q13", "durée minimale dans clean ≥ seuil", True, float(mind) >= rules["min_duration_sec"])
        qa.add("Q13b", "motifs incohérents avec le signe de la durée", (0, 0), (int(u_neg), int(n_pos)))
        qa.add("Q13c", "durées nulles exclues (dans under_60s)", "—", int(zero), "INFO")

        # Q14–Q16 — indicateurs et sous-ensembles
        noend, over24, smiss, emiss, maxd = q("flags")[0]
        qa.add("Q14", "trajets sans arrivée conservés", fl["has_end_location_false"], int(noend))
        qa.add("Q16", "trajets > 24 h conservés", fl["is_over_24h"], int(over24))
        qa.add("Q16b", "durée maximale ≤ référence", True, float(maxd) <= exp["max_ride_length_sec_at_most"])
        qa.add("Q17a", "stations manquantes départ / arrivée", (fl["start_station_missing"], fl["end_station_missing"]),
               (int(smiss), int(emiss)))
        subsets = {s: int(c) for s, c in q("subsets")}
        sens1 = subsets.pop("v_sens1_population")
        qa.add("Q15", "effectifs des vues d'analyse", exp["subsets"], subsets)
        qa.add("Q15b", "population SENS-1 = conservés + under_60s", exp["kept"] + exp["excluded"]["under_60s"], sens1)

        # Q17, Q20 — stations
        q17 = tuple(map(int, q("q17_stations")[0]))
        qa.add("Q17", "'' / paires nom-ID / clean ≠ btrim(raw, ' ')", (0, 0, 0), q17)
        nz = exp["normalization"]
        log_rows = {rr[0]: rr for rr in q("q20_log")}
        for col, raw_sp, flags, left, dbl_clean, dbl_raw in q("q20_trim"):
            raw_sp, flags, left, dbl_clean, dbl_raw = map(int, (raw_sp, flags, left, dbl_clean, dbl_raw))
            qa.add("Q20", f"{col} : indicateurs = valeurs brutes avec espace en bordure", raw_sp, flags)
            qa.add("Q20", f"{col} : espaces en bordure restants", 0, left)
            qa.add("Q20", f"{col} : espaces doubles internes préservés", dbl_raw, dbl_clean)
            qa.add("Q20", f"{col} : lignes normalisées ≤ référence brute", True, flags <= nz["max_trimmed_rows_raw"][col])
            lr = log_rows.get(col)
            n_vals, n_rows_log = (int(lr[1]), int(lr[2])) if lr else (0, 0)
            merges = set(lr[3].split(" | ")) if lr and lr[3] else set()
            qa.add("Q20", f"{col} : journal (lignes) = indicateurs", flags, n_rows_log)
            qa.add("Q20", f"{col} : valeurs distinctes normalisées ≤ référence", True,
                   n_vals <= nz["max_distinct_trimmed_values_raw"][col])
            qa.add("Q20", f"{col} : fusions ⊆ fusions attendues", True, merges <= set(nz["allowed_merges"][col]))

        # Q19 — journal des étapes
        steps = [tuple(map(int, rr)) for rr in q("q19_transform_log")]
        chain = all(steps[i][3] == steps[i + 1][1] and steps[i + 1][1] - steps[i + 1][2] == steps[i + 1][3]
                    for i in range(len(steps) - 1))
        qa.add("Q19", "journal des étapes chaîné et final = clean", (True, k), (chain, steps[-1][3] if steps else None))

        # Q21 — anomalie connue
        q21 = int(q("q21_march_april")[0][0])
        known = exp["known_anomalies"]["march_april_crossings"]
        qa.add("Q21", "trajets de mars terminés en avril (anomalie connue F14)", known, q21,
               "ANOMALIE_CONNUE" if q21 == known else "INFO")

        # Q22 — provenance du dédoublonnage
        nd_, from_, kept_, md5diff, kept_missing = (q("q22_dedup")[0] + [""] * 5)[:5]
        dd = exp["duplicates"]
        qa.add("Q22", "doublons exclus / fichier exclu / fichier gardé / contenus différents / ligne gardée absente",
               (exp["excluded"]["duplicate_ride_id"], dd["excluded_from"], dd["kept_from"], 0, 0),
               (int(nd_), from_, kept_, int(md5diff or 0), int(kept_missing or 0)))

        # S1–S6 — stations (rapports ; seuls S6 est bloquant)
        ref = exp["reference_info_raw_rows"]
        for side, n_ids, n_multi, n_triv in q("s1_summary"):
            qa.add("S1", f"{side} : ID à plusieurs noms (dont triviaux) — référence lignes brutes",
                   ref["S1_ids_with_several_names"][side], f"{n_multi} ({n_triv} triviaux) sur {n_ids} ID", "INFO")
        for side, n in q("s2_summary"):
            qa.add("S2", f"{side} : noms à plusieurs ID — référence lignes brutes",
                   ref["S2_names_with_several_ids"][side], int(n), "INFO")
        s3 = q("s3_spatial")
        span_flag = sum(1 for rr in s3 if float(rr[2]) > 0.005)
        p95_100 = sum(1 for rr in s3 if float(rr[3]) > 100)
        p95_250 = sum(1 for rr in s3 if float(rr[3]) > 250)
        qa.add("S3", "ID (vélos classiques) : étendue > 0,005° / p95 > 100 m / p95 > 250 m (repères indicatifs)",
               "—", (span_flag, p95_100, p95_250), "INFO")
        s5 = q("s5_staff_test")
        qa.add("S5", "lignes conservées touchant une station « interne » (aucune exclusion)",
               ref["S5_staff_or_test_rows_kept"], int(q("s5_rows")[0][0]), "INFO")
        s6 = tuple(map(int, q("s6_presence")[0]))
        qa.add("S6", "nom NULL ⇔ ID NULL / ID vide", (0, 0), s6)

        run = q("run")
        qa.add("RUN", "exécution enregistrée dans audit.run", 1, len(run), None)

        write_csv(os.path.join(out, "qa_results.csv"), ["controle", "libelle", "attendu", "mesure", "statut"], qa.rows)
        write_csv(os.path.join(out, "s1_id_plusieurs_noms.csv"), ["cote", "id", "nom", "lignes"], q("s1_list"))
        write_csv(os.path.join(out, "s2_nom_plusieurs_id.csv"), ["cote", "nom", "id", "lignes"], q("s2_list"))
        write_csv(os.path.join(out, "s3_dispersion_id.csv"), ["id", "n_classiques", "etendue_deg", "p95_m", "max_m"], s3)
        write_csv(os.path.join(out, "s4_noms_par_mois.csv"), ["cote", "id", "mois", "nom", "lignes"], q("s4_names_by_month"))
        write_csv(os.path.join(out, "s5_stations_internes_agrege.csv"), ["id", "nom", "occurrences"], s5)

        print(f"\nBILAN : {len(qa.rows)} contrôles — {len(qa.failed)} ÉCHEC — résultats dans {out}")
        if qa.failed:
            sys.exit(1)


if __name__ == "__main__":
    main()
