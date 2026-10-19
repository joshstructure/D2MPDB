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
  report no crossings between views, and the annotation audit
  (`View.audit`, manifest `annotation_overlaps`, printed by the build as
  "NOTE (annotation over linework)") lists every text inside a view that a
  line runs through or ends in; the list is worked down to nothing but
  justified cases before delivery.  Break lines and pile break lobes count
  as linework (they are drawn on the Symbols level, which the check
  otherwise skips): a note inside a broken element goes in one of the
  drawn bands, never on the break (the pier wall note, 2026-10-19).  Follow-up markup 2026-10-17: "in
  general please double check that we are minimizing overlapping annotation
  with linework".  Markups: "Fit annotations to minimize overlap
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
  the elevation callouts (5~6A1, 4~6A3 (EF), 4~8A2).  Checked since
  2026-10-19 (round 3): an arrow piece of any leader that runs within 0.05"
  of a parallel drawn line (concrete or bar) for more than 0.2" is a
  finding; the "3~5C (TYP.)" callout under the elevation had its leader
  along the stirrup legs (markup "Hard to see leader").
- **A4 Elevation points in plan and elevation.**  Every lettered point of the
  table of elevations is called out in the elevation and, where it has a
  plan location (cheek wall tops, backwall top at the ends and at the PGL,
  cap top at the ends), also in the plan, as on sample sheet B1-15.  Points
  without a plan position (bottom of cap, bottom of cheek lug) appear in
  the elevation only.  Markup: "Show the elevation points on both the plan
  and elevation if applicable".
- **A5 Direction of stationing on every plan-type view**, including the
  pedestal plan detail (sample B1-17), placed clear of labels (upper right
  of the plan, right of the pedestal plan).  The arrow line is long enough
  for its text to sit along the plain part of the line, clear of the
  arrowhead, which is on the other side of the line from the text.  Markups:
  on the pedestal plan; follow-up "Stationing still has overlap".
- **A6 Section flags are the FDOT "L" flag.**  A heavy tick along the cut, a
  short heavy base toward the viewing direction, a solid wedge on the
  outside of the L (beyond the base, thick at the corner, tapering in the
  viewing direction) and the letter inside the L beside the tick (sample
  B1-15/B1-17).  The wedge is never drawn inside the L.  Markup: "The arrow
  head triangles should fill to the outside not the inside".
- **A7 Centerline labels by leader** (centerline glyph before the name:
  "CL BEARING", "CL CAP & CL PILES"), the leaders in open space, never under
  the stationing arrow or over the dimension rows (B4-1 markup).
- **A8 Pile numbers** in circles beside the pile bottoms (pier) or under
  the stirrup row (end bents), there 0.5 ft off the pile on the side away
  from the section flag letters, so the number at the pile that carries a
  flag clears its letter; the pile description leader and the "PT." leaders
  stay clear of the number circles.
- **A9 Text widths for layout** are estimated per glyph from the installed
  FDOT font (`cad.text_extent`, `_ADV`), so texts with quotes, parentheses
  and points are not sized a quarter too wide; the audit boxes (A1) and the
  fit tests of the dimension rows use the same estimate.
- **A10 Leader bends are square or obtuse, and leaders leave a text toward
  what they point at.**  The angled piece of a leader never runs back under
  its text (an acute angle at the knee): where the tip lies on the text side
  of the knee, the knee moves over the tip and the piece is vertical
  (`View.leader`).  A fan of arrows leaves the text on the side of the bars
  it points to (`View.leader_fan` flips the text side when the tips are on
  the text side).  Markups 2026-10-19: "Make leaders either 90 degree bends
  or obtuse interior angles, don't cut under the text with an acute interior
  angle unless absolutely necessary", "Leaders extend from the right side of
  text when objects are on the left side".
- **A11 Leaders do not cross leaders.**  Two leaders (or a pulled value's
  pointer and a leader) never cross; the audit lists every crossing
  ("LEADER CROSSES LEADER") and the list is worked to nothing.  A callout
  whose leader would have to cross another moves to a different side, or its
  tip to a different point of the bar (the hoop callout tip sits above the
  side-bar fan, the pier's end U-bar callout under the cap end with its two
  tips well apart).  Markups 2026-10-19: "Leaders unnecessarily cross other
  leaders", "The leaders here have too much overlap with drawing items and
  it's hard to see what they point to ... have wider distances between the
  separate leaders", "There's no need for these annotations to cross".
- **A12 Several lines called out by one label get parallel leaders**, one
  arrowhead per line, the leaders crossing any other centerline through a
  gap in it (the cap centerline is broken either side of each leader), the
  text once at the end of the leaders (pier sections, "CL BEARING (TYP.)").
  Markup 2026-10-19: "Do a set of parallel leaders where you have an arrow
  per line and make sure the leaders cross the other centerline in a dash
  area so it's clear they are distinct".
- **A13 A centerline label points at the centerline**, extended clear of the
  dimension rows if need be, never at a point beside a dimension text (pier
  View D-D).  Markup 2026-10-19: "Extend the centerline and point to it
  because this looks like we are pointing to the dim text".  Leaders keep
  0.3" from the circled pile numbers (A8): "No need for the annotation
  leaders to be so close to the circled number".  No leader or pointer runs
  through a circled number or a section flag (checked).
