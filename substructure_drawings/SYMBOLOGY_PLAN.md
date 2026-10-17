# Symbology plan: FDOT CADD Manual line weights, line styles, fonts and levels

Sources (attached by the user on 2026-10-17):
- `C:\Users\joshs\Downloads\caddmanual2025.pdf` — FDOT CADD Manual, Topic No. 625-050-001,
  publish date November 1, 2024 (119 pages). Cited below by section and PDF page.
- `C:\Users\joshs\Downloads\fdotcaddstandardleveltable-10-25-2023.xlsx` — FDOT CADD Standard
  Level Table (worksheet "Level Definition Details", 2,824 levels). Its content is identical
  to the table the generator already uses (`fdot.LEVELS` was built from it); the level
  names, numbers, Bentley colors, styles and weights need no change.
- `project_current/geometry/details/B4 Pedestrian Bridge - Working.dxf` — a DXF exported
  from the FDOT workspace. It is the local evidence of how FDOT's own text styles and
  dimension styles come across to DXF (values quoted in A5/A6).

Generator: `substructure_drawings/` (fdot.py, cad.py, sheets.py, views.py, build.py,
scripts/build_substructure_dxf.py), tests in `tests/test_substructure_dxf.py`. Rebuild
and preview: `.venv\Scripts\python.exe scripts\build_substructure_dxf.py --previews`.

## A. What the CADD Manual requires

### A1. Levels (5.10.1.3 Structures Levels/Layers and Symbology, PDF p. 47)
- Structures elements use the levels of the `FDOT_OBM_Standards_Features.dgnlib` Structures
  Level Library; each level has a ByLevel color, line weight, line style and print property.
- Autodesk: layers from `StructuresTemplateDetail.dwt` / `StructuresTemplatePlan.dwt`;
  "Color must remain set to ByLayer and line weight & line style may be modified as needed."
- "User created Levels ARE NOT acceptable." Level `Default` (Bentley) / layer `0` (Autodesk)
  "is not to be used for drawing elements."
- Right of Way (5.10.1.4): all symbology ByLevel. The same ByLevel practice is the intent for
  structures; the generator will keep every entity ByLayer (see B5).

### A2. Colors (5.10, "Color Symbology", PDF p. 48)
- The default Bentley color table. The DXF mapping used now (Bentley 0 white -> ACI 7,
  1 blue -> 5, 2 green -> 3, 3 red -> 1, 4 yellow -> 2, 5 magenta -> 6, 6 orange -> 30,
  7 cyan -> 4) agrees with the FDOT workspace export (SubStrConc 3, Rebar 2, CL_Major 1,
  Dimension 7). No change.

### A3. Line styles (5.10.3.1 / 5.10.3.2, PDF p. 49)
- Bentley line style 0..7 correspond to the Autodesk linetypes `Continuous`, `DGN1` ..
  `DGN7` (FDOT.LIN). Custom styles must not reuse FDOT names; user-defined styles must be
  unique and delivered with the project (5.10.3.4).
- Levels used here need styles 0, 2, 4, 6 and 7 only.

### A4. Line weights (5.10 "Line Weight Symbology", PDF p. 50)
Bentley weight index -> plotted width; the Autodesk (DXF) line weight in mm:

| MS weight | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Autodesk mm | 0.09 | 0.15 | 0.20 | 0.30 | 0.35 | 0.40 | 0.53 | 0.60 | 0.70 | 0.80 | 0.90 | 0.90 | 1.00 | 1.06 |

(14, 15 -> 1.20; 16-18 -> 1.40; 19, 20 -> 2.11.) Output must stay legible on 2nd-generation
copies (7.11.2.2, PDF p. 94). The FDOT.tbl pen table and the FDOT print drivers apply these
widths on the Bentley side (7.11.3, PDF p. 95).

### A5. Text (5.12, PDF pp. 52-54)
- FDOT delivers TrueType fonts: **FDOT** (standard slanted proportional font for most
  annotation), **FDOT Bold**, **FDOT Heavy**, **FDOT Imprint** and **FDOT Imprint Bold**
  (chiseled, used within the sheet border), **FDOT Mono**, **FDOT Mono Bold**, **FDOT Mono
  Heavy** (tables). The FDOT fonts carry special characters: `¡` centerline, `¢` plate line,
  `£` base line, `¥` flow line, `§` main line; fractions in quarters `¼ ½ ¾` (U+00BC-00BE),
  eighths `ƃ`-`Ɔ` (U+0183-0186 = 1/8, 3/8, 5/8, 7/8), sixteenths `Ƈ`-`Ǝ` (U+0187-018E =
  1/16 .. 15/16), thirty-seconds `Ə`-`ƞ`, sixty-fourths `Ɵ`-`ƾ`; superscripts and subscripts.
