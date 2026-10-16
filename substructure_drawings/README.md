# End bent and pier DXF (FDOT format)

[`output/B4_Substructure_EndBents_Pier.dxf`](output/B4_Substructure_EndBents_Pier.dxf)
is one DXF with plans, elevations (concrete and reinforcement together),
sections and details for End Bent 1, the pier and End Bent 2, plus a
reinforcing bar list. The sheets follow the formatting and configuration of an
FDOT structures plan set (sample PA-PS-0037.1, BCC Engineering, 2025; see
[`STYLE_PLAN.md`](STYLE_PLAN.md)).
It is generated from the registered FreeCAD model
(`project_current/geometry/freecad`, the current file hash is in
[`output/manifest.json`](output/manifest.json)). Review copies are in
[`output/previews/review_sheets.pdf`](output/previews/review_sheets.pdf). The
DXF is preliminary: it is not selected as a project source, and it does not
represent engineering acceptance.

## Sheets

| Sheet | Content | Scale |
|---|---|---|
| B4-1 | End Bent 1 plan; elevation (looking back station) with the reinforcement; table of elevations, pile cutoff elevations, notes, footnote legend | 3/8" |
| B4-2 | End Bent 1 details (1 of 2): sections A-A (between piles), B-B (at piles); pedestal plan and elevation; top of pedestal elevations | 3/4" |
| B4-3 | End Bent 1 details (2 of 2): section C-C (at CL beam); views D-D and E-E (cheek walls, WWR limits) | 3/4", 1/2" |
| B4-4 | Pier plan; broken elevation (looking ahead station) with the reinforcement; end view D-D; tables, notes | 3/8" |
| B4-5 | Pier details: sections A-A, B-B, C-C; pedestal plan and elevation; top of pedestal elevations | 3/4" |
| B4-6 to B4-8 | End Bent 2, as End Bent 1 (looking ahead station; B4-7 is laid out as the mirror image of B4-2) | |
| B4-9 | Reinforcing bar list on the FDOT bar list form | |

