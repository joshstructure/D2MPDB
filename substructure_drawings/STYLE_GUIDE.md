# Substructure drawing style guide

Rules for the generated FDOT substructure sheets (`substructure_drawings/`),
collected so that the same mistakes are not made again.  Every rule has an
id; the generator code, `STYLE_PLAN.md`, `SYMBOLOGY_PLAN.md` and the review
checklist at the end refer to these ids.  When a rule is added or changed,
add it here first, then change the generator, then re-check the previews.

Sources, in order of authority:

1. FDOT Structures Detailing Manual (SDM), January 2026 (`2026 SDM.pdf`):
   2.11 dimensioning, 2.14/2.16 annotation, 4.3 reinforcing (4.3.7 bars in
   section).
2. FDOT CADD Manual 625-050-001, November 2024 (`caddmanual2025.pdf`) and the
   FDOT CADD Standard Level Table 10-25-2023 (see `SYMBOLOGY_PLAN.md`,
   `fdot.py`).
3. The FDOT sample plan set PA-PS-0037.1 (BCC Engineering, 2025), sheets
   B1-15 (end bent plan/elevation), B1-17 (end bent details, construction
   joint and geotextile details), B1-19 (cheek wall sections J-J, H-H),
   B1-20 and B1-34 ("NOT SHOWN FOR CLARITY" notes).
4. The engineer's review markups of 2026-10-17 (`review_sheets.pdf` markups,
   logged in section M below).  A markup is a standing instruction: it
   applies to every sheet, not only to the spot it was written on.

Reading the sample set: compare at the same zoom (crop both PDFs with
`tools/zoom_pdf.py`), symbol by symbol (flags, arrowheads, dashes), not by
general impression.  Several of the mistakes below came from reading a
symbol at page scale.

## A. Annotation placement

- **A1 Annotations keep clear of linework and of each other.**  Labels,
  leader texts, tables and dimension texts are placed in open space; a
  text may cross a line only when no open space exists, and then it is
  masked (B2).  The layout check (`Composer.check`, `cad.boxes_cross`) must
  report no crossings between views, and the previews are inspected for
  crossings inside a view.  Markups: "Fit annotations to minimize overlap
  with linework", "Prevent overlap of annotations as much as possible",
  "Place annotations in places that don't overlap linework".
- **A2 Separate annotations read as separate.**  Unrelated texts are at
  least one line pitch apart (1.75 text heights) and never share a landing
  or a column; a multi-line callout (BEGIN BRIDGE / FFBW END BENT 1 /
  STA.) is placed where it cannot merge with a neighbouring label.  Markup:
  "Create separation between separate annotations so they don't appear as
  the same annotation".
- **A3 Leaders to bars meet the bar at an angle.**  A leader never runs
  along or parallel to the bar it points to, because the reader cannot see
  where the bar ends.  The leader is a horizontal landing beside the text
  and an angled segment (30 to 60 degrees to the bar) ending in the arrowhead
  on the bar.  Several bars of one callout fan from one knee.  Markup on
  the elevation callouts (5~6A1, 4~6A3 (EF), 4~8A2).
- **A4 Elevation points in plan and elevation.**  Every lettered point of the
  table of elevations is called out in the elevation and, where it has a
  plan location (cheek wall tops, backwall top at the ends and at the PGL,
  cap top at the ends), also in the plan, as on sample sheet B1-15.  Points
  without a plan position (bottom of cap, bottom of cheek lug) appear in
  the elevation only.  Markup: "Show the elevation points on both the plan
  and elevation if applicable".
- **A5 Direction of stationing on every plan-type view**, including the
  pedestal plan detail (sample B1-17), placed clear of labels (upper right
  of the plan, right of the pedestal plan).  Markup on the pedestal plan.
- **A6 Section flags are the FDOT "L" flag.**  A heavy tick along the cut, a
  short heavy base toward the viewing direction, a solid wedge on the
  outside of the L (beyond the base, thick at the corner, tapering in the
  viewing direction) and the letter inside the L beside the tick (sample
  B1-15/B1-17).  The wedge is never drawn inside the L.  Markup: "The arrow
  head triangles should fill to the outside not the inside".
- **A7 Centerline labels by leader** (centerline glyph before the name:
  "CL BEARING", "CL CAP & CL PILES"), the leaders in open space, never under
  the stationing arrow or over the dimension rows (B4-1 markup).
- **A8 Pile numbers** in circles beside the pile bottoms; the pile
  description leader and the "PT." leaders stay clear of the number circles.

## B. Dimensions

