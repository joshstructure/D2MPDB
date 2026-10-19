# End-bent backwall, cheek walls and tie-back straps

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/End_Bent_Backwall_Design.ipynb)

[End_Bent_Backwall_Design.ipynb](End_Bent_Backwall_Design.ipynb) replaces the template Mathcad sheet *3.End Bent 1 Backwall Design* (I-4 Bridge 920232, FC 02/2025) with a calculation built on this project's registered sources. It shares the cap notebook's unit-aware formula engine, MathML notation, Recalc control and widget/Plotly compatibility layers. The calculation package is `end_bent_walls/`.

## Basis

| Subject | Basis |
| --- | --- |
| Sources | EB-CASE, EB-XML and CAD-MODEL from `project_current`, checked against `source_register.csv` on upload; journal values for the Type F pad, temperature, span and wind; MCAD-S1 for the 90 psf pedestrian load |
| Decisions | D-004 common end-bent basis; D-014–019 loading and strap assumptions; D-026/D-033 adopted wall geometry; D-034 verified landing quantities. Connection and fabrication acceptance remain separate. |
| Codes | AASHTO LRFD 10th edition (2024); Guide Specifications for Pedestrian Bridges; FDOT Structures Manual January 2026 (SDG and SDM) |
| Combinations | Service I, Strength I, Strength III (FBMP WS1 and WS2), Strength IV. Strength V is not required for this pedestrian bridge. TU/SH use the force-effect factor. |

## Method

1. **Loads on the end bent.** Active Coulomb earth pressure acts over the cap and backwall height (cap soffit to crown, 7.090 ft), conservatively across the full 251-in cap/cheek envelope. The concrete cap and backwall are 235 in long. The pedestrian load (LS) and 4 in landing slab weight (ES) act as uniform surcharges. Bearing-level forces retain temperature/shrinkage pad actions and the available FBMP wind actions, pending matching current raw analyses. Native concrete volumes include the cheek lugs; the minimum stabilizing backwall weight and maximum cheek weight bound the two ends. Landing gravity uses the verified maximum slab area divided by backwall length as an equivalent tributary length, retaining D-017's 50% share and no stabilizing credit.
2. **Overturning about the pile top.** SDG 3.13.2.N.3 requires the strap loading to include pile placement tolerance. Vertical-load arms therefore use the pile line shifted 3 in toward the fill. Each vertical item takes the maximum or minimum permanent-load factor according to the sign of its arm. Live load and wind uplift take no stabilizing credit. The landing slab reaction is excluded from overturning (D-017).
3. **Tie-back force.** The single pile row is effectively pinned (FBMP fixity 0.10). The design strap force is `max(H, M / y_strap)`; `M / y_strap − H` is the force the piles must supply at the pile top. The template reported ΣH under an `M/y` label; this calculation shows both and designs for the larger. Loads are reported per foot of **backwall** with the SDM 12.3.F plan note.
4. **Backwall.** The backwall is a 1-ft vertical cantilever at the cap construction joint. *Strap slack:* soil pressure causes fill-face tension. *Strap engaged:* the strap pull at its elevation exceeds the backwall soil moment and causes span-face tension. Both faces are designed:
   - flexure with the exact required-steel quadratic
   - minimum reinforcement
   - tension-controlled strain
   - crack control at fss ≤ 0.80 fy (SDG 3.10.F)
   - spacing and shrinkage/temperature steel
   - shear (β = 2)
   - interface shear (SDG 1.15)
5. **Cheek walls.** No retained fill (D-018). Strength III and Service I wind act on a 1-ft vertical strip (V = 130 / 70 mph, G = 0.85, C_D = 1.6). Strength III K_Z = 1.020 conservatively rounds the current journal's 1.019. One centered mat of #4 at 10 in each way has tangent vertical/horizontal bars, 3.5 in minimum physical face cover and a 3.75 in effective depth in the weaker wind direction. Both face shrinkage/temperature requirements are combined in the mat (0.220 in²/ft); provided steel is 0.240 in²/ft. The required cover input remains 2 in pending environmental classification. Interface resistance assumes developed bars; actual anchorage and the cap/lug load path remain pending.
6. **Cap supplement.** Torsion and weak-axis bending along the cap come from discrete bearing actions against uniform strap restraint. Torsion is screened against 0.25 φ Tcr. These actions are not in the FBMP cap model.

## Differences from the template Mathcad

