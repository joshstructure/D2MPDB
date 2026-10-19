# Distilled pile Mathcad worksheets

## What they are

Two Mathcad 15 worksheets distill the pile analysis and design notebook (`Pile_Design.ipynb`, package `pile_design/`) for the D2 I-95 pedestrian bridge:

- `End Bent 1 Pile Design.xmcd`: the 18 in square prestressed concrete pile, Standard Plans Index 455-018, 12 x 0.6 in strands, 18 tons of downdrag per pile.
- `Pier Pile Design.xmcd`: the 20 in x 0.48 in steel pipe pile, noncomposite, no downdrag.

Both use the registered FB-MultiPier fixed-run exports of 19 October 2026 (`project_current/source_register.csv`, D-049). The `.xmcd` files are for Mathcad Prime's XMCD converter or Mathcad 15. The generator has not opened them in Mathcad: recalculate each sheet after opening it.

The notebook's export button writes the same sheet for whatever case is loaded (`pile_design.mathcad.build(e)`). This folder holds the two preset cases.

## How each sheet is tied to the notebook

`scripts/build_pile_mathcad.py` evaluates the preset case (`default_case('End Bent 1')`, `default_case('Pier')`) with the notebook model and writes the sheet from `pile_design/mathcad.py`. The title block names the pile_design package digest (SHA-256 of its sources and data), the FBMP file and its SHA-256, and whether the file is a registered export.

Inputs are the notebook's inputs, converted to the notebook's units and highlighted yellow. Some quantities cannot be derived in Mathcad without a search the notebook did in Python. They are inputs read from the notebook and say so in their captions:

- the FBMP governing records of each check (axial force, M2, M3, resultant moment and shear),
- the maximum strength head compression (Factored Design Load) and the maximum uplift,
- the folded bending-axis angles of the resultant-moment record and of the shear record (the sheet proves each with tan(alpha) = M_min / M_max),
- the neutral-axis depth `c_gov` at which the demand ray meets the resultant-axis curve (the sheet finds the same depth from its own vectors and compares it with the input).

## Contents

End Bent 1 (23 pages):

1. Design basis.
2. Inputs, including the Standard Plans option (strand count, area, jacking force, driving limit, splice strength).
3. Demands: the governing records and the drag load (P_u = FBMP + gamma_DR DD).
4. Pile spacing.
5. Section and prestress (Figure 1: strand pattern and bending axes), strand coordinates.
6. Axial resistance, Pn,max and phi Pn,max.
7. Interaction by strain compatibility. Live vectors over the neutral-axis sweep: strand strain and stress matrices (PCI power formula), compression block, Pn, Mn, net tensile strain, phi, Pr, Mr, plus the pure-compression and pure-tension points as scalars, a sample table, and Mr at P = 0 (Figure 2 is the picture).
8. Combined axial load and biaxial flexure, LRFD 5.6.4.5 (Eq. 5.6.4.5-3 or -1, chosen by the governing record).
9. Resultant bending axis: the sweep repeated with the section rotated, the demand ray and its intersection with the curve, and the check at the notebook's solved depth `c_gov`.
10. Tension (5.6.6.1, 5.8.2.4.1-1).
11. Shear, general procedure (5.7.3.4.2, with Eq. 5.7.3.4.2-2 when Av < Av,min and the negative-strain recomputation).
12. Service I stresses with the capped tension limits (0.6 ksi moderate, 0.3 ksi severe).
13. Prestress, driving strength and minimum size.
14. Geotechnical resistance: SDG Eq. 3-1 and Table 3.5.13-1.
15. Summary: the D/C of every check, the largest, the status, Figure 3 (a live D/C plot), and notes on the pending items.

Pier (10 pages): the same Sections 1 to 4, then the pipe section (Figure 1), axial compression (6.9.4.1 with the depth to fixity), flexure (6.12.2.2.3), combined axial load and flexure and tension (6.9.2.2.1, 6.8.2.1; Figure 2 is the envelope picture), shear (6.12.1.2.3b), geotechnical resistance, and the summary with the live plot.

