"""Tests du nettoyage sur DONNÉES SYNTHÉTIQUES, dans une instance PostgreSQL JETABLE.

Usage : python -I tests/test_cleaning_synthetic.py [--keep]

- Crée une instance PostgreSQL temporaire (initdb dans un dossier temporaire, port 55433,
  127.0.0.1 uniquement, authentification « trust » locale), totalement distincte du service
  PostgreSQL de l'utilisateur et de la base `cyclistic`. Elle est arrêtée et supprimée à la fin
  (sauf --keep).
- 20 trajets fictifs couvrent chaque règle : doublon identique entre fichiers, hors période,
  durée négative (heure d'automne), durée nulle, < 60 s, heure d'été (correction confirmée,
  y compris une durée corrigée < 60 s), chevauchement de l'heure d'automne, stations manquantes,
  arrivée manquante, > 24 h, espaces en bordure (avec et sans fusion), espaces doubles internes,
  station « de test », CSV mal nommé (202501 dans le ZIP 202601), millisecondes à zéro final.
- Scénarios : pré-contrôle seul ; --execute sans --confirm ; exécution complète (QA incluse) ;
  seconde exécution (refusée) ; garde-fou SQL direct ; conflit de ride_id (refus) ; attendus faux
  (annulation complète de la transaction) ; raw inchangé (empreinte avant/après).
"""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import pg  # noqa: E402

BIN = os.path.dirname(pg.PSQL)
PORT = "55433"
COLS = ["ride_id", "rideable_type", "started_at", "ended_at", "start_station_name", "start_station_id",
        "end_station_name", "end_station_id", "start_lat", "start_lng", "end_lat", "end_lng", "member_casual"]
ST = {  # stations fictives : (nom, id, lat, lng)
    "A": ("Clark St & Lake St", "CHI00010", "41.886", "-87.631"),
    "B": ("Wells St & Elm St", "CHI00011", "41.903", "-87.634"),
}


def trip(rid, typ, s, e, start, end, member, coords=None):
    sn, si, sla, slo = start if start else ("", "", "41.89", "-87.63")
    en, ei, ela, elo = end if end else ("", "", "41.90", "-87.64")
    if coords == "no_end":
        ela = elo = ""
    return [rid, typ, s, e, sn, si, en, ei, sla, slo, ela, elo, member]


def stn(name, sid, base="A"):
    return (name, sid, ST[base][2], ST[base][3])


