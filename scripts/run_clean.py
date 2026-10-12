"""Orchestrateur du nettoyage Cyclistic (plan v3.2).

Usage :
  python -I scripts/run_clean.py                         # PRÉ-CONTRÔLE SEUL (lecture seule, défaut)
  python -I scripts/run_clean.py --execute --confirm v3.2  # exécution réelle (après autorisation)

Pré-contrôles (toujours, en session lecture seule) :
  schémas clean/audit absents ; nombre de lignes de raw.trips ; SHA-256 des 24 fichiers sources
  = raw.source_files ; empreinte exhaustive de raw.trips = audit 4.1 ; aucun ride_id en conflit
  (liste écrite dans reports/logs/ le cas échéant) ; version des règles cohérente.
Exécution (--execute --confirm <version>) :
  sql/02_clean.sql en UNE transaction ; puis empreinte de raw.trips recontrôlée ; puis
  contrôles qualité (run_qa_clean.py) et sensibilités (run_sensitivity.py), en lecture seule.
Refus : toute anomalie de pré-contrôle, ou schéma clean/audit déjà présent (seconde exécution).
"""
import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cleanlib as cl  # noqa: E402
from pg import psql  # noqa: E402
from runlog import RunLog  # noqa: E402

CLEAN_SQL = os.path.join(cl.ROOT, "sql", "02_clean.sql")
QA_SQL = os.path.join(cl.ROOT, "sql", "03_qa_clean.sql")
TRACKED = ["sql/02_clean.sql", "sql/03_qa_clean.sql", "sql/04_sensitivity.sql", "sql/01_create_raw.sql",
           "scripts/run_clean.py", "scripts/run_qa_clean.py", "scripts/run_sensitivity.py",
           "scripts/cleanlib.py", "scripts/pg.py", "scripts/runlog.py"]


class Refused(Exception):
    pass


