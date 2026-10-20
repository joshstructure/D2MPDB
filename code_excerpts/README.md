# Code excerpts for report citation cards

Every calculation report that cites a code provision ("LRFD 5.7.3.3", "SDG 3.13.2.N.3",
"SDM 12.3.F") can show the highlighted provision in a hover card. This folder is the
store those cards draw from.

- `library.json` — the code PDFs (kept **outside** the repository in `../code_library`,
  or the folder named by `D2MPDB_CODE_LIBRARY`), their editions, the page range of each
  volume inside a combined PDF, and the citation sources to collect.
- `overrides.json` — hand entries: scanned pages with a drawn rectangle, GetRefs
  one-page excerpts from `journal/References` to reuse, and pieces to skip.
- `excerpts.json` — the generated store (`scripts/build_code_excerpts.py`). Its
  `inputs_sha256` covers the cited pieces, the overrides and the builder version, so
  `tests/test_report_cards.py` fails when the store is stale.
- `pages/` — tracked page images: `<slug>_crop.png` (context crop embedded in every
  report) and `<slug>_full.png` (full page, embedded once per page).
- `References/` — one-page PDFs with highlight annotations, in the GetRefs naming
  convention. Rebuilt from the library, not tracked.

## Adding a calculation

1. Give the calculation a `data/references.json` in the shared schema
   (`key: {"code", "article", "governs"}`) and render citations through a `_refs()`
   that joins `"{code} {article}"` with `"; "` inside `class="ref"` elements, as the
   backwall and pile reports do. Prose citations in Python sources also work: list the
   files under `"scan"` instead.
2. Add the source to `citation_sources` in `library.json`.
3. Run `scripts/build_code_excerpts.py`; fix anything it reports as not located with a
   `manual` override (0-based PDF page, rectangle in page points).
4. In the report builder append `report_cards.cards_html(report_cards.cite_data(REFERENCES))`
   before `</body>`, and make the calculation's `symbol()` tag glyphs with `data-var`
   (see `end_bent_walls/notation.py`). Variable cards need nothing else.
5. Run `tests/test_report_cards.py`.

Excerpts are copyrighted code pages for the firm's internal calculation records.