- Text styles (5.12.1.1), height = width, in feet on the 1:1 sheet (11 x 17 in):
  `FDOT Structures` FDOT .0063 (0.0756 in) · `FDOT Structures Annotation` FDOT .0063 ·
  `FDOT Structures Dimensions` FDOT .0063 · `FDOT Structures Initials` FDOT .0058 ·
  `FDOT Structures Superscript` FDOT .0044 · `FDOT Structures Revision` FDOT .005 ·
  `FDOT Structures Views_SectionArrow` FDOT Bold .008 (0.096 in) ·
  `FDOT (Small)` .005833 (0.07 in) · `FDOT (Medium)` .008333 (0.10 in) · `FDOT (Large)`
  .010417 (0.125 in) · `FDOT Bold (Small/Medium/Large)` same heights · `FDOT Mono (Small)`
  .006 · `FDOT_SHEET_DESCRIPTION` FDOT Imprint Bold .010417 · `FDOT_SHEET_COUNTY`,
  `FDOT_SHEET_FPID`, `FDOT_SHEET_SR` FDOT Bold .005833 · `FDOT_SHEET_REVISION_DATE`,
  `FDOT_SHEET_REVISION_DESCRIPTION` FDOT Mono .005 high x .004 wide.
- Text size follows the annotation scale (5.12.1.2); line spacing averages three-fourths of
  the text height.
- The FDOT workspace export in `project_current` confirms the structures styles as DXF text
  styles with height 0.0063 and width 1.0 (`FDOT Structures`, `FDOT Structures Annotation`,
  `FDOT Structures Dimensions`, `FDOT Structures Views_SectionArrow` 0.008, `FDOT (Small)`
  0.005833, `FDOT Bold (Medium)` 0.008333).
- **Verified on this machine (2026-10-17, fonts installed in `C:\Windows\Fonts`, registered
  in HKLM):** file -> TrueType family / subfamily: `FDOT.ttf` -> `FDOT` / Regular (built-in
  italic angle -12°, so DXF oblique = 0); `FDOTBold.ttf` -> family `FDOT`, subfamily Bold
  (same family, bold flag); `FDOTHeavy.ttf` -> `FDOT Heavy`; `FDOTImprint.ttf` -> `FDOT
  Imprint`; `FDOTImprintBold.ttf` -> `FDOT Imprint Bold`; `FDOTMono.ttf` / `FDOTMonoBold.ttf`
  -> family `FDOT Mono` Regular / Bold; `FDOTMonoHeavy.ttf` -> `FDOT Mono Heavy` (the Vert
  fonts are not used, 5.12). The special glyphs are present in FDOT, FDOT Bold, FDOT Heavy and
  FDOT Mono (not in the Imprint fonts): U+00A1 draws the ℄ centerline symbol; U+00BC-00BE =
  ¼ ½ ¾; U+0183..0186 = 1/8, 3/8, 5/8, 7/8; U+0187..018E = 1/16, 3/16, ... 15/16, all drawn
  as small tight fractions (rendered and checked: `4'-0½"`, `7¼"`, `3⅛"`, `2'-5⅞"`).
  matplotlib only sees newly installed fonts after `font_manager.fontManager.addfont(path)`
  for each `C:\Windows\Fonts\FDOT*.ttf` (or a cache rebuild); the preview code must do that.

### A6. Dimension styles (5.13 link; values from the FDOT workspace export)
`FDOT Structures Note-Arrow`: text style `FDOT Structures Annotation`, DIMTXT 0.0063 ft,
DIMASZ 0.006509 ft (0.078 in), DIMEXO = DIMEXE = DIMGAP 0.00315 ft (0.038 in), DIMLUNIT 4
(architectural), DIMLFAC 12, DIMZIN 15, DIMFRAC 1 (diagonal), DIMTAD 1, DIMTIH = DIMTOH 0,
DIMTFAC 0.7, DIMTMOVE 1, DIMATFIT 1, closed filled arrowheads. `FDOT Structures Note-S`
uses the tilde terminator block `Terminator-S_5.0` (SDM 2.16.E surface callouts) and
`FDOT Structures Note-Elevation` the elevation terminator `Terminator-Elv_0.2`.

