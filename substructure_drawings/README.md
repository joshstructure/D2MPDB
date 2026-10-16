# End bent and pier DXF (FDOT format)

[`output/B4_Substructure_EndBents_Pier.dxf`](output/B4_Substructure_EndBents_Pier.dxf)
is one DXF with plans, elevations, reinforcement elevations, sections and
details for End Bent 1, the pier and End Bent 2, plus a reinforcing bar list.
It is generated from the registered FreeCAD model
(`project_current/geometry/freecad`, the current file hash is in
[`output/manifest.json`](output/manifest.json)). Review copies are in
[`output/previews/review_sheets.pdf`](output/previews/review_sheets.pdf). The
DXF is preliminary: it is not selected as a project source, and it does not
represent engineering acceptance.

## Sheets

| Sheet | Content | Scale |
|---|---|---|
| B4-1 | End Bent 1 plan, elevation (looking back station), tables of elevations, pedestal tops, pile cutoffs, notes | 3/8" |
| B4-2 | End Bent 1 reinforcement elevation | 1/2" |
| B4-3 | End Bent 1 sections A-A (between piles), B-B (at pile) | 3/4" |
| B4-4 | End Bent 1 section C-C (at CL beam), pedestal plan and elevation | 3/4" |
| B4-5 | End Bent 1 views D-D and E-E (cheek walls, lug WWR limits) | 3/4" |
| B4-6 | Pier plan, broken elevation (looking ahead station), tables, notes | 3/8" |
| B4-7 | Pier reinforcement elevation | 1/2" |
| B4-8 | Pier sections A-A, B-B, C-C | 3/4" |
| B4-9 | Pier pedestal plan and elevation, end view D-D | 3/4" |
| B4-10 to B4-14 | End Bent 2, as End Bent 1 (looking ahead station) | |
| B4-15 | Reinforcing bar list with bending diagrams | |

Model space holds every view at full size (1:1, international feet,
`$INSUNITS = 2`), with annotation sized for the sheet scale. Each paper-space
layout is an 11 x 17 sheet with an FDOT-style border and scaled viewports.
MicroStation imports the layouts as sheet models and model space as the
drawing model. The border approximates the FDOT structures border cell. Replace it with
the FDOT CADD border when the sheets are finalized. Bridge number, FPID,
county, road and EOR fields are blank because no project source gives them.

## Conventions applied

- **Bar marks (SDM 4.3.C-E, 4.3.10.B).** Each mark is the bar size followed by a designation, unique within
  a support. The letters I, O and Q are not used. A letter stands alone when only one bar type
  has that application; otherwise numbers run from 1 with no gaps. End bents use
  A cap longitudinal, B cap stirrups and hoops, C cap U-bars between piles,
  D backwall, E cheek walls and F pedestals. The pier uses A to C as above, D cap
  end U-bars and E pedestals. Backwall verticals that differ only in length with
  the crowned top share one mark (5D1, VARIES). Each length and its count are listed in the bar
  list notes. [`output/bar_mark_register.csv`](output/bar_mark_register.csv)
  maps every native FreeCAD bar (object name, label, current model `Mark`) to
  its SDM mark. The marks are not written into the FCStd.
- **Representation (SDM 4.3.B, 4.3.7).** Plan and elevation views draw the
  first and last bar of each uniform series. Each series is called out
  `count~mark` with its spacing dimensioned (SDM 4.3.1.C). Stirrups use the
  established CAD_AI symbol: a line at the bar station with filled end dots.
  Sections show all cut bars as filled circles at true size. Each section also shows the
  nearest in-plane bar of every series within 1'-3" beyond the cut, drawn
  with double lines (3/4" scale is at least 1/2", SDM 4.3.7.B).
- **Dimensions (SDM 2.11).** Concrete is dimensioned to 1/8" and bar spacing to
  1/4". Bar-list lengths round to the nearest inch, elevations to 0.001 ft, pile
  cutoffs to 0.1 ft and stations to 0.01 ft. Dimension text uses
  feet-inch-fraction form (4'-0 1/2", 7 1/2", 3/4") with diagonal stacked
  fractions. The dimension style uses architectural units with DIMLFAC 12, as
  in the FDOT-seeded working DXF. The orientation follows SDM 2.8.B: End Bent 1
  is drawn looking back station and the others looking ahead station, with
  stationing increasing left to right in sections.
- **Levels.** Every element is on an FDOT CADD Standard Level (table dated
  10-25-2023), as listed in `fdot.LEVELS`. The levels used are:
  - Concrete: SubStrConc (cap, backwall, pier wall) and SubStrConc2 (cheek walls, pedestals).
  - Piles: PileConc and PileSteel.
  - Context: BearingPadMisc, WallMSEPanel and AppSlabConc (landing slab).
  - Reinforcement: Rebar, with Rebar2 for the WWR limits.
  - Annotation: CL_Major, CL_Minor, BaseLineSurveyPGL, Dimension, Leader, TextStructures, Symbols, Tables, Border and TextStructShtNo.
  - Viewports: ClipBorder_dp (set not to plot).

  Hidden lines are on the matching `_h` levels. Colors, weights and the "DGN Style n" linetypes follow the FDOT-seeded working
  DXF, so MicroStation maps them back to standard line codes. Apply the FDOT
  workspace level library (ByLevel) after import. The centerline symbol is a
  small block (`FDOT_CL_SYMBOL`), so it displays in any font.

## Bringing it into MicroStation / OpenBridge

1. Open or reference the DXF with the FDOT workspace active and choose
   **Feet** as the DXF units.
2. Check a known dimension before copying, for example the End Bent 1 cap at 19'-7"
   and 20'-11" with the cheeks.
3. Keep the level names. Set elements to ByLevel so the FDOT level
   symbology applies.
4. Use the layouts as sheet models, or attach model space to your own
   sheets at the scales above. Text and dimensions are already sized for those scales.

## Rebuild

```
.venv\Scripts\python.exe scripts\build_substructure_dxf.py --extract --previews
```

`--extract` copies the registered FCStd to a temporary folder and reads it
with FreeCAD 1.1 `freecadcmd`
([`freecad_extract.py`](freecad_extract.py), read-only). That refreshes
[`data/model_snapshot.json`](data/model_snapshot.json), which holds:
- hidden-line projections
- sections
- every bar centerline, checked against the bar's solid
- the WWR wires

Without `--extract`, the DXF is rebuilt from the committed snapshot, and the
output is byte-identical. `tests/test_substructure_dxf.py` fails when the model hash,
snapshot or generator output no longer match. It also checks the mark rules,
the levels, the units and the sheet layout.

## Open items carried on the drawings

- The model top of the End Bent 1 backwall at the cap ends is 47.192. The
  selected geometry CAD tables give 47.132 (the crown matches). The CAD EB1
  backwall seat is still to be rebuilt from the notebook. Sheet B4-1 carries a
  "MODEL CHECK" note until this is resolved.
- Backwall verticals are labelled as schematic dowels in the model, and their
  embedment is not detailed.
- The pier wall is provisional and has no modeled reinforcement.
- The SDM 12.3.F soil-reinforcement note is included with blank service and
  factored loads.
- Standard Plans Index 415-001 bar type numbers are not assigned. The bar
  list gives out-to-out dimensions against its own bending diagrams. Assign
  the type numbers with the FDOT Rebar program.
- Existing coordination findings in the model remain open, as the FreeCAD
  README records (COH-024/025). The drawings show the model as it is.
