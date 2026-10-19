# Distilled cap Blockpad documents

## What they are

Three Blockpad 1.9 documents distill the 10-19 cap design reports in `project_current/cap_design/`. Each document holds one report. The reports are named `CapDesignEndBentOne`, `CapDesignEndBentTwo` and `CapDesignPier`. They are the Blockpad edition of the three Mathcad worksheets in `cap_mathcad/`.

Nothing here has been opened in Blockpad. The results stored in the files come from the generator's own evaluator, not from Blockpad. Recalculate each document after opening it.

## How each sheet is tied to its report

The mechanism is the same as for the Mathcad sheets. The generator evaluates the saved case (`selected_case.json`) with the cap tool (`pier_cap`). It uses the newest report in that folder whose printed case SHA-256 (canonical JSON) and C005 formula SHA-256 both match. The build stops if none matches.

The provenance paragraph in the title block names the report, its generation time and the case hash. `verification.json` also records the report file, both hashes, the FBMP XML and its hash, and the cap notebook package revision. `tests/test_cap_bpad.py` checks that the report is the newest dated one for its cap and that the hashes match what the report prints.

## Contents of each sheet

Each report has the same 12 sections as the Mathcad edition:

1. Scope.
2. Inputs (amber).
3. Figure 1, cap elevation, and Figure 2, cross-section between piles.
4. Steel areas and effective depths.
5. Flexure and minimum reinforcement.
6. Service I crack control.
7. Shear depth.
8. Actual-cage checks at the governing stations.
9. Transverse spacing at the governing interval.
10. Face shrinkage and temperature steel, and skin steel.
11. Hook development of the governing added span bar.
12. Summary of checks, then Figure 3.

What differs from the Mathcad edition:

- Blockpad has no vector variables, so the vectors become scalars. Region quantities end in `_N`, `_P`, `_B`. Station quantities end in `_S`, `_N`, `_P`, `_B`, `_M`. Face quantities end in `_1`, `_2` and so on. The bar tables `A_bar` and `d_bar` become the functions `Ab(k)` and `Db(k)`.
- Each equation is shown once, for region N, station S and face 1. The same equations for the other regions, stations and faces sit in collapsed sections. The values of all of them appear side by side in green tables (regions N, P, B; the five stations; the faces).
- The inputs are amber definitions. The station inputs and the face inputs are tables whose cells hold the definitions.
- Figures 1 and 2 are native canvases drawn from `PlotLines`, circles, labels and linear dimensions. The Figure 2 dimensions `h`, `d (B)`, `d (N)` and `b` read the live values. They are not pictures.
- Figure 3 is a live stem chart on a canvas. Every check has a blue stem and a red stem. The blue stem shows when the ratio is within 1.0 and the red stem when it is over. The other stem is `null` and does not draw. The vertical scale `DC_ymax` follows the largest ratio.
- Each check has a result string `Chk_...` in a collapsed section. The strings are the journal's standard `✓ PASS` and `⊗ FAIL`, and `Status` is `✓ All Checks Pass` or `⊗ There are FAILURES`. The journal's conditional table colours apply to them. The Summary table lists every check, with regions N, P and B as separate rows, each with its ratio and result, and an OVERALL row.

## Taken from the tool, not recomputed

The same as the Mathcad edition: the station search, the intersected-leg window areas and developed steel areas (shown as inputs), detailing and geometry flags, transverse anchorage, the end grid and the D-regions. The notes at the end of Section 12 list the failing and pending tool checks that the sheet does not recompute. As in the Mathcad edition, both End Bent sheets read `⊗ There are FAILURES` because of face bar spacing, and the pier reads `✓ All Checks Pass`. That covers only the distilled numerical checks. It is not design acceptance.

## Verification

`scripts/build_cap_bpad.py` walks the same blocks as `scripts/build_cap_mathcad.py`. Before it writes anything it does these, and it stops on any failure:

- It reads every formula back out of the XML it is about to write and evaluates it with `BpEngine` (`scripts/bpad_sheet.py`), an evaluator of Blockpad syntax that does not share code with the Mathcad evaluator. It checks units and undefined names, and rejects any report or definition name that looks like a spreadsheet cell address, duplicate names, XML comments, newlines in paragraphs, exponent notation, bare-unit division or multiplication, and function names outside the set the journal uses.
- It compares the results with the cap tool to 1 part in 10⁹ (`verification.json` has the counts, about 860 to 890 per cap). Rows the sheet does not print cover the general shear method, flange cracking, torsion, missing minimum transverse steel, the 0.006 strain limit, the moment floor and end-truncated windows. They are real tool rows plus synthetic actions run through the tool's section calculation, as for the Mathcad sheets. Every branch must be reached.
- It builds the Mathcad worksheet for the same cap and compares the values both sheets hold (535 per cap). The Blockpad `Status` must agree with the Mathcad `Status`.
- It checks that the Figure 3 stems follow the check list in order, and that every `Chk_` string matches its ratio.