### A7. Printing (7.11, PDF pp. 94-96)
- PDF is the required print format; FDOT.tbl pen table; `$LWDISPLAY` on; print border
  for 11 x 17 plan sheets typically 16.5 x 10.6 in; non-plotting clip-border levels.

## B. What the generator does now, and the change

| # | Item | Now (`fdot.py`, `cad.py`) | Change |
|---|------|---------------------------|--------|
| 1 | Line weights | `BENTLEY_WEIGHT_TO_LW = {0:0, 1:13, 2:30, 3:40}` (copied from a MicroStation DWG export) | The manual's table (A4): `{0:9, 1:15, 2:20, 3:30, 4:35, 5:40, 6:53, 7:60, 8:70, 9:80, 10:90, 11:90, 12:100, 13:106}`; all are valid DXF lineweights |
| 2 | Linetype names | `DGN Style 2/4/6/7` | `DGN2`, `DGN4`, `DGN6`, `DGN7` (A3), descriptions "DGN line code n"; keep the pattern lengths; keep a one-line switch to the MicroStation round-trip names (`DGN Style n`) and document both in the README |
| 3 | Fonts | `isocpeur.ttf` with a 15° oblique; `times.ttf` for the DOT block; title stroke by a lineweight override (35) | FDOT TrueType fonts (now installed here, see A5): `FDOT.ttf` (family `FDOT`) for annotation; `FDOTBold.ttf` (family `FDOT`, bold flag in the extended font data) for titles and section letters; `FDOTImprint.ttf` (`FDOT Imprint`) and `FDOTImprintBold.ttf` (`FDOT Imprint Bold`) in the border; `FDOTMono.ttf` (`FDOT Mono`) for the revision rows; oblique 0 (the font's own 12° slant), width 1.0; no lineweight override on text |
| 4 | Text styles | `FDOT Structures`, `FDOT Structures Title`, `FDOT Serif` | The FDOT names and heights of A5: `FDOT Structures` (notes, callouts, tables), `FDOT Structures Annotation` (dimension text), `FDOT Structures Views_SectionArrow` (section/view letters 0.096 in), `FDOT Bold (Large)` (view titles and bridge number 0.125 in, underlined), `FDOT Bold (Medium)` (table titles 0.10 in), `FDOT (Large)`, `FDOT Structures Initials`, `FDOT_SHEET_DESCRIPTION`, `FDOT_SHEET_COUNTY`, `FDOT_SHEET_FPID`, `FDOT_SHEET_SR`, `FDOT_SHEET_REVISION_DATE`, `FDOT_SHEET_REVISION_DESCRIPTION`, `FDOT Imprint` (DOT block). Style height 0 in the DXF (entity heights = FDOT height x viewport scale factor, as now) |
| 5 | Text sizes | `NOTE_IN 0.08`, `TITLE_IN 0.14`, `TABLE_TITLE_IN 0.13`, `BRIDGE_NO_IN 0.16` | FDOT style heights: notes 0.0756, titles 0.125, table titles 0.10, bridge number 0.125, section letters 0.096, initials 0.07, revision rows 0.06 |
| 6 | Centerline symbol | Block `FDOT_CL_SYMBOL` with geometry on layer `0` | The FDOT font's `¡` (U+00A1) centerline character in the text itself; delete the block (layer 0 must carry nothing, A1) |
| 7 | Fractions | MTEXT stacked `{\H0.6x;\S1#2;}` | FDOT font fraction glyphs (A5, verified) in dimensions, callouts and the bar list, behind a switch `FDOT_FONT_GLYPHS` (default on); the stacked form stays as the fallback for a machine without the fonts |
| 8 | Dimension style | `FDOT Structures` with DIMEXE 0.06 in, DIMGAP 0.03 in, DIMFRAC 0, DIMTFAC 0.6, DIMLWD/DIMLWE unset | Name and values of `FDOT Structures Note-Arrow` (A6): DIMTXSTY `FDOT Structures Annotation`, DIMASZ 0.078 in, DIMEXO/DIMEXE/DIMGAP 0.038 in, DIMFRAC 1, DIMTFAC 0.7, DIMZIN 15, DIMTMOVE 1, DIMATFIT 1, DIMLWD = DIMLWE = -1 (ByLayer) |
| 9 | Line spacing | MTEXT default | Line spacing factor giving a three-quarter-height gap (about 1.05 x AutoCAD single spacing) |
| 10 | ByLevel compliance | Entities are ByLayer except the title lineweight override and the hidden-line linetype override on `BearingPadMisc` | All entities ByLayer for color, lineweight and linetype; per-entity LTSCALE stays (it is not a style override). Hidden bearing pads: keep the linetype override only if no FDOT level with a hidden twin fits; document it |
| 11 | Layer table | FDOT levels plus ezdxf's `0`; check for `Defpoints` | Only FDOT level names in the layer table besides an empty `0`; no entity on `0` or `Defpoints`; viewports stay on `ClipBorder_dp` (plot off) |
| 12 | Level table provenance | `LEVEL_TABLE` cites the 10-25-2023 URL | Also record the attached file and its SHA-256 (8D2AC22A...) and the CADD Manual edition in `fdot.py` and the README |
| 13 | Previews | Century Gothic Italic substitutes | Render with the installed FDOT fonts (register `C:\Windows\Fonts\FDOT*.ttf` with matplotlib's font manager, resolve by family + bold flag); keep a substitute map (FDOT -> GOTHICI, FDOT Bold -> GOTHICBI, FDOT Imprint -> a serif, FDOT Mono -> Consolas) with stacked fractions and a plain-text centerline for a machine without the fonts; the review PDF must show the ℄ glyph and the tight fraction glyphs |
| 14 | Tests | Levels, units, marks, determinism | Add: lineweight map equals A4; linetype names per A3; text styles per A5 (names, fonts, heights, width 1, oblique 0); every entity ByLayer; nothing on `0`/`Defpoints`; centerline glyph in use; fraction glyph table; DXF byte-identical on rebuild |

## C. Steps (in order; rebuild, test and look at a crop after each)

1. `fdot.py`: weight map, linetype names (+ switch), font families/files, text-style table
   (name -> family, height in feet), sizes, fraction glyph table (U+00BC-00BE, U+0183-0186,
   U+0187-018E) with `FDOT_FONT_GLYPHS`, centerline glyph, provenance strings.
2. `cad.py`: build the styles from the table (oblique 0, width 1, extended font data = family);
   dimension style per A6; remove the CL block and `TITLE_LW`; `cltext()` writes `¡`; text
   helpers take a style name; MTEXT line spacing.
3. `views.py`, `build.py`, `sheets.py`: use the named styles (section letters, titles, tables,
   border fields, revision rows, initials); heights from the table; bar list fractions.
4. Entity audit: a build-time check that every entity is ByLayer (color 256, lineweight -1,
   linetype BYLAYER except the documented override) and that only FDOT levels carry entities;
   make it a test and a manifest field.
5. Previews (`scripts/build_substructure_dxf.py`): family substitution map; glyph fallback;
   lineweight scaling that shows the 0.09 / 0.15 / 0.20 / 0.30 mm contrast.
6. Tests (B14), README "Symbology" section with the manual citations and the receiving-side
   notes (install the FDOT fonts; ByLevel after import; linetype name switch), rebuild twice
   for determinism, regenerate previews, commit and push (one commit).

## Status (2026-10-17, generator 2.0.0)

The manual's tables were re-read from the PDF (pp. 46-54, 94-96) and the font names and
glyphs from the installed font files before coding; all items below are verified on the
output DXF with ezdxf (layer table, every entity in every block, styles, dimension style).

| # | Done |
|---|------|
| 1 | `BENTLEY_WEIGHT_TO_LW` is the manual's table for weights 0-30 (0.09 ... 2.11 mm). Layers now plot concrete 0.30 mm (was 0.40), rebar 0.15 (0.13), annotation 0.09 (0.00) |
| 2 | Linetypes `DGN2/4/6/7`, description "DGN line code n", same patterns; one-line switch `LINETYPE_NAME = "DGN Style %d"` (checked by a scratch build) |
| 3 | Styles reference `FDOT.ttf`, `FDOTBold.ttf` (family FDOT + bold flag), `FDOTImprint.ttf`, `FDOTImprintBold.ttf`, `FDOTMono.ttf`; oblique 0, width 1 (revision styles 0.8); no lineweight override on text |
| 4 | 17 text styles, height 0 in the DXF: the 13 manual styles of B4's list, three more manual styles in use (FDOT (Small): table heads, small notes, EOR and 61G15 lines; FDOT (Medium): NOTES: headings, project name, bending-diagram title; FDOT Mono (Small): plot stamp), and `FDOT Imprint` for the border-cell lettering (no manual height; sized to the cells). Old `FDOT Structures Title` and `FDOT Serif` removed |
| 5 | Entity heights = FDOT style height x scale factor (model) or the style height (layouts); notes 0.0756", titles and bridge number 0.125", table titles 0.10", section letters 0.096", border values 0.07"; the plot stamp is FDOT Mono (Small) 0.072" |
| 6 | `¡` (U+00A1) before centerline labels (`¡ BEARING`, `¡ CAP & ¡ PILES`, legend `ALONG ¡ PIER`); `FDOT_CL_SYMBOL` block and `cltext()` removed |
| 7 | Fraction glyphs (U+00BC-00BE, U+0183-0186, U+0187-018E) in dimensions, callouts and the bar list; `FDOT_FONT_GLYPHS = False` gives U+2104 and `{\H0.7x;\S1#2;}` stacks (checked by a scratch build: no glyphs left, no layout warnings) |
| 8 | Dimension style `FDOT Structures Note-Arrow` with the A6 values, DIMLWD = DIMLWE = -1; `$DIMSTYLE`, `$TEXTSTYLE` set. DIMTOFL 1 kept (not in the plan's list; the layout relies on it) |
| 9 | MTEXT line spacing factor 1.05 (`fdot.LINE_PITCH` 1.75 h also used for the overlap boxes). Table cells keep their 1.45 h row pitch (table geometry, not MTEXT) |
| 10 | Everything ByLayer. Title and section-tick lineweight overrides removed (ticks, frame, title band and table outlines are now constant-width polylines: 0.014"/0.02"). ezdxf's dimension-block contents (layer 0, ByBlock) moved to the dimension's level; the arrowhead block `_CLOSEDFILLED` to Dimension. Documented exception: hidden bearing-pad edges keep linetype DGN2 on BearingPadMisc (the level table has no hidden bearing-pad level) |
| 11 | Layer table = FDOT levels + empty `0`; ezdxf's 1,122 Defpoints POINTs in dimension blocks dropped and the Defpoints layer removed (ezdxf re-adds an empty one in memory when reading); viewports on ClipBorder_dp (plot off) |
| 12 | `fdot.CADD_MANUAL` and `LEVEL_TABLE` carry file names and SHA-256; both in the manifest and the README |
| 13 | Previews register `FDOT*.ttf` with ezdxf's font manager (the drawing add-on draws glyph outlines from ezdxf's own font cache, not matplotlib's, so `matplotlib.font_manager.addfont` would not reach it) and resolve each style by family + bold flag; substitutes and plain-text glyph fallback only without the fonts. Two preview defects found and fixed: ezdxf's matplotlib backend shrank every page to 7.26 x 4.8 in (`adjust_figure`), and it takes lineweights in mm as points, so the old 0.6 pt floor drew 0.09/0.15/0.30 mm all alike. Pages are now 17 x 11 in (PNG 1870 x 1210 px) and the weights are scaled mm -> pt with a 0.25 pt floor, so 0.09/0.15/0.30 mm plot true size and distinct |
| 14 | Six new tests (19 in all): line weights, linetype names, text styles and entity heights, ByLevel audit, layer 0/Defpoints, FDOT characters and the fallback, dimension style, provenance; the existing determinism test rebuilds and compares bytes |

Layout: views stay where they were. Text sizes changed with the FDOT styles, so tables and
note blocks are a little shorter. Two border labels were reduced to fit Imprint (ROAD NO. /
COUNTY / FINANCIAL PROJECT ID 0.04", REF. DWG. NO. / SHEET NO. 0.045"). The DOT block is
0.065" Imprint. Viewport edges on the drawing-window boundary now clip 0.08" outside it:
the wider FDOT lettering pushed `¡ BEARING` (B4-2) and `LANDING SLAB` past the hard clip
by up to 0.05", within the layout check's tolerance (yesterday's `BEARING` on B4-2 already
was clipped by 0.04"). A text clip check with the real FDOT metrics now finds none.
Not done: no revision rows or initials exist on the sheets, so the
`FDOT_SHEET_REVISION_*` and `FDOT Structures Initials` styles are defined but unused, as is
`FDOT (Large)` (no text needs it).

## D. Fixed points
- Level names, numbers, colors, styles and weights of `fdot.LEVELS` (they match the attached
  table); the SDM bar marks and register; the model snapshot; the sheet layout and views from
  STYLE_PLAN.md; DXF units (international feet, 1:1 model space); deterministic output.
- No download or installation in this task. The user installed the FDOT TrueType fonts on
  this machine on 2026-10-17 (15 `FDOT*.ttf` files in `C:\Windows\Fonts`, registered for all
  users); the FDOTConnect workspace itself is not installed, so FDOT.LIN and the dgnlib are
  not available locally.