Model space holds every view at full size (1:1, international feet,
`$INSUNITS = 2`), with annotation sized for the sheet scale. Each paper-space
layout is an 11 x 17 sheet with an FDOT-style border and scaled viewports.
MicroStation imports the layouts as sheet models and model space as the
drawing model. The border approximates the FDOT structures border cell (0.8"
title band, the sample's column widths). Replace it with the FDOT CADD border
when the sheets are finalized. Bridge number, FPID, county, road and EOR fields
are blank because no project source gives them. The plot stamp outside the
left border names the file, the generator version and the FreeCAD model hash.
It has no clock time, so rebuilds stay byte-identical.

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
  its SDM mark. Decision D-042 wrote these marks into the model's `Mark`
  properties, and the schedules follow them. Controllers give any bar they
  regenerate their default mark. After a regeneration, rebuild with
  `--extract`, then apply [`freecad_marks.py`](freecad_marks.py) through
  the CAD_AI update workflow (job example:
  `CAD_AI/reports/sdm-bar-marks-20261016`). The test fails until the model
  and the drawings agree again.
- **Sheet configuration (FDOT sample).** Each support has one plan and
  elevation sheet: plan at the top, elevation below it showing the concrete
  and the reinforcement together, table of elevations (POINT, ELEVATION) and
  pile cutoff table at the upper right, notes below them, the footnote legend
  (`* DIMENSIONS MEASURED ALONG FFBW`) at the lower left. There are no
  separate reinforcement elevation sheets. The details follow the sample's
  End Bent Details sheets: sections A-A and B-B with the pedestal plan,
  elevation and TOP OF PEDESTAL ELEVATIONS table; section C-C with the cheek
  wall views (1/2", as in the sample).
- **Representation (SDM 4.3.B, 4.3.7).** Plan and elevation views draw the
  first and last bar of each run. Stirrups use the established CAD_AI symbol:
  a line at the bar station with filled end dots. Sections show all cut bars
  as filled dots at true size and the nearest in-plane bar of every series
  within 1'-3" beyond the cut. As on the sample sheets, the in-plane bar is
  drawn as a single line with its bends and 135° hooks, the concrete heavy.
- **Dimensions (SDM 2.11, FDOT sample).** A bar series is one dimension with
  the count, mark and spacing in the text: `4~6B1 @ 9" = 2'-3"`, or
  `4~6B1 @ 9" MAX.` where the model spacing within a run varies.
  Equal spaces of piles and beams read `3 EQUAL SPA @ 4'-6" = 13'-6"`, in
  rows labelled at the left (`PILE SPACING *`, underlined). Odd end spaces
  are separate small dimensions. A value that does not fit is written beside
  its space with a short leader, never on a second row. Concrete is
  dimensioned to 1/8" and bar spacing to 1/4". Bar-list lengths round to the
  nearest inch, elevations to 0.001 ft, pile cutoffs to 0.1 ft and stations
  to 0.01 ft. Fractions are diagonal stacks at 60 % of the text height
  (DIMTFAC 0.6; `{\H0.6x;\S1#2;}` in MTEXT). The dimension style uses
  architectural units with DIMLFAC 12, as in the FDOT-seeded working DXF.
  The orientation follows SDM 2.8.B: End Bent 1 is drawn looking back
  station and the others looking ahead station, with stationing increasing
  left to right in sections.
- **Callouts and symbols (FDOT sample).** Leaders have a filled arrowhead, a
  short horizontal landing and the text after it. Callouts sit beside the
  bars, and one callout may fan several arrows. Consecutive marks read
  `10E04 THRU 10E07`. Centerlines (beam, bearing, cap and piles) are labelled
  with the centerline symbol by leader. Section cuts use the FDOT flag at both
  ends: a short heavy line, a solid flag in the viewing direction and the
  letter beside it. Piles end in a curved break (round-member break for pipe
  piles, S-curve for square piles) with a dash-dot centerline and the circled
  pile number beside the bottom. DIRECTION OF STATIONING is a long thin arrow
  with the text along it.
- **Lettering.** The text styles use the single-stroke engineering font
  `isocpeur.ttf` (ISOCPEUR) slanted 15°. Dimension and callout text is 0.075",
  notes 0.08". View titles are 0.14" on a separate style plotted at 0.35 mm,
  underlined, with the subtitle in parentheses below. Table titles are 0.13".
  The receiving workspace maps the font to the FDOT structures font. The
  STATE OF FLORIDA block uses an upright serif (`times.ttf`).
- **Bar list (FDOT form).** The columns are MARK (SIZE, DES), LENGTH, NO BARS,
  TYP BAR, STY A/G, B to K, N and Ø, with FT-IN values without unit marks
  (`20-5`, `18-8¾`). Each support has a heading row between blank rows.
  Bar types follow Standard Plans Index 415-001 (FY 2025-26). Straight bars
  are Type 1 (B = length). U-bars are Type 11 (B = base, C and D = legs).
  Closed stirrups are Type 4 (B = height, C = width), with hook style 5
  (135°) at A and G. The open stirrups at the piles have their end legs
  turned in plan, which matches no standard type. Their letters refer to the
  bending diagram on the bar list sheet.
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
the levels, the units, the sheet set, the lettering and dimension style, the
dimension and callout text formats and the bar list types. A build reports a
layout warning, and the test fails, when a view leaves its viewport or draws
over another view.

`--previews` renders each sheet with the ezdxf drawing add-on to
`output/previews` (PNG per sheet and `review_sheets.pdf`). The renderer has no
single-stroke font and ignores the TEXT oblique angle, so the previews show
the lettering in Century Gothic Italic (bold italic for view titles). The
renderer also scales linetypes by the viewport scale, so the previews
convert the per-entity linetype scales so that hidden and center lines plot
dashed at their paper size. The DXF itself is not changed. If the PDF is
open in a viewer, the new copy is written as `review_sheets_new.pdf`.
`CAD_AI/reports/dxf-style-review-20261016/tools/crop.py` renders a
paper-inch window of a layout with the same settings.

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
- The open stirrups at the piles (end legs turned in plan) have no Standard
  Plans Index 415-001 type. They are detailed by the bending diagram on the bar
  list sheet. Check the other type assignments with the FDOT Rebar program
  before issue.
- Existing coordination findings in the model remain open, as the FreeCAD
  README records (COH-024/025). The drawings show the model as it is.
