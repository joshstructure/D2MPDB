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
  to 0.01 ft. Fractions are the FDOT font fraction characters, tight
  against the whole number (`4'-0½"`, `2'-5⅞"`; see Symbology). The
  dimension style is FDOT Structures Note-Arrow with architectural units and
  DIMLFAC 12, as in the FDOT-workspace DXF export.
  The orientation follows SDM 2.8.B: End Bent 1 is drawn looking back
  station and the others looking ahead station, with stationing increasing
  left to right in sections.
- **Callouts and symbols (FDOT sample).** Leaders have a filled arrowhead, a
  short horizontal landing and the text after it. Callouts sit beside the
  bars, and one callout may fan several arrows. Consecutive marks read
  `10E04 THRU 10E07`. Centerlines (beam, bearing, cap and piles) are labelled
  with the FDOT font centerline character by leader (`¡ BEARING` displays as
  ℄ BEARING). Section cuts use the FDOT flag at both
  ends: a short heavy line, a solid flag in the viewing direction and the
  letter beside it. Piles end in a curved break (round-member break for pipe
  piles, S-curve for square piles) with a dash-dot centerline and the circled
  pile number beside the bottom. DIRECTION OF STATIONING is a long thin arrow
  with the text along it.
- **Lettering.** FDOT text styles and FDOT TrueType fonts (see Symbology).
  Notes, callouts and table values are FDOT Structures (0.0756"),
  dimension text FDOT Structures Annotation (0.0756"). View titles are FDOT
  Bold (Large) (0.125"), underlined, with the subtitle in parentheses below.
  Table titles are FDOT Bold (Medium) (0.10"), section and view letters FDOT
  Structures Views_SectionArrow (0.096"). The border cell lettering is FDOT
  Imprint and the sheet title FDOT_SHEET_DESCRIPTION.
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

  Hidden lines are on the matching `_h` levels. Level symbology is
  described under Symbology.

## Symbology

The DXF follows the FDOT CADD Manual (Topic No. 625-050-001, publish date
November 1, 2024; `caddmanual2025.pdf`, SHA-256 `3074D002...DE222`) and the
FDOT CADD Standard Level Table (10-25-2023,
`fdotcaddstandardleveltable-10-25-2023.xlsx`, SHA-256 `8D2AC22A...735D50`).
Both are recorded in [`fdot.py`](fdot.py) and in the manifest.

- **Levels (5.10.1.3, PDF p. 47).** Every element is on a Structures level
  of the table (`fdot.LEVELS`). Color, line weight and line style are
  ByLevel on every entity, including the contents of the dimension blocks.
  The one exception is the hidden edges of the bearing pads. They keep the
  DGN2 linetype on BearingPadMisc, because the table has no hidden twin for
  that level. Layer 0 is empty and the file has no Defpoints layer:
  ezdxf's dimension definition points are dropped. The build audits all of
  this (`symbology_audit` in the manifest) and the tests fail on any other
  override. Heavy border and table outlines and the section-cut ticks are
  constant-width polylines, which are geometry and not a weight override.
- **Colors (5.10, p. 48).** Default Bentley color table. Bentley 0-7 map to
  ACI 7, 5, 3, 1, 2, 6, 30, 4, as in the FDOT-workspace DXF export.
- **Line styles (5.10.3.2, p. 49).** Bentley line style n is the Autodesk
  linetype `DGNn` (FDOT.LIN): `Continuous`, `DGN2` hidden, `DGN4` and
  `DGN7` centerlines, `DGN6` baseline/PGL. The pattern lengths are those of
  the FDOT-workspace export. A MicroStation DWG/DXF export names the same
  linetypes `DGN Style n`. To write those names for a round trip to
  MicroStation line codes, change the one line `LINETYPE_NAME = "DGN%d"` in
  `fdot.py` to `"DGN Style %d"` and rebuild.
- **Line weights (5.10 Line Weight Symbology, p. 50).** MicroStation weight
  0, 1, 2, 3 ... 13 plot at 0.09, 0.15, 0.20, 0.30 ... 1.06 mm
  (`fdot.BENTLEY_WEIGHT_TO_LW`, the manual's table to weight 30). Text and
  dimensions plot at 0.09 mm, reinforcement at 0.15 mm, concrete at 0.30 mm.
  `$LWDISPLAY` is on.
- **Fonts and text styles (5.12, 5.12.1.1, pp. 52-53).** The styles carry
  the FDOT text style names and heights: FDOT Structures, FDOT Structures
  Annotation, FDOT Structures Views_SectionArrow, FDOT Structures Initials,
  FDOT (Small/Medium/Large), FDOT Bold (Medium/Large), FDOT Mono (Small),
  FDOT_SHEET_DESCRIPTION, FDOT_SHEET_COUNTY, FDOT_SHEET_FPID,
  FDOT_SHEET_SR, FDOT_SHEET_REVISION_DATE and
  FDOT_SHEET_REVISION_DESCRIPTION. FDOT Imprint holds the border cell
  lettering. Fonts are given by file and family: `FDOT.ttf` (family FDOT),
  `FDOTBold.ttf` (family FDOT, bold flag), `FDOTImprint.ttf`,
  `FDOTImprintBold.ttf` and `FDOTMono.ttf`. The FDOT fonts have their own
  12° slant, so the oblique angle is 0 and the width factor 1. The
  revision styles use 0.8. The DXF styles have height 0. Entity heights are
  the FDOT height times the sheet scale factor in model space, and the FDOT
  height in the layouts. MTEXT uses a line spacing factor of 1.05, which
  gives the three-quarter-height line gap of 5.12.1.2.
- **Special characters (5.12 FDOT Special Symbols, p. 54).** The text uses
  the FDOT font characters. U+00A1 is the centerline symbol. U+00BC-00BE are
  ¼ ½ ¾, U+0183-0186 the eighths and U+0187-018E the sixteenths. They were
  checked by rendering the installed fonts. `fdot.FDOT_FONT_GLYPHS = False`
  writes U+2104 (℄) and MTEXT stacked fractions instead, for a receiving
  workstation without the FDOT fonts.
- **Dimension style.** FDOT Structures Note-Arrow with the values of the
  FDOT-workspace export: text style FDOT Structures Annotation, DIMASZ
  0.078", DIMEXO = DIMEXE = DIMGAP 0.038", DIMFRAC 1, DIMTFAC 0.7, DIMZIN 15,
  DIMTMOVE 1, DIMATFIT 1, closed filled arrows. Lines are ByLayer.
- **Printing (7.11, pp. 94-96).** PDF is the required print format. The
  ClipBorder_dp viewports do not plot.

The receiving OBM workstation needs:
1. The FDOT TrueType fonts installed (part of the FDOTConnect workspace).
   The styles find them by family name. Without them the special
   characters show as `¡` and `ƃ`-`Ǝ`. If the fonts cannot be installed,
   rebuild with `FDOT_FONT_GLYPHS = False`.
2. Elements set to ByLevel after import, so the FDOT level library symbology
   governs. The DXF already is ByLayer throughout, with the one documented
   exception above.
3. The right linetype names. Use `DGN2`-`DGN7` with FDOT.LIN (Autodesk, and
   the manual's names), or switch `LINETYPE_NAME` to `DGN Style %d` when
   MicroStation should map the linetypes back to its line codes.

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
the levels, the units, the sheet set, the dimension and callout text formats
and the bar list types. It checks the symbology against the CADD Manual:
line weights, linetype names, text styles and heights, the dimension style,
ByLevel on every entity, nothing on layer 0 or Defpoints, and the FDOT font
characters. A build reports a
layout warning, and the test fails, when a view leaves its viewport or draws
over another view.

`--previews` renders each sheet with the ezdxf drawing add-on to
`output/previews` (PNG per sheet and `review_sheets.pdf`). The renderer draws
text from ezdxf's own font cache, which does not see fonts installed after
it was built. The preview therefore registers the installed
`FDOT*.ttf` files with it and resolves each text style by its family and
bold flag. Fonts installed later are picked up without code changes. On a
machine without the FDOT fonts, the previews use stand-ins (Century Gothic
Italic, Times, Consolas) and plain-text centerlines and fractions. The
renderer also scales linetypes by the viewport scale, so the previews
convert the per-entity linetype scales so that hidden and center lines plot
dashed at their paper size. Pages are 17 x 11 in, and lines plot true size
at their level weights. The DXF itself is not changed. If the PDF is open in a viewer, the new copy is written as
`review_sheets_new.pdf`.
`CAD_AI/reports/dxf-symbology-review-20261017/tools/crops.py` renders
paper-inch windows of the layouts with the same settings, and `clipcheck.py`
there lists model-space text that a viewport clips (measured with the FDOT
fonts).

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