- Discrete two-bearing actions on a 235-in core cap / 251-in overall envelope replace loads spread over a 111 ft cap with 15 bearings. Skew terms drop out (0°).
- Pedestrian surcharge replaces the HL-93 equivalent height. Braking, wind on live load and vehicular surcharge are not applicable.
- The pile placement tolerance (SDG January 2026) and every dead-load arm enter the overturning sum.
- The backwall is designed for the engaged-strap reversal. The template ignored the strap load in backwall design, which is unconservative for the span face and the joint.
- Required steel uses the exact quadratic. The template's `Find` held the stress-block depth at its provided-steel value: 0.2197 in² against the exact 0.2185 in².
- The crack-control stress limit is 0.80 fy (SDG 3.10.F), not 0.6 fy.

## Results with the reviewed defaults (16 October 2026)

| Item | Value |
| --- | --- |
| Tie-back load per foot of backwall | 3.09 kip/ft service · 3.75 kip/ft factored (Strength I), provisional pending current analysis loads |
| Strength I resultant | 5.23 ft above the pile top; strap at 3.50 ft |
| Pile-head force for equilibrium | up to 24.3 kip (Strength I); not in the FBMP model |
| Backwall φMn, #5 @ 12 in each face | 11.89 kip-ft per ft; demand 1.30 (fill face) and 4.31 (span face) |
| Cheek #4 @ 10 in each way, one centered mat | φMn = 3.91 kip-ft/ft, Mu = 0.760; shrinkage/temperature D/C = 0.917 |
| Cap torsion screen | 51.43 kip-ft vs 0.25 φ Tcr = 81.20 kip-ft |
| Check register | All numerical checks pass; prerequisites remain pending |

The 6-in toleranced bearing eccentricity remains a major overturning contribution. Raising the strap toward the resultant reduces strap and pile forces; its final elevation needs MSE vendor coordination. The spacing study checks whole-inch common cheek spacings: 12 in has shrinkage/temperature D/C 1.100; 11 in has 1.008; 10 in has 0.917. Ten inches is the widest passing whole-inch spacing. Existing CAD remains at its prior layout, including the 12 3/8-in horizontal gap under COH-024; this notebook update does not relocate CAD bars.

## Pending before final design

- SDG 3.13.2.N.3: geotechnical confirmation that settlement of the soil above the cap bottom will not exceed 2 in.
- Strap elevation aligned with an MSE reinforcement level.
- Cheek mat development, lug/cap load transfer, strap interfaces and fabrication details (COH-023).
- FIB-36 shrinkage strain (the template value is a placeholder; the Span 1 `.dat` file is missing).
- Environmental classification for the covers.
- **FBMP source audit.** In `End Bent 1_Fixed.XML` one 3.0 kip DC end load is on node 4, which is pile 4's head, not the right cap end (node 44).
- **Analysis currency.** Current EB1 case requires XML SHA-256 `23bb3afc…`; the available XML is `8414fbed…`. EB2's matching XML is missing. Common EB1 bearing actions have not been verified to bound EB2.

Cell 1 checks three evidence-backed confirmations: adopted calculation geometry, wind factor consistent with the journal, and landing bearing/tributary basis. Six confirmations remain unchecked. The current journal matches accepted T009 but the source register still lists T006; this update records both identities without changing journal acceptance. The journal's MSE exclusion module explicitly excludes elevation strap routing. Details and native measurements are embedded in `end_bent_walls/data/project_evidence.json`.

CAD uploads now use native measurements tied to the exact reviewed file hash. The old BRep-text extent parser misread the transformed, Boolean-cut and spline surfaces. A different CAD revision is refused until its native measurements are reviewed. Cap-case/XML uploads cannot overwrite physical cap dimensions with a combined or historical analysis envelope. Editing a dimension clears its measured volume override; editing a confirmed input reopens its confirmation. Schema-1 saved cases retain their original two-face cheek reinforcement and unconfirmed assumptions.

## Use and maintenance

Run all cells in Colab. Cell 1 re-reads registered files and records confirmations. Cell 2 holds inputs, drawings, overturning tables, the D/C register with *Equation & values*, reviews and exports:
- case JSON
- HTML report
- checks CSV
- MSE strap handoff workbook

**Report navigation.** The linked contents list opens and jumps to any of the 17 sections. Click a section heading to collapse or expand it, or use the toolbar to expand or collapse every section. Sections initially open; charts resize when reopened. Printing opens sections, equations and tables, then restores their prior state afterward.

