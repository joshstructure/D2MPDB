# Bridge Development Report (BDR)

`bdr/` generates the FDOT-style Bridge Development Report of the B4 Pedestrian Bridge
over I-95 from the current project record. The outline is FDM Chapter 121 (January
2026): the BDR contents of 121.9.1, the format of 121.9.2 (executive summary, narrative,
self-contained arguments), aesthetics 121.9.3, construction and maintenance 121.9.4,
conclusions 121.9.8, the 30% Structures Plans of 121.9.9 and the submittal checklist of
121.10 (Form 121-A).

Output: [`output/B4_Bridge_Development_Report.html`](output/B4_Bridge_Development_Report.html),
one self-contained file (cover, contents, executive summary, sections 1 to 15, appendices
A to H with the general plan, the generated typical section and elevation, the sixteen
substructure sheets, the geotechnical sections, the calculation index, the source
register, the checklist and the open items). `output/bdr_data.json` is every value the
report read, for review; `output/manifest.json` records the SHA-256 of each source file
and output. `--pdf` prints the PDF with Microsoft Edge (headless).

```
.venv\Scripts\python.exe scripts\build_bdr.py            # HTML + data + manifest
.venv\Scripts\python.exe scripts\build_bdr.py --pdf      # also output/B4_Bridge_Development_Report.pdf
.venv\Scripts\python.exe scripts\build_bdr.py --check    # rebuild to a temporary folder and compare
python -m unittest tests.test_bdr -v
```

## What the report reads

Everything is read as saved; nothing is recalculated (`sources.py`):

- the journal (`journal/D2_I95_Project_Journal.bpad`): Project Information, Materials,
  Bridge Geometry - 2 Beam (stations, PGL, spans, section, fence, caps, bearings), Pile
  Section Properties, Access Geometry and ADA, Loads - Wind Basis, the gravity sheet and
  the two quantity sheets, and the calculation module titles C001 to C018;
- `project_current`: the source register, decisions, the assumptions register, the latest
  coherence review, the selected cases (caps, backwall, pier wall, cheek walls, piles),
  the Pile Data Tables, the check registers and the cap READMEs (FAIL and pending counts);
- the Mathcad beam runs (saved results, through `geometry_tables.sources`);
- the geotechnical sections snapshot and manifest (`geotech_sections/`), the substructure
  drawing manifest, sheet previews and bar-mark register, and the general plan
  (`substructure_drawings/output/`);
- `data/facts.json`: the facts no registered source supplies (district, county, FPID,
  bridge number, the FDM 260 clearance criterion, the notebook vertical clearance) and
  the BDR items the record does not yet answer. Each entry carries a status: `project
  source`, `inferred` (with its basis; confirm before issue) or `to be supplied`.

Items the record cannot answer are printed as flagged placeholders ("To be supplied",
"Pending") and collected in Appendix H; the FDM 121.10 checklist (Appendix G) shows which
submittal elements exist. The test `tests/test_bdr.py` fails when a source file, the facts
or the generator move on without a rebuild, and checks the outline, the embedded figures
and that every flagged item reaches the appendix.

## Figures

`figures.py` draws the typical section from the journal values (schematic FIB-36 shape)
and the elevation on the PGL from the geotechnical sections A-2 and B-2 (model components,
existing ground, Pond 14D). Both are record drawings, not contract drawings. The
sixteen substructure sheets and the general plan are the generator's PNG previews.

## Not engineering acceptance

The report is a generated record document: source selection in `project_current` is not
engineering acceptance, the drawings are preliminary, and the flagged items (geotechnical
report, drainage concurrence, corrosion report, TTC, GRS and precast statements, wall
study, aesthetics level, unit costs, cost, construction time) must be supplied before the
BDR is submitted.
