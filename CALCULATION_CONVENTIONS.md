# Conventions for a new calculation

How a calculation package in this repository is built so that its report, portable
notebook, Mathcad and Blockpad editions and project-record entries match the existing
ones (backwall `end_bent_walls/`, piles `pile_design/`, cap `pier_cap/`, pier wall
`ring_wall/`). Follow this list; the tests named at the end enforce most of it.
Last revised 2026-10-21 (journal-calculation packages on `calc_common`, T027; report definition and citation cards, D-068).

## 0. Two ways to build a calculation

- **Hand-written package** (backwall, piles, cap, pier wall): `model.py` holds the definition list in code; the report, exports,
  widgets, Mathcad and Blockpad builders are written for that calculation. Follow sections 1–7.
- **Data-driven package on `calc_common/`** (the journal calculations C001–C004, C006, C015, C016): the package is its
  `data/` folder (`inputs.json`, `definitions.json`, `checks.json`, `tables.json`, `sections.json`, `text.json`,
  `references.json`, `sources.json`, `journal_blocks.xml`) plus thin modules that bind `calc_common` (the modules
  `scripts/build_journal_calc_data.py` writes) and a hand-drawn `schematics.py`: a few scene functions built on the
  `calc_common.schematics` toolkit (`Svg`, `Frame`, dimensions, load arrows, moments, gauges, bar comparisons, small
  plots) and a `drawer(name)` map that gives every definition its own "What it represents" drawing from the current
  case, with the result in red in the right-hand panel. `tests/test_journal_calc_packages.py` fails when a definition
  falls back to the generic term diagram. The shared framework supplies the engine, MathML, report, exports, Colab UI,
  Blockpad editions (standalone and journal, with the same verification steps as the backwall builder) and the portable
  notebook. A calculation that starts as a journal module is imported with `scripts/import_journal_calc.py`, drafted with
  `scripts/build_journal_calc_data.py`, then authored (titles, overview, captions of referenced values, check ratios, key
  results). Rebuild chain: `build_journal_calc_notebooks.py` → `build_journal_calc_bpads.py` (→ `--journal`) →
  `export_journal_calc_reports.py`; `tests/test_journal_calc_packages.py` enforces currency and the journal fidelity
  (every former journal definition reproduced to 1e-9). These packages have no Mathcad edition.

## 1. Package layout

```
<calc>/
  model.py        definitions (name, expr, unit, caption, section, refs), evaluate(case), default_case()
  notation.py     symbol() and MathML rendering; reuse pier_cap.math_notation primitives
  report.py       build_report(e) -> self-contained HTML (Plotly inline, native MathML, no network)
  exports.py      case_json / load_case / checks_csv / WRITERS for the notebook export buttons
  widgets.py      the Colab notebook UI (ipywidgets), calls exports.WRITERS
  schematics.py   "What it represents" SVG per equation (QC drawing of the current case)
  data/
    references.json   {key: {"code": "LRFD|SDG|SDM|...", "article": "...", "governs": "..."}}
    sources.json      registered project sources (ids, paths, sha256) the calculation reads
```

- Every equation is a definition evaluated by the shared engine (`pier_cap.engine`), so the
  report, the Mathcad sheet, the Blockpad edition and the tests all walk the same list.
- Inputs carry a caption, unit, source id and status; the report's inputs table prints them.

## 2. Report

- MathML only, rendered through the package's `symbol()`. `symbol()` must tag the outer
  `<mi>` or `<msub>` with `data-var="<name>"` (see `end_bent_walls/notation.py`); that is
  what makes the hover definition cards work. Block equations are
  `symbol = formula = substituted values = result` (`definition_mathml`).
- Under every equation: a `details.qc` "What it represents" with the schematic and a term
  legend (symbol, meaning, value, source).
- Citations: `_refs(keys)` renders `"{code} {article}"` joined with `"; "` inside
  `class="ref"` elements, from `data/references.json`. Prose citations in captions
  ("LRFD 5.10.3.2 / 5.10.6") also work: the cards script recognises them.
