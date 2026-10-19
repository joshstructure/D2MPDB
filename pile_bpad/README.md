# Distilled pile Blockpad documents

## What they are

Three Blockpad 1.9 documents distill the pile analysis and design notebook (`Pile_Design.ipynb`, package `pile_design/`) for the D2 I-95 pedestrian bridge. Each document holds one report. The reports are named `PileDesignEndBentOne`, `PileDesignEndBentTwo` and `PileDesignPier`:

- `End Bent 1 Pile Design.bpad` and `End Bent 2 Pile Design.bpad`: the 18 in square prestressed concrete pile, Standard Plans Index 455-018, 12 x 0.6 in strands, 18 tons of downdrag per pile.
- `Pier Pile Design.bpad`: the 20 in x 0.48 in steel pipe pile, noncomposite, no downdrag.

They are the Blockpad edition of the two Mathcad worksheets in `pile_mathcad/` (End Bent 2 has no Mathcad sheet; its sheet uses the same equations with its own FBMP export). All three use the registered FB-MultiPier fixed-run exports of 19 October 2026 (`project_current/source_register.csv`, D-049).

Nothing here has been opened in Blockpad. The results stored in the files come from the generator's own evaluator, not from Blockpad. Recalculate each document after opening it.

## How each sheet is tied to the notebook

`scripts/build_pile_bpad.py` evaluates the preset case of each support (`default_case('End Bent 1')`, `'End Bent 2'`, `'Pier'`) with the notebook model and writes the sheet from `pile_design/bpad.py`. The notebook's "Export distilled Blockpad (.bpad)" button calls the same generator for whatever case is loaded.

The title block names the `pile_design` package digest (SHA-256 of its sources and data) and the Design basis names the FBMP file and its SHA-256. `verification.json` records the package revision, the FBMP file and hash, the support, the family, the comparison counts, the status and the SHA-256 of each document. `tests/test_pile_bpad.py` checks that these equal the current package (`pile_design.mathcad.package_revision()`) and the hashes registered in `pile_design/data/sources.json`.

## Contents of each sheet

The sheet walks the block list of the Mathcad generator (`pile_design.mathcad.sheet`), so the sections, equations and captions agree with the Mathcad edition.

End Bent 1 and End Bent 2 (prestressed pile), 15 sections:

1. Design basis.
2. Inputs (amber), including the Standard Plans option.
3. Demands from the FBMP export: the governing record of each check (amber table), the drag load and `P_u` (green table).
4. Pile spacing.
5. Section and prestress (Figure 1) and the strand coordinates.
6. Axial resistance.
7. Interaction by strain compatibility: the end points of the curve, the section about an axis parallel to a face, and the moment resistance at P = 0.
8. Combined axial load and biaxial flexure, LRFD 5.6.4.5.
9. Resultant bending axis, the check at the solved neutral-axis depth `c_gov`, the strand table, and Figure 2.
10. Tension.
11. Shear, general procedure.
12. Service I stresses.
13. Prestress, driving strength and minimum size.
14. Geotechnical resistance.
15. Summary of checks, then Figure 3.

Pier (pipe pile): Sections 1 to 4, the pipe section (Figure 1), axial compression, flexure, combined axial load and flexure with tension (Figure 2), shear, geotechnical resistance and the summary with Figure 3.

## What differs from the Mathcad edition