- **A14 Labels of one side form a column with even rows.**  The labels on
  one side of a view share one text column and one landing length, and
  their rows are spread evenly over the band they occupy (`callouts(...,
  spread=)`); a label never sits on a dimension row or a dimension line.
  Markups 2026-10-19 (round 2): "There is plenty of space here to spread
  these annos out vertically with more of an equal space distribution. Get
  better at organizing annos so they are more row and column like with more
  equal space distribution", "Move this slightly so it doesn't look like
  it's an anno about the dim line".  A leader crosses as little drawing
  linework as the placement allows (checked: more than four concrete or bar
  lines under one leader is a finding).  Markup: "Minimize the leaders
  crossing line work if you can just shift the annotations a bit".
- **A15 Labels at the ends of a plan go outside the drawing.**  The point
  labels, centerline labels and context labels at an end of the plan form
  one column beyond the cheek wall (clear of the section flags), with
  horizontal landings; nothing is squeezed between the cheek and the cap
  end.  Markups 2026-10-19 (round 2): "Pull these out into space and
  minimize leader line overlaps with drawings", "Plenty of space to move
  these off to the right outside the drawing", "Too close to other stuff,
  there is plenty of space".
- **A16 Pulled-out values and pile numbers have their own rows.**  Under a
  stirrup row the pulled-out values take the first band and the circled
  pile numbers the band below it, the section flags below those; no pointer
  passes a circle.  Markup 2026-10-19 (round 2): "All these leaders are
  overlapping the text".
- **A17 Labels stay outside the concrete when the view has open space
  beside it**, and the leader's bend and landing never lie over the
  drawing: the break line of a stub is moved out so the labels sit beyond
  it (pedestal elevation).  Markup 2026-10-19 (round 2): "No need to
  overlap the drawings so much, there is plenty of drawing space. Move the
  break line if needed and shift these annos out into the space. I don't
  like the text overlapping drawing lines and I don't like the leader break
  line overlapping drawings".
