# End bent and pier DXF (FDOT format)

**Generator 2.9.0 (23 October 2026)** writes the dashed linetypes with
FDOT's plotted line code sizes (hidden 0.08 in dash, 0.04 in gap; see
Symbology), and the PNG/PDF previews plot those dashes at their size (the
renderer's dash clamp had drawn every dash and gap one equal length).

**Generator 2.8.0 (22 October 2026)** draws the pier wall of model decisions
D-076 (the wall's reinforcement and annular pile ring plates added to the
CAD model) and D-079 (the plates 1/2 in thick, matching the selected ring
calculation D-078): three new pier sheets (STYLE_GUIDE E10), PIER DETAILS
(4 OF 6) with the PIER WALL ELEVATION (the first and last bar of each run,
the plates hidden, the flags of sections H-H and J-J), (5 OF 6) with
SECTION J-J (through a pile, broken between ring rows 2 and 4, the five
plates cut), the ANNULAR RING PLATE plan and SECTION K-K (the plate on the
pipe with the two continuous 5/16 in fillets), and (6 OF 6) with SECTION
H-H (the horizontal cut through ring row 3). The snapshot (schema 3) reads
the model's `PierWallSteelInputs` and the twenty `PierWallRing*` solids and
adds the wall's own projections; the wall bars are the pier's G family
(5G1 verticals, 5G2 horizontals, 5G3 end U returns, 124 bars) and join the
bar list. The End Bent 2 sheets are now B4-12 to B4-15 and the bar list
B4-16. The model carried the controller's PW- identifiers on the wall
bars ("drawing SDM marks pending", D-076), so the bar list carried a
MODEL CHECK note until the marks were written back (D-042 pattern): D-083
(22 October 2026) wrote 5G1 to 5G3 into the model with `freecad_marks.py`
and the snapshots were re-extracted, so the note is silent; the sheets
still carry the model's own open items (the RING-GRID check of the
selected calculation, the verticals stopping inside the wall). The same
day D-084 put the ring calculation's tension development on LRFD 10th
edition 5.10.8.2.1 (the 72-in end U return legs had answered a 71-in lap
computed without confinement credit; the code lap is 26 in) and D-085 set
the model's legs to 27 in (2 ft 3 in); the snapshots were re-extracted
again without a generator change, so sheet B4-11 dimensions the legs at
2'-3" and the bar list shows 5G3 at 7'-2".