- Blockpad has no vector variables, so the vectors become scalars. The record vectors (index g, one record per check) end in `_1` to `_6` (`_1` to `_4` for the pier). The strand vectors end in `_1` to `_12` (the count of the strand pattern). The record number replaces the zero-based index of the Mathcad sheet, and the text says "record 2" where the Mathcad sheet says "index 1".
- Each equation is shown once, for record 1 and strand 1. The same equations for the other records and strands sit in collapsed sections. The values appear side by side in green tables (the demands, the strands at `c_gov`, the shear strands).
- **The two 121-point interaction sweeps are not written as formulas.** Figure 2 is a native canvas drawn from the resolved curve points of the notebook (`e.curve`): the factored curve for bending parallel to a face, the factored curve about the resultant axis, and the nominal curve as a dashed native line. The curves are a picture and do not move when an input changes. The phi Pn,max line, the three demand points and the legend values are live formulas of the sheet. The note under the figure says so.
- The check at the notebook's solved neutral-axis depth `c_gov` is written in full: `c_gov` is an amber input, then the strain, power-formula factor and stress of every strand, the running sums, the compression block, `P_n_cg`, `M_n_cg`, `eps_t_cg`, `phi_cg`, `P_r_cg`, `M_r_cg` and the ratio `DC_cg`. Names ending in `_cg` are the Blockpad names of the Mathcad vectors that end in `_p`.
- Values that the Mathcad sheet finds by a search over the sweep are amber inputs read from the notebook, and say so in their captions: `M_r_P0` (moment resistance at P = 0), `P_r_rs` and `M_r_rs` (where the demand ray meets the resultant-axis curve) and, when Eq. 5.6.4.5-1 applies, `P_rx` and `P_ry`. The equations that use them (`M_rx`, `DC_bi`, `DC_splice`, `DC_ray`, `DC_rs`, `P_rxy`) stay live.
- The sweep vectors, the sample table of the sweep and the Figure 3 data vectors are not written. The summary uses the individual `DC_` scalars.
- Figure 1 (section or pipe ring) is a native canvas. The outline and strands are the notebook's layout as a picture. The dimensions `D_pile`, `d_edge` or `D_out` and the bending-axis angles are live.
- Figure 3 is the live stem chart of the cap sheets: every check has a blue stem and a red stem on a canvas, the other stem is `null`, and `DC_ymax` follows the largest ratio.
- Each check has a result string `Chk_...` in a collapsed section, using the journal's `✓ PASS` and `⊗ FAIL`. `Status = If(DC_max <= 1, "✓ All Checks Pass", "⊗ There are FAILURES")`. The notebook's tolerance for a check at exactly 1.0 is 1 part in 10⁹. The pile spacing check is exactly 1.0 for these piles (3 diameters), so `DC_max <= 1` is satisfied only because the quotient is exactly 1 in floating point. Rebuild after any change there.
- A distilled result of ✓ covers only the recomputed numerical checks. It is not design acceptance, and the pending items of the notebook stay open (the notes at the end of Section 11 or 15 list them).

## Verification

`pile_design/bpad.py` builds each sheet and stops on any failure:

- It reads every formula back out of the XML it is about to write and evaluates it with `BpEngine` (`scripts/bpad_sheet.py`), an evaluator of Blockpad syntax that does not share code with the Mathcad evaluator. It checks units and undefined names, and rejects any report or definition name that looks like a spreadsheet cell address, duplicate names, XML comments, newlines in paragraphs, exponent notation, bare-unit division or multiplication, and function names outside the set the journal uses.
- It compares the results with the notebook model to 1 part in 10⁹: every definition and external of the case, every input, the D/C of every check, every governing record, the strand layout, the end points of the curve, the section depths, the 5.6.4.5 ratio, the resultant-axis ratio, and the section evaluated exactly at `c_gov` against an independent call of the notebook's own routine. The D/C evaluated exactly at `c_gov` differs from the notebook's interpolated resultant-axis D/C by design and is held to 2 %. The Pile Data Table entries that the sheet's values produce (columns C, I, J, K, L, P, Q) are compared with the notebook's table.
- It runs the Mathcad worksheet for the same case (`pile_design.mathcad.verify`) and compares the values both sheets hold.
- It checks that the Figure 3 stems follow the check list in order, that every `Chk_` string matches its ratio and that `Status` agrees with the Mathcad status.

`verification.json` has the counts. At the preset cases: End Bent 1 and End Bent 2, 223 comparisons with the notebook, 419 values compared with the Mathcad sheet; Pier, 119 comparisons and 116 values.

`tests/test_pile_bpad.py` builds all three sheets once and checks:

- the committed documents, fragments, preview data and `verification.json` equal a fresh build (the failure message names `scripts/build_pile_bpad.py`);
- each build is tied to the current package revision and the registered FBMP hashes;
- at least 150 comparisons for the prestressed sheets, 60 for the pier, and 40 values compared with the Mathcad environment;
- a deliberately wrong equation, input or c_gov-section equation stops the build;
- the XML parses, loads with the workflow's `Journal` class, has one report whose name is not used in the journal, and follows the formula rules above;
- `Status` and the `Chk_` strings agree with the notebook checks, for the preset piles and for a pile that fails, the Figure 3 stems name the checks in order, and `DC_ymax` reaches the largest ratio;
- the preview data has an entry for each canvas;
- other cases build: Eq. 5.6.4.5-1, bending axes at 0 and 45 degrees, other strand patterns, clay and corroded pipe;
- the notebook route (`pile_design.bpad.build(e)`) writes the same document, and the export writes the named file with its `verification.json`.

None of this is a Blockpad recalculation.

## Preview

An independent HTML and PNG preview can be made without Blockpad:

```
.venv\Scripts\python.exe scripts\bpad_preview.py "pile_bpad\End Bent 1 Pile Design.bpad" --out generated\pile_bpad_preview --expand --png
```

`--expand` opens the collapsed sections. `--png` needs Microsoft Edge. The preview shows the results stored in the file and draws the canvases from `pile_bpad/preview/<ReportName>.canvases.json`. It is an approximation. It is not a native Blockpad rendering, it recalculates nothing, and it draws a linear dimension as a line on the edge it measures.

## Adding to the journal