- Append the cards before `</body>`:

  ```python
  body = ''.join(parts) + REPORT_SCRIPT
  try:
      from report_cards import cards_html, cite_data, prose_pieces
  except ImportError:          # portable package without the cards module
      pass
  else:
      body += cards_html(cite_data(REFERENCES, extra_pieces=prose_pieces(body)))
  ```

  The cite-data block uses `type="application/report-cards+json"`; plain
  `application/json` blocks are read as Plotly figures by the report tests.
- Toolbar with Expand/Collapse/Print; sections as `details.report-section` with ids so
  links and the cards' "Go to definition" can open them.

## 3. Code excerpts (citation cards)

- Register the calculation in `code_excerpts/library.json` under `citation_sources`:
  `{"references": "<calc>/data/references.json"}` and/or `{"scan": ["<calc>/*.py"]}`.
- Run `scripts/build_code_excerpts.py`. Anything "not located" gets a `manual` entry in
  `code_excerpts/overrides.json` (0-based PDF page, rectangle in page points) or a
  `journal` entry reusing a GetRefs excerpt from `journal/References/`.
- The code PDFs live outside the repository (`../code_library`, or `D2MPDB_CODE_LIBRARY`);
  the tracked store is `code_excerpts/excerpts.json` plus `code_excerpts/pages/*.png`.
  `tests/test_report_cards.py` fails when citations change without a rebuild.

## 4. Portable notebook

- `scripts/build_<calc>_notebook.py` embeds the package as a zip in the setup cell
  (`revision` + `PACKAGE` lines). Its `package_files()` includes `<calc>/*.py`,
  `<calc>/data/*.json`, `pier_cap/*.py`, `report_cards/*.{py,js,css}`,
  `code_excerpts/excerpts.json` and `cited_page_files(repo, references=[...], scan=[...])`
  so Colab-built reports carry the excerpt images. Use `*repo.glob(...)` for optional
  files so the portable-build test's temporary root still builds.
- The notebook's setup cell must accept the package paths it embeds (`report_cards/`,
  `code_excerpts/`), and its test must compare the embedded package with the working tree
  (`test_embedded_package_is_current_and_intact` pattern).

## 5. Mathcad and Blockpad editions

- `scripts/build_<calc>_mathcad.py` writes the distilled `.xmcd` from the same definition
  list (`scripts/mathcad_sheet.py`), verifies every value against the notebook, and embeds
  the notebook package revision. `scripts/build_<calc>_bpad.py` (+ `--journal`) writes the
  Blockpad editions through `scripts/bpad_sheet.py` and verifies them with the independent
  Blockpad-syntax evaluator.
- Rebuild chain after any package, `pier_cap` or `report_cards` edit, per calculation:
  notebook → Mathcad → Blockpad (standalone, then `--journal`). The
  `test_committed_*_equal_a_fresh_build` tests say which edition is stale.

## 6. Project record (when a report becomes a registered source)

- Export from the unchanged `selected_case.json` with the current package; write the report
  as `<Title> <m-d>.html` beside the previous one and keep the previous one.
- Register with an adoption script kept under `project_current/coherence/evidence/<date>-<topic>/`
  (pattern: `2026-10-20-report-cards/adopt_reports.py`): compare check registers old vs new,
  rewrite only the affected `source_register.csv` lines, add the `D-0xx` decision row, update
  the READMEs (keep each file's own line endings), write `source_receipt.json`.
- Pile-style reports need the dated case copy, check CSV and data table beside the report
  for their `--check`. Then run `tools/project_coherence.py --write-report`,
  `scripts/build_lineage_graph.py`, and the atlas gate (`design_atlas.refresh status`).

## 7. Tests that enforce this

- `tests/test_<calc>.py` (engine, checks, report content, exports round trip)
- `tests/test_report_cards.py` (excerpt store currency, cards in every report, portable package carries crops)
- `tests/test_<calc>_mathcad.py`, `tests/test_<calc>_bpad.py` (editions current)
- `tests/test_<calc>_notebook.py` (embedded package current, extracted package runs alone)
- `tests/test_project_coherence.py`, `tests/test_lineage_graph.py`, `tests/test_design_atlas.py`

Run them without `python -X utf8` (the subprocess tests decode cp1252 output).
