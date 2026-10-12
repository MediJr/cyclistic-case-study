"""Fonctions communes aux scripts de nettoyage (run_clean, run_qa_clean, run_sensitivity).

Aucune fonction de ce module n'écrit dans la base : les accès en écriture sont
uniquement dans run_clean.py --execute (sql/02_clean.sql).
"""
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "config", "regles_nettoyage_v3.2.json")
EXPECTED_PATH = os.path.join(ROOT, "config", "attendus_v3.2.json")
DB = os.environ.get("CYCLISTIC_DB", "cyclistic")
# Dossier des sorties (journaux, résultats QA, sensibilités) ; redirigé vers un dossier temporaire par les tests.
REPORTS = os.environ.get("CYCLISTIC_REPORTS_DIR", os.path.join(ROOT, "reports"))


def utf8_console():
    """Sortie console en UTF-8 même redirigée (python -I ignore PYTHONIOENCODING sous Windows)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_blocks(path):
    """Requêtes nommées d'un fichier SQL (blocs « -- name: xxx »)."""
    text = open(path, encoding="utf-8").read()
    parts = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def rules_variables(rules):
    """Variables psql dérivées de la configuration des règles."""
    d = rules["dst"]
    b = rules["chicago_bbox"]
    return {
        "period_start": rules["period"]["start_inclusive"],
        "period_end": rules["period"]["end_exclusive"],
        "min_duration_sec": int(rules["min_duration_sec"]),
        "tz": d["timezone"],
        "fb_start": d["fall_back_ambiguous_hour_start"],
        "fb_end": d["fall_back_ambiguous_hour_end"],
        "sf_start": d["spring_forward_gap_start"],
        "sf_end": d["spring_forward_gap_end"],
        "sf_correction_sec": int(d["spring_forward_correction_sec"]),
        "trim_chars": rules["station_normalization"]["trim_characters"],
        "lat_min": float(b["lat_min"]), "lat_max": float(b["lat_max"]),
        "lng_min": float(b["lng_min"]), "lng_max": float(b["lng_max"]),
        "long_trip_sec": int(rules["long_trip_flag_sec"]),
        "staff_pattern": rules["staff_or_test_stations"]["name_pattern"],
    }


def fingerprint_matches(rows, reference):
    """Compare l'empreinte exhaustive (source_csv, n, somme) à la référence de l'audit 4.1."""
    got = {r[0]: (int(r[1]), str(int(r[2]))) for r in rows}
    ref = {k: (int(v[0]), str(v[1])) for k, v in reference.items()}
    return got == ref, got, ref


def check_sources(source_rows, data_dir):
    """Recalcule les SHA-256 des fichiers sources et les compare à raw.source_files."""
    problems = []
    for csv_name, zip_name, csv_sha, zip_sha in source_rows:
        for path, expected in ((os.path.join(data_dir, "extracted", csv_name), csv_sha),
                               (os.path.join(data_dir, "raw", zip_name), zip_sha)):
            if not os.path.isfile(path):
                problems.append(f"absent : {path}")
            elif sha256(path) != expected:
                problems.append(f"empreinte différente : {path}")
    return problems