A, B = ST["A"], ST["B"]
DUP = trip("SYN0008", "electric_bike", "2026-04-30 23:50:00.500", "2026-05-01 00:10:00.250", A, B, "member")
FILES = {
    ("202601-divvy-tripdata.zip", "202501-divvy-tripdata.csv", "2026-01"): [
        trip("SYN0001", "classic_bike", "2026-01-10 08:00:00.640", "2026-01-10 08:15:00.120", A, B, "member"),
        trip("SYN0002", "electric_bike", "2025-12-31 23:50:00.000", "2026-01-01 00:20:00.000", A, B, "casual"),
        trip("SYN0003", "electric_bike", "2026-01-11 09:00:00.000", "2026-01-11 09:00:30.000", A, B, "member"),
        trip("SYN0004", "electric_bike", "2026-01-12 10:00:00.000", "2026-01-12 10:00:00.000", A, B, "casual"),
        trip("SYN0005", "electric_bike", "2026-01-13 11:00:00.000", "2026-01-13 11:20:00.000", None, None, "member"),
    ],
    ("202604-divvy-tripdata.zip", "202604-divvy-tripdata.csv", "2026-04"): [
        trip("SYN0006", "classic_bike", "2026-04-02 08:00:00.000", "2026-04-02 08:10:00.000",
             stn("Sheffield Ave & Addison St ", "CHI00020"), A, "member"),
        trip("SYN0007", "classic_bike", "2026-04-03 08:00:00.000", "2026-04-03 08:12:00.000",
             stn("Sheffield Ave & Addison St", "CHI00020"), stn("Clark St & Eddy St ", "CHI00021", "B"), "casual"),
        DUP,
        trip("SYN0009", "classic_bike", "2026-04-05 08:00:00.000", "2026-04-05 08:30:00.000",
             stn("Franklin St & Randolph St", " CHI02331"), stn("Franklin St & Randolph St", " CHI02331"), "member"),
        trip("SYN0010", "classic_bike", "2026-04-06 08:00:00.000", "2026-04-06 08:30:00.000",
             stn("Franklin St & Randolph St", "CHI02331"), stn("Franklin St & Randolph St", "CHI02331"), "casual"),
        trip("SYN0011", "classic_bike", "2026-04-07 08:00:00.000", "2026-04-07 08:09:00.000",
             stn("Public Rack - Torrence Ave  & 106th St", "CHI01389"), A, "member"),
        trip("SYN0012", "classic_bike", "2026-04-08 08:00:00.000", "2026-04-08 08:05:00.000",
             stn("Hastings Test Station", "CHI02362"), A, "member"),
        trip("SYN0013", "classic_bike", "2026-04-10 12:00:00.000", "2026-04-11 13:00:00.000", A, None, "casual", "no_end"),
        trip("SYN0014", "classic_bike", "2025-09-30 23:00:00.000", "2025-10-01 00:10:00.000", A, B, "member"),
        trip("SYN0015", "classic_bike", "2026-03-08 01:50:00.000", "2026-03-08 03:10:00.000", A, B, "member"),
        trip("SYN0016", "electric_bike", "2026-03-08 01:59:30.000", "2026-03-08 03:00:10.000", A, B, "casual"),
        trip("SYN0017", "classic_bike", "2025-11-02 01:50:00.000", "2025-11-02 01:10:00.000", A, B, "member"),
        trip("SYN0018", "classic_bike", "2025-11-02 01:30:00.000", "2025-11-02 01:45:00.000", A, B, "casual"),
    ],
    ("202605-divvy-tripdata.zip", "202605-divvy-tripdata.csv", "2026-05"): [
        list(DUP),
        trip("SYN0019", "electric_bike", "2026-05-03 08:00:00.000", "2026-05-03 08:20:00.000", B, A, "member"),
    ],
}

# Oracle établi À LA MAIN à partir de la conception des 20 lignes ci-dessus (indépendant du code testé)
ORACLE = {
    "rules_version": "v3.2",
    "raw_rows": 20, "source_files": 3,
    "excluded": {"duplicate_ride_id": 1, "out_of_period": 1, "negative_duration": 1, "under_60s": 2},
    "kept": 15,
    "kept_by_member": {"casual": 6, "member": 9},
    "kept_by_month": {"2025-11": 1, "2025-12": 1, "2026-01": 2, "2026-03": 2, "2026-04": 8, "2026-05": 1},
    "flags": {"has_end_location_false": 1, "is_over_24h": 1, "dst_fall_back_overlap": 1, "dst_spring_forward_span": 2,
              "start_station_missing": 1, "end_station_missing": 2},
    "subsets": {"v_trips_geo": 14, "v_trips_start_station": 14, "v_trips_end_station": 13, "v_trips_station_pair": 13},
    "max_ride_length_sec_at_most": 93597,
    "duplicates": {"excluded_from": "202605-divvy-tripdata.csv", "kept_from": "202604-divvy-tripdata.csv"},
    "normalization": {
        "max_trimmed_rows_raw": {"start_station_name": 1, "start_station_id": 1, "end_station_name": 1, "end_station_id": 1},
        "max_distinct_trimmed_values_raw": {"start_station_name": 1, "start_station_id": 1, "end_station_name": 1, "end_station_id": 1},
        "allowed_merges": {"start_station_name": ["Sheffield Ave & Addison St"], "end_station_name": [],
                           "start_station_id": ["CHI02331"], "end_station_id": ["CHI02331"]},
    },
    "known_anomalies": {"march_april_crossings": 0},
    "reference_info_raw_rows": {"S1_ids_with_several_names": {"start": 0, "end": 0},
                                "S2_names_with_several_ids": {"start": 0, "end": 0},
                                "S5_staff_or_test_rows_kept": 1},
}

