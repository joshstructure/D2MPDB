# Style plan: match the FDOT sample sheets (PA-PS-0037.1, BCC Engineering, 2025)

Sample: `C:\Users\joshs\Downloads\PA-PS-0037.1.pdf`, sheets B1-15 (p7, End Bent 1-1),
B1-17 (p9, End Bent Details 1 of 4), B1-19 (p11, cheek views), B1-21 (p13, Pier 1-2),
B1-22 (p14, pier reinforcement), B1-23 (p15, pier sections), B1-24 (p16, pedestals),
B1-40 (p32, bar list). Zoomed crops of the sample (`s*.png`) and of the current
generated sheets (`m*.png`) are in `C:\Users\joshs\Desktop\CAD_AI\reports\dxf-style-review-20261016\zoom\`.

Current output: `substructure_drawings/output/B4_Substructure_EndBents_Pier.dxf`
(15 sheets) and `output/previews/review_sheets.pdf`. Generator package:
`substructure_drawings/` (see its README). Rebuild and preview with
`.venv\Scripts\python.exe scripts\build_substructure_dxf.py --previews`.

## A. What the sample does (style specification)

### A1. Lettering
- One slanted (italic) single-stroke engineering font, all caps, wide letter
  spacing, for every annotation, dimension, table and note.
- Sizes on the 11x17 sheet: dimension and callout text ~0.075"; notes ~0.08";
  view titles ~0.14", heavier stroke, underlined, with the subtitle in
  parentheses below at normal size, e.g. `SECTION A-A` / `(SECTION BETWEEN PILES)`;
  table titles ~0.12-0.14" (`TABLE OF` / `ELEVATIONS` on two lines in a box);
  `NOTES:` and `LEGEND:` underlined headings; `BRIDGE NO. 920232` and the
  bridge name ~0.16" italic at the lower right above the title block.
- Fractions in dimensions are small (about 60% of the text height), diagonal
  (`3¹⁄₈"`), tight against the whole number.

### A2. Dimensions
- Thin dimension and extension lines, closed filled arrowheads ~0.08", text
  centered above the line. Extension lines start with a small gap from the
  object and run slightly past the dimension line.
- Series are one dimension with the count, mark and spacing in the text:
  `13~6E29 @ 4'-0" = 48'-0"`, `50~5E27 (EF) @ 1'-0" = 49'-0"`,
  `6 EQUAL SPA @ 7'-6⅛" = 45'-0¾"`, `7 EQUAL SPA @ 6'-6" = 45'-6"`,
  `5~4A02 @ 5¼"`, `4 SPA. @ 7¾"`, `2 SPA. 3½"`, `6 EQ. SPA. = 3'-8"`.
  Odd end spaces are separate small dimensions (`6"`, `1'-3" (TYP.)`, `4½"`).
- Rows of dimensions carry a label at the left end, underlined, e.g.
  `BEAM SPACING ✱`, `PILE SPACING ✱`, `V-GROOVE SPACING`, `MEASURED ALONG ℄ CAP`.
- Footnote symbols `✱`, `✱✱`, `◒`, `Δ` with a legend placed under the elevation
  at the lower left: `✱ DIMENSIONS MEASURED ALONG FFBW`.
- Values that do not fit are written beside the extension line with a short
  leader, never stacked on a second row.

### A3. Leaders and callouts
- Thin leader with a filled arrowhead at the object, a short horizontal landing,
  and the text after it. Several bars called out by one text with several
  arrows fanning from the landing (`6E15 (EF)` with four arrows, `3~8E16 THRU 8E19`).
- Callouts sit next to the bars they name, on both sides of the view, with
  short leaders; they are not collected in one column far to the right.
- Bars shown end-on are pointed at with arrowheads (not circled).
- Centerline labels are drawn with the ℄ symbol and placed with a leader:
  `℄ BEAM 1-14`, `℄ PILES`, `℄ BEARING`, `℄ CAP & ℄ PILE`, `℄ COLUMN 1`.
