# English report — LaTeX sources

Sources of [`../Cyclistic_Professional_Report.pdf`](../Cyclistic_Professional_Report.pdf): 21 A4 pages, built with XeLaTeX.

This is a faithful English translation of the original French report. The structure, figures, tables, findings and recommendations are unchanged. Only the language, the number format (`6,012,458`, `64.8%`) and the line breaks required by the English text differ.

## Layout

| Path | Role |
|---|---|
| `report.tex` | Main document: class, cover metadata (author, date, period, source), order of the sections |
| `cyclistic-eisvogel.sty` | Layout: fonts, colors, margins, headings, header and footer, tables, boxes, cover page |
| `sections/00_reading_guide.tex` … `13_appendices.tex` | Report text, one file per section |
| `generated/t_*.tex` | Numerical tables **generated** from `results/analysis/*.csv` by `scripts/generate_latex_tables.py`; do not edit by hand |
| `third_party/eisvogel/` | Unmodified copies of the Eisvogel template files used as a basis, and their license |
| `build/` | Intermediate build files (ignored by Git) |

The charts are read directly from [`../../visualizations/`](../../visualizations/).

## Template: Eisvogel

- **Repository:** <https://github.com/Wandmalfarbe/pandoc-latex-template>, by Pascal Wagler and John MacFarlane.
- **License:** BSD 3-Clause. Reuse and modification are allowed provided the copyright notice is kept.
  - The license is copied in [`third_party/eisvogel/LICENSE`](third_party/eisvogel/LICENSE).
  - It is restated at the top of `cyclistic-eisvogel.sty`.
  - The template is cited in reference [5] of the report.
- **Version:** `master` branch, commit `93cc5b8e`. Files copied: `eisvogel-title-page.latex`, `eisvogel-added.latex` and `LICENSE`.

Eisvogel is designed for pandoc. Its layout was transposed into the stand-alone package `cyclistic-eisvogel.sty`:

- KOMA-Script `scrartcl` class;
- colored cover page;
- header rule;
- booktabs tables;
- captions above tables.

Project-specific changes:

- **Fonts:** Charis SIL (body), Fira Sans (headings), Source Code Pro (code), all under the SIL Open Font License;
- **Color palette:** shared with the charts, navy `#1E2761`, blue `#2A78D6` for members, orange `#EB6834` for casual riders;
- **Summary boxes and key-figure cards;**
- **Status labels:** [M] measured fact, [I] interpretation, [H] hypothesis to test.

## Requirements

- MiKTeX 25.12 or TeX Live 2024+, with the **XeLaTeX** engine.
- **LaTeX packages:** `koma-script`, `scrlayer-scrpage`, `fontspec`, `babel` (English), `geometry`, `xcolor`, `graphicx`, `float`, `caption`, `booktabs`, `tabularx`, `array`, `multirow`, `colortbl`, `csquotes`, `setspace`, `tcolorbox`, `enumitem`, `pagecolor`, `afterpage`, `microtype`, `lastpage`, `hyperref`, `xurl`.
- **Fonts:** Charis SIL, Fira Sans and Source Code Pro. MiKTeX and TeX Live ship them as the `charissil`, `fira` and `sourcecodepro` packages.
- **Python 3** with pandas, to generate the tables and check the numbers.

## Build

From the repository root:

```bash
python -I scripts/build_latex_report.py
```

The script:

1. regenerates `generated/t_*.tex` from `results/analysis/*.csv` and `config/attendus_v3.2.json`;
2. checks that every number quoted in `sections/*.tex` matches a value computed from these files, or a documented constant listed in the script, and stops if a number cannot be matched;
3. runs `xelatex` three times (contents, cross-references, total page count);
4. stops on LaTeX errors, missing glyphs or undefined references, and reports overfull boxes;
5. copies the PDF to `reports/Cyclistic_Professional_Report.pdf`.

To check the numbers without compiling, run `python -I scripts/build_latex_report.py --no-compile`.

To compile by hand, run this from `reports/latex/` three times:

```bash
xelatex -interaction=nonstopmode -output-directory=build report.tex
```

No step accesses the database.

## Limits of the automatic number check

The check confirms that each number in the text **exists** among the computed values: CSV values rounded to 0, 1 or 2 decimals, derived percentages and ratios, and documented constants. It does not confirm that the number is quoted **in the right place**. Small integers (days, hours, section numbers) and layout dimensions are ignored. It catches invented or wrongly rounded values, but not a swap between two valid values, so proofreading is still needed.
