"""Reconstruction reproductible des mesures de la revue 4.3 (M1, M2) et de l'examen D6 (mission 4.4).

Usage : python -I scripts/mesure_stations_durees.py
Lecture seule des CSV (identiques à raw.trips, audit 4.1). Aucun accès à PostgreSQL.
Sortie : reports/mesure_stations_durees_output.txt — AGRÉGÉE uniquement : aucun détail ligne à
ligne (identifiants de trajet, heures) n'est écrit pour les stations « internes », afin de ne pas
exposer de régularités individuelles (PDF, P7).

Les mesures M1/M2 d'origine ont été exécutées en entrée standard et ne sont pas archivées :
ce script en est une RÉÉCRITURE, pas une copie ; l'égalité des résultats est vérifiée par
comparaison aux valeurs publiées (bloc « Comparaison » en fin de sortie).
"""
import collections
import csv
import datetime as dt
import os
import re
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
EXT = os.path.join(ROOT, "data", "extracted")
MONTHS = ["202510", "202511", "202512", "202601", "202602", "202603",
          "202604", "202605", "202606", "202607", "202608", "202609"]
P0, P1 = dt.datetime(2025, 10, 1), dt.datetime(2026, 10, 1)
STAFF = re.compile(r"test|charging|warehouse|divvy|lbs-wh|hubbard bike|repair|valet|base", re.I)
COLS = ["start_station_name", "start_station_id", "end_station_name", "end_station_id"]
PUBLISHED = {  # valeurs publiées (revue 4.3, plan v3.2) à retrouver
    "combos": {(False, False, False, False, False): 6012458, (False, False, False, False, True): 159192,
               (False, True, False, False, False): 71, (True, False, False, False, False): 35,
               (False, False, True, False, False): 29},
    "under60_by_type": {("electric_bike", "member"): 84724, ("electric_bike", "casual"): 74468},
    "under60_station": {"same_station": 45028, "no_station": 110742, "diff_station": 3422},
    "kept_pair": 4049494, "kept_has_end": 6007026,
    "ids_multi_names": {"start": 55, "end": 53}, "ids_trivial": {"start": 7, "end": 7},
    "names_multi_ids": {"start": 60, "end": 59}, "span_005": 6, "span_01": 4,
    "trimmed_rows": {"start_station_name": 34541, "start_station_id": 643, "end_station_name": 36756, "end_station_id": 587},
    "staff_rows": 42, "staff_kept": 41,
}
out = []


