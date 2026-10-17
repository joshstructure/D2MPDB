# Distilled cap Mathcad worksheets

## What they are

Three Mathcad 15 worksheets distill the latest cap design reports in `project_current/cap_design/`: the 17 October 2026 re-exports (D-043). End Bent 1 and End Bent 2 use their 14 October cases. The pier uses its 12 October case.

Mathcad Prime can open the files through its XMCD converter. The generator has not opened them in Mathcad. Recalculate each worksheet after opening it.

## How each sheet is tied to its report

The generator evaluates the saved case (`selected_case.json`) with the cap tool (`pier_cap`). It uses the newest report in that folder whose printed case SHA-256 (canonical JSON) and C005 formula SHA-256 both match. The build stops if none matches.

The title block names the report, its generation time, the FBMP XML and the cap notebook package revision.

## Contents of each sheet

Each sheet has 12 sections:

1. Scope.
2. Inputs (yellow).
3. Two figures: cap elevation (piles, bearings, runs R1 to R9, added span bars, governing stations S, N, P, B) and cross-section between piles.
4. Steel areas and effective depths.
5. Flexure and minimum reinforcement.
6. Service I crack control.
7. Shear depth.
8. Actual-cage checks at the governing stations: torsion screen, simplified or general shear method (V_c, V_s from the hoop legs in the shear window, V_r), longitudinal tension, minimum transverse steel.
9. Transverse spacing at the governing interval.
10. Face shrinkage and temperature steel, and skin steel.
11. Hook development of the governing added span bar.
12. Summary of D/C ratios.

Regions N, P, B are vectors (index r). The five governing stations are vectors (index k). Each equation appears once.

## Taken from the tool, not recomputed

The station search, the intersected-leg window areas and developed (credited) steel areas (shown as inputs), detailing and geometry flags, transverse anchorage, the end grid and the D-regions come from the tool. Service III is not applicable (D-007). Fatigue is pending.

The summary notes list failing and pending tool checks that the sheet does not recompute. End Bent 1 and End Bent 2 fail calculated anchorage and closure at R2, R4, R6 and R8. The pier fails the end-grid pile envelope clearance. The sheet does recompute face shrinkage spacing. Both End Bent sheets fail it at D/C 2.938, so their distilled Status reads FAIL.

## Verification

`scripts/build_cap_mathcad.py` evaluates every expression with unit checking. It compares each result with the cap tool to 1 part in 10⁹ (about 830 to 890 values per cap). Rows the sheet does not print cover the general shear method, flange cracking, torsion, missing minimum transverse steel and the 0.006 strain limit. Some are real station rows from the tool. Others are synthetic actions run through the tool's own section calculation, because these caps' governing stations never reach those branches. The build stops on any mismatch.

A distilled Status of PASS covers only the recomputed numerical checks. It is not design acceptance.

## Rebuild

From the repository root:

```
.venv\Scripts\python.exe scripts\build_cap_mathcad.py
```

To redraw the figures first (needs Microsoft Edge):

```
.venv\Scripts\python.exe scripts\build_cap_mathcad.py --render-figures
```

Rebuild after the selected case, the report or the cap tool changes. Edits made inside Mathcad are lost on the next rebuild. The shared writer `scripts/mathcad_sheet.py` also serves the backwall worksheet.

## Files

- `End Bent 1 Cap Design.xmcd`
- `End Bent 2 Cap Design.xmcd`
- `Pier Cap Design.xmcd`
- `figures/`: elevation and section PNGs for each cap
- `../scripts/build_cap_mathcad.py`: builds the worksheets and runs the value comparison
- `../scripts/cap_mathcad_figures.py`: draws the figure PNGs
