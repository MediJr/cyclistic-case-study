# Licenses and scope

This repository uses **different licenses for different kinds of content**. Third-party material is **not** covered by any license granted here.

| Content | License | Rights holder |
|---|---|---|
| Original code (section 1) | MIT | LUMU BAMANA MANASSE |
| Original report, figures, aggregated tables and documentation (section 2) | CC BY 4.0 | LUMU BAMANA MANASSE |
| Third-party material (section 3) | Not licensed here | Respective owners |

## 1. Code: MIT License

The MIT License in [`LICENSE`](LICENSE) (Copyright (c) 2026 LUMU BAMANA MANASSE) applies to the original source code written for this project:

- `scripts/` (Python);
- `sql/`;
- `tests/`;
- `config/`;
- the hand-written LaTeX files `reports/latex/report.tex` and `reports/latex/sections/`.

The file `reports/latex/cyclistic-eisvogel.sty` is a **derivative of the Eisvogel template**. It is distributed under the template's BSD 3-Clause license (section 3), with the original copyright notices kept at the top of the file. The project's own modifications to it are also offered under the same BSD 3-Clause terms.

The MIT License does not cover the dependencies used by the code (pandas, NumPy, Matplotlib, PostgreSQL, LaTeX packages), which remain under their own licenses.

## 2. Original content: CC BY 4.0

Copyright (c) 2026 LUMU BAMANA MANASSE. The following original content is licensed under the [Creative Commons Attribution 4.0 International License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/):

- the report `reports/Cyclistic_Professional_Report.pdf` (text, tables and layout choices);
- the charts in `visualizations/`;
- the aggregated result tables in `results/`;
- the documentation: `README.md`, `data/README.md`, `results/README.md`, `docs/` and `reports/latex/README.md`.

Suggested attribution: *"Cyclistic Bike-Share Case Study" by LUMU BAMANA MANASSE, licensed under CC BY 4.0.*

The charts and tables are derived from the Divvy trip data (section 3). Reusing them is also subject to the Divvy Data License Agreement.

## 3. Third-party material: not licensed by this repository

- **Divvy trip data.** Owned by the City of Chicago and made available by Lyft Bikes and Scooters, LLC under the [Divvy Data License Agreement](https://divvybikes.com/data-license-agreement). The Google case study describes the data as made available by Motivate International Inc.
  - The agreement allows the data to be used as source material in analyses, reports or studies.
  - It does not allow redistributing them as a stand-alone data set.
  - **No raw or cleaned row-level data are distributed here**; see [`data/README.md`](data/README.md).
- **Eisvogel LaTeX template.** Copyright (c) 2017–2026 Pascal Wagler and (c) 2014–2026 John MacFarlane, BSD 3-Clause license.
  - Source: <https://github.com/Wandmalfarbe/pandoc-latex-template>, commit `93cc5b8e` (4 July 2026). The copies of `LICENSE`, `eisvogel-title-page.latex` and `eisvogel-added.latex` in [`reports/latex/third_party/eisvogel/`](reports/latex/third_party/eisvogel/) were checked byte for byte against that commit (SHA-256).
  - `reports/latex/cyclistic-eisvogel.sty` is an adaptation of these files. Its header reproduces the full copyright notice, conditions and disclaimer, as required by condition 1 of the license.
  - The PDF report is typeset with this adapted layout. It cites the template in its references ([5]). The full notice, required for redistribution in non-source form by condition 2, is the [`LICENSE`](reports/latex/third_party/eisvogel/LICENSE) file distributed with this repository.
  - In line with condition 3, the names of the Eisvogel authors are used for attribution only. They do not endorse this project.
- **Case-study brief.** The Cyclistic scenario, the names of the company and characters (for example Lily Moreno), and the three guiding questions come from *Case Study 1: How does a bike-share navigate speedy success?* (Google Data Analytics Professional Certificate).
  - They are paraphrased or briefly quoted.
  - The brief itself is not distributed.
- **Fonts embedded in the PDF.** These fonts are not distributed as files:
  - Charis SIL, Fira Sans and Source Code Pro, under the SIL Open Font License 1.1;
  - Computer Modern symbols (CMR10, CMMI10, CMSY10), AMS Type 1 versions under the SIL Open Font License.

  Chart text is rendered as images with Matplotlib's default font (DejaVu Sans).
- **Trademarks.** Divvy, Lyft, Google and Coursera are trademarks of their respective owners.

## 4. Disclaimer

This is an independent educational project. It is not affiliated with, endorsed by or sponsored by Divvy, Lyft Bikes and Scooters, the City of Chicago, Motivate International, Google or Coursera. This file describes the licenses chosen by the repository owner and is not legal advice.