results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {label}{(' — ' + str(detail)) if detail and not cond else ''}")


def run(cmd, env, **kw):
    return subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def fingerprint(rows_by_file):
    out = {}
    for (_, csv_name, _), rows in rows_by_file.items():
        s = 0
        for i, row in enumerate(rows, start=2):
            key = f"{i}\x1f" + "\x1f".join(v if v != "" else "\\N" for v in row)
            s += int(hashlib.md5(key.encode("utf-8")).hexdigest()[:15], 16)
        out[csv_name] = [len(rows), str(s)]
    return out


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def build_data(tmp, files):
    data = os.path.join(tmp, "data")
    os.makedirs(os.path.join(data, "raw"), exist_ok=True)
    os.makedirs(os.path.join(data, "extracted"), exist_ok=True)
    meta = []
    for (zip_name, csv_name, month), rows in files.items():
        cpath = os.path.join(data, "extracted", csv_name)
        with open(cpath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\r\n")
            w.writerow(COLS)
            w.writerows(rows)
        zpath = os.path.join(data, "raw", zip_name)
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.write(cpath, csv_name)
        meta.append((zip_name, csv_name, month, os.path.getsize(zpath), sha(zpath), os.path.getsize(cpath), sha(cpath), len(rows)))
    return data, meta


def lit(v):
    return "NULL" if v == "" else "'" + v.replace("'", "''") + "'"


def load_raw(db, meta, files):
    pg.psql(db, file=os.path.join(ROOT, "sql", "01_create_raw.sql"))
    stmts = []
    for zip_name, csv_name, month, zb, zs, cb, cs, n in meta:
        stmts.append(f"INSERT INTO raw.source_files (zip_name, csv_name, file_month, zip_bytes, zip_sha256, csv_bytes, csv_sha256, csv_data_rows) "
                     f"VALUES ({lit(zip_name)}, {lit(csv_name)}, {lit(month)}, {zb}, {lit(zs)}, {cb}, {lit(cs)}, {n});")
    for (zip_name, csv_name, _), rows in files.items():
        for i, row in enumerate(rows, start=2):
            stmts.append(f"INSERT INTO raw.trips (source_zip, source_csv, source_line, {', '.join(COLS)}) VALUES "
                         f"({lit(zip_name)}, {lit(csv_name)}, {i}, {', '.join(lit(v) for v in row)});")
    pg.psql(db, "\n".join(stmts))


def setup_db(name, files, tmp, oracle, tag):
    pg.psql("postgres", f"CREATE DATABASE {name} ENCODING 'UTF8' TEMPLATE template0")
    data, meta = build_data(os.path.join(tmp, tag), files)
    load_raw(name, meta, files)
    exp = dict(oracle, raw_fingerprint=fingerprint(files))
    exp_path = os.path.join(ROOT, "tests", f"_expected_{tag}.json")   # sous ROOT : chemin relatif journalisable
    with open(exp_path, "w", encoding="utf-8") as f:
        json.dump(exp, f, ensure_ascii=False, indent=1)
    return data, exp_path


def schemas(db):
    return pg.psql(db, "SELECT to_regnamespace('clean') IS NOT NULL, to_regnamespace('audit') IS NOT NULL")[0]


def main():
    keep = "--keep" in sys.argv
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tmp = tempfile.mkdtemp(prefix="cyclistic_pgtest_")
    pgdata, logfile = os.path.join(tmp, "pgdata"), os.path.join(tmp, "server.log")
    env = dict(os.environ, PGHOST="127.0.0.1", PGPORT=PORT, PGUSER="tester", PGPASSWORD="synthetique",
               CYCLISTIC_REPORTS_DIR=os.path.join(tmp, "reports"), PYTHONIOENCODING="utf-8")
    os.environ.update({k: env[k] for k in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "CYCLISTIC_REPORTS_DIR")})
    started = False
    created = []
    try:
        r = run([os.path.join(BIN, "initdb.exe"), "-D", pgdata, "-U", "tester", "-A", "trust", "-E", "UTF8",
                 "--locale=C", "--no-instructions"], env)
        check("instance jetable initialisée", r.returncode == 0, r.stderr[-500:])
        # Sous Windows, le serveur hérite des canaux de sortie : ne pas les capturer (sinon attente infinie).
        r = subprocess.run([os.path.join(BIN, "pg_ctl.exe"), "-D", pgdata, "-l", logfile, "-w", "-o",
                            f"-p {PORT} -c listen_addresses=127.0.0.1", "start"], env=env,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        started = r.returncode == 0
        check("instance jetable démarrée (127.0.0.1:%s)" % PORT, started, open(logfile, encoding="utf-8", errors="replace").read()[-500:])
        if not started:
            return 1
        py = [sys.executable, "-I"]
        rc = os.path.join(ROOT, "scripts", "run_clean.py")

        # --- Scénarios sur la base nominale ---------------------------------------------
        data, exp = setup_db("cyclistic_test", FILES, tmp, ORACLE, "nominal")
        created.append(exp)
        e = dict(env, CYCLISTIC_DB="cyclistic_test")
        fp_before = pg.psql("cyclistic_test", open(os.path.join(ROOT, "sql", "03_qa_clean.sql"), encoding="utf-8")
                            .read().split("-- name: raw_fingerprint")[1].split("-- name:")[0])
        base = ["--expected", exp, "--data-dir", data]

        r = run(py + [rc] + base, e)
        check("T1 pré-contrôle seul : succès", r.returncode == 0, r.stdout[-1500:])
        check("T1 pré-contrôle seul : aucun schéma créé", schemas("cyclistic_test") == ["f", "f"])

        r = run(py + [rc, "--execute"] + base, e)
        check("T2 --execute sans --confirm : refus (code 2)", r.returncode == 2, r.stdout[-800:])
        check("T2 aucun schéma créé", schemas("cyclistic_test") == ["f", "f"])

        r = run(py + [rc, "--execute", "--confirm", "v3.2"] + base, e)
        check("T3 exécution + QA + sensibilités : code 0", r.returncode == 0, r.stdout[-4000:] + r.stderr[-2000:])
        qa_fail = [ln for ln in r.stdout.splitlines() if "ÉCHEC" in ln and ln.startswith("[")]
        check("T3 aucun contrôle QA en ÉCHEC", not qa_fail, qa_fail)
        q = lambda s: pg.psql("cyclistic_test", s)  # noqa: E731
        check("T3 15 conservées / 5 exclues", q("SELECT (SELECT count(*) FROM clean.trips), (SELECT count(*) FROM audit.excluded_rows)") == [["15", "5"]])
        check("T3 doublon : copie 202605 exclue, référence 202604",
              q("SELECT source_csv, kept_source_csv FROM audit.excluded_rows WHERE ride_id='SYN0008'")
              == [["202605-divvy-tripdata.csv", "202604-divvy-tripdata.csv"]])
        check("T3 motifs : 0 s et 30 s → under_60s ; négatif → negative_duration ; septembre → out_of_period",
              q("SELECT ride_id, reason FROM audit.excluded_rows WHERE ride_id <> 'SYN0008' ORDER BY ride_id")
              == [["SYN0003", "under_60s"], ["SYN0004", "under_60s"], ["SYN0014", "out_of_period"], ["SYN0017", "negative_duration"]])
        check("T3 heure d'été : 4800→1200 s et 3640→40 s corrigés (colonne séparée), durée brute intacte",
              q("SELECT ride_id, ride_length_sec::int, ride_length_sec_dst_adj::int, dst_adj_status FROM clean.trips "
                "WHERE dst_spring_forward_span ORDER BY ride_id")
              == [["SYN0015", "4800", "1200", "corrected"], ["SYN0016", "3640", "40", "corrected"]])
        check("T3 heure d'automne : chevauchement signalé, non corrigé",
              q("SELECT dst_fall_back_overlap, dst_adj_status, ride_length_sec::int FROM clean.trips WHERE ride_id='SYN0018'")
              == [["t", "not_applicable", "900"]])
        check("T3 espaces en bordure retirés (ID et nom), indicateurs posés",
              q("SELECT start_station_id, start_station_id_trimmed, end_station_id_trimmed FROM clean.trips WHERE ride_id='SYN0009'")
              == [["CHI02331", "t", "t"]]
              and q("SELECT start_station_name, start_station_name_trimmed FROM clean.trips WHERE ride_id='SYN0006'")
              == [["Sheffield Ave & Addison St", "t"]])
        check("T3 espaces doubles internes préservés",
              q("SELECT start_station_name FROM clean.trips WHERE ride_id='SYN0011'") == [["Public Rack - Torrence Ave  & 106th St"]])
        check("T3 journal de normalisation : 4 valeurs, fusions = Sheffield (départ), CHI02331 (départ, arrivée)",
              q("SELECT column_name, normalized_value, merges_with_existing_value FROM audit.normalization_log ORDER BY 1")
              == [["end_station_id", "CHI02331", "t"], ["end_station_name", "Clark St & Eddy St", "f"],
                  ["start_station_id", "CHI02331", "t"], ["start_station_name", "Sheffield Ave & Addison St", "t"]])
        check("T3 station « de test » conservée (aucune exclusion par le nom)",
              q("SELECT count(*) FROM clean.trips WHERE ride_id='SYN0012'") == [["1"]])
        check("T3 trajet sans arrivée et > 24 h conservé et signalé",
              q("SELECT has_end_location, is_over_24h FROM clean.trips WHERE ride_id='SYN0013'") == [["f", "t"]])
        check("T3 horodatage .640 : valeur conservée (comparaison de valeurs)",
              q("SELECT to_char(started_at, 'YYYY-MM-DD HH24:MI:SS.MS') FROM clean.trips WHERE ride_id='SYN0001'")
              == [["2026-01-10 08:00:00.640"]])
        check("T3 CSV 202501 : trajet du 31/12 rattaché à 2025-12",
              q("SELECT to_char(ride_month,'YYYY-MM') FROM clean.trips WHERE ride_id='SYN0002'") == [["2025-12"]])
        check("T3 journal des étapes 20→19→18→17→15",
              q("SELECT string_agg(rows_after::text, '→' ORDER BY step_no) FROM audit.transform_log") == [["20→19→18→17→15"]])
        check("T3 exécution enregistrée (version, empreintes de scripts)",
              q("SELECT rules_version, jsonb_typeof(scripts), scripts ? 'sql/02_clean.sql' FROM audit.run") == [["v3.2", "object", "t"]])
        logs = os.listdir(os.path.join(tmp, "reports", "logs"))
        check("T3 journaux persistants créés (exécution, QA, sensibilités)",
              any(l.startswith("nettoyage_execution") for l in logs) and any(l.startswith("qa_nettoyage") for l in logs)
              and any(l.startswith("sensibilite") for l in logs), logs)

        r = run(py + [rc, "--execute", "--confirm", "v3.2"] + base, e)
        check("T4 seconde exécution refusée (code 2)", r.returncode == 2 and "seconde exécution refusée" in r.stdout, r.stdout[-800:])
        check("T4 contenu inchangé après refus", q("SELECT count(*) FROM clean.trips") == [["15"]])
        try:
            pg.psql("cyclistic_test", file=os.path.join(ROOT, "sql", "02_clean.sql"), single_transaction=True,
                    variables={"expected_raw_rows": 20, "expected_source_files": 3})
            direct = "exécuté"
        except RuntimeError as ex:
            direct = str(ex)
        check("T5 garde-fou SQL direct (sans orchestrateur) : refus", "seconde exécution refusée" in direct, direct[:300])

        # --- Phase Analyze : extraction en lecture seule sur la table nettoyée synthétique ------
        out_an = os.path.join(tmp, "analyse_csv")
        n_tables = q("SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')")
        r = run(py + [os.path.join(ROOT, "scripts", "run_analyse.py"), "--out-dir", out_an], e)
        check("T9 extraction d'analyse : code 0 et contrôles de cohérence OK", r.returncode == 0 and "ÉCHEC" not in r.stdout,
              (r.stdout + r.stderr)[-1500:])
        if r.returncode == 0:
            with open(os.path.join(out_an, "a01_usagers.csv"), encoding="utf-8") as f:
                rows = {x[0]: x for x in csv.reader(f)}
            check("T9 a01 : 9 trajets member, 6 casual, 15 au total",
                  (rows["member"][1], rows["casual"][1], rows["TOUS"][1]) == ("9", "6", "15"))
            check("T9 aucune table créée par l'analyse",
                  q("SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')")
                  == n_tables)

        fp_after = pg.psql("cyclistic_test", open(os.path.join(ROOT, "sql", "03_qa_clean.sql"), encoding="utf-8")
                           .read().split("-- name: raw_fingerprint")[1].split("-- name:")[0])
        check("T6 raw.trips inchangé (empreinte exhaustive avant = après)", fp_before == fp_after)

        # --- Conflit de ride_id --------------------------------------------------------
        conflict = {k: [list(r_) for r_ in v] for k, v in FILES.items()}
        conflict[("202605-divvy-tripdata.zip", "202605-divvy-tripdata.csv", "2026-05")][0][12] = "casual"
        data_c, exp_c = setup_db("cyclistic_conflit", conflict, tmp, ORACLE, "conflit")
        created.append(exp_c)
        r = run(py + [rc, "--execute", "--confirm", "v3.2", "--expected", exp_c, "--data-dir", data_c],
                dict(env, CYCLISTIC_DB="cyclistic_conflit"))
        check("T7 conflit de ride_id : refus au pré-contrôle (code 2)", r.returncode == 2 and "conflit" in r.stdout, r.stdout[-800:])
        check("T7 aucun schéma créé", schemas("cyclistic_conflit") == ["f", "f"])
        check("T7 liste des conflits écrite", any(f.startswith("conflits_ride_id") for f in os.listdir(os.path.join(tmp, "reports", "logs"))))

        # --- Attendus faux : la transaction doit être annulée entièrement -------------------
        bad = json.loads(json.dumps(ORACLE))
        bad["excluded"]["under_60s"] = 3
        bad["kept"] = 14
        data_b, exp_b = setup_db("cyclistic_attendus_faux", FILES, tmp, bad, "attendus_faux")
        created.append(exp_b)
        r = run(py + [rc, "--execute", "--confirm", "v3.2", "--expected", exp_b, "--data-dir", data_b],
                dict(env, CYCLISTIC_DB="cyclistic_attendus_faux"))
        check("T8 attendus faux : échec bloquant (R4b)", r.returncode != 0 and "R4b" in (r.stdout + r.stderr), (r.stdout + r.stderr)[-800:])
        check("T8 transaction annulée : aucun schéma créé", schemas("cyclistic_attendus_faux") == ["f", "f"])
    finally:
        for p in created:
            if os.path.exists(p):
                os.remove(p)
        if started:
            subprocess.run([os.path.join(BIN, "pg_ctl.exe"), "-D", pgdata, "-m", "fast", "-w", "stop"], env=env,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if keep:
            print(f"Instance et fichiers conservés : {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    failed = [l for l, ok in results if not ok]
    print(f"\nBILAN TESTS : {len(results) - len(failed)}/{len(results)} réussis")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