## NOTE: the interaction diagram is a picture

The interaction diagram in Figure 2 of the End Bent 1 sheet is a static picture. The points behind it are live vectors (`P_r_x`, `M_r_x` for bending parallel to a face and `P_r_r`, `M_r_r` for the resultant axis): Mathcad recomputes them when an input changes, but the picture does not move. A live X-Y line plot needs a plot object that Mathcad itself saved, and none exists yet for a curve. The only native plot is Figure 3, the D/C summary.

## The live D/C plot

Figure 3 of both sheets is a Mathcad plot of `CheckGood` and `CheckNoGood`, patched from the plot Mathcad saved in the FDOT PSBeam run by `scripts/mathcad_plot.py` (same template and rules as the cap sheets). Blue stems are within the limit and red stems exceed it. The plot has not yet been opened in Mathcad.

## Verification

The generator evaluates every expression with unit checking and compares each result with the notebook (`pile_design.mathcad.verify`) to 1 part in 10^9 (an absolute 1e-9 below 1) before it writes a file:

- End Bent 1: 2,370 comparisons. Every notebook definition and external of the case is in the sheet and compared. All 121 points of both sweeps (neutral-axis depth, Pn, Mn, net tensile strain, phi, Pr, Mr), the end points, the strand coordinates, the ray intersection, Mr at P = 0, the shear quantities and the D/C of every check are included.
- Pier: 84 comparisons (every notebook definition and external plus the D/C of every check).
- One further value differs by design and is held to 2 %: the D/C evaluated exactly at `c_gov` against the notebook's interpolated resultant-axis D/C (0.3981 against 0.3982).

The build stops on any mismatch, on an evaluation order Mathcad would not follow (`check_order`), on a region that crosses a page or passes the right edge, and on a displayed unit that does not fit its value. `tests/test_pile_mathcad.py` repeats these checks, proves that both files and both figures are current, tests the other branches (Eq. 5.6.4.5-1, a bending axis parallel to a face, other strand patterns, clay), and checks that the D/C plot splits at the limit.

A distilled Status of PASS covers the recomputed numerical checks only. It is not design acceptance. The pending items of the notebook (environment classification, pile-to-cap connection, downdrag source, minimum tip, scour, drivability, steel grade and corrosion allowance for the pipe) stay open; the last notes of each sheet list them.

## Limitations

- The Mathcad sheets of the prestressed pile are structural in the strand count: the strand-row sums are written for the pattern of the case. Changing the numbers (strength, loads, prestress, geometry) recalculates. Changing the strand pattern needs a rebuild.
- Hollow piles (Index 455-030) are not distilled; the generator refuses them.
- The sheet takes the governing records from the notebook. A different load case needs a rebuild.
- Edits made inside Mathcad are lost on the next rebuild.
- The Blockpad edition of these sheets is in `../pile_bpad/`. Blockpad has no vector variables, so it does not carry the 121-point sweeps as formulas (Figure 2 there is a picture; the check at `c_gov` is live).

## Rebuild

From the repository root:

```
.venv\Scripts\python.exe scripts\build_pile_mathcad.py
```

To redraw the figure PNGs first (matplotlib; no browser needed):

```
.venv\Scripts\python.exe scripts\build_pile_mathcad.py --render-figures
```

Rebuild after changing the pile_design package, the registered FBMP exports or the generator. The tests fail with a rebuild message until you do.

## Files

- `End Bent 1 Pile Design.xmcd`, `Pier Pile Design.xmcd`
- `../pile_design/mathcad.py`: the generator (`sheet`, `verify`, `build`, `figures`)
- `../pile_design/mathcad/*.png`: the figures (section and interaction picture of each support)
- `../scripts/build_pile_mathcad.py`: the command line
- `../scripts/mathcad_sheet.py`, `../scripts/mathcad_plot.py`: the shared writer and the plot patcher (also used by the backwall and cap sheets)
- `../tests/test_pile_mathcad.py`: the tests