- **B1 Text that does not fit is pulled out with a line to its dimension.**
  The value goes beside its space (in the free half of the neighbouring
  space or beyond the end of the row) or just below the row, and a plain
  line (no arrowhead) runs from the text to the dimension line so the
  reader sees which dimension it belongs to.  Values are never stacked on a
  second row.  Markups: "Add line/arrow when the dim doesn't fit right so we
  can see which one it is", "If a dim text doesn't fit pull it out and add
  a line pointing to the dim".
- **B2 Dimension text is masked.**  Dimension text carries an opaque
  background in the drawing background colour, so where a dimension line,
  extension line or object line passes under the text the text wins.
  Markup: "When there are overlapping dims and dim lines have the text have
  a fill so that it blocks out the line underneath and retains and
  prioritizes the dim text".
- **B3 Extension lines reach the feature.**  A dimension's points sit on the
  feature dimensioned (cap top corner, end of a centerline, backwall top),
  so the extension lines run from the dimension line to just short of it
  (the dimexo gap).  A row of dimensions over features at different
  heights has its points at those heights, not at one common level far
  from the features.  Markup: "Dim lines should extend closer to the things
  they dim".
- **B4 Reorient a dimension before letting it overlap.**  Example: the pile
  embedment "1'-0" (MIN.) (TYP.)" is a vertical dimension inside the pile
  from the cap bottom to the pile top, with the text outside and a line to
  it (B1), not a dimension floating among the stirrups.  Markup: "Reorient
  dims like this to minimize overlap; put it inside the pile if necessary
  and move the text and add a line to the dim".
- **B5 Embedment across a construction joint is dimensioned.**  Bars that
  cross a construction joint (backwall verticals into the cap) get an
  embedment dimension "x'-x" (MIN.)" from the joint to the bar end (sample
  B1-17, "1'-6" (MIN.)").  Markup: "Need to show the embed dim for the bars
  crossing the construction joint".
- **B6 Precision and format** (SDM 2.11.3): concrete to 1/8", bar spacing and
  partial bar lengths to 1/4", overall bar lengths to 1", elevations to
  0.001 ft, stations to 0.01 ft; feet-inch-fraction text with the FDOT font
  fraction glyphs (`fdot.ft_in`).  Bar runs read "n~MARK @ s = total",
  equal spaces "n EQUAL SPA @ s = total", a value that varies "@ s MAX.".

## C. Reinforcing (SDM 4.3)

