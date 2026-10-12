"""Build the English Cyclistic PDF report (LaTeX) reproducibly.

Usage: python -I scripts/build_latex_report.py [--no-compile]
Steps:
  1. regenerate the tables (scripts/generate_latex_tables.py) from the analysis CSV files;
  2. check that every number quoted in reports/latex/sections/*.tex matches a value computed from
     the CSV files, the cleaning configuration or a documented constant (CONST below);
     fail if a number cannot be matched;
  3. compile reports/latex/report.tex with xelatex, three passes (output in reports/latex/build/);
  4. parse the log (errors, missing characters, undefined references, overfull boxes);
  5. copy the PDF to reports/Cyclistic_Professional_Report.pdf.
No database access.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_latex_tables  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LTX = os.path.join(ROOT, "reports", "latex")
CSV = os.path.join(ROOT, "results", "analysis")
PDF_OUT = os.path.join(ROOT, "reports", "Cyclistic_Professional_Report.pdf")

# Constants quoted in the text that are not computed from the CSV files, with their source
CONST = {
    "5824": "fleet size (case study brief)", "692": "stations (case study brief)",
    "6171785": "raw rows (import audit)", "35": "duplicates", "71": "out of period", "29": "negative durations",
    "159192": "shorter than 60 s", "159327": "total excluded", "72": "quality checks", "62": "checks OK",
    "8": "INFO checks", "93597": "Q16b reference", "93597.011": "Q16b actual maximum", "3600": "DST correction (s)",
    "40": "DST-corrected rides", "474": "fall-back overlap", "41": "staff/test station rides",
    "28": "low estimate March-April", "102": "high estimate March-April", "173": "max rides at a month boundary",
    "646.2": "SENS-1 casual with <60 s (s)", "669.9": "SENS-1 casual without", "510.6": "SENS-1 members with",
    "521.4": "SENS-1 members without", "568.0": "SENS-2 without 31/03-01/04 (s)", "567.4": "SENS-2 with (s)",
    "28.6": "2/7 days (uniform reference)", "60": "threshold (s) / conversion days", "11": "charts produced / 11:59 p.m.",
    "3": "questions / appendix", "2025": "year", "2026": "year",
}
# Structural numbers ignored: days, hours, section numbers, minute bands
STRUCT = {"0", "1", "2", "4", "5", "6", "7", "9", "10", "12", "15", "16", "17", "18", "19", "20", "23", "24", "30",
          "31", "59", "00", "256", "14", "90"}
NUMBER = re.compile(r"(?<![\w.,])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.,])\d+(?:\.\d+)?")


def fmt(x, dec):
    q = Decimal(str(x)).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)
    return f"{q:f}"


def allowed_values():
    vals = set()
    for path in glob.glob(os.path.join(CSV, "*.csv")):
        df = pd.read_csv(path)
        for col in df.select_dtypes("number").columns:
            for v in df[col].dropna():
                for dec in (0, 1, 2):
                    vals.add(fmt(v, dec))
    # percentages and ratios derived from the counts
    u = pd.read_csv(os.path.join(CSV, "a01_usagers.csv")).set_index("member_casual")
    tot = {mc: int(u.loc[mc, "trajets"]) for mc in ("member", "casual", "TOUS")}
    j = pd.read_csv(os.path.join(CSV, "a03_jour.csv"))
    m = pd.read_csv(os.path.join(CSV, "a04_mois.csv"))
    h = pd.read_csv(os.path.join(CSV, "a05_heure.csv"))
    d2 = pd.read_csv(os.path.join(CSV, "a02_durees_tranches.csv"))
    it = pd.read_csv(os.path.join(CSV, "a07_interactions.csv"))
    v = pd.read_csv(os.path.join(CSV, "a06_velo.csv"))
    b = pd.read_csv(os.path.join(CSV, "a08_boucles.csv")).set_index("member_casual")
    a09 = pd.read_csv(os.path.join(CSV, "a09_contexte.csv")).set_index("member_casual")

    def addp(n, d, decs=(0, 1)):
        for dec in decs:
            vals.add(fmt(Decimal(int(n)) * 100 / Decimal(int(d)), dec))
    for mc in ("member", "casual"):
        we = j[(j.member_casual == mc) & (j.day_of_week.isin([1, 7]))].trajets.sum()
        addp(we, tot[mc]); addp(tot[mc] - we, tot[mc])
        for r in j[j.member_casual == mc].itertuples():
            addp(r.trajets, tot[mc])
        for first in ("01", "03", "05", "06"):
            addp(d2[(d2.member_casual == mc) & (d2.tranche.str[:2] >= first)].trajets.sum(), tot[mc])
        addp(d2[(d2.member_casual == mc) & (d2.tranche.str[:2] <= "02")].trajets.sum(), tot[mc])
        for r in it[it.member_casual == mc].itertuples():
            addp(r.trajets, tot[mc])
        for r in v[v.member_casual == mc].itertuples():
            addp(r.trajets, tot[mc])
        sw = h[(h.member_casual == mc) & (h.type_jour == "semaine")]
        for hours in ([7, 8], [17], list(range(10, 16))):
            addp(sw[sw.heure.isin(hours)].trajets.sum(), sw.trajets.sum())
        swe = h[(h.member_casual == mc) & (h.type_jour == "week-end")]
        addp(swe[swe.heure.isin(range(10, 16))].trajets.sum(), swe.trajets.sum())
        addp(sw[sw.heure.isin([7, 8, 16, 17, 18])].trajets.sum(), tot[mc])
        mo = m[m.member_casual == mc]
        addp(mo[mo.mois.between("2026-05", "2026-09")].trajets.sum(), tot[mc])
        r = mo.trajets.max() / mo.trajets.min()
        vals.update({fmt(r, 1), fmt(r, 0)})
        addp(b.loc[mc, "trajets_boucle"], b.loc[mc, "trajets_avec_2_stations"])
        addp(b.loc[mc, "trajets_avec_2_stations"], b.loc[mc, "trajets"])
    for mo in m.mois.unique():
        sub = m[m.mois == mo]
        addp(sub[sub.member_casual == "casual"].trajets.sum(), sub.trajets.sum())
    pk = {mc: h[(h.member_casual == mc) & (h.type_jour == "semaine") & (h.heure.isin([7, 8, 16, 17, 18]))].trajets.sum()
          for mc in ("member", "casual")}
    addp(pk["member"], pk["member"] + pk["casual"])
    vals.add(fmt(pk["casual"], 0))
    vals.add(fmt(b.loc["casual", "part_boucle_pct"] / b.loc["member", "part_boucle_pct"], 1))
    addp(tot["member"], tot["TOUS"]); addp(tot["casual"], tot["TOUS"])
    for mc in ("member", "casual", "TOUS"):
        vals.add(fmt(u.loc[mc, "mediane_min"], 1)); vals.add(fmt(u.loc[mc, "moyenne_min"], 1))
    vals.add(fmt(100 * (u.loc["casual", "mediane_min"] / u.loc["member", "mediane_min"] - 1), 0))
    vals.add(fmt(100 * (u.loc["casual", "p90_min"] / u.loc["member", "p90_min"] - 1), 0))
    exp = json.load(open(os.path.join(ROOT, "config", "attendus_v3.2.json"), encoding="utf-8"))
    addp(exp["flags"]["start_station_missing"], tot["TOUS"]); addp(exp["flags"]["end_station_missing"], tot["TOUS"])
    for mc in ("member", "casual"):
        vals.add(fmt(a09.loc[mc, "depart_sans_station_pct"], 1))
    return vals


def check_numbers():
    vals = allowed_values() | set(CONST) | STRUCT
    unknown, checked = [], 0
    for path in sorted(glob.glob(os.path.join(LTX, "sections", "*.tex"))):
        for ln, line in enumerate(open(path, encoding="utf-8"), 1):
            line = line.split("%")[0] if not re.search(r"\\%", line) else line
            text = re.sub(r"\\(ref|label|file|url|input|includegraphics)\{[^}]*\}", " ", line)
            text = re.sub(r"\d+(?:\.\d+)?\s*(?:cm|mm|pt|em|ex|\\linewidth|\\textwidth)", " ", text)  # layout dimensions
            text = text.replace("\\,", "").replace("{,}", ",")
            for n in NUMBER.findall(text):
                checked += 1
                if n.replace(",", "") not in vals:
                    unknown.append(f"{os.path.basename(path)}:{ln}: {n}")
    return unknown, checked


def main():
    generate_latex_tables.main()
    unknown, checked = check_numbers()
    if unknown:
        print("UNMATCHED NUMBERS (check them, or add them to CONST with their source):")
        print("\n".join("  " + u for u in unknown))
        sys.exit(1)
    print(f"Numbers quoted in the text: {checked} checked, all matched.")
    if "--no-compile" in sys.argv:
        return
    build = os.path.join(LTX, "build")
    os.makedirs(build, exist_ok=True)
    # xelatex is called directly (latexmk needs Perl); 3 passes for contents, cross-references
    # and LastPage. The previous log is removed so that a stale build is never analyzed.
    logpath = os.path.join(build, "report.log")
    if os.path.exists(logpath):
        os.remove(logpath)
    for _ in range(3):
        r = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory=build", "report.tex"],
                           cwd=LTX, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            break
    log = open(logpath, encoding="utf-8", errors="replace").read()
    errors = re.findall(r"^! .*", log, re.M)
    missing = re.findall(r"Missing character.*", log)
    undef = re.findall(r"(?:Reference|Citation) `[^']+' on page \d+ undefined", log)
    over = [float(x) for x in re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide\)", log)]
    pages = re.findall(r"Output written on .*?\((\d+)\s+page", log, re.S)
    print(f"xelatex: exit code {r.returncode}; pages: {pages[-1] if pages else '?'}")
    print(f"errors: {len(errors)}; missing characters: {len(missing)}; undefined references: {len(undef)}; "
          f"overfull boxes > 2 pt: {sum(1 for o in over if o > 2)} (max {max(over) if over else 0:.1f} pt)")
    for e in errors + missing[:5] + undef[:5]:
        print("  " + e)
    if r.returncode != 0 or errors or missing or undef:
        sys.exit(1)
    shutil.copyfile(os.path.join(build, "report.pdf"), PDF_OUT)
    print(f"PDF: {os.path.relpath(PDF_OUT, ROOT)}")


if __name__ == "__main__":
    main()
