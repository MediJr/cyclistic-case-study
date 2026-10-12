"""Mesures complémentaires pour le plan v3.1 (lecture seule, fichiers CSV uniquement).

Usage : python -I scripts/mesure_espaces_limites.py
Les CSV sont identiques à raw.trips (empreinte exhaustive, audit 4.1, V12) : ces mesures
s'appliquent donc aussi à la table brute. Aucun accès à PostgreSQL.
Sortie : reports/mesure_espaces_limites_output.txt
1. Espaces en bordure des noms et ID de stations : nature, fréquence, fusions induites par btrim.
2. Trajets à cheval sur deux mois, rapportés aux trajets commencés le dernier jour du mois.
"""
import collections
import csv
import datetime as dt
import os
import statistics
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
EXT = os.path.join(ROOT, "data", "extracted")
MONTHS = ["202510", "202511", "202512", "202601", "202602", "202603",
          "202604", "202605", "202606", "202607", "202608", "202609"]
TEXT_COLS = ["start_station_name", "start_station_id", "end_station_name", "end_station_id"]
out = []


def log(s=""):
    print(s)
    out.append(str(s))


def csv_name(m):
    with zipfile.ZipFile(os.path.join(RAW, f"{m}-divvy-tripdata.zip")) as zf:
        return [n for n in zf.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX")][0]


def main():
    kind = {c: collections.Counter() for c in TEXT_COLS}          # lead / trail / both
    chars = {c: collections.Counter() for c in TEXT_COLS}         # caractères de bordure
    by_file = {c: collections.Counter() for c in TEXT_COLS}
    internal = collections.Counter()                              # doubles espaces internes
    values = {c: collections.Counter() for c in TEXT_COLS}        # valeur brute -> lignes
    pairs_raw = collections.defaultdict(set)                      # (côté, id brut) -> noms bruts
    seen = set()
    last_day = collections.Counter()      # mois -> trajets commencés le dernier jour (ride_id uniques)
    cross = collections.Counter()         # mois de départ -> trajets terminés le mois suivant
    last_hour = collections.Counter()     # mois -> départs entre 23:00 et 23:59 le dernier jour

    for m in MONTHS:
        name = csv_name(m)
        with open(os.path.join(EXT, name), newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                for c in TEXT_COLS:
                    v = row[c]
                    if v == "":
                        continue
                    values[c][v] += 1
                    lead, trail = v != v.lstrip(), v != v.rstrip()
                    if lead or trail:
                        kind[c]["both" if lead and trail else "lead" if lead else "trail"] += 1
                        by_file[c][name] += 1
                        for ch in v[:len(v) - len(v.lstrip())] + v[len(v.rstrip()):]:
                            chars[c][f"U+{ord(ch):04X}"] += 1
                    if "  " in v.strip():
                        internal[c] += 1
                for side in ("start", "end"):
                    i, n = row[f"{side}_station_id"], row[f"{side}_station_name"]
                    if i:
                        pairs_raw[(side, i)].add(n)
                rid = row["ride_id"]
                if rid in seen:
                    continue
                seen.add(rid)
                s, e = row["started_at"], row["ended_at"]
                sd = dt.date.fromisoformat(s[:10])
                if (sd + dt.timedelta(days=1)).day == 1:          # dernier jour du mois
                    last_day[s[:7]] += 1
                    if s[11:13] == "23":
                        last_hour[s[:7]] += 1
                if s[:7] != e[:7]:
                    cross[s[:7]] += 1

    log("## 1. Espaces en bordure (valeurs non vides)")
    for c in TEXT_COLS:
        affected_vals = [v for v in values[c] if v != v.strip()]
        merged = [v for v in affected_vals if v.strip() in values[c]]
        merged_rows = sum(values[c][v] for v in merged)
        distinct_before = len(values[c])
        distinct_after = len({v.strip() for v in values[c]})
        log(f"{c}: lignes affectées={sum(kind[c].values())} {dict(kind[c])} | caractères={dict(chars[c])}")
        log(f"  valeurs distinctes affectées={len(affected_vals)} ; distinctes avant/après btrim="
            f"{distinct_before}/{distinct_after} ; valeurs qui fusionnent avec une valeur existante="
            f"{len(merged)} ({merged_rows} lignes) ; espaces doubles internes={internal[c]}")
        log(f"  par fichier : {dict(sorted(by_file[c].items()))}")
        log(f"  exemples : {[repr(v) for v in sorted(affected_vals, key=lambda v: -values[c][v])[:5]]}")
    # Cohérence ID -> nom avant/après btrim
    for side in ("start", "end"):
        multi_raw = sum(1 for (sd, i), ns in pairs_raw.items() if sd == side and len(ns) > 1)
        trimmed = collections.defaultdict(set)
        for (sd, i), ns in pairs_raw.items():
            if sd == side:
                trimmed[i.strip()] |= {n.strip() for n in ns}
        multi_trim = sum(1 for ns in trimmed.values() if len(ns) > 1)
        log(f"{side}: ID associés à plusieurs noms — brut={multi_raw} ; après btrim={multi_trim}")

    log("\n## 2. Trajets à cheval sur deux mois (ride_id uniques)")
    log("mois | départs le dernier jour | dont 23:00-23:59 | terminés le mois suivant | ratio")
    for k in sorted(last_day):
        ratio = cross[k] / last_day[k] if last_day[k] else 0
        log(f"{k} | {last_day[k]} | {last_hour[k]} | {cross[k]} | {ratio:.4%}")
    ratios = sorted(cross[k] / last_day[k] for k in last_day if k not in ("2025-09", "2026-03", "2026-09") and last_day[k])
    log(f"ratios hors 2025-09 (incomplet), 2026-03 (étudié) et 2026-09 (fichier 202610 absent) : min={ratios[0]:.4%} médiane={statistics.median(ratios):.4%} max={ratios[-1]:.4%}")
    n = last_day["2026-03"]
    log(f"2026-03 : {n} départs le 31/03 ; équivalent attendu par analogie = "
        f"{n*ratios[0]:.0f} à {n*ratios[-1]:.0f} (médiane {n*statistics.median(ratios):.0f}) ; observé = {cross['2026-03']}")

    with open(os.path.join(ROOT, "reports", "mesure_espaces_limites_output.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