**QC dropdowns in the report.** Each equation is followed by a collapsible row. The row's summary, *What it represents*, is visible when collapsed. Opening it shows a drawing built from the current case (`end_bent_walls/schematics.py`) with the defined quantity in red. A panel beside the drawing gives the result and the substituted values. Free-body rows add a numbered table of γ, arm, γ·F and γ·M. A legend lists each term's value and source. The report toolbar opens or closes all QC rows separately; printing retains their selected state.

After changing `end_bent_walls/` or the shared `pier_cap/` modules, run `python scripts/build_backwall_notebook.py`. Then run `python -m unittest tests.test_end_bent_walls`. The tests reproduce the template's flexure, crack-control and shear values with its own inputs, pin the project statics, and verify that the embedded package matches the repository files.

## Mathcad edition

[End_Bent_Backwall_Design.xmcd](End_Bent_Backwall_Design.xmcd) is a Mathcad 15 worksheet with the same inputs, equations and load combinations as the notebook. Mathcad Prime opens it through its XMCD converter. It runs in 12 sections, from design basis and inputs to the summary of checks. The five combinations are vectors and the three wall strips (backwall fill face, backwall span face, cheek wall) use a range variable, so each equation appears once and shows every case. It has two figures: the end-bent free body and the backwall strip in both strap states. Inputs are yellow and the plan values are boxed.

`scripts/build_backwall_mathcad.py` writes the worksheet from a compact equation list. It evaluates every expression with unit checking and compares more than 240 results with the notebook to 1 part in 10⁹. It stops if any result differs, if an input differs from the notebook, or if two names would display the same in Mathcad. Rebuild it after rebuilding the notebook:

```
python scripts/build_backwall_notebook.py
python scripts/build_backwall_mathcad.py
python -m unittest tests.test_end_bent_walls
```

Add `--render-figures` to redraw `end_bent_walls/mathcad/*.png` (requires Microsoft Edge). The tests fail when the committed worksheet is out of date. The worksheet is generated, so edits made in Mathcad are lost on the next rebuild. Change the equation list instead, or treat an edited copy as a separate calculation.

## Blockpad edition

[end_bent_walls/End Bent Backwall Design.bpad](end_bent_walls/End%20Bent%20Backwall%20Design.bpad) is a Blockpad 1.9 document with one report, `EndBentBackwallDesign`, distilled from the same equation list as the Mathcad worksheet. `scripts/build_backwall_bpad.py` translates each equation with the emitter and evaluator of `scripts/bpad_sheet.py` (the ones the cap sheets in `cap_bpad/` use) and follows the same scalarisation: Blockpad has no vector variables, so the five combinations become scalars ending in `_SERI`, `_STRI`, `_STRIII1`, `_STRIII2`, `_STRIV`, the three strips in `_FF`, `_SF`, `_CK`, and the torsion stations in `_0` to `_7`. Each equation is shown once (Service I, the fill face, station 0); the others sit in collapsed sections with the values side by side in green tables. Inputs are amber definitions. The two figures are native canvases with live dimensions, Section 12 ends with a live stem chart of the D/C ratios, and the results use the journal's `✓ PASS` / `⊗ FAIL` strings. The sidecars (`end_bent_walls/bpad/`: the report fragment for a journal task, the canvas geometry for `scripts/bpad_preview.py`, and `verification.json`) are written with it.

Before writing, the generator reads every formula back out of the XML, evaluates it with the independent Blockpad-syntax evaluator, checks every amber input against the notebook input, compares more than 240 results with the notebook to 1 part in 10⁹, and (for the committed build) compares the values it shares with the Mathcad worksheet. `tests/test_backwall_bpad.py` fails when the committed document is out of date. Rebuild it after the notebook or the generator changes:

```
python scripts/build_backwall_bpad.py
python -m unittest tests.test_backwall_bpad tests.test_backwall_bpad_export
```

The notebook's **Export distilled Blockpad (.bpad)** button (Exports tab) writes the same sheet for the current case, built and verified in memory by the same generator (`end_bent_walls/exports.py`, `distilled_bpad`), into a timestamped `exports/` folder together with `backwall_bpad_verification.json`; the full bundle ZIP holds both. The portable notebook embeds the scripts it needs (`scripts/build_backwall_notebook.py`, `EMBEDDED_SCRIPTS`). Nothing here is a Blockpad recalculation: open the document in Blockpad and recalculate it. A distilled result of ✓ covers the recomputed numerical checks only and is not design acceptance.