- **A18 Bars get splayed fans; centerlines get one leader line.**  Several
  bars called out by one label (a column of side-bar ends included) get a
  fan of arrows splayed from the knee at the text, the arrows at least 5
  degrees apart (A12; the row sits at the middle of the bar ends so the
  arrows open up and down).  Horizontal leaders joined by a vertical
  connector read as drawn construction, so they are not used for bars
  (follow-up 2026-10-19: "splay out the leaders for the bars because too
  geometric makes it look like there's some construction on the drawing. We
  want to differentiate from drawn objects and annos").  Two centerlines
  called out by one label (the pier's "CL BEARING (TYP.)") get ONE level
  leader line with an arrowhead at each centerline; the nearer centerline
  ends at its arrowhead and the farther runs on above the line (follow-up:
  "Put the CL leader two arrows on the same line").  Markups 2026-10-19
  (round 2): "Put these parallel leaders in the same plane. It should feel
  like the leaders only touch the text at one point", "Either put these
  leaders parallel or move the anno and spread these leaders out so they
  are distinct. Don't do these kind of almost parallel leaders".  The two
  bars of a pair that a cut pile separates from the rest of their run (the
  bottom bars of Section B-B) get one leader line through both with an
  arrowhead at each and the count of the pair: "2~8A2 (EF)" (markup
  2026-10-19 round 4: "Do a double arrow leader and say 2~9A2 (EF)").
- **A19 Deterministic checks.**  Every rule above that can be measured is
  a check in `anno_check.py` (rule ids in the findings), run on every view
  by the build and written to the manifest; the tests fail on any finding.
  The checks are the first thing to extend when a markup names a new kind
  of fault.  Request 2026-10-19: "Perhaps there should be deterministic
  helpers to help check the anno layouts".
- **A20 A label beside a column breaks into two lines rather than reach
  its neighbours.**  Where a one-line label would come within 0.4 th of a
  neighbouring annotation (a parallel-leader connector, the next column, a
  pulled value) or would push its own leader into a vertical run along the
  bars, the label is written in two lines ("3" COVER" over "(TYP., U.N.O.)",
  "3~5C" over "(TYP.)") and placed in the nearer gap.  Markups 2026-10-19
  (round 3): "Overlapping put in 2 lines of text for fit", "Hard to see
  leader make 2 lines of text for fit".
- **A21 The tips of different callouts stand apart.**  Two callouts never
  point at the same spot: when two bars meet (the pedestal U-bar's top run
  and the first end-on bar on it), one callout takes another part of its
  bar (the run between the second and third dot), so the tips are at least
  0.1" apart (checked).  Markup 2026-10-19 (round 4): "Adjust so the
  leader ends are not so close to each other.  There are other parts of
  the steel we can point to to spread the leaders out a bit for clarity".
- **A22 A label that stands between two views goes under its view.**  The
  pile description of Section B-B sits under the section in the row of the
  centerline label, on the front side, its leader up to the pile face
  above the break; the strap label of the sections sits beyond the
  back-side dimension columns just under the strap's level, its leader to
  the strap's free end passing under the series text of the first column.
  Markups 2026-10-19 (round 4): "Move to a better spot" (both).

## B. Dimensions

- **B1 Text that does not fit is pulled out with a line to its dimension.**
  The value goes beside its space (in the free half of the neighbouring
  space or beyond the end of the row) or just below the row, and a plain
  line (no arrowhead) runs from the text to the dimension line so the
  reader sees which dimension it belongs to.  Values are never stacked on a
  second row.  The pointer (`View.pointer`) is one piece square to the row
  from the point of the text edge over the dimension when the dimension
  lies under (over) the text, and otherwise two pieces: a 0.12" landing
  along the text from the side facing the dimension, then the angled piece
  to the dimension line.  Markups: "Add line/arrow when the dim doesn't fit
  right so we can see which one it is", "If a dim text doesn't fit pull it
  out and add a line pointing to the dim", follow-up "Make dim pointer two
  piece lines, one straight looks weird".
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
- **B7 Pulled-out values sit in open space with a two-piece pointer.**  A
  value that does not fit is placed on the side away from the object it
  measures (above the row's other texts, or beyond a dimension column), never
  between its own extension lines and never closer than a text height to any
  line; a two-piece pointer (a short landing along the text, then the angled
  piece, no arrowhead) runs from the text to its dimension line.  The same
  goes for cover values: they go into open space beyond the concrete (past
  the break line), not over the bars.  Several values pulled out beside one
  row (`chain_dims`) sit at one level in row order, each over the middle of
  its space; where two would overlap, the earlier slides back along the row
  as far as its own space stays under it (its pointer then drops square to
  the row) before the later one is pushed on, so no pointer runs through a
  neighbouring text.  The end bent pile embedment value ("1'-0"" over
  "(MIN.)") sits in the band between the pile cut-offs and the stirrup
  row's two-line texts, in the first run space outboard of the last pile
  wide enough for it, its landing clear of the extension line and the
  angled piece passing above the row's texts into the pile.  Follow-up
  markups 2026-10-17: "This text is too close to the lines, pull it out and
  use a pointer", "Move the text into space and use a two-piece pointer for
  this cover annotation", "Make dim pointer two piece lines, one straight
  looks weird".
- **B8 Dimension columns.**  A vertical column right of the view carries its
  text on its outer (right) side; columns are 0.45" apart where a rotated
  two-line series text sits between them; the back-face strap dimension
  sits 0.15" off the face inside the first column.  Follow-up markup:
  "overlap here" (Section A-A back side).
- **B9 Pulled-out values stand clear of their line.**  A value pulled out
  of its space keeps a clear gap between its text box and its own dimension
  line (or that line's extension): 1.2 text heights in a vertical column,
  one text height on the far side of a horizontal row, a quarter beyond the
  end of a horizontal row; the pointer's landing never lies over another
  line.  A two-line in-place dimension text is placed explicitly beside its
  line (ezdxf would put its second line on the line).  Markups 2026-10-19:
  "Dim text sits on dim lines", "Shift dims like these slightly to the left
  so they don't look like they are sitting on the other dim line and it's
  clear they are a pop out because they didn't fit", "Text is overlapping
  with the dim line because the pop out isn't far enough away. Also do not
  make the break in the leader overlap another line".
- **B10 A cover value sits beside its dimension.**  The pulled-out cover
  value is at the height of its dimension line, just outside the concrete,
  with a straight horizontal pointer, never at the far end of a long
  pointer that crosses other leaders (pedestal plan, sections).  Markups
  2026-10-19 (round 2): "Why all the way up here for the text and not here?
  Look at how drawing items get crossed", "Overlap" (the cover text on the
  bottom-bar leader).
- **B11 A pointer stops short of its text.**  The pointer of a pulled-out
  value (B1) ends 0.35 text heights before the text box (`View.pointer`,
  `cad.POINTER_GAP_TH`; checked at 0.3): the FDOT font's stacked fractions
  rise about a fifth of a text height above the capital line, so a pointer
  drawn to the box edge touched the glyph.  Markup 2026-10-19 (round 3):
  "Dim leaders are still overlapping dim text" (the 3½" under the pile
  spacing row).
- **B12 A dimension line keeps off parallel drawn lines.**  A dimension
  line is never laid along a parallel bar line, outline or surface break
  within 0.08" when there is room elsewhere (checked at 0.05"): the cover
  dimension of a pedestal plan goes in the widest band clear of the bars,
  the top-surface breaks and the centerline labels.  Markup 2026-10-19
  (round 3): "Dont put a dim so close to a parallel line if there is plenty
  of space".
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
- **C4 Overlapping bars get daylight (single-line views only).**  When two
  single-line bars would draw on the same line (a backwall vertical over a
  hoop leg in the 3/8" elevation), the shorter bar is offset by about 0.03"
  on paper away from the nearest face, so each bar end stays visible.  At
  double-line scales bars stay where the model has them (C10).  Markup:
  "When bars overlap bump the representational line ever so slightly away
  from each other so there's a little daylight and we can see where the
  bars end".
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
- **C8 Bar ends are round and end-on legs are dots.**  A double-line bar
  (C1) ends in a semicircle, not a square cap; a leg or hook seen end-on in
  a view (the projected length under 0.35 of the true length) is drawn as
  an end-on dot (C2) at its position, never as a notched stub of the
  projected bend (`views.draw_bar3`: pedestal plan and elevation, cheek
  views).  Markups 2026-10-19 on the pedestal plan: "The bar ends at the
  bends here have odd shapes instead of smooth semi-circles", "appears to
  show multiple clashing bars that don't occur in the model" (the 4F2 legs
  stand under the first 4F1 bar: end-on dots on its line, not stubs).  A
  dot is a leg, never a joint: the model's bar polylines carry segments of
  about 0.001 ft where a bend arc meets a straight leg (a FreeCAD arc-end /
  line-start mismatch), and `draw_bar3` ignores segments under 0.001 ft, so
  no dot appears 1¾" off the leg dots.  Markup 2026-10-19 (round 3): "Where
  are these extra dots coming from?" (pedestal plan and elevation).
- **C11 Cover is dimensioned to the outermost bar only, where it
  matters.**  A cover dimension runs from the concrete face to the bar
  nearest it (the leg of the pedestal U-bar at the side, the hoop leg of a
  cap section); no cover is given to an inner bar (the pedestal elevation
  carried a top cover down to the second layer).  It is drawn inside the
  element whose cover it is, at the face it is measured from: the
  pedestal's side cover inside the pedestal, not in the cap below where the
  leg is embedded.  No cover or clear value for a bar mat centred in a wall
  (the cheek wall sections): the project's clear-spacing requirement
  governs.  Markups 2026-10-19: "Remove. Only detail cover to the outermost
  bar" (round 3); "Call out the cover where it matters", "Remove this clear
  spacing anno since the project has a required clear spacing and these
  bars are in a mat centered in the wall with plenty of space" (round 4).
- **C10 Full-width bars are at their true positions.**  At double-line
  scales (C1) every bar is drawn exactly where the model has it; the C4
  daylight nudge is for single-line views only.  Bars the model has tangent
  (the backwall verticals 5D1 against the horizontals 4D2 at 0.55" centre to
  centre, the pedestal legs against the cap top bars, the 4F2 legs on the
  line of the first 4F1 bar) are drawn touching; what looks like a clash is
  the model's layout and is reported (C9), not hidden.  A run of a U-bar
  seen from above ends at its leg's dot, never beside it.  Markups
  2026-10-19 (round 2): "When we show full width we have to show the actual
  locations", "These appear to show clashes but I don't believe there are
  clashes in the model", "Are these the actual locations of the bars since
  we are showing full width?", "What are these circles, the pedestal bars
  don't have two legs on one end?".
- **C9 Bars that nearly touch in the model are drawn as modelled and
  reported.**  Section G-G of End Bent 2 shows the backwall end verticals
  5D1 inside the cheek wall 1.1" from the cheek verticals 4E1: that is the
  model (SteelBridgeBackwallEB2F1VEL/F2VEL beside SteelBridgeCheekEB21MV04/
  MV05; End Bent 1 interleaves its bars 3.4" apart).  The sheet carries a
  MODEL CHECK note (`Builder.cage_clash_note`) until the cage is reconciled.
  Markup 2026-10-19: "There appear to be multiple clashing bars here that
  don't exist in the model".  The doubled 5D1 dots of End Bent 2's Section
  G-G are the model's too: each backwall's run of 21 verticals at 1'-0"
  from one end bar lands 3/8" short of the other end bar's offset, where a
  closing bar stands as well (V20 and V21 of both faces, 3/8" centre to
  centre, overlapping; End Bent 1's pair is at its right end, which no
  section cuts).  `Builder.bar_overlap_note` reports the closest such pair
  on the (3 OF 3) sheet.  Markup 2026-10-19 (round 5): "I'm seeing doubled
  bars here.  Do they exist in the model?"  The answer to such a question
  is always measured from the snapshot, never guessed.

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
  sheet via `LTSCALE_PER_SF`), and every centerline is long enough to show
  its dashes: at least 1.5 patterns (a line shorter than its pattern plots
  solid; checked), so the minor pattern plots 0.34" and the major 0.63".
  Markups: "Centerlines should have dashes not dots", 2026-10-19 (round 2)
  "All centerlines should be dashed".
- **D12 Everything the view clips gets a break line, each stub its
  own.**  A stub cut by the view window or by the extractor's clip (strap
  stubs, coping stubs, the closure slab in front of the cap, the cap stub
  beside a cheek wall, a pile) ends in a break line or a pile break at the
  cut (checked: a clipped edge without a break within 0.12" is a finding).
  Separate stubs along one clip get separate short break lines (one per
  strap stub, 0.08" beyond its edges); only elements that overlap along
  the clip (the closure slab and the front coping) share one.  Markups
  2026-10-19: "Add breaklines for elements that are broken" (round 2), "Do
  a bunch of small breaklines at the straps not one giant one" (round 4).
- **D4 Context is minimal.**  Bent sections do not show the landing or
  approach slab ("we want to focus on the end bents").  The end bent
  sections end at a break line through the rain closure slab 1.2 ft beyond
  the cap face: no coping and no MSE wall stub with its own break ("weird
  cutoffs").  Markup 2026-10-19: "Make these details smaller to fit the MSE
  walls in the details without the weird cutoffs or do a breakline at the
  4" closure slab and leave the details the same size".  A member that
  continues beyond the view (the pier wall under the cap in the pier
  sections) ends in a break line, with the dimension rows clear of its
  edges (markup 2026-10-19: "We need a breakline at 1 for the pier wall and
  we need to shift the dims down at 2 because they are too close to the pier
  wall edges").
- **D5 Construction joints are shown and named, with their shape.**  The
  cap/backwall joint is labelled "CONST. JOINT (SEE DETAIL "A")" in the
  sections, drawn there with the key of DETAIL "A" in the joint line: the
  straight joint piece is cut out across the key and the keyway profile is
  drawn dashed (hidden level) in its place, so it reads as a shear key; the
  joint is detailed as a keyed joint (DETAIL "A", sample B1-17).  The
  callout's tip is ON the joint line, at the corner where the straight
  piece meets the key on the FFBW side, never in the open top of the key
  (follow-up 2026-10-19: "it should point to the line where the two
  concrete surfaces interface").  The cap/pedestal joint is NOT called
  out (follow-up: "Don't call out the construction joint at the
  pedestals"); the pedestal sheet's note says the pedestals are cast on
  the cap and the cap top is a construction joint.  In Section C-C the
  joint row sits between the 5D1 and FFBW rows and its leader runs level to
  just before the FFBW face, then down to the key corner, so it crosses
  the face bar only and never the pedestal (follow-up sketch "Put the
  construction joint anno like this").  Follow-up markups: "Show the shape
  of the construction joint at the joint", 2026-10-19 "construction joint
  shape should be dashed and the horizontal line be removed to indicate a
  shear key".
- **D6 Reinforcing straps** (MSE soil reinforcement attached to the backwall)
  are shown in the sections as a line out of the back face at the strap
  elevation with a representative 6" embedment into the backwall, labelled
  "Δ REINF. STRAP" and dimensioned from the cap top, with the Δ legend giving
  the design responsibility and the loads from the backwall design calc
  (`data/strap_loads.json`, written by `scripts/export_strap_loads.py` from
  the selected backwall case; the test fails when the case changes), once
  per bent on the (1 OF 3) sheet, the other sheets referring to it (markups
  2026-10-19 round 2: "Update from backwall design calc", "Take out this
  note and only have it once in the drawings per bent and in this case on
  the next sheet"); the plan shows them as
  4" stubs out of the back face with one callout giving count and spacing
  ("7~Δ REINF. STRAPS @ 2'-9⁹⁄₁₆"").  They come from the model's schematic
  strap references (D-045).  Follow-up markup: "Show a representative embed
  into the wall for the strap".  The embedded end carries a small circle,
  the anchorage in the concrete (markup 2026-10-19: "Add a circle to
  indicate strap anchorage within the concrete").
- **D10 Monolithic pours have no joint line.**  The cheek wall and the
  backwall are one pour: no line is drawn on the cheek's inner face within
  the backwall thickness (SECTION G-G).  The face edge is one line from the
  cheek top to the lug, so the stretch within the backwall is cut out of it
  (`details._cut_joint`), not merely edges lying wholly inside it dropped.
  Follow-up markup: "Remove the joint here and show it monolithic";
  2026-10-19 (round 3): "Remove this interface line to make appear
  monolithic".
- **D13 A cut member's outline is closed.**  In a section the faces of a
  cut member are joined by its top and bottom edges; an edge the extractor
  tags with a context role because a context solid shares it (the landing
  slab sits on the backwall top, so that edge came back as "landing" and
  was skipped with the slab) is rebuilt from the model (the backwall top at
  the cut from the FFBW top edge, `Support.backwall_top`).  Checked: an end
  of a visible concrete outline segment in a section that no other outline,
  hidden edge or break line meets, and that is not a window clip, is a
  finding.  Markup 2026-10-19 (round 3): "Where are the tops of the
  backwalls?" (Sections A-A, B-B, C-C).
- **D14 A section draws the cut outline, not the silhouette beyond the
  cut.**  Concrete within the bar depth beyond the cut (1'-3") is not
  drawn: the backwall top rises toward the crown beyond the cut and its
  silhouette on the face edges (up to 0.025 ft above the cut) read as a
  sloped top with a second line under it.  The face edges are trimmed to
  the cut top and one level line joins them.  Model fact (checked
  2026-10-19 on the snapshot's backwall vertices): both backwall tops are
  two planes sloping along the bent to the crown and level across the
  wall thickness; the engineer expects a cross slope ("Check the model for
  all the backwalls, there should be a slope of the top of the backwall
  across the thickness of the wall"), so the (2 OF 3) sheets carry a MODEL
  CHECK note until the model has it.  The drawings follow the model (D11).
- **D11 Every callout describes modelled geometry.**  A feature removed from
  the model disappears from the sheets with its callout (D-044 omitted the
  nominal 3/4" pedestal chamfers: no chamfer callout; and chamfers are never
  called out on the details, they belong in the General Notes: follow-up
  2026-10-19 "Don't call out 3/4 chamfers. This will go in the General Notes
  later"), and modelled context
  near the bent is drawn: the end bent weather closure (4" rain closure slab
  between the front coping and the cap face, the closure copings on the low
  MSE walls, the side copings stopping at the cheek lugs) in the plan and
  sections, labelled "4" CLOSURE SLAB" and "COPING".  Markup: "These don't
  look like they incorporate the CAD model updates".
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
  more room"), never squeezed against the frame or over other views.  On
  the (1 OF 3) sheets the sections' boxes stand 0.15" apart, so the labels
  of one section and the dimension columns of the other keep about 0.45"
  between them, and the details column starts 0.3" beyond the sections and
  takes the rest of the width (the details centred in it, the legend
  wrapped to it).  Markups 2026-10-19: "Slide this down and shift Section
  B-B over slightly to make room for the overlapping annos between the
  details" (round 3), "Shift detail left to make room for the annos in
  between the details", "Shift detail over to make room for annos in
  between detail" (round 4).  The notes block of those sheets runs to the
  title block, so further notes go on the (2 OF 3) sheet.
- **E2 Tables** stay inside the drawing window with a margin to the frame;
  notes are a single numbered column with hanging indents.  Notes and other
  blocks at the lower right stop short of the BRIDGE NO. / bridge name
  block above the title block (`Sheet.bridge_block`; the layout check
  warns when a block runs into it).
- **E3 Notes** say what is representative, where sections are located, what
  is not shown and why, and carry the MODEL CHECK items (removed before
  issue).
- **E4 Status** stays "PRELIMINARY - NOT FOR CONSTRUCTION" until the EOR
  fields are filled.
- **E5 Titles are centred on their subject and aligned in a row.**  A view
  title is centred on the concrete outline it names (the cap centre of a
  section, the pedestal, the cheek wall), not on the box with its dimension
  columns, and the titles of views placed in one row share one baseline
  (`Composer.row` moves the higher ones down; checked).  Markup 2026-10-19
  (round 2): "Center the title on the drawing and line titles up
  vertically".
- **E6 A title stands clear of its view.**  The title is at least 0.3"
  below the lowest annotation of the view (the section flags and pile
  numbers under an elevation), so the drawing and its name do not read as
  one block; the footnote legend under the elevation ("* DIMENSIONS
  MEASURED ALONG FFBW") stands 0.3" under the flag row, clear of the
  circled pile numbers.  Markups 2026-10-19: "Shift up a bit to create
  space between drawing and title" (round 3), "Shift note down to make
  space between it and the number" (round 4).

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
   no crossings between views, titles centred and aligned) and
   `annotation_overlaps` (the `anno_check` findings, rule ids A1, A2, A3,
   A10, A11, A12, A13, A14, A21, B9, B11, B12, D3, D12, D13, E5) is empty
   (A19).
2. No leader parallel to or along the bar it points to (A3, checked); no
   leader under the stationing arrow (A7); no leader crossing another
   (A11, audit); no acute bend under a text (A10); fans leave the text
   toward the bars (A10); label columns with even rows (A14), end labels
   outside the plan (A15), pile numbers below the pulled values (A16),
   labels beyond the stub breaks (A17), parallel leaders joined at one
   landing (A18); labels beside a column in two lines where one line would
   reach a neighbour (A20); tips of different callouts apart (A21); labels
   that would stand between two views under their view (A22).
3. Every dimension text either sits in its space or has a line to it (B1);
   none crosses a line without a mask (B2); no stacked values; pulled-out
   values stand clear of their line (B9) and their pointer stops short of
   the text (B11); no dimension line along a parallel drawn line (B12).
4. Centerlines show as long-short dashes on every line, short ones included
   (D3); no stray break symbols (D2) and a break on everything clipped
   (D12); no dashed line over a solid line (D1); every cut outline closed,
   backwall tops included (D13); no joint line in a monolithic pour (D10).
5. Sections at 1/2" and larger draw bars as double lines (C1) with round
   ends and end-on legs as dots (C8, one dot per leg, none at a bend
   joint) at their true positions (C10); single-line views give
   overlapping bars daylight (C4); cover only to the outermost bar (C11);
   the title clear of the view (E6).
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

Follow-up comments on the rebuilt sheets, 2026-10-17/18 (all general):

| Where | Comment (engineer's words) | Rule | Resolution |
|---|---|---|---|
| all | These don't look like they incorporate the CAD model updates | D11 | chamfer callout gone with the chamfers; closure slab, copings and strap layout drawn; snapshot from model D-048 |
| dims | Make dim pointer two-piece lines, one straight looks weird | B1 | `View.pointer`: landing along the text, then the angled piece |
| plan | Stationing still has overlap | A5 | arrow sized to its text, wedge on the far side |
| Section A-A | Overlap here (back-side columns and the strap dimension) | B8 | columns 0.45" apart, strap dimension 0.15" off the face, right-hand columns text outward |
| pedestal elev. | Move the text into space and use a two-piece pointer for this cover annotation | B7 | cover values beyond the cap break with pointers |
| sections | This text is too close to the lines, pull it out and use a pointer (3") | B7 | pulled-out values go to the side away from the object, beyond the row's texts |
| Section A-A | Show the shape of the construction joint at the joint | D5 | keyway drawn in the joint line |
| Section A-A | Show a representative embed into the wall for the strap | D6 | 6" embed drawn |
| Section G-G | Remove the joint here and show it monolithic | D10 | cheek/backwall interface line dropped |
| all | In general double check that we are minimizing overlapping annotation with linework | A1 | annotation audit in the build and manifest, worked down to no entries: pulled values placed in row order (B7), the end bent pile embedment value in the band above the stirrup row (B7), end bent pile numbers off the flag letters (A8), pier bottom flags below the pile breaks, per-glyph text widths (A9), notes clear of the BRIDGE NO. block (E2) |

Markups on the 2.2.1 sheets, 2026-10-19 (all general):

| Where | Comment (engineer's words) | Rule | Resolution |
|---|---|---|---|
| B4-8 sections | Leaders unnecessarily cross other leaders; dim text sits on dim lines; leaders extend from the right side of text when objects are on the left side | A10, A11, B9 | leader-crossing audit; hoop callout tip above the side-bar fan; pulled values clear of their line, two-line in-place text placed beside its line; fans leave the text toward the bars |
| Section A-A | Add a circle to indicate strap anchorage within the concrete | D6 | circle at the embedded strap end |
| Section A-A | Construction joint shape should be dashed and the horizontal line be removed to indicate a shear key | D5 | keyway dashed, joint line cut across the key |
| B4-2 | Make these details smaller to fit the MSE walls without the weird cutoffs, or do a breakline at the 4" closure slab and leave the details the same size | D4 | break line through the closure slab; no coping or MSE stub in the sections |
| B4-3 | Shift dims like these slightly to the left so they don't look like they are sitting on the other dim line and it's clear they are a pop out | B9 | 1.2 text heights clear in vertical columns |
| View D-D | Minimize the leaders crossing line work if you can just shift the annotations a bit | A1 | WWR label with a horizontal leader into the hatch edge |
| pedestal elev. | Make leaders either 90 degree bends or obtuse interior angles | A10 | vertical angled piece when the tip is on the text side |
| pedestal elev. | Make better fit so these don't overlap or are so near each other; give each annotation some buffer | A2 | 4F2 label above the pedestal, the embedment column clear of the break line |
| pedestal elev. | Text is overlapping with the dim line because the pop out isn't far enough away; do not make the break in the leader overlap another line | B9 | cover value above the pedestal top with a square pointer |
| pier View D-D | Extend the centerline and point to it because this looks like we are pointing to the dim text | A13 | centerline extended above the dimension row |
| pier elevation | No need for the annotation leaders to be so close to the circled number | A13 | pile description and PT. leaders 0.3" off the circles |
| pier elevation | The leaders have too much overlap with drawing items; reposition and widen the distance between the separate leaders | A11 | end U-bar callout under the cap end |
| pier sections | Do a set of parallel leaders with an arrow per line crossing the other centerline in a dash area; put the text at the end | A12 | two parallel bearing leaders, cap centerline gapped |
| pier sections | Breakline for the pier wall; shift the dims down, too close to the pier wall edges | D4 | wall break line, bottom row lowered |
| pier sections | No need for these annotations to cross: text up, cover dim down | A11 | cover value above its pointer path |
| B4-10 G-G | Multiple clashing bars here that don't exist in the model | C9 | they are modelled (EB2 backwall end verticals inside the cheek); MODEL CHECK note |
| pedestal plan | Bar ends at the bends have odd shapes instead of smooth semi-circles; appears to show clashing bars that don't occur in the model | C8 | round bar ends, end-on legs as dots |

Markups on the 2.3.0 sheets, 2026-10-19 round 2 (all general; "for every comment check the rest of the drawings for similar problems"):

| Where | Comment (engineer's words) | Rule | Resolution |
|---|---|---|---|
| B4-1 plan | Add breaklines for elements that are broken | D12 | break lines on the strap and coping stubs and the closure slab; clipped-edge check |
| B4-1/B4-7 plan | Pull these out into space and minimize leader line overlaps; plenty of space to move these off to the right outside the drawing; too close to other stuff | A15 | one label column beyond the right cheek |
| B4-1 plan | All centerlines should be dashed | D3 | shorter dash patterns, centerlines lengthened, short-centerline check |
| B4-1 elevation | Shift to add more space (PT. K) | A2 | PT. K/H rows apart |
| B4-1 elevation | All these leaders are overlapping the text (pulled values, pile numbers) | A16 | pile numbers and flags in their own bands below the pulled values |
| B4-1 notes | Take out this note and only have it once per bent, on the next sheet | D6 | legend on the (1 OF 3) sheet only; cross-references elsewhere |
| B4-2 legend | Update from backwall design calc | D6 | 3.09 / 3.75 kip/ft (Strength I) from `strap_loads.json` |
| B4-2/B4-8 sections | Overlap (3" COVER text on the bottom-bar leader) | B10 | cover value at its dimension height, clear of the rows |
| B4-2 sections | I don't think these bars are actually here in the model; when we show full width we have to show the actual locations | C10 | no daylight nudge at double-line scales; tangency reported |
| B4-2 sections | Spread these annos out vertically with more equal space distribution; more row and column like | A14 | backwall labels in one evenly spread column |
| B4-3 Section C-C | These appear to show clashes but I don't believe there are clashes in the model | C10 | model has the pedestal legs tangent to the cap bars; drawn as modelled |
| B4-3 Section C-C | Either put these leaders parallel or move the anno and spread these leaders out; don't do almost parallel leaders | A18 | one tip for the bottom-bar callout; near-parallel check |
| B4-4 pedestal elev. | No need to overlap the drawings so much; move the break line and shift these annos out; no text over drawing lines, no leader break over drawings | A17 | cap stub break moved out, labels beyond it |
| B4-6 pier sections | Put these parallel leaders in the same plane; leaders only touch the text at one point | A18 | `parallel_leaders` with one connector and one landing |
| B4-6 pedestal plan | Why all the way up here for the text and not here? Look at how drawing items get crossed | B10 | cover value at its dimension height |
| B4-6 pedestal plan | What are these circles, the pedestal bars don't have two legs on one end? | C10 | U-bar runs end at the leg dot |
| B4-6 Section C-C | Are these the actual locations of the bars since we are showing full width? | C10 | yes: true positions, no nudge |
| B4-7 plan | Move this slightly so it doesn't look like it's an anno about the dim line (strap callout) | A14 | strap callout in its own row |
| B4-8 | Center the title on the drawing and line titles up vertically | E5 | titles on the subject centre, rows aligned |
| all | Perhaps there should be deterministic helpers to help check the anno layouts | A19 | `anno_check.py` with rule-id findings, run by the build and the tests |

Markups on the 2.4.0 sheets, 2026-10-19 round 3 (all general):

| Where | Comment (engineer's words) | Rule | Resolution |
|---|---|---|---|
| B4-11 pedestal plan/elev. | Where are these extra dots coming from? | C8 | 0.001 ft joint segments between the bend arcs and the legs of the model's bars were taken as end-on legs; `draw_bar3` ignores them |
| B4-10 Section C-C | Where are the tops of the backwalls? | D13 | the backwall top edge came back tagged "landing" (the slab shares it) and was skipped with the slab; reclassified to the backwall in every section; open-outline check |
| B4-10/B4-3 Section C-C | Move to make the leader cross less drawing items; adjust so leader doesn't cross so many drawing items | A14 | with a pedestal in the cut the joint callout points at the cap-top corner at the front face from the front column ("CONST. JOINT"); the keyed joint keeps its DETAIL "A" callout in A-A and B-B |
| B4-9 Section A-A | Overlapping put in 2 lines of text for fit (3" COVER) | A20 | cover value in two lines in every section |
| B4-8 elevation | Hard to see leader make 2 lines of text for fit (3~5C (TYP.)) | A20, A3 | two lines in the first gap right of the tip, angled leader; leader-along-line check |
| B4-7 pedestal plan | Dont put a dim so close to a parallel line if there is plenty of space (2" MIN. COVER) | B12 | cover dimension in the widest band clear of bars and surface breaks; parallel-line check |
| B4-6 Section A-A | Dim leaders are still overlapping dim text (3½") | B11 | pointer stops 0.35 th short of the text; pointer-gap check |
| B4-4 pedestal elev. | Remove. Only detail cover to the outermost bar (2¼" COVER) | C11 | top cover dimension removed; side cover to the outer leg stays |
| B4-1 elevation | Shift up a bit to create space between drawing and title | E6 | title 0.25" lower under the flags (the rows above are at their minimum pitch, A16) |
| B4-4 Section G-G | Remove this interface line to make appear monolithic | D10 | the cheek face edge is cut within the backwall thickness |
| B4-9 Section B-B (follow-up) | Check the model for all the backwalls; there should be a slope of the top of the backwall across the thickness of the wall | D14, C9 | the model's backwall tops are level across the thickness (slope along the bent only); the wedge was the silhouette of the top rising beyond the cut; sections draw the cut top level; MODEL CHECK note added |
| B4-11 pedestal elev. (follow-up) | Don't call out the construction joint at the pedestals; if you did it should point to the line where the two concrete surfaces interface | D5 | pedestal joint callout removed (the note stays); every joint tip on the joint line at the key corner |
| B4-10 Section C-C (follow-up) | Put the construction joint anno like this (sketch: column row between 5D1 and FFBW, level leader to the FFBW face, then down to the keyway) | D5 | C-C joint row between 5D1 and FFBW, leader by hand as sketched |
| B4-9 Section B-B (follow-up) | Slide this down and shift Section B-B over slightly to make room for the overlapping annos between the details (18" SQUARE PRESTRESSED CONCRETE PILE) | E1 | label 0.1" lower in its band; sections overlap 0.25", details column 0.3" off |
| B4-7 pedestal elev. (follow-up) | Don't call out 3/4 chamfers. This will go in the General Notes later | D11 | chamfer callout removed |
| B4-6 Section A-A (follow-up) | Put the CL leader two arrows on the same line; splay out the leaders for the bars, too geometric makes it look like there's some construction on the drawing | A18 | one CL BEARING leader line with two arrowheads; stacked bar ends get a splayed fan |

Markups on the 2.5.0 follow-up sheets, 2026-10-19 round 4 ("Look at the applicability of these comments to the rest of the drawings"):

| Where | Comment (engineer's words) | Rule | Resolution |
|---|---|---|---|
| B4-4 pedestal elev. | Call out the cover where it matters | C11 | side cover dimensioned inside the pedestal (end bents and pier) |
| B4-2 / B4-9 (1 OF 3) | Shift detail left / over to make room for the annos in between the details | E1 | sections 0.15" apart, details column narrower |
| B4-1 elevation | Shift note down to make space between it and the number | E6 | footnote 0.3" under the flag row (end bents and pier) |
| B4-1 plan | Do a bunch of small breaklines at the straps not one giant one | D12 | one short break line per strap and coping stub |
| B4-6 Section B-B | Do a double arrow leader and say 2~9A2 (EF) | A18 | the pair on the near side of the cut pile: one leader line, two arrowheads, "2~…A2 (EF)" (pier and end bents) |
| B4-9 Section B-B | Move to a better spot (pile description) | A22 | under the section in the centerline label's row |
| B4-10 Section C-C | Move to a better spot (Δ REINF. STRAP) | A22 | beyond the back dimension columns under the strap level (A-A and C-C of both bents) |
| B4-11 Section F-F | Remove this clear spacing anno; the project has a required clear spacing and these bars are in a mat centered in the wall | C11 | cover values removed from F-F and G-G |
| B4-10 Section C-C | Adjust so the leader ends are not so close to each other (4F1 / 5~4F2) | A21 | the U-bar's tip on its top run between the second and third dot; tips-apart check |

Markups on the round-4 sheets, 2026-10-19 round 5:

| Where | Comment (engineer's words) | Rule | Resolution |
|---|---|---|---|
| B4-11 pedestal elev. | 4F2 has a ton of space available: shift right and point at the bar midway between the other bars. No need to be so close to the corner and to the other bars | A21 | tip on the run midway between the second and third end-on bar, knee straight above, text to the right (end bents and pier) |
| B4-11 Section G-G | I'm seeing doubled bars here. Do they exist in the model? | C9 | yes: V20 and V21 of each face stand 3/8" apart (the run at 1'-0" from one end lands 3/8" short of the other end bar); drawn as modelled, MODEL CHECK note on the (3 OF 3) sheets |