def preflight(db, rules, exp, data_dir, blocks, log_dir):
    res = {}

    def q(name):
        return psql(db, blocks[name], read_only=True, label=f"preflight:{name}")

    ro = psql(db, "SHOW default_transaction_read_only", read_only=True)[0][0]
    if ro != "on":
        raise Refused("la session de pré-contrôle n'est pas en lecture seule")
    if rules["rules_version"] != exp["rules_version"]:
        raise Refused(f"versions incohérentes : règles {rules['rules_version']} / attendus {exp['rules_version']}")
    plan = os.path.join(cl.ROOT, rules["plan_document"])
    if not os.path.isfile(plan):
        raise Refused(f"document du plan introuvable : {plan}")

    clean_exists, audit_exists = (v == "t" for v in q("preflight_schemas")[0])
    res["schemas_absent"] = not (clean_exists or audit_exists)
    if not res["schemas_absent"]:
        raise Refused("schéma clean ou audit déjà présent : seconde exécution refusée (voir procédure de retour arrière)")

    n = int(q("preflight_raw_rows")[0][0])
    res["raw_rows"] = n
    if n != exp["raw_rows"]:
        raise Refused(f"raw.trips contient {n} lignes, {exp['raw_rows']} attendues")

    problems = cl.check_sources(q("source_files"), data_dir)
    res["sources_sha256_ok"] = not problems
    if problems:
        raise Refused("fichiers sources : " + "; ".join(problems))

    ok, got, _ = cl.fingerprint_matches(q("raw_fingerprint"), exp["raw_fingerprint"])
    res["raw_fingerprint_ok"] = ok
    if not ok:
        raise Refused(f"empreinte exhaustive de raw.trips différente de la référence : {got}")

    conflicts = q("preflight_conflicts")
    res["ride_id_conflicts"] = len(conflicts)
    if conflicts:
        path = os.path.join(log_dir, f"conflits_ride_id_{dt.datetime.now():%Y%m%d-%H%M%S}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([["ride_id", "lignes"]] + conflicts)
        raise Refused(f"{len(conflicts)} ride_id en conflit (R2.1) — liste : {path}")
    res["checked_at"] = dt.datetime.now().astimezone().isoformat()
    return res


def main(argv=None):
    cl.utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="exécuter réellement le nettoyage (écrit dans la base)")
    ap.add_argument("--confirm", default=None, help="version des règles à confirmer (ex. v3.2), obligatoire avec --execute")
    ap.add_argument("--rules", default=cl.RULES_PATH)
    ap.add_argument("--expected", default=cl.EXPECTED_PATH)
    ap.add_argument("--data-dir", default=os.path.join(cl.ROOT, "data"))
    ap.add_argument("--db", default=cl.DB)
    ap.add_argument("--skip-followups", action="store_true", help="ne pas lancer QA et sensibilités après exécution")
    a = ap.parse_args(argv)

    rules, exp = cl.load_json(a.rules), cl.load_json(a.expected)
    blocks = cl.load_blocks(QA_SQL)
    files = TRACKED + [os.path.relpath(a.rules, cl.ROOT), os.path.relpath(a.expected, cl.ROOT), rules["plan_document"]]
    step = "nettoyage_execution" if a.execute else "nettoyage_precontrole"
    executed = False
    with RunLog(step, files=files) as log:
        log.info(f"base={a.db} règles={rules['rules_version']} mode={'EXÉCUTION' if a.execute else 'pré-contrôle seul'}")
        if a.execute and a.confirm != rules["rules_version"]:
            raise Refused(f"--confirm {rules['rules_version']} est obligatoire avec --execute")
        pre = preflight(a.db, rules, exp, a.data_dir, blocks, log.log_dir)
        log.info(f"pré-contrôle réussi : {pre}")
        if not a.execute:
            log.info("mode pré-contrôle : aucune écriture effectuée. Exécution : --execute --confirm "
                     + rules["rules_version"])
            return 0

        variables = cl.rules_variables(rules)
        params = {k: v for k, v in rules.items() if k not in ("description",)}
        variables.update({
            "rules_version": rules["rules_version"],
            "rules_sha256": log.hashes[os.path.relpath(a.rules, cl.ROOT).replace("\\", "/")],
            "plan_sha256": log.hashes[rules["plan_document"]],
            "scripts_json": json.dumps(log.hashes, ensure_ascii=False, sort_keys=True),
            "params_json": json.dumps(params, ensure_ascii=False, sort_keys=True),
            "preflight_json": json.dumps(pre, ensure_ascii=False, sort_keys=True),
            "run_started": log.started.isoformat(),
            "expected_raw_rows": int(exp["raw_rows"]),
            "expected_source_files": int(exp["source_files"]),
            "exp_duplicate": int(exp["excluded"]["duplicate_ride_id"]),
            "exp_out_of_period": int(exp["excluded"]["out_of_period"]),
            "exp_negative": int(exp["excluded"]["negative_duration"]),
            "exp_under_60s": int(exp["excluded"]["under_60s"]),
            "exp_kept": int(exp["kept"]),
        })
        log.info("exécution de sql/02_clean.sql (transaction unique)")
        out = psql(a.db, file=CLEAN_SQL, single_transaction=True, variables=variables, label="02_clean.sql")
        for row in out:
            print("  " + " | ".join(row))
        executed = True

        ok, got, _ = cl.fingerprint_matches(psql(a.db, blocks["raw_fingerprint"], read_only=True, label="post:raw_fingerprint"),
                                            exp["raw_fingerprint"])
        log.info(f"empreinte de raw.trips après nettoyage identique : {ok}")
        if not ok:
            raise RuntimeError("raw.trips a changé pendant le nettoyage : ALERTE")

    if executed and not a.skip_followups:
        py = [sys.executable, "-I"]
        common = ["--db", a.db]
        r1 = subprocess.run(py + [os.path.join(cl.ROOT, "scripts", "run_qa_clean.py"), "--rules", a.rules,
                                  "--expected", a.expected, "--data-dir", a.data_dir] + common)
        r2 = subprocess.run(py + [os.path.join(cl.ROOT, "scripts", "run_sensitivity.py")] + common)
        return 1 if (r1.returncode or r2.returncode) else 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refused as e:
        print(f"REFUS : {e}")
        sys.exit(2)