**Generator 2.7.0 (20 October 2026)** rebuilds both DXFs from the model with
revision D-065 (level as-cast bearing seats: the six pedestal tops level at
each pedestal's maximum, eight uniform 2 9/16" pads) and applies the
engineer's seventh markup round ("Reinforcing Sheets.pdf", 2026-10-20, logged
in `STYLE_GUIDE.md` section M): the TOP OF PEDESTAL ELEVATIONS tables list one
elevation per pedestal (a sloped top would get lettered columns with the
letters in the pedestal plan), the pedestal top edge the extractor hands to
the level pad goes back to the pedestal (D13), PT. K is centred in its free
space (new rule and check A25), the 5C callouts point at the middle of their
U-bar runs, the bottom-bar callouts come from above the bar, every
construction-joint leader is routed as Section C-C's, the pile label of
Section B-B threads the dimension row between its arrows, every subtitle is
placed by `View.title` at one gap (E8), the pier's PT. A/PT. B stand above the
cap ends, "(PROVISIONAL)" leaves the pier wall label, the pier pile
description stands beside its pile (A26), the pedestals and pads behind the
pier cheek wall are not drawn in View D-D, and arrowheads point only at drawn
lines while areas take the arrowless area leader (A27; the PIER CAP, END
BENT CAP, closure slab, coping and WWR callouts). The same day, for the DGN
import: both DXFs declare US survey feet (`$INSUNITS` 21, the project DGN's
master units; the values are the model's feet, 1:1), and model space holds
one labelled group per sheet ("SHEET B4-2  END BENT 1 DETAILS (1 OF 3)",
a box on the Border level, the sheet's zones side by side with their
intended scales noted, the groups 60 ft apart) instead of zones 600 ft
apart (E9); and every double-line bar ends square, not round (C8: "that's
how it's actually cut and also it's easier to dim to"). After the first
import, the dimensions chained in a row came in off the row where their
value was pulled out: the DGN importer follows a DIMENSION's moved-text
location, so the style now has DIMTMOVE 0 and every displaced value is a
separate masked MTEXT with the dimension's own text suppressed (B13). The
import still rebuilt the dimensions with its own offsets, so each build also
writes a flat variant, `output/B4_Substructure_EndBents_Pier_flat.dxf` (and
`B4_Model_Plan_flat.dxf`), with every dimension exploded into lines,
arrowheads and masked text as drawn, as a fallback. The engineer keeps real
dimensions, so (21 October) every drawing scale has its own dimension style
("FDOT Structures Note-Arrow 3-8", "... 3-4", ...; the sizes times the scale
factor, DIMSCALE 1) and no dimension carries a DIMSCALE override, which an
import may read as a style scale and shrink the dimension-line offsets with.

**Generator 2.6.0 (19 October 2026)** rebuilt this DXF from the model with
revision D-061 (D-044 weather closure and copings, D-045 strap references,
D-046 cheek hooks, D-047 pedestal edge bars, D-048 backwall extensions, D-053
simplified backwall tops, D-055 backwall vertical coordination, D-059 pier
cheek walls, D-060 their bar marks, D-061 their verticals developed 1'-0"
into the cap) and applies
the engineer's review markups of
2026-10-17, 18 and 19 (three rounds), which are distilled into
[`STYLE_GUIDE.md`](STYLE_GUIDE.md) (every drawing rule has an id there). The
measurable rules are deterministic checks in [`anno_check.py`](anno_check.py),
run on every view by the build; the findings list is empty on every sheet and
the tests fail otherwise. 2.4.0 (the fourth round) added those checks, put
end labels outside the plan in one column, spread label columns evenly, kept
pile numbers under the pulled values, broke every clipped stub, shortened the
centerline dashes so short centerlines still read dashed, put cover values at
their dimensions, joined parallel leaders at one landing, drew full-width bars
at their true positions, ended U-bar runs at their leg dots, centred and
aligned titles, and filled the strap legend from the backwall design calc
(once per bent). 2.5.0 (the fifth round) closes the backwall outlines in the
sections (the top edge came back from the extractor tagged as the landing
slab's), drops the spurious dots at the bar bends (0.001 ft joint segments in
the model's bar polylines), moves the C-C joint callout off the pedestal,
writes the cover and the stirrup callouts in two lines, keeps dimension lines
off parallel bars, stops pointers short of their text, removes the inner-bar
cover of the pedestal elevation, cuts the cheek/backwall interface line in
G-G, lowers the elevation titles, and adds the checks A3, B11, B12 and D13.
Its follow-ups draw the cut backwall top level at the cut (the model's tops
slope along the bent only; MODEL CHECK note), drop the pedestal joint and
chamfer callouts, put every joint tip on the keyway corner (C-C routed as
sketched), give bar columns splayed fans and the pier bearing centerlines one
two-arrow leader, and move Section B-B off the details column; the round-4
markups dimension the pedestal side cover inside the pedestal, drop the
cheek sections' cover values, give each strap stub its own break line, call
out the bottom-bar pair beside a cut pile with one two-arrow leader
("2~8A2 (EF)"), move the pile and strap labels out from between the views,
space the (1 OF 3) sections apart, and add the tips-apart check A21. 2.6.0
draws the pier cheek walls of D-059 (two 4 x 4 ft x 12 in walls on the cap
top, 3 in inside its ends, with a 30 in square panel recessed 3/4 in with a
3/4 in chamfer on the outside face, and a centred #4 mat): in the plan, as
1 ft stubs with break lines in the elevation (the sheet has no height for the
full walls under the stirrup row), whole in the end view D-D (now cut 0.6 ft
under the cap) and on a new sheet PIER DETAILS (3 OF 3) with view E-E and the
sections F-F and G-G through the panel; the mats are 4E1/4E2 and the pier
pedestal bars move to 4F1/4F2 (E = cheek walls, F = pedestals on every
support, D-060 writes the marks into the model). With D-061 (the verticals
developed 1'-0" into the cap) Section F-F dimensions the embedment, and the
check A23 (no leader, pointer or dimension line through another
annotation's text) joins the build after that value and the PIER CAP leader
once collided; A24 (no leader tip within 0.12" of a break line) follows the
pedestal plan markup ("extend these centerlines a bit"): the pedestal plans'
centerlines run 0.35" past their break, and the pier elevation's pile
description, the pier's Section B-B pile label (now beside the cap under
its bottom, since every route to the centerline-label row crossed the 4"
value) and the end bent plans' coping callouts moved off their breaks.

[`output/B4_Substructure_EndBents_Pier.dxf`](output/B4_Substructure_EndBents_Pier.dxf)
is one DXF with plans, elevations (concrete and reinforcement together),
sections and details for End Bent 1, the pier and End Bent 2, plus a
reinforcing bar list. The sheets follow the formatting and configuration of an
FDOT structures plan set (sample PA-PS-0037.1, BCC Engineering, 2025; see
[`STYLE_GUIDE.md`](STYLE_GUIDE.md) for the rules and
[`STYLE_PLAN.md`](STYLE_PLAN.md) for the plan that matched the sample).
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
| B4-2 | End Bent 1 details (1 of 3): sections A-A (between piles), B-B (at piles) with the keyed construction joint, reinforcing strap with its embedment, bar embedment, closure slab and coping; beside them detail "A" (construction joint) over detail "B" (backwall V-groove and geotextile fabric); strap legend and notes | 3/4", 1-1/2", 1" |
| B4-3 | End Bent 1 details (2 of 3): section C-C (at CL beam); views D-D and E-E (cheek walls, WWR limits; D-D carries the flags of sections F-F and G-G); notes and the strap legend | 3/4", 3/8" |
| B4-4 | End Bent 1 details (3 of 3): section F-F (vertical, through the cheek wall) and section G-G (horizontal, through the cheek wall and backwall, monolithic); pedestal plan and elevation; top of pedestal elevations; notes | 3/4" |
| B4-5 | Pier plan with the cheek walls; broken elevation (looking ahead station) with the reinforcement, the cheek walls as 1 ft stubs with break lines; end view D-D (the cheek wall face with its recessed panel, cut under the cap); tables, notes | 3/8" |
| B4-6 | Pier details (1 of 3): sections A-A, B-B, C-C on one row with a common top; notes | 3/4" |
| B4-7 | Pier details (2 of 3): pedestal plan and elevation; top of pedestal elevations under the elevation; notes | 3/4" |
| B4-8 | Pier details (3 of 6): view E-E (left cheek wall, the recessed panel and the bars; carries the flags of F-F and G-G), section F-F (vertical, through the panel, the cap stub under the wall with the 1'-0" embedment of the verticals, D-061) and section G-G (horizontal, through the panel); notes | 3/8", 3/4" |
| B4-9 | Pier details (4 of 6): the pier wall elevation (D-076 / D-079) with the wall reinforcement, the hidden annular ring plates, the piles under the wall and the flags of sections H-H and J-J; notes | 3/8" |
| B4-10 | Pier details (5 of 6): section J-J (through the wall at a pile, broken; the cut pile with its five plates, the horizontals end-on, the nearest verticals), the annular ring plate plan and section K-K (the plate on the pipe pile with its fillets); notes | 1/2", 1-1/2", 3" |
| B4-11 | Pier details (6 of 6): section H-H (the horizontal cut through ring row 3: the cut wall, piles and plates, the verticals end-on, the horizontals and the end U returns in plane); notes | 1/2" |
| B4-12 to B4-15 | End Bent 2, as End Bent 1 (looking ahead station; B4-13 and B4-14 are laid out as the mirror images of B4-2 and B4-3) | |
| B4-16 | Reinforcing bar list on the FDOT bar list form | |

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

- **Style guide.** [`STYLE_GUIDE.md`](STYLE_GUIDE.md) holds the rules (ids A1
  to G, and the markup log M) that the generator, the tests and the review
  checklist follow. In short: bars are single unbroken lines at scales smaller
  than 1/2" = 1'-0" and double lines at the true width at 1/2" and larger (C1);
  dimension text is masked with the drawing background, and text that does not
  fit is pulled out with a line to its dimension (B1, B2); section flags are the
  FDOT L flag with the wedge outside the L (A6); centerlines are long dash,
  short dash, never dots (D3); hidden edges lying on visible edges are dropped
  (D1); and the bar list uses Standard Plans Index 415-001 types 1, 4, 11, 17
  and 18 with hook styles 3, 4 and 5 (C6).
- **Bar marks (SDM 4.3.C-E, 4.3.10.B).** Each mark is the bar size followed by a designation, unique within
  a support. The letters I, O and Q are not used. A letter stands alone when only one bar type
  has that application; otherwise numbers run from 1 with no gaps. End bents use
  A cap longitudinal, B cap stirrups and hoops, C cap U-bars between piles,
  D backwall, E cheek walls and F pedestals. The pier uses A to C as above, D cap
  end U-bars, E cheek walls (D-059), F pedestals (4E1/4E2 before D-060) and
  G the pier wall mats and end U returns (D-076; the end-face verticals are
  the same bar as the face verticals, 5G1).
  Backwall verticals that differ only in length with
  the crowned top share one mark (5D1, VARIES). Each length and its count are listed in the bar
  list notes. [`output/bar_mark_register.csv`](output/bar_mark_register.csv)
  maps every native FreeCAD bar (object name, label, current model `Mark`) to
  its SDM mark. Decision D-042 wrote these marks into the model's `Mark`
  properties, and the schedules follow them. Controllers give any bar they
  regenerate their default mark. After a regeneration, rebuild with
  `--extract`, then apply [`freecad_marks.py`](freecad_marks.py) through
  the CAD_AI update workflow (job examples:
  `CAD_AI/reports/sdm-bar-marks-20261016` for D-042 and
  `CAD_AI/reports/sdm-bar-marks-pier-cheeks-20261019` for D-060: native step on
  a disposable copy, text-level delivery into the registered archive, cold
  reopen, then archive, evidence, manifest, register and decision). The test
  fails until the model and the drawings agree again.
- **Sheet configuration (FDOT sample).** Each support has one plan and
  elevation sheet: plan at the top, elevation below it showing the concrete
  and the reinforcement together, table of elevations (POINT, ELEVATION) and
  pile cutoff table at the upper right, notes below them, the footnote legend
  (`* DIMENSIONS MEASURED ALONG FFBW`) at the lower left. There are no
  separate reinforcement elevation sheets. The details follow the sample's
  End Bent Details sheets: sections A-A and B-B (3/4", with the start of the
  modelled closure slab ending in a break line) beside a column with the
  construction joint and geotextile details A and B (sample B1-17); section C-C with the cheek
  wall views (3/8", so the views and their callouts fit); and a third sheet
  with the cheek wall sections F-F and G-G (sample B1-19 sections J-J and
  H-H) and the pedestal plan, elevation and TOP OF PEDESTAL ELEVATIONS
  table. The strap legend (the delta paragraph) is a LEGEND block beside the
  NOTES on each sheet that draws the strap, as on the sample.
- **Representation (SDM 4.3.B, 4.3.7).** Plan and elevation views draw the
  first and last bar of each run. Stirrups use the established CAD_AI symbol:
  a line at the bar station with filled end dots. Sections show all cut bars
  as filled dots at true size and the nearest in-plane bar of every series
  within 1'-3" beyond the cut. Bars not seen end-on are single lines at 3/8"
  (plan, elevation) and double lines at the true bar width at 1/2" and larger
  (sections, cheek views, pedestal details, cheek wall sections), with their
  bends and hooks, the concrete heavy (SDM 4.3.7.B). Where two in-plane bars
  would draw on one line the shorter is offset slightly so both ends show.
- **Dimensions (SDM 2.11, FDOT sample).** A bar series is one dimension with
  the count, mark and spacing in the text: `4~6B1 @ 9" = 2'-3"`, or
  `4~6B1 @ 9" MAX.` where the model spacing within a run varies.
  Equal spaces of piles and beams read `3 EQUAL SPA @ 4'-6" = 13'-6"`, in
  rows labelled at the left (`PILE SPACING *`, underlined). Odd end spaces
  are separate small dimensions. A value that does not fit is written beside
  its space or on the far side of the row, with a pointer to its dimension
  line (one piece square to the row when the dimension is under the text,
  otherwise a landing along the text and an angled piece), never on a
  second row (STYLE_GUIDE B1, B7). Dimension text carries a background fill in the
  drawing colour, so it wins over any line under it. Concrete is
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
  short horizontal landing and the text after it. A leader meets its bar at an
  angle and never runs along it. Callouts sit beside the bars, and one callout
  may fan several arrows. Consecutive marks read
  `10E04 THRU 10E07`. Centerlines (beam, bearing, cap and piles) are labelled
  with the FDOT font centerline character by leader (`¡ BEARING` displays as
  ℄ BEARING). Section cuts use the FDOT L flag at both ends: a heavy tick
  along the cut, a short heavy base toward the viewing direction, a solid
  wedge outside the L and the letter inside it.
  Piles end in a curved break (round-member break for pipe piles, S-curve for
  square piles), drawn only where a pile body crosses the bottom of the view,
  with a long-dash, short-dash centerline and the circled pile number beside
  the bottom. DIRECTION OF STATIONING is a long thin arrow
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
  Bar types follow Standard Plans Index 415-001 (FY 2026-27), and every bar
  has one. Straight bars are Type 1 (B = length). A bar with one 90° leg is
  Type 10 (B = the long leg, C = the short) and one with two legs on one side
  Type 11 (B = base, C and D = legs), whatever the legs' lengths (the cheek
  horizontals 4E3/4E4, the pile-head U-bars 5C, the pier cap-end bars 5D1/5D2
  and the pedestal U-bars); no bar carries a 90° hook style. Closed stirrups
  are Type 4 (B = height, C = width), with hook style 5 (135°) at A and G. The open stirrups at the piles are Type 5 (an
  inverted U: B = height, C = width, D and E = the feet turned in at the
  open end): the feet are field bent to
  clear the pile heads, as the bar list note says, so the list carries no
  custom bending diagram.
- **Levels.** Every element is on an FDOT CADD Standard Level (table dated
  10-25-2023), as listed in `fdot.LEVELS`. The levels used are:
  - Concrete: SubStrConc (cap, backwall, pier wall) and SubStrConc2 (cheek walls, pedestals).
  - Piles: PileConc and PileSteel.
  - Context: BearingPadMisc, WallMSEPanel (MSE wall front face, geotextile
    fabric), WallConc (MSE copings), SubStrConc2 (closure slab). The landing
    slab is not drawn (D4).
  - Patterning: the WWR limit hatch and the fill behind the backwall in detail "B".
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
  `DGN7` centerlines, `DGN6` baseline/PGL. The patterns are FDOT's plotted
  line code definitions in inches (CADD Manual 2017 update p. 3-12 and FDM
  edition 5.9.3: DGN2 0.08 in dash, 0.04 in gap; DGN4 0.200/0.053/0.03/0.053;
  DGN6 0.32/0.056/0.048/0.056/0.048/0.056; DGN7 0.59/0.053/0.03/0.053;
  `fdot.FDOT_LINE_CODES_IN`), each element at a linetype scale of one paper
  inch in model feet (scale factor / 12; generator 2.9.0, 2026-10-23, the
  hidden dash was 0.12 in with a 0.08 in gap before). A MicroStation DWG/DXF export names the same
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

## Whole-model plan (B4_Model_Plan.dxf)

[`output/B4_Model_Plan.dxf`](output/B4_Model_Plan.dxf) is a second DXF: the
plan of the whole model (bridge and both ramps) looking down, with stationing
increasing left to right, End Bent 1 at the left and End Bent 2 at the right.
Model space is at full size in feet in that plan frame (u = -Y of the model,
v = +X of the model). One 11 x 17 layout, `P-1 GENERAL PLAN`, shows it at
1" = 40' with the FDOT border and notes; a review copy is
[`output/B4_Model_Plan.png`](output/B4_Model_Plan.png). Rebuild with

```
.venv\Scripts\python.exe scripts\build_model_plan_dxf.py --extract --previews
```

What is drawn is what the model itself calls finished: the bridge assembly
groups (decks, beams, haunches, bearings, pedestals, caps, piles, pier wall,
end bent walls, deck barriers), `MSEAssembly.FinishedConcrete` (the mitred
MSE wall panels and the walking slabs), `MSECopingsAndBarriers.FinishedDetails`
(copings, barriers, plinths and returns, the corrected object where one
exists), the end bent weather closures and the schematic geotechnical straps.
Reinforcement, WWR, the MSE leveling footings, fill envelopes, sources, checks
and schedules are left out (`model_plan_manifest.json` lists the objects by
role and the ones skipped). Hidden lines (what lies under the deck and the
slabs) are on the `_h` levels; visible superstructure concrete is on
SupstrConc, beams and haunches on BeamConc, barriers on TrafBarrierConc,
copings on WallConc, walking slabs on AppSlabConc, MSE panels on WallMSEPanel
and the substructure on the levels of the bent sheets. The FFBW of each end
bent and the pier centerline are drawn with their stations, the PGL through
the bridge, the direction of stationing and the ramp names.
[`freecad_plan_extract.py`](freecad_plan_extract.py) writes the snapshot
[`data/model_plan_snapshot.json`](data/model_plan_snapshot.json) (one
hidden-line pass over all components, `fc_hlr.py`), [`model_plan.py`](model_plan.py)
builds the DXF and `tests/test_model_plan_dxf.py` fails when the model, the
snapshot or the generator output no longer match.

## Superstructure typical section (B4_Typical_Section.dxf)

[`output/B4_Typical_Section.dxf`](output/B4_Typical_Section.dxf) is a third DXF:
sheet S-1, TYPICAL SECTION, with two views cut from the registered model
normal to the stationing, looking ahead station (SDM 2.8.B: sheet right is
south, -X): the TYPICAL SECTION at mid-span 1 (Sta. 16+46.89) at 3/8" = 1'-0"
and, under it, the SECTION AT PIER at the Span 1 bearing line (Sta. 16+99.69,
10 1/2 in from the pier centreline) at 1/4" = 1'-0" (the 19'-2" cap with its
callouts fits the sheet width at that scale only), each in its own viewport,
with the FDOT border; a review copy is
[`output/B4_Typical_Section.png`](output/B4_Typical_Section.png). Rebuild with

```
.venv\Scripts\python.exe scripts\build_typical_section_dxf.py --extract --previews
```

[`freecad_typical_section_extract.py`](freecad_typical_section_extract.py)
slices the finished superstructure components of Span 1 (the deck with its
chamfers and drip grooves, the haunches, the two FIB-36 beams and the deck
barriers) with both cut planes, and at the pier also the bearing pads, the
pedestals, the pier cap and the pier wall (bars, ring plates and the piles are
left out), and writes the wires as (u, z) feet, u = -x, to
[`data/typical_section_snapshot.json`](data/typical_section_snapshot.json)
(schema 2, one `sections` entry per cut);
[`typical_section.py`](typical_section.py) draws the cut outlines on the
superstructure levels (SupstrConc, BeamConc, TrafBarrierConc) and, at the
pier, SubStrConc, SubStrConc2 and BearingPadMisc, measures each section on the
model (typical: out to out, clear width between the barriers, beam spacing
and overhangs, slab thickness and PGL elevation at the crown, beam depth,
barrier height, crossfall; pier: cap length and depth, cap top and pedestal
top elevations, pad thickness and width, wall length) and dimensions it in
the FDOT style: on the typical section the clear width and out-to-out rows
above, the overhang / beam spacing / overhang row below with the beam
centerlines, the barrier height and beam depth in a column at the right, the
℄ BRIDGE & PGL centerline stopped short of the symmetric dimension values it
would cross (A1), the crossfall arrows and the PGL elevation at the cut; on
the section at the pier the cap length under the wall stub (the wall broken
0'-9 5/8" below the cap, D12/D15), the cap depth at the right, the PIER CAP,
PIER WALL, pad-on-pedestal callouts and the cap top elevation. Every leader
tip is snapped onto the cut outline (A27; the checker now counts the
superstructure levels as drawn lines). The measured values are in the
manifest (`section`, `section_at_pier`) and the test compares them with the
journal geometry (13'-7" out to out, 12'-0" clear, 8'-7" beams, 6" slab, 2%
crossfall, 19'-2" x 3'-0" cap, the D-065 level seats). The pedestrian fence
enclosure and the handrails are not in the model, so they are not drawn and a
MODEL CHECK note says so; the pier cheek walls, piles and ring plates lie
beyond the pier cut and are referred to the pier sheets.
`tests/test_typical_section_dxf.py` fails when the model, the snapshot or the
generator output no longer match. The Bridge Development Report (`bdr/`)
embeds the sheet as its typical section figure.

## Modules

| Module | Role |
|---|---|
| `freecad_extract.py` | Read-only FreeCAD side: writes the snapshot (projections, sections, bars, WWR, strap context, cheek wall views and sections; the pier cheek walls are cut through their recessed panel, having no backwall to cut by) |
| `fc_hlr.py` | Hidden-line projection helpers shared by the FreeCAD-side extractors (frames, edge records, HLR with role tagging, clip box) |
| `freecad_plan_extract.py` | Read-only FreeCAD side of the whole-model plan: the finished components projected looking down |
| `model_plan.py` | The whole-model plan DXF (`B4_Model_Plan.dxf`, sheet P-1) |
| `freecad_typical_section_extract.py` | Read-only FreeCAD side of the typical section: the superstructure sliced at mid-span 1 |
| `typical_section.py` | The superstructure typical section DXF (`B4_Typical_Section.dxf`, sheet S-1) |
| `support.py` | Derived geometry of one support (cap, backwall, cheek walls, pedestals, piles, elevations) |
| `bars.py` | Bar geometry, SDM marks and Standard Plans Index 415-001 bar shapes and types |
| `fdot.py` | FDOT CADD levels, line styles, text styles, symbols and number formats |
| `cad.py` | DXF document setup and drawing primitives (views, dimensions, flags, polyline offsets); each view records its texts, leaders, dimensions, break lines, clips and centerlines for the checks |
| `anno_check.py` | Deterministic annotation layout checks (STYLE_GUIDE A19): one function per measurable rule, findings carry the rule id |
| `strap_loads.py` | The Δ legend text with the tie-back loads from `data/strap_loads.json` (`scripts/export_strap_loads.py`, backwall design calc) |
| `views.py` | Plan, elevation, sections A-A to C-C, cheek wall views, pedestal views, end view |
| `details.py` | Cheek wall sections F-F and G-G (end bents, and `pier_cheek_section` for the pier walls), section flags, detail "A" (construction joint) and detail "B" (geotextile) |
| `pier_wall.py` | The pier wall sheets (D-076 / D-079): wall elevation, sections H-H and J-J, the annular ring plate plan and section K-K, the AWS fillet weld symbol |
| `sheets.py` | Paper-space border, title block, tables and notes |
| `build.py` | Sheet composition (E1), layout checks, symbology audit, outputs and manifest |
| `freecad_marks.py` | Writes the SDM bar marks back into the FreeCAD model |

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
- the context solids with their role (schema 2: the schematic soil
  reinforcement straps have role `strap` and are drawn in the sections)
- the cheek wall sections (`cheek_sections`: for each cheek wall the cut
  positions and the projected `side_edges` and `top_edges` of sections F-F and G-G)
- the pier wall steel block (`pier_wall`, schema 3): the controller's
  inputs (`PierWallSteelInputs`, inches), the source case and its failed
  checks, the twenty ring plates (pile, row, centre, top and bottom), the
  wall elevation with the hidden plates and piles, the horizontal section
  through the middle ring row and the transverse section through a pile

Without `--extract`, the DXF is rebuilt from the committed snapshot, and the
output is byte-identical. `tests/test_substructure_dxf.py` fails when the model hash,
snapshot or generator output no longer match. It also checks the mark rules,
the levels, the units, the sheet set and its cross references, the dimension
and callout text formats, the bar list types and note, and the style rules that
can be tested (no zero-length lines and masked text in the dimension blocks,
centerlines without dots, offset polylines, dropped coincident hidden edges).
It checks the symbology against the CADD Manual:
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

## Working on the generator

The review loop that each markup round has followed, so the same mistakes
are not made again:

1. Write the rule into [`STYLE_GUIDE.md`](STYLE_GUIDE.md) first (a new id, or
   an amendment, plus a row in the markup log M quoting the engineer), then
   add a check for it to [`anno_check.py`](anno_check.py) if it can be
   measured, then change the generator.
2. Rebuild with `--previews`. The build prints `WARNING` (a view outside its
   window, views drawing over each other, a block in the BRIDGE NO. area, a
   title off its subject) and `NOTE (annotation check)` lines, each with the
   STYLE_GUIDE rule id it fails: text over linework (A1), texts too close or
   overlapping (A2), a leader running along a drawn line (A3), acute leader
   bends and fans leaving toward their text (A10), leaders crossing leaders
   (A11), near-parallel fan arrows (A12), leaders through circled numbers or
   flags (A13), leaders over many drawing lines (A14), tips of different
   callouts too close (A21), pulled values too near a dimension line (B9), a
   pointer touching its text (B11), a dimension line
   along a parallel drawn line (B12), centerlines too short to show dashes
   (D3), clipped edges without a break line (D12), a break line that breaks
   nothing (D15), an open concrete outline in a section (D13), titles off
   centre (E5). Both lists must be empty
   before delivery; they are
   in `manifest.json` (`layout_warnings`, `annotation_overlaps`,
   `anno_rules_checked`) and the tests fail on either.
3. Look at every sheet at full size and crop the places you changed (the
   PDF at 5x to 12x); the checklist is STYLE_GUIDE section G.
4. Run `tests\test_substructure_dxf.py` and `tests\test_model_plan_dxf.py`.
5. Source files hold non-ASCII literals (Δ, °, Ø, ¼ ½ ¾, the ¡ centerline
   glyph) and are UTF-8. An editor or agent that rewrites them in another
   encoding turns them into mojibake in the DXF; the test
   `test_fdot_font_characters` and the glyph test guard this.

## Open items carried on the drawings

- Resolved 2026-10-19 with model decision D-053 (simplified backwall tops):
  the End Bent 1 backwall tops at the cap ends and at the PGL now match the
  selected geometry CAD tables (all nine `WORKBOOK_CHECKS` pass), and sheet
  B4-1 no longer carries a "MODEL CHECK" note for them.
- Backwall verticals are labelled as schematic dowels in the model. Their
  embedment into the cap is dimensioned from the construction joint but not
  otherwise detailed.
- Details "A" (construction joint) and "B" (V-groove and geotextile fabric) on
  the (3 OF 3) sheets are schematic: the joint key and the V-groove locations
  are not in the CAD model, and those sheets carry a "MODEL CHECK" note.
- The backwall tops are level across the wall thickness in the model (two
  planes sloping along the bent to the crown; both faces share the same z at
  the ends and at the crown). The engineer expects a cross slope, so the
  (2 OF 3) sheets carry a "MODEL CHECK" note until the model has it; the
  sections draw the cut top level (D14).
- The pier wall reinforcement and annular ring plates are the model's
  (D-076 / D-079) and are drawn on sheets B4-9 to B4-11. While the model
  carried the controller's PW- identifiers on the wall bars ("drawing SDM
  marks pending") the bar list had a MODEL CHECK note; `freecad_marks.py`
  wrote 5G1 to 5G3 into the model under D-083 (the D-042 / D-060 job
  pattern) and the note goes silent once the snapshot shows the model
  marks (the model's `MarkStatus` says when every wall bar carries its SDM
  mark; a regenerated bar gets a PW- mark again, so rerun the script). The
  wall verticals stop 3 5/16" below the cap bottom and above the wall
  bottom in the model (no anchorage into the cap), and the selected ring
  calculation's RING-GRID check fails at the 3" placement tolerance; both
  are MODEL CHECK notes on sheet B4-9.
- The SDM 12.3.F soil-reinforcement legend carries the tie-back loads of the
  selected backwall case (3.09 kip/ft service, 3.74 kip/ft factored, Strength
  I, from the 19 October evening case), which the backwall design calls
  provisional pending the current analysis loads. The test fails when the
  case changes; rerun `scripts/export_strap_loads.py` and rebuild.
- Resolved 2026-10-19 with model decision D-055 (backwall vertical
  coordination): the four doubled 5D1 verticals are gone, one end bar per
  face sits inside each cheek hook, and each backwall has 44 verticals
  (22 per face at 1'-0" maximum). `Builder.bar_overlap_note` stays as a
  guard and is silent.
- The model has bars tangent to each other: the backwall verticals 5D1
  against the horizontals 4D2 (0.55" centre to centre), the pedestal U-bar
  legs against the cap top bars 6A1 and hoops 6B2 (zero clear), and the 4F2
  legs on the line of the first 4F1 bar. The sections draw them where the
  model has them (C10), so they appear touching.
- The open stirrups at the piles are listed as Type 5 (feet D and E
  dimensioned, no hook style) and field bent to clear the pile heads. Check
  the type and hook style assignments with the FDOT Rebar program before issue.
- The cheek wall verticals 4E1 are to be Type 10 L-bars (engineer's bar-list
  review 2026-10-19), but the model carries them straight, so the list shows
  Type 1 and carries a "MODEL CHECK" note until the model has the legs. The
  backwall verticals 5D1 and horizontals 4D2 are straight bars, Type 1.
- Resolved 2026-10-19 with model decision D-061 (pier cheek vertical
  development): the pier cheek wall verticals 4E1 run straight 1'-0" into
  the cap (57¾" bars, the outer bars 1" inward for the cap cover). Section
  F-F dimensions the embedment and note 5 of sheet B4-8 states it; the
  "MODEL CHECK" anchorage note of 2.6.0 is silent (`Support.cheek_embedment`),
  and the bar list's Type 10 note names the end bent cheek verticals only
  (D-061 supersedes the Type 10 for the pier). The cheek wall structural
  design remains separate.
- The pier elevation shows the cheek walls as 1 ft stubs with break lines
  (E7): at 3/8" the sheet has no height for the stirrup row above 4 ft walls.
  View D-D and sheet B4-8 show them whole.
- Existing coordination findings in the model remain open, as the FreeCAD
  README records (COH-024/025). The drawings show the model as it is.