def log(s=""):
    print(s)
    out.append(str(s))


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    vals = {c: collections.Counter() for c in COLS}
    id_names = {s: collections.defaultdict(collections.Counter) for s in ("start", "end")}
    name_ids = {s: collections.defaultdict(set) for s in ("start", "end")}
    coords = {}
    seen = set()
    combos = collections.Counter()
    lt60 = collections.Counter()
    lt60_station = collections.Counter()
    kept_pair = kept_end = 0
    staff = collections.Counter()
    staff_rows = staff_kept = 0
    staff_kept_by = collections.Counter()
    staff_months = collections.Counter()
    staff_dir = collections.Counter()

    for m in MONTHS:
        with zipfile.ZipFile(os.path.join(RAW, f"{m}-divvy-tripdata.zip")) as zf:
            name = [n for n in zf.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX")][0]
        with open(os.path.join(EXT, name), newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for c in COLS:
                    if row[c]:
                        vals[c][row[c]] += 1
                for s in ("start", "end"):
                    i, n = row[f"{s}_station_id"], row[f"{s}_station_name"]
                    if i:
                        id_names[s][i.strip()][n.strip()] += 1
                        name_ids[s][n.strip()].add(i.strip())
                if row["rideable_type"] == "classic_bike" and row["start_station_id"]:
                    c4 = coords.setdefault(row["start_station_id"].strip(), [99.0, -99.0, 999.0, -999.0])
                    la, lo = float(row["start_lat"]), float(row["start_lng"])
                    c4[0], c4[1] = min(c4[0], la), max(c4[1], la)
                    c4[2], c4[3] = min(c4[2], lo), max(c4[3], lo)
                rid = row["ride_id"]
                dup = rid in seen
                seen.add(rid)
                s_ = dt.datetime.fromisoformat(row["started_at"])
                e_ = dt.datetime.fromisoformat(row["ended_at"])
                d = (e_ - s_).total_seconds()
                k = (dup, not (P0 <= s_ < P1), d < 0, d == 0, 0 < d < 60)
                combos[k] += 1
                kept = not any(k)
                if kept:
                    kept_pair += bool(row["start_station_id"] and row["end_station_id"])
                    kept_end += bool(row["end_lat"])
                elif k == (False, False, False, False, True):
                    lt60[(row["rideable_type"], row["member_casual"])] += 1
                    si, ei = row["start_station_id"].strip(), row["end_station_id"].strip()
                    lt60_station["no_station" if not (si and ei) else "same_station" if si == ei else "diff_station"] += 1
                hits = [c for c in ("start_station_name", "end_station_name") if row[c] and STAFF.search(row[c])]
                if hits:
                    staff_rows += 1
                    staff_months[name] += 1
                    staff_dir[tuple(h.split("_")[0] for h in hits)] += 1
                    for h in hits:
                        staff[(row[h.replace("name", "id")].strip(), row[h].strip())] += 1
                    if kept:
                        staff_kept += 1
                        staff_kept_by[(row["rideable_type"], row["member_casual"])] += 1

    res = {}
    log("## Bilan : combinaisons de critères indépendants (doublon, hors période, négatif, nul, 0<d<60)")
    for k, n in sorted(combos.items(), key=lambda x: -x[1]):
        log(f"  {k} {n}")
    res["combos"] = dict(combos)
    log(f"  conservées avec les deux stations : {kept_pair} ; avec coordonnées d'arrivée : {kept_end}")
    res["kept_pair"], res["kept_has_end"] = kept_pair, kept_end

    log("\n## D5 : positifs < 60 s")
    log(f"  par (type de vélo, usager) : {dict(lt60)}")
    log(f"  relation des stations : {dict(lt60_station)}")
    res["under60_by_type"], res["under60_station"] = dict(lt60), dict(lt60_station)

    log("\n## D1 : valeurs avec espace en bordure (lignes brutes)")
    res["trimmed_rows"] = {}
    for c in COLS:
        aff = {v: n for v, n in vals[c].items() if v != v.strip()}
        res["trimmed_rows"][c] = sum(aff.values())
        for v, n in sorted(aff.items(), key=lambda x: -x[1]):
            log(f"  {c} | {v!r} | {n} | forme sans espace : {vals[c].get(v.strip(), 0)}")

    log("\n## D2 : espaces doubles internes")
    for c in ("start_station_name", "end_station_name"):
        for v, n in vals[c].items():
            if "  " in v.strip():
                red = re.sub(" {2,}", " ", v.strip())
                log(f"  {c} | {v!r} | {n} | forme réduite présente : {vals[c].get(red, 0)}")

    log("\n## D4 : cohérence ID / noms (après btrim)")
    res["ids_multi_names"], res["ids_trivial"], res["names_multi_ids"] = {}, {}, {}
    for s in ("start", "end"):
        multi = {i: ns for i, ns in id_names[s].items() if len(ns) > 1}
        triv = sum(1 for ns in multi.values() if len({norm(n) for n in ns}) == 1)
        nmi = sum(1 for ids in name_ids[s].values() if len(ids) > 1)
        res["ids_multi_names"][s], res["ids_trivial"][s], res["names_multi_ids"][s] = len(multi), triv, nmi
        log(f"  {s} : ID={len(id_names[s])} ; à plusieurs noms={len(multi)} (triviaux {triv}) ; noms à plusieurs ID={nmi}")
    spans = [max(c[1] - c[0], c[3] - c[2]) for c in coords.values()]
    res["span_005"], res["span_01"] = sum(sp > 0.005 for sp in spans), sum(sp > 0.01 for sp in spans)
    log(f"  ID de départ (classiques) : étendue > 0,005° = {res['span_005']} ; > 0,01° = {res['span_01']} sur {len(spans)}")

    log("\n## D6 : stations dont le nom évoque un usage interne (agrégé, non nominatif)")
    for (i, n), c in staff.most_common():
        log(f"  {i} | {n} | {c} occurrence(s)")
    log(f"  lignes brutes : {staff_rows} ; conservées : {staff_kept} ; par fichier : {dict(staff_months)}")
    log(f"  sens : {dict(staff_dir)} ; conservées par (vélo, usager) : {dict(staff_kept_by)}")
    res["staff_rows"], res["staff_kept"] = staff_rows, staff_kept

    log("\n## Comparaison aux valeurs publiées")
    allok = True
    for key, want in PUBLISHED.items():
        got = res.get(key)
        ok = got == want
        allok &= ok
        log(f"  [{'OK' if ok else 'ÉCART'}] {key} : publié={want} recalculé={got}")
    log(f"  RÉSULTAT : {'toutes les valeurs publiées sont retrouvées' if allok else 'ÉCART à examiner'}")
    with open(os.path.join(ROOT, "reports", "mesure_stations_durees_output.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