- **C1 Single or double lines by scale (SDM 4.3.7.B).**  Bars not seen end-on
  are single unbroken lines at scales smaller than 1/2" = 1'-0" and double
  unbroken lines at the true bar width at 1/2" = 1'-0" and larger.  Plan and
  elevation (3/8") draw single lines; sections, cheek views, pedestal details
  and the cheek wall sections (1/2", 3/4", 1") draw double lines.  Markup:
  "follow the FDOT SDM requirements for when to show rebar as a single line
  versus actual width; it is based on the scale of the detail".
- **C2 End-on bars** are filled circles at true size (SDM 4.3.7.D), the same
  symbol on every sheet; stirrup ends in elevation are the same dots.
- **C3 Representative reinforcement** in plan and elevation: the first and
  last bar of each run (SDM 4.3.B/C), with the note saying so; sections show
  every bar in the cut plane plus the nearest in-plane bar of each series
  within 1'-3" beyond the cut.
- **C4 Overlapping bars get daylight.**  When two in-plane bars would draw on
  the same line (a backwall vertical over a hoop leg), the shorter bar is
  offset by about 0.03" on paper away from the nearest face, so each bar
  end stays visible.  Markup: "When bars overlap bump the representational
  line ever so slightly away from each other so there's a little daylight
  and we can see where the bars end".
- **C5 Callouts** sit beside the bars with leaders per A3; one callout per
  series with count, mark and spacing (B6); "(EF)" for each-face bars;
  "x THRU y" for three or more consecutive marks.
- **C6 Open stirrups are standard bars with field-bent hooks.**  No custom
  bending diagram on the bar list; bars are listed by their Standard Plans
  Index 415-001 type and the sheet note reads "FIELD BEND OPEN STIRRUP HOOKS
  AS REQUIRED TO CLEAR PILE HEAD LOCATION."  Markups on B4-9: "Remove this,
  they can refer to the Standard Plans"; note 2 wording.
- **C7 Bar marks** per SDM 4.3 (size + designation, unique within a
  component, numbers from 1 without gaps, no I, O or Q); the FreeCAD rebar
  Mark properties carry the same marks (D-042), so marks are re-applied to
  the model after any cage change (`freecad_marks.py`).

## D. Linework and context

- **D1 No hidden line on top of a visible line.**  The hidden-line projection
  returns hidden edges of the backwall bottom, pedestal bottoms and pad
  bottoms that lie exactly along visible edges on the cap top; such hidden
  edges are dropped before drawing.  Only hidden geometry that reveals
  something (the cap end behind a cheek wall, hidden pad edges) is drawn.
  Markup: "I don't know what these overlapping solid and dashed lines
  represent; see if something needs to be removed".
- **D2 Break symbols only where something is broken.**  A pile break is drawn
  only when a pile body crosses the bottom of the drawn window; a sliver
  of a pile outside the window is no reason for a break.  Markup on pier
  Section C-C: "Remove break line if there is nothing to break".
- **D3 Centerlines are long dash, short dash**, never dash-dot with dots
  (`fdot.LINETYPE_PATTERNS` DGN4 and DGN7, dashes of plotted size on every
  sheet via `LTSCALE_PER_SF`).  Markup: "Centerlines should have dashes not
  dots".
- **D4 Context is minimal.**  Bent sections do not show the landing or
  approach slab ("we want to focus on the end bents").  The MSE wall front
  face is shown only where there is room; otherwise it is omitted with the
  note "MSE WALLS NOT SHOWN FOR CLARITY." and shown in a separate detail
  without reinforcing (sample B1-34 style).
- **D5 Construction joints are shown and named.**  The cap/backwall joint is
  labelled "CONST. JOINT (SEE DETAIL "A")" in the sections and detailed as a
  keyed joint (DETAIL "A", sample B1-17); the cap/pedestal joint is labelled
  "CONST. JOINT" in the pedestal elevation.
- **D6 Reinforcing straps** (MSE soil reinforcement attached to the backwall)
  are shown in the sections as a short line out of the back face at the
  strap elevation, labelled "Δ REINF. STRAP" and dimensioned from the cap
  top, with the Δ legend giving the design responsibility and loads (sample
  B1-17).  They come from the model's schematic strap references (D-045).
- **D7 Geotextile fabric detail** (DETAIL "B", sample B1-17): the back of the
  backwall with the fabric strip and the note "ATTACH TYPE D-5
  (SPECIFICATIONS SECTION 985) GEOTEXTILE FABRIC, 1'-0" WIDE AND FULL HEIGHT
  OF FILL, TO THE BACK OF BACKWALL AT V-GROOVE LOCATIONS WITH AN ADHESIVE
  APPROVED BY THE ENGINEER."  V-grooves are not in the CAD model: the detail
  is schematic and says so until they are modelled.
- **D8 Cheek wall steel** gets, besides the outside views (VIEW D-D/E-E), a
  vertical section through the cheek wall and a horizontal section through
  the cheek/backwall corner (sample B1-19 Sections J-J and H-H), so the
  hooks into the cap and backwall are seen.
- **D9 Hidden pad edges** keep the hidden linetype on BearingPadMisc (the one
  documented ByLevel exception); everything else is ByLevel.

## E. Sheets

- **E1 Sheet set**: for each support a plan/elevation sheet with the
  reinforcement, then details; the bar list last.  Details that do not fit
  go to a further details sheet ("perhaps on the next sheet if there is
  more room"), never squeezed against the frame or over other views.
- **E2 Tables** stay inside the drawing window with a margin to the frame;
  notes are a single numbered column with hanging indents.
- **E3 Notes** say what is representative, where sections are located, what
  is not shown and why, and carry the MODEL CHECK items (removed before
  issue).
- **E4 Status** stays "PRELIMINARY - NOT FOR CONSTRUCTION" until the EOR
  fields are filled.

## F. Symbology

Levels, colours, weights, line styles, fonts and text styles are the FDOT
CADD Manual's (see `SYMBOLOGY_PLAN.md` and `README.md`, Symbology): every
element ByLevel on an FDOT Structures level, layer 0 and Defpoints empty,
FDOT TrueType fonts and FDOT text styles, FDOT font glyphs for the
centerline symbol and fractions, the FDOT Structures Note-Arrow dimension
style.  Dimension blocks hold no zero-length lines (they render as point
markers; this was the source of the "circles" questioned on B4-5).

## G. Review checklist (before any delivery)

Render the previews (`--previews`) and look at every sheet at full size:

1. `manifest.json` `layout_warnings` is empty (views inside their windows,
   no crossings between views).
2. No leader parallel to the bar it points to (A3); no leader under the
   stationing arrow (A7).
3. Every dimension text either sits in its space or has a line to it (B1);
   none crosses a line without a mask (B2); no stacked values.
4. Centerlines show as long-short dashes (D3); no stray break symbols (D2);
   no dashed line over a solid line (D1).
5. Sections at 1/2" and larger draw bars as double lines (C1); overlapping
   bars show daylight (C4).
6. Plan shows the PT. labels (A4) and the stationing arrow (A5); the
   pedestal plan shows the stationing arrow.
7. No landing slab in the sections (D4); construction joint, embedment and
   strap called out (D5, B5, D6).
8. Bar list: no custom bending diagram, note wording per C6, every bar has
   a Standard Plans type.
9. The test suite passes (`tests/test_substructure_dxf.py`), the DXF is
   byte-identical on rebuild, and the snapshot hash equals the registered
   model's.

## M. Markup log, 2026-10-17 (review_sheets.pdf)

| Sheet | Markup (engineer's words, abridged) | Rule | Resolution |
|---|---|---|---|
| B4-1 | Add line/arrow when the dim doesn't fit (1'-0" at the cheek) | B1 | `View.dim` draws a line from an outside text to its dimension line |
| B4-1 | If a dim text doesn't fit pull it out and add a line (3") | B1 | same |
| B4-1 | Show the elevation points on both the plan and elevation | A4 | PT. leaders added to the plan |
| B4-1 | Fit annotations to minimize overlap with linework (90°00'00") | A1 | skew label moved into open space between the beam lines |
| B4-1 | Arrow head triangles should fill to the outside not the inside | A6 | `View.section_cut` wedge outside the L |
| B4-1 | Prevent overlap of annotations (stationing arrow over CL labels) | A1, A7 | stationing arrow placed above the table column, CL labels shortened |
| B4-1 | Place annotations where they don't overlap linework (CL BEAM 1-1 over the spacing row) | A1 | beam labels placed between the beam lines above the spacing rows, as on B1-15 |
| B4-1 | Create separation between separate annotations (BEGIN BRIDGE block and CL BEAM 1-2) | A2 | station block placed above the plan at the PGL, as on B1-15 |
| B4-1 | Overlapping dims: text with a fill that blocks the line underneath | B2 | dimension text masked |
| B4-1 | Reorient dims to minimize overlap; put the pile embedment inside the pile, move the text, add a line | B4 | pile embedment dimension inside the pile |
| B4-1 | Overlapping solid and dashed lines at the cap top: figure out and remove | D1 | coincident hidden edges dropped |
| B4-1 | Don't make leader arrows parallel to the bars | A3 | angled bar leaders |
| B4-2 | Don't show the landing slab | D4 | removed from the sections |
| B4-2 | Dim lines should extend closer to the things they dim | B3 | per-feature dimension points |
| B4-2 | Show a construction joint similar to the examples | D5 | CONST. JOINT (SEE DETAIL "A") leader and DETAIL "A" |
| B4-2 | Need the reinforcing strap, as in the example, now modelled | D6 | strap from the model in the sections, Δ legend |
| B4-2 | Bump overlapping bars apart so bar ends show | C4 | offset of overlapping in-plane bars |
| B4-2 | Show the embed dim for the bars crossing the construction joint | B5 | embedment dimension of the backwall verticals |
| B4-2 | Find a place for a construction joint detail like B1-17 | D5, E1 | DETAIL "A" on the (3 OF 3) sheet |
| B4-2 | Find a place for the geotextile fabric like B1-17 | D7, E1 | DETAIL "B" on the (3 OF 3) sheet |
| B4-2 | Follow the SDM: single line vs actual width by scale | C1 | double lines at 1/2" and larger |
| B4-2 | Add direction of stationing to the pedestal plan | A5 | added |
| B4-2 | If there is not enough room omit the MSE walls and slabs with a note | D4 | MSE front face kept (room exists); rule recorded |
| B4-2 | Centerlines should have dashes not dots | D3 | DGN4 pattern changed |
| B4-3 | Side and top views of the cheek wall steel like B1-19 J-J and H-H | D8 | SECTION F-F and SECTION G-G on the (3 OF 3) sheet |
| B4-5 | Remove the break line if there is nothing to break | D2 | pile break only for a pile crossing the window |
| B4-5 | Not sure what these circles are | F | zero-length lines in dimension blocks removed |
| B4-9 | Remove the bending diagram; refer to the Standard Plans | C6 | diagram removed, open stirrups typed per Index 415-001 |
| B4-9 | Change note 2 to "FIELD BEND OPEN STIRRUP HOOKS AS REQUIRED [TO] CLEAR PILE HEAD LOCATION" | C6 | note changed ("TO" added for grammar) |