The journal is not changed by this folder. To add the reports, plan a task and run from the repository root (leave out the reports you do not need):

```
.venv\Scripts\python.exe tools\bpad_workflow.py prepare T0xx --objective "Add the distilled pile design reports" --add report:PileDesignEndBentOne --add report:PileDesignEndBentTwo --add report:PileDesignPier --write report:PedBridge
```

Then:

1. In `tasks/T0xx/`, `components.json` names the file in `components/` for each key. Copy each `pile_bpad/fragments/<ReportName>.xml` over the matching added file (each starts as an empty `<report name="..." />`).
2. In the `PedBridge` file, add the index links under "Specific calculations and foundations", in the form the other links use (`<link address="#PileDesignPier">`).
3. `.venv\Scripts\python.exe tools\bpad_workflow.py import-components T0xx`
4. `.venv\Scripts\python.exe tools\bpad_workflow.py check T0xx`
5. `.venv\Scripts\python.exe tools\bpad_workflow.py assemble T0xx --output generated\T0xx-review-01`
6. Review the candidate, then `.venv\Scripts\python.exe tools\bpad_workflow.py promote generated\T0xx-review-01`.

The fragment is the report element only. The document-level `PASS` and `FAIL` colour rules, the `All Checks Pass` and `There are FAILURES` colour rules, and the `Result only` style already exist in the journal. The report names are not used in the journal (the test checks this against the stable journal). The workflow rules in `workflow/README.md` and `AGENTS.md` apply, including the promotion policy.

## Journal

The three reports were added to the journal under task T015 on 19 October 2026 (decision D-054) and promoted without native Blockpad or engineering review, as the promotion policy allows. The promoted journal has SHA-256 `033bf8ff64ca83f0cb9dd38aa5f43bb0c427852b8e2111623cb2123b8fa0f49d` (previous `119261e3e7cc86d67bdde67052ca2953cdb81c24d559e468032f32d072c1e01b`, T014). `PedBridge` links them under "Specific calculations and foundations", after the cap design links: `#PileDesignEndBentOne`, `#PileDesignEndBentTwo` and `#PileDesignPier`. The fragments were copied byte for byte (`tasks/T015/build_components.py`) and checked by `tasks/T015/verify_task.py`. The journal holds the version of these reports built at package revision `32d46a79afd4...`: rebuild the sheets and add a new task if the package or an FBMP export changes. The source reports and cases are in `project_current/pile_design/`.

## Points to confirm natively in Blockpad

Open a document, recalculate, and look at these first:

- Amber input definitions inside table text cells (the FBMP record table).
- Names with a trailing digit group after a subscript, such as `M_2_1`, `S_f_cg1` and `eps_p_cg_12`.
- Compound-unit literals such as `1 kip^2*ft^2`, and `to kip*ft` display suffixes.
- `Tan` and `Sin` of an angle in degrees (`theta_v`, `alpha_rs`, `alpha_sh`).
- Fractional powers of dimensioned quantities (`L_fix`, the power-formula factor `g_p_cg_k`).
- `If` with a comparison between plain numbers, as in the strand-position equations (`If(0 < k_row, ...)`).
- The dashed `lines` element and `PlotLines` with formula coordinates in Figure 2, and live labels (`planecontainer` with a formula) showing plain numbers.
- `null` inside `PlotLines` hiding a stem (Figure 3), a `lineardim` whose label is a live formula (Figure 1), and a long `Max(...)` argument list (`DC_max`, `DC_ymax`).

## Rebuild

From the repository root:

```
.venv\Scripts\python.exe scripts\build_pile_bpad.py
```

Rebuild after the `pile_design` package, the registered FBMP exports or the generator change. The document names the package revision, so a change to any `pile_design/*.py` file makes these files stale. Edits made inside Blockpad are lost on the next rebuild. Use the full build for the committed files: `--skip-mathcad` leaves out the Mathcad comparison and writes a different `verification.json`. Run the tests with:

```
.venv\Scripts\python.exe -m unittest tests.test_pile_bpad -v
```

## Files

- `End Bent 1 Pile Design.bpad`, `End Bent 2 Pile Design.bpad`, `Pier Pile Design.bpad`
- `fragments/<ReportName>.xml`: the report element alone, for adding to the journal
- `preview/<ReportName>.canvases.json`: the resolved canvas geometry used by the preview
- `verification.json`: report, hashes and verification counts for each document
- `../pile_design/bpad.py`: the generator (`build`, `build_outputs`)
- `../scripts/build_pile_bpad.py`: the command line
- `../scripts/bpad_sheet.py`: formula emitter, `BpEngine` and the XML writers (shared with the cap sheets)
- `../scripts/bpad_preview.py`: independent HTML and PNG preview
- `../tests/test_pile_bpad.py`: staleness and verification tests
