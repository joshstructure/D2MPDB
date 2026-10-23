# Geotechnical sections

Four longitudinal sections for the geotechnical engineer, cut through the
registered FreeCAD model and the existing-ground survey at the lines marked on
the general plan (2026-10-23). Each section runs from the pier centerline
(match line, Sta. 17+00.57) to at least 100 ft beyond the outermost project
element on its exterior end.

| Section | Plane | Stations |
|---|---|---|
| A-1 Ramp A | 70.0 ft north of the bridge PGL | 14+60.00 to 17+00.57 |
| A-2 End Bent 1 | on the PGL | 14+60.00 to 17+00.57 |
| B-1 Ramp B | 57.0 ft north of the PGL | 17+00.57 to 22+00.00 |
| B-2 End Bent 2 | on the PGL | 17+00.57 to 22+00.00 |

Outputs (`output/`):

- `B4_Geotech_Section_<id>.dxf`: 1:1 in US survey feet, x = station, y =
  elevation; layers EXISTING_GROUND, POND_14D_PROPOSED, CUT_* per element type
  (hatched), PILE_PROJECTED (piles within 15 ft of the plane), grid, title notes
  and an element table (station range, top and bottom elevations).
- `B4_Geotech_Sections.html`: self-contained report; hover a section to read the
  station, existing ground, Pond 14D and the top/bottom of every element under
  the cursor. Scroll zooms, drag pans, double-click resets; 1x/2x/4x vertical
  exaggeration.

## Sources

- Structure: the registered model (`project_current/geometry/freecad`), sliced
  read-only on a copy by `freecad_section_extract.py` (finished components as the
  plan DXF, plus MSE leveling pads and piles).
- Existing ground: `Ex_I-95_Middle` LandXML TIN; Pond 14D: supplied proposed pond
  TIN. Both are cut exactly from their triangles, placed by the verified rigid
  registration of the CAD tooling (`CAD_AI/reports/terrain-20261003/placement.json`).
  Paths and SHA-256 of all terrain inputs are in the snapshot.
- **The survey does not reach the full 100 ft:** on these planes it covers about
  Sta. 15+10 to 21+08. West of that on the A sections and east of it on the B
  sections the sections show no existing ground ("limit of existing-ground
  survey"). A wider survey is needed to fill those ends.
- The B-side windows count the Pond 14D grading as part of the project, so they
  run 100 ft past the east edge of the pond.

No soil layers, borings or water table. Preliminary, not for construction.

## Rebuild

```
.venv\Scripts\python.exe scripts\build_geotech_sections.py --extract
```

`--extract` needs FreeCAD 1.1 and the terrain caches in `CAD_AI`; it rewrites
`data/sections_snapshot.json`. Without it the DXFs and report are rebuilt from
the committed snapshot. Edit `cuts.json` to move or add a plane, then extract.
`tests/test_geotech_sections.py` fails when the model, `cuts.json` or the
generator moves on without a rebuild.
