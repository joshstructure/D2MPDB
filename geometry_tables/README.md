# Geometry CAD-table workbook

[`B4_Geometry_CAD_Tables.xlsx`](B4_Geometry_CAD_Tables.xlsx) is one workbook that
calculates the bridge geometry the same way as the
[geometry notebook](../Bridge_Geometry_2%20Beam_V2.ipynb). It fills out the
FDOT-style CAD tables from those results.

**Authority.** The Colab geometry notebook (`CONFIG` + `BridgeModel`) is the source
of truth for all geometry. The CAD model and these CAD tables are built from it,
never the reverse. Beam-design values are the saved results of the two
registered Mathcad runs. Mathcad is not recalculated.

## Tabs

Each tab is followed by a **Method** tab that gives the math notation, a
plain-language explanation and schematics. The schematics are drawn from the
live notebook model.

| Tab | Contents |
| --- | --- |
| Inputs | Every input with provenance: notebook `CONFIG`, Mathcad saved results, designer and template constants |
| Profile & Deck | PGL grades, deck edges, beam offsets, haunch check points |
| Beam Geometry | Physical beam ends, bearings, chords; Dims J, K, P, L and shortening R |
| Camber & Haunch | Closed-form common support drop D, Dims B/C/D, minimum flange haunch, Mathcad deflections |
| FGE | Finished grade elevations at every line and station |
| Bearing Seats | Seat planes, bearing slopes, pedestal tops (A–D, pier E/F), bearing plate data |
| Substructure | Cap tops, pedestal heights, cap corners, pile cutoffs, end-bent backwalls, cheek webs and lugs (D-026/D-033) |
| Beam Data | Bars 5K zones from the Mathcad stirrup layout and FIB bar dimensions |
| Clearance | Exact minimum vertical clearance under the beams |
| CAD FGE / CAD Build-Up / CAD Beam Variables / CAD Bearing Plates / CAD Pedestal Elevs | The tables to place in CADD; CAD Pedestal Elevs also lists cap, pile-cutoff and end-bent wall elevations |
| QC | Every key result compared with the notebook, plus validity checks |

Every calculation and CAD cell is a live Excel formula over named inputs.
Hover over a name in Formulas > Name Manager to trace it.

## Rebuild

```powershell
.venv\Scripts\python.exe scripts\build_geometry_cad_tables.py
```

The script runs these steps in order:

1. Executes the notebook's model cells, the same cells the notebook tests use.
2. Reads the Mathcad results and writes all 31 tabs.
3. Has Microsoft Excel recalculate and save, so the values are cached.
4. Verifies there are no formula errors, QC passes, and the values reproduce the live notebook model.

[`tests/test_geometry_cad_tables.py`](../tests/test_geometry_cad_tables.py) fails
if any source changes without a rebuild. The sources it watches are the notebook,
the roadway XML, both Mathcad runs and this generator.

## Method notes

- The haunch along each beam is an exact quadratic in station, because the PGL is
  straight (brokeback) or one parabola over each beam. The common support drop
  therefore has a closed form, `D = h_req − min[δ_min − t_d − r − d_b − max(m/4, m·t_lo(1−t_lo), m·t_hi(1−t_hi))]`.
  It equals the notebook's extremum search to machine precision.
- Seat planes chord the cambered soffit over each pad. Pedestal tops follow those
  planes, which is the notebook method. The BCC template instead levelled seats
  below a 0.5% slope.
- The notebook is silent on some items, so the BCC example workbook's formulas are
  used for them. Each is flagged on its Method tab:
  - Table of Beam Variables bar constants
  - Dim L = sloped length + R
  - build-up case rule
  - beveled-plate rule
- Not implemented: deck transition mode, and a brokeback PI that falls inside a
  beam. The generator stops and QC fails if either is selected.