`tests/test_cap_bpad.py` builds all three caps once and checks:

- the committed documents, fragments, preview data and `verification.json` equal a fresh build;
- each build is tied to the newest matching report;
- each cap has at least 800 tool comparisons, reaches every branch and compares at least 500 values with the Mathcad sheet;
- a deliberately wrong station equation (`V_c` with 0.0316 changed to 0.0317) stops the build;
- the XML parses, loads with the workflow's `Journal` class, has one report whose name is not used in the journal, and follows the formula rules above;
- `Status` and the failing `Chk_` strings agree with the Mathcad sheet, the Figure 3 stems name the checks in order, and `DC_ymax` reaches the largest ratio;
- the preview data has an entry for each canvas.

None of this is a Blockpad recalculation. A distilled result of ✓ is not design acceptance.

## Preview

An independent HTML and PNG preview can be made without Blockpad:

```
.venv\Scripts\python.exe scripts\bpad_preview.py "cap_bpad\Pier Cap Design.bpad" --out generated\cap_bpad_preview --expand --png
```

`--expand` opens the collapsed sections. `--png` needs Microsoft Edge. The preview shows the results stored in the file and draws the canvases from `cap_bpad/preview/<ReportName>.canvases.json`. It is an approximation. It is not a native Blockpad rendering, and it recalculates nothing.

## Adding to the journal

The journal is not changed by this folder. To add the three reports, plan a task and run from the repository root:

```
.venv\Scripts\python.exe tools\bpad_workflow.py prepare T0xx --objective "Add the distilled cap design reports" --add report:CapDesignEndBentOne --add report:CapDesignEndBentTwo --add report:CapDesignPier --write report:PedBridge
```

Then:

1. In `tasks/T0xx/`, `components.json` names the file in `components/` for each key. Copy each `cap_bpad/fragments/<ReportName>.xml` over the matching added file (each starts as an empty `<report name="..." />`).
2. In the `PedBridge` file, add three index links under "Specific calculations and foundations", in the form the other links use (`<link address="#CapDesignPier">`).
3. `.venv\Scripts\python.exe tools\bpad_workflow.py import-components T0xx`
4. `.venv\Scripts\python.exe tools\bpad_workflow.py check T0xx`
5. `.venv\Scripts\python.exe tools\bpad_workflow.py assemble T0xx --output generated\T0xx-review-01`
6. Review the candidate, then `.venv\Scripts\python.exe tools\bpad_workflow.py promote generated\T0xx-review-01`.

The fragment is the report element only. The document-level `PASS` and `FAIL` colour rules, the `All Checks Pass` and `There are FAILURES` colour rules, and the `Result only` style already exist in the journal. The report names do not collide with `PierCapDesign`. The workflow rules in `workflow/README.md` and `AGENTS.md` apply, including the promotion policy.

## Points to confirm natively in Blockpad

Open a document, recalculate, and look at these first:

- Amber input definitions inside table text cells (the station and face input tables).
- Unicode Greek names with two underscores, such as `ε_s_S` and `θ_g_S`.
- Compound-unit literals such as `0.6 in^2/ft`, and the `to in^2/in` and `to in^2/ft` displays.
- `Tan` of an angle (`θ_g_S` and `θ_S` are in degrees).
- `null` inside `PlotLines` hiding a stem.
- A `lineardim` whose label is a live formula (Figure 2).
- Long `Max(...)` argument lists (the Summary scale `DC_ymax`).

## Rebuild

From the repository root:

```
.venv\Scripts\python.exe scripts\build_cap_bpad.py
```

Rebuild after the selected case, a report, the formulas or the generator changes. Edits made inside Blockpad are lost on the next rebuild. Use the full build for the committed files: `--skip-mathcad` leaves out the Mathcad comparison and writes a different `verification.json`. Run the tests with:

```
.venv\Scripts\python.exe -m unittest tests.test_cap_bpad -v
```

## Files

- `End Bent 1 Cap Design.bpad`, `End Bent 2 Cap Design.bpad`, `Pier Cap Design.bpad`
- `fragments/<ReportName>.xml`: the report element alone, for adding to the journal
- `preview/<ReportName>.canvases.json`: the resolved canvas geometry used by the preview
- `verification.json`: report, hashes and verification counts for each document
- `../scripts/build_cap_bpad.py`: builds the documents and runs the comparisons
- `../scripts/bpad_sheet.py`: formula emitter, `BpEngine` and the XML writers
- `../scripts/bpad_preview.py`: independent HTML and PNG preview
- `../tests/test_cap_bpad.py`: staleness and verification tests