- Section cut symbol: a short line at the cut with a solid triangular flag
  pointing in the viewing direction and the letter (~0.12", italic) beside the
  flag; the symbol is repeated at both ends of the cut line. See s7, s11, s13.

### A4. Plan and elevation sheet (End Bent 1-1 / Pier 1-2)
- Plan at the top, elevation directly below and aligned, TABLE OF ELEVATIONS at
  the upper right, NOTES at the lower right, footnote legend at the lower left,
  view titles under each view, bridge number at the lower right.
- The elevation shows the concrete AND the reinforcement together: stirrups as
  vertical lines (pier sheet: with a dot at each end of each set), longitudinal
  bars as lines, U-bars over piles, with `count~mark` callouts and the stirrup
  spacing strings above the cap. There is no separate "reinforcement elevation".
- Piles in elevation: two solid lines continuing below the cap, a dash-dot
  centerline, the bottom cut with a curved (elliptical) break, and the circled
  pile number beside the pile at its bottom. Embedment `1'-0" (MIN.) (TYP.)`.
- Beam centerlines in plan: short lines through the cap with a leader label
  `℄ BEAM 1-10`, staggered on two rows; bearing and pile centerlines labelled by
  leaders; `BEGIN BRIDGE / FFBW END BENT 1-1 / STA. 3043+75.38` by leader at the
  PGL; skew angle shown with an arc at one beam.
- Pedestals dimensioned once in plan as `3'-6" PEDESTAL (TYP.)`, `2'-5¾" (TYP.)`, `1'-0¼" (TYP.)`.
- DIRECTION OF STATIONING: a long thin line with a slender solid arrowhead and
  the text written along the line, at the upper right of the plan; a north
  arrow beside it on plan sheets.
- Cheek wall thickness and lug dims noted in plan (`8" (TYP.) CHEEKWALL`, `1'-4"`).

### A5. Sections (3/4" scale)
- Concrete outline heavy; bars as single thin lines (hoops as one rounded
  loop with the 135° hooks drawn, U-bars as one line), end-on bars as filled
  dots ~0.05".
- Full dimension strings of the bar layout: bottom bars `4½" | 4 SPA. @ 7¾" | 4½"`,
  `2 SPA. 3½"`; side bars `6 EQ. SPA. = 3'-8"` vertical; backwall verticals
  `6~5E23/5E24/5E25 @ 1'-0" MAX.` rotated along the wall; covers by leader
  `3" COVER (TYP., UNO)`, `4" COVER`; `1'-0"` leg lengths; chamfer callouts.
- `℄ CAP & ℄ PILE` below the pile with an arrow; the pile drawn under the cap
  with an elliptical bottom; `24" Ø x 0.5" THICK STEEL PIPE PILE` by leader.
- `℄ BEARING` horizontal text with an arrow to the dash-dot line.
- Context: approach slab/landing, MSE wall `FRONT FACE OF MSE WALL`, straps `Δ REINF. STRAP`.
- Titles: `SECTION A-A` + `(SECTION BETWEEN PILES)`, `SECTION B-B` + `(SECTION AT PILES)`.

### A6. Cheek wall views (VIEW C-C / D-D)
- Light diagonal hatch (lines ~0.1" apart on paper) for the WWF limits, label
  `SHADED AREA SHOWS LIMITS OF WWF (SEE NOTE 5)`.
- Bars as lines with small end dots (horizontals) and plain verticals; dims
  `5~4E31 @ EQ. SPA.`, `7~4E33 @ 7"` (rotated along the side), `6" LUG`, `4" CLR.`,
  `6½"`, `5½"`; `CONST. JT. PERMITTED` dashed; PT. callouts; section flags.

### A7. Pedestal details
- PEDESTAL PLAN: cap edges and pedestal outline only (no bearing pad), bars as
  lines, `7~4A02 @ 5½"` across the top, `6~4A01 @ 6"` down the side, cover dims
  `5½"`, `6½"`, `2" MIN. COVER` by leader, `℄ CAP`, `℄ BEARING`, `℄ BEAM` by leaders,
  parenthetical note under the title: `(PEDESTAL BAR SPACING MAY BE SLIGHTLY
  ADJUSTED TO CLEAR CONFLICTS WITH MAIN CAP REINFORCEMENT)`.
- PEDESTAL ELEVATION: U-bars drawn into the cap, `4A01`, `4A02 (TYP.)` leaders,
  `CONST. JOINT` dashed line, `TOP OF PEDESTAL (SEE TABLE BELOW FOR ELEVATIONS)`,
  `¾" X ¾" CHAMFER (TYP.)`, `2" COVER` both ways, `1'-0" (MIN.)`, `4" (MIN.)`,
  break lines on the cap each side.
- Table `TOP OF PEDESTAL ELEVATIONS`: `BEAM NO. | ELEVATION (FEET)`.

### A8. Tables
- Boxed title row in larger italic, column headers, thin cell rules, values
  italic and centered. TABLE OF ELEVATIONS has two columns only: POINT, ELEVATION.

### A9. Bar list (B1-40)
- The FDOT bar-list form: two header rows
  `MARK | LENGTH | NO | TYP | STY | B | C | D | E | F | H | J | K | N | Ø` over
  `SIZE DES | FT IN | BARS | BAR | A G | FT IN ... | NO | ANG`; a component
  heading row spanning the table `PIER 1-2 CAP (1 REQUIRED)` in larger italic,
  with a blank spacer row before and after; lengths and bend dimensions as
  `FT-IN` without unit marks (`20-4`, `18-8¾`); `TYP BAR` is the Standard Plans
  Index 415-001 bar type number; `STY A G` hook styles; `N` phase symbols; `Ø`
  angle. Note: `FOR BAR BENDING DETAILS, REFER TO FDOT DESIGN STANDARD INDEX NO. 415-001.`

### A10. Border and title block
- Bottom band ~0.8" tall: REVISIONS (two DATE/BY/DESCRIPTION groups), EOR block
  (name, P.E. license, firm, address) in italic, initials block (DRAWN BY,
  CHECKED BY, DESIGNED BY, CHECKED BY with initials and dates), STATE OF
  FLORIDA / DEPARTMENT OF TRANSPORTATION in an upright serif, ROAD NO. | COUNTY |
  FINANCIAL PROJECT ID, SHEET TITLE box (title large italic), PROJECT NAME,
  REF. DWG. NO., SHEET NO. (`B1-15`). Rotated 61G15-23.004 statement outside the
  right border; tiny rotated plot stamp (date, file path) outside the left border.
- Line weights: concrete outlines heavy, hidden dashed medium, bars thin,
  dimensions and leaders thin.

## B. Differences in the generated sheets (what to change)

| # | Item | Generated now | Change to match |
|---|------|---------------|-----------------|
| 1 | Sheet configuration | Separate "ELEVATION - REINFORCEMENT" sheet per support; geometry elevation without steel | One plan + elevation sheet per support with the steel in the elevation (A4); drop the reinforcement sheets; renumber (EB1 B4-1..3, pier B4-4..5, EB2 B4-6..8, bar list B4-9) |
| 2 | Font in review PDF | Upright sans fallback | Italic engineering-style font in the previews; DXF style keeps a 15° oblique and an italic TrueType font reference the receiving workspace can map |
| 3 | Fractions | Same height as the text, overlapping (`1'-1½"` unreadable in m8) | DIMTFAC 0.6 and `\H0.6x;` wrapping in MTEXT; verify `4'-0½"`, `7½"`, `¾"` in a crop |
| 4 | Stirrup spacing | Two rows of segment dims plus a `CAP STIRRUPS *` row and separate run callouts | One dimension per run: `4~6B1 @ 9" = 2'-3"` with the end spaces as small dims; no second row |
| 5 | Pile/beam spacing | `4'-6"` repeated per bay | `3 EQUAL SPA @ 4'-6" = 13'-6"` with the end dims; row labels underlined |
| 6 | Callouts | Collected in a column at the far right with long leaders | Next to the bars, both sides, short leaders, fanned arrows for a group; `THRU` where marks are consecutive |
| 7 | Section cut symbol | Arrow with a tail | FDOT flag: line at the cut, solid triangular flag in the look direction, letter beside it, both ends |
| 8 | Piles in elevation | Zigzag break, number below | Curved (elliptical) bottom break, dash-dot centerline, circled number beside the pile bottom |
| 9 | Beam/bearing/pile centerline labels | Text along the line, rotated | Leader labels `℄ BEAM 1-1` etc. (A4) |
| 10 | Sections: bars | Double-line hoop/U outlines; no bar-spacing dims; cover as a text line | Single-line bars with hooks; bottom/side/backwall spacing strings; cover by leader; `℄ CAP & ℄ PILES` at the bottom; horizontal `℄ BEARING` by leader; pile below with elliptical bottom; subtitle wording `(SECTION BETWEEN PILES)` etc. (A5) |
| 11 | Cheek views | Dense hatch (reads black); many small spacing dims | Light hatch ~0.1" pitch; `5~4E1 @ 10" = 3'-4"` strings; lug/clear dims; `SHADED AREA SHOWS LIMITS OF WWR (SEE NOTE n)` |
| 12 | Pedestal plan | Shows the bearing pad; spacing text wrong (`7~4F1 @ 0"±`, `4~4F2/4F3 @ ¼"±` - bug: positions taken from the wrong coordinate) | No pad; correct `7~4F1 @ 5½"`-style strings from bar centroids; cover dims; ℄ leaders; the parenthetical note (A7) |
| 13 | Pedestal elevation | Minimal | `CONST. JOINT` dashed, `TOP OF PEDESTAL (SEE TABLE...)`, chamfer, `2" COVER` both ways, `1'-0" (MIN.)`, `4" (MIN.)`, cap break lines |
| 14 | Table of elevations | POINT, LOCATION, ELEVATION | POINT, ELEVATION only (two-line boxed title); keep the pedestal table with its A/B/C/D corners (ours are sloped) but in the sample's title/header style |
| 15 | Footnotes | `* DIMENSIONS...` as note 1 | Symbol legend under the elevation at the lower left: `✱ DIMENSIONS MEASURED ALONG FFBW` (use `*` if the font lacks ✱) |
| 16 | Direction of stationing | Vertical arrow beside the plan | Long slender arrow with the text along it at the upper right of the plan |
| 17 | View titles | 0.125" | ~0.14", heavier stroke (width factor or lineweight), subtitle in parentheses |
| 18 | Bar list | Custom SHAPE/A-E table; fractions overlap cells | FDOT form (A9); `FT-IN` without unit marks; small fractions; component heading rows with spacers; `TYP BAR` from Index 415-001 if the index can be fetched (see step 9), else blank with a note |
| 19 | Preview rendering | Hidden levels grey, weights flat, upright font | Dashed hidden lines, visible weight contrast, italic font, so the review PDF reads like the sample |
| 20 | Title block | Proportions close; EOR block/initials present | Keep; make the band ~0.8" with the sample's column widths; serif upright for the STATE OF FLORIDA block; tiny plot stamp on the left edge (file name and build date) |

## C. Plan (execute in this order; rebuild and look at crops after each group)

1. **Preview renderer first** (`scripts/build_substructure_dxf.py::previews`,
   `cad.new_document`): italic font for text in previews, dashed hidden lines
   (fix the viewport/linetype rendering: if ezdxf's layout renderer ignores
   linetypes through viewports, render each zone's model-space window directly
   with the paper-space border drawn around it), lineweight contrast. Acceptance:
   a crop of sheet 1 shows dashed piles under the cap, heavier cap outline, italic text.
2. **Text and fraction sizes** (`fdot.py`, `cad.py`): DIMTFAC 0.6; MTEXT fraction
   wrapper; TITLE_IN 0.14 with a heavier stroke; table-title size. Acceptance:
   crops of `4'-0½"`, `7½"`, `¾"`, a view title, a table title.
3. **Symbols** (`cad.py`): FDOT section flag (both ends), curved pile break,
   circled numbers beside piles, stationing arrow with text along it, underlined
   row labels, footnote legend block. Acceptance: crops of the plan ends and the
   pile bottoms match s7/s13.
4. **Sheet configuration** (`build.py`, `views.py`): merge the steel into the
   main elevation (A4) at 3/8" (go to 1/2" only if callouts cannot be kept
   legible at 3/8"); remove the reinforcement sheets; renumber; update notes and
   cross references; keep the EB1 MODEL CHECK note.
5. **Dimension strings** (`views.py`): one dimension per bar run with
   `count~mark @ spacing = total`; EQUAL SPA strings for piles and beams; small
   end dims; no stacked second row.
6. **Callouts and ℄ labels** (`views.py`): leader labels for beam, bearing, pile,
   cap centerlines; callouts beside the bars on both sides; fanned multi-arrow
   leaders for grouped bars; `℄ CAP & ℄ PILES` at the bottom of sections.
7. **Sections, cheek views, pedestals** (`views.py`): items 10-13 above; fix the
   pedestal spacing bug (use each bar's centroid along the spacing axis).
8. **Tables and notes** (`build.py`, `sheets.py`): two-column table of
   elevations with the boxed two-line title; pedestal table header style;
   legend placement; title block proportions and serif DOT block; plot stamp.
9. **Bar list** (`build.py`): FDOT form (A9). Try to fetch Standard Plans Index
   415-001 (fdot.gov, Standard Plans FY2025-26 or current, "Bar Bending Details
   (Steel)") and assign `TYP BAR` and `STY` from it; if it cannot be fetched or
   read, leave those cells blank and keep the note that types are to be assigned
   with the FDOT Rebar program. Straight bars: dimension B = length.
10. **Regression**: `.venv\Scripts\python.exe -m unittest tests.test_substructure_dxf`
    (update the sheet-count expectations and any layout assertions), rebuild with
    `--previews`, re-run the crops in the review folder (`crop.py` there) and
    compare side by side with the `s*.png` sample crops. Update
    `substructure_drawings/README.md` (sheet table, conventions). Commit and push
    (standing instruction: completed work is committed and pushed; one commit).

## D. Fixed points (do not change)
- FDOT level names, DXF units (feet, 1:1 model space), paper layouts, the SDM
  bar marks and `bar_mark_register.csv` (the FreeCAD model now carries them,
  D-042), the snapshot (`data/model_snapshot.json`), deterministic output
  (`write_fixed_meta_data_for_testing`, sorted CLASSES), the QC checks and the
  EB1 backwall MODEL CHECK note, the WWR designations.
- No new geometry is invented: chamfers, construction joints and straps are
  shown only where the model or the project sources have them (the pedestal
  construction joint and the ¾" chamfer are in the model; cap chamfers are not).

## Status (16 October 2026, generator 2.0.0)

Executed in the order of section C. Comparison crops of the new sheets are
`n*.png` beside the sample `s*.png` crops in
`CAD_AI/reports/dxf-style-review-20261016/zoom/`. `tools/crop.py` there now
renders with the same settings as the review PDF.

| # | Status | What was done |
|---|--------|---------------|
| 1 | Done | 9 sheets, numbered as planned: EB1 B4-1..3, pier B4-4..5, EB2 B4-6..8, bar list B4-9. The reinforcement is in the 3/8" elevation, and there are no reinforcement sheets. EB details (1 of 2) follow sample B1-17: A-A, B-B, pedestal plan, elevation and table. EB details (2 of 2) hold C-C and the cheek views. The pier end view D-D moved to the pier plan sheet, as VIEW A-A is on sample B1-21. EB2's first details sheet is the mirror image of EB1's. Notes and cross references were renumbered. The EB1 MODEL CHECK note is kept. |
| 2 | Done | Previews use Century Gothic Italic (bold italic for titles). The DXF styles reference the TrueType `isocpeur.ttf` (family ISOCPEUR) with a 15° oblique. The XDATA italic flag is not set, so the slant comes only from the oblique and is not doubled. A separate title style and an upright serif style for the DOT block were added. |
| 3 | Done | DIMTFAC 0.6; MTEXT fractions `{\H0.6x;\S1#2;}`. See `n1_fractions.png` (`3'-0½"`) and `n2_secA.png` (`4½"`, `5¼"`). |
| 4 | Done | One dimension per stirrup run. Within a run the model spacing varies (9", 9", 7¼"), so most runs read `4~6B1 @ 9" MAX.`; a uniform run reads `@ s = total`. The gaps between runs are small dimensions written beside or below the row. There is no second row. |
| 5 | Done | `3 EQUAL SPA @ 4'-6" = 13'-6"` (`5'-0"` at the pier) with the end dimensions. BEAM and PILE SPACING row labels are underlined. |
| 6 | Done | Callouts sit beside the bars: the cap's right end and below the cap in elevation; the front face, backwall and inside of the cap in sections. Groups get fanned arrows (`4~6A3 (EF)`, `3~5C`, `4~8A2`). `mark_list` writes THRU for three or more consecutive marks; the current marks only need `/`. |
| 7 | Done | FDOT flag at both ends: short heavy line, solid flag in the viewing direction, letter beside it. |
| 8 | Done | Curved break: round-member break for pipe piles, S-curve for the square concrete piles. Dash-dot centerline through the pile, circled number beside the pile bottom. |
| 9 | Done | Leader labels with the centerline symbol: beams (plan), cap and piles, bearing (plan, sections, pedestal plan), beam (pedestal plan), pier. The elevation no longer carries beam centerlines, as on the sample. |
| 10 | Done | Single-line hoops and U-bars with the 135° hooks. Bottom bar string (`4½" \| 3" \| 8" \| 2 SPA. @ 5½" \| ...`). Back-face string (`5 EQ. SPA. = 2'-2¾"`, `5~4D2 (EF) @ 1'-0" MAX.`). Cover as a small dimension with `3" COVER (TYP., U.N.O.)` beside it. Centerline leaders: CAP and PILES at the bottom, BEARING above. Curved pile break. Subtitles read `(SECTION BETWEEN PILES)` and similar. The landing slab is cut to a stub over the backwall. Straps are not shown because they are not in the model. |
| 11 | Partly | Done: light 45° hatch at 0.1"; series strings (`5~4E1 @ 10" MAX.`, `11~4E2 @ 10" MAX.`); `6" LUG`; `SHADED AREA SHOWS LIMITS OF WWR (SEE NOTE 2)`; labels inside the wall face; drawn at 1/2" as in the sample. Not done: `4" CLR.` (no clear distance is defined in the model or sources) and `CONST. JT. PERMITTED` (no joint in the model). |
| 12 | Done | Spacing bug fixed: positions are bar centroids along the spacing axis (`7~4F1 @ 6¾" MAX.`, `4~4F2 @ 6" = 1'-6"`). No bearing pad. Cover is `2¼" MIN. COVER`. CAP, BEARING and BEAM labelled by leaders. Cap break lines. The parenthetical note is under the title. Marks that differ at the other beam line moved to a sheet note. |
| 13 | Done | Dashed CONST. JOINT at the cap top. TOP OF PEDESTAL (SEE TABLE FOR ELEVATIONS). `¾" X ¾" CHAMFER (TYP.)`. Top and side covers. `1'-0" (MIN.)` embedment and `5¼" (MIN.)` height at the low corner, both model values. Cap break lines on both sides and at the bottom. |
| 14 | Done | TABLE OF ELEVATIONS has POINT and ELEVATION, with a boxed two-line title. The pile cutoff table uses the same style. TOP OF PEDESTAL ELEVATIONS keeps the A–D corners in the sample's title and header style and moved to the pedestal details, as in the sample. |
| 15 | Done | Legend `*  DIMENSIONS MEASURED ALONG FFBW` (pier: along the pier centerline) at the lower left beside the elevation title. It uses `*`; the fonts lack ✱. |
| 16 | Partly | The arrow is long and slender with a solid half arrowhead and the text along it, at the upper right of the plan. It is vertical because the alignment is square to the bents. No north arrow was added: the snapshot and generator inputs have no north bearing. |
| 17 | Done | 0.14" title style plotted at 0.35 mm, underlined, subtitle in parentheses at text size. |
| 18 | Done | FDOT bar list form with two header rows, component heading rows between spacers, FT-IN without unit marks, small fractions, and blank form rows to the sheet note. Index 415-001 (FY 2025-26) was fetched from fdot.gov. Types were assigned from it: 1 straight (B = length), 11 U-bar (B, C, D), 4 closed stirrup (B height, C width, STY 5/5). The open stirrups have their legs turned in plan, so they have no type and keep a bending diagram on the sheet. |
| 19 | Done | `preview_doc()` converts linetype scales for ezdxf's viewport rendering, so hidden lines plot dashed and centerlines dash-dot. It also keeps the level lineweights, plots black, and maps the italic fonts. If the PDF is locked by a viewer, it is written as `review_sheets_new.pdf`. |
| 20 | Done, one change | The 0.8" band and column widths match the sample (already did). The STATE OF FLORIDA block is now upright serif. A plot stamp outside the left border shows the file, generator version and FreeCAD model hash. It omits the build date so a rebuild stays byte-identical. |

Also added: each build checks that no view leaves its viewport or draws over
another view (primitive and text boxes), and reports any case as a layout
warning, which the test treats as a failure. `tests/test_substructure_dxf.py`
gained checks for the sheet set, the lettering and dimension style, the text
formats and the bar types (13 tests). Not in section B and not done: the plan
callouts `3'-6" PEDESTAL (TYP.)` and `8" (TYP.) CHEEKWALL` (A4).

## Markup round 2026-10-17

The engineer's review markups of 17 October 2026 (`review_sheets.pdf`) were
distilled into [`STYLE_GUIDE.md`](STYLE_GUIDE.md), one rule per instruction (the
markup log is its section M; the table is not repeated here), and implemented in
generator 2.1.0:

- Annotation: A1 to A8 (clear of linework and of each other, angled bar leaders,
  elevation points in plan and elevation, stationing arrow on every plan-type
  view, L section flags, centerline labels, pile numbers).
- Dimensions: B1 to B6 (pull-out lines, masked text, extension lines to the
  feature, reoriented pile embedment, embedment across the construction joint,
  precision).
- Reinforcing: C1 to C7 (single or double lines by scale, end-on dots, daylight
  between overlapping bars, open stirrups as standard Type 11 bars with field
  bent hooks, hooked cheek bars Types 17 and 18).
- Linework and context: D1 to D9 (coincident hidden edges dropped, break symbols
  only where something is broken, long-dash short-dash centerlines, no landing
  slab, construction joint, reinforcing strap and Δ legend, geotextile detail,
  cheek wall sections F-F and G-G).
- Sheets: E1 to E3 (a third details sheet per end bent, so the set is 11 sheets
  B4-1 to B4-11 with the bar list last; legends and notes inside the window), and
  F (no zero-length lines in dimension blocks).

This supersedes the 9-sheet numbering in item 1 of the status table above.
Regression tests for the testable rules are in `tests/test_substructure_dxf.py`.
