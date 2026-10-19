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

## Exporting from the notebook

The cap notebook (`Cap_and_Pile_Design.ipynb`, package `pier_cap/`) writes the same sheet for its current case: the **Export distilled Blockpad (.bpad)** control in *Save / reuse a selected case*, next to the C005 review-copy panel. It first saves the case bundle (`exports/case-<stamp>/`, with `selected_case.json` and `calculation_report.html`), then builds the sheet in memory with `scripts/build_cap_bpad.py` (`build_cap(..., e=, report=, revision=, names=)`) tied to that report's printed hashes, runs the full verification above (the tool comparisons, the branch coverage, the formula rules; the Mathcad comparison is left out because it needs the project files), and writes `blockpad/<cap> Cap Design.bpad`, the fragment, the preview sidecar and `verification.json` into the bundle folder. In Colab the file downloads; in Jupyter a download link appears. The case must hold an FBMP analysis and the actual transverse runs; the cap (End Bent 1, End Bent 2 or Pier) is read from the case name and the FBMP file name, and an unrecognised case becomes report `CapDesignNotebook` in `Cap Design.bpad`. The code is `pier_cap/bpad_distill.py` (`distill_cap`) and the shared panel `pier_cap/bpad_export.py`; the portable notebook embeds the scripts it imports (`scripts/build_portable_notebook.py`, `EMBEDDED_SCRIPTS`). `tests/test_bpad_distill.py` runs the export headlessly.

## Adding to the journal

The journal is not changed by this folder. Add the journal edition (see "Journal edition (live references)" below), not the standalone fragments: both editions use the same three report names, and the journal should hold one authoritative definition of each shared input. Plan a task and run from the repository root:

```
.venv\Scripts\python.exe tools\bpad_workflow.py prepare T0xx --objective "Add the distilled cap design reports" --add report:CapDesignBasis --add report:CapDesignEndBentOne --add report:CapDesignEndBentTwo --add report:CapDesignPier --write report:PedBridge
```

Then:

1. In `tasks/T0xx/`, `components.json` names the file in `components/` for each key. Copy each `cap_bpad/journal/<ReportName>.xml` (`CapDesignBasis`, `CapDesignEndBentOne`, `CapDesignEndBentTwo`, `CapDesignPier`) over the matching added file (each starts as an empty `<report name="..." />`).
2. In the `PedBridge` file, add the index links under "Specific calculations and foundations", in the form the other links use (`<link address="#CapDesignPier">`).
3. `.venv\Scripts\python.exe tools\bpad_workflow.py import-components T0xx`
4. `.venv\Scripts\python.exe tools\bpad_workflow.py check T0xx`
5. `.venv\Scripts\python.exe tools\bpad_workflow.py assemble T0xx --output generated\T0xx-review-01`
6. Review the candidate, then `.venv\Scripts\python.exe tools\bpad_workflow.py promote generated\T0xx-review-01`.

The fragment is the report element only. The document-level `PASS` and `FAIL` colour rules, the `All Checks Pass` and `There are FAILURES` colour rules, and the `Result only` style already exist in the journal. The report names do not collide with `PierCapDesign`. The workflow rules in `workflow/README.md` and `AGENTS.md` apply, including the promotion policy. The task reads `BridgeGeometry_2Beam`, `FBMPEndBent` and `PierCapDesign` and writes none of them. (The standalone fragments in `cap_bpad/fragments/` are for a journal that should carry the three reports without cross-references; they hold the same inputs as literals.)

## Journal edition (live references)

The standalone sheets repeat every shared input as a literal. The journal edition (`scripts/build_cap_bpad.py --journal [path]`, default `journal/D2_I95_Project_Journal.bpad`) writes the same three reports with those inputs as live references to the journal (BPAD Ref V5, 16.7: one authoritative definition per input), plus one small shared report, `CapDesignBasis`. It writes only `cap_bpad/journal/`; the standalone files are not touched. Nothing here has been opened in Blockpad.

Mapping (Section 2 of each cap report; each reference is an ordinary equation with the caption `shared journal value — <owner>`, not an amber input):

| Input | End Bent 1 and 2 | Pier |
| --- | --- | --- |
| `b`, `h` | `BridgeGeometry_2Beam.EndBentCap_width`, `.EndBentCap_depth` | `BridgeGeometry_2Beam.PierCap_width`, `.PierCap_ht` |
| `L_cap` | literal 251 in (see below) | `BridgeGeometry_2Beam.PierCap_length` |
| `C_t`, `C_b`, `C_s` | `BridgeGeometry_2Beam.EndBent_coverTop`, `_coverBottom`, `_coverSide` | `PierCapDesign.C_t`, `.C_b`, `.C_s` |
| `fc`, `fy`, `Es` | `FBMPEndBent.EBSteel_fc`, `_fy`, `_Es` | `PierCapDesign.fc`, `.fy`, `.Es` |
| `φ_f`, `φ_v`, `φ_a`, `γ_e`, `λ`, `s_proj` | `CapDesignBasis.φ_f`, `.φ_v`, `.φ_a`, `.γ_e`, `.λ`, `.s_proj` | the same |
| bar tables | `CapDesignBasis.Ab(k)`, `CapDesignBasis.Db(k)` (no local `Ab`/`Db`) | the same |

Everything else (actions, reinforcement, fitted coordinates, station inputs, interval data, faces, hook data) stays as it is: the cap reports own those. `CapDesignBasis` (`Cap Design Basis - shared factors`, one page) holds the constants no other journal report owns, each an amber `Required Input` with its caption and code reference: `φ_f = 0.9`, `φ_v = 0.9`, `φ_a = 0.9` (LRFD 5.7.3.5), `γ_e = 1`, `λ = 1`, `s_proj = 12 in`, and the two bar-table functions. A discussion box states which reports read it, the codes (LRFD 10th edition 2024, FDOT SDG January 2026) and that C005 (`PierCapDesign`) keeps its own copies of `φ_f`, `φ_v` and `γ_e` under decision D-003. The pier cap reads `PierCapDesign` for its cover and materials, as C005 does, and the factors from `CapDesignBasis`.

**Coherence gate.** `JournalLinks` (`scripts/bpad_sheet.py`) parses the journal once and evaluates each referenced definition with `BpEngine`: it collects the owner report's `name = ...` formulas, takes the transitive closure of the asked-for name, strips the `to ...` display suffix (including the two-token `to ft in`) and reads literals such as `4ft`, `36 in`, `0.9` and `3/4 in`. Before anything else is built, each journal value is compared with the cap-case input (`input_values`) to 1 part in 10⁹ in the display unit of the input. A mismatch stops the build with a message naming the cap, the input, the owner and both values, for example `b (End Bent 1): the case holds 42 in but the journal owner BridgeGeometry_2Beam.EndBentCap_width holds 43 in`. The `CapDesignBasis` values are compared with the case in the same way. After the sheet is built it also checks that every `CapDesignBasis.` name used resolves to a definition written in `CapDesignBasis.xml`, that no `Ab(`/`Db(` definition or unqualified call remains, and that no literal remains for a name that has a reference. The rest of the verification is the standalone one (the tool comparisons, the branch coverage, the Mathcad comparison, Figure 3): the engine takes the referenced names as externals with the journal values, so the comparison counts are the same as in the standalone edition.

**`coherence.json`.** Per report, one row per mapped input (and per kept literal), in Section 2 order: `input`, `owner` (the qualified journal name), `journal_value`, `case_value` (both in the display unit of the input), `status` and `note`. `status` is `reference` (compared, equal), `literal_owner_here` (the report is the owner and keeps the literal) or `literal_incoherent_journal` (kept as a literal because the journal disagrees; reported, not compared). The `KEEP_LITERAL` table in the generator holds the kept names with their reason text; a name is never special-cased in code. If a kept literal starts to agree with the journal, the build stops and asks for it to become a reference.

**Known incoherence: End Bent `L_cap`.** `BridgeGeometry_2Beam.EndBentCap_length` evaluates to 212 in (17 ft 8 in, from the 8 October record with `EndBent_endDetail = 4 in`), while decisions D-026, D-027 and D-036 adopted 235-in end caps with two 8-in cheek webs, and the cap cases use the 251-in cap plus cheek cage envelope (`E_detail = 23.5 in`). So End Bent `L_cap` stays an amber literal (`L_cap = 251 in`, row `literal_incoherent_journal`, 212 in against 251 in). To make it a reference: set `BridgeGeometry_2Beam.EndBent_endDetail` to 15.5 in so that the 235-in cap follows from the pile layout, decide whether the two 8-in cheek webs enter `EndBentCap_length` (the 251 in is 235 in plus 2 x 8 in), then move `L_cap` from `KEEP_LITERAL` to `END_BENT_REFS` in the generator. That is a change to the geometry report, so it is a journal task of its own.

**Outputs** (`cap_bpad/journal/`): `CapDesignBasis.xml`, `CapDesignEndBentOne.xml`, `CapDesignEndBentTwo.xml` and `CapDesignPier.xml` (report elements only, like `fragments/`); `coherence.json`; `verification.json` (the counts per report and the basis); `preview/<ReportName>.canvases.json`; and `Cap Design - Journal Edition (review).bpad`, one document with the four reports in the order Basis, End Bent 1, End Bent 2, Pier. In the review document the references to `BridgeGeometry_2Beam`, `FBMPEndBent` and `PierCapDesign` do not resolve outside the journal (a banner at the top of its Basis report says so; the stored results are the journal values at build time). The bytes are the same on every rerun. Index links are not part of this edition.

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

The journal edition is rebuilt separately, and the same rule applies to it (it also reads the journal, so rebuild it when `BridgeGeometry_2Beam`, `FBMPEndBent` or `PierCapDesign` change a referenced value):

```
.venv\Scripts\python.exe scripts\build_cap_bpad.py --journal
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
- `journal/`: the journal edition (`CapDesignBasis.xml`, the three cap reports with live references, `coherence.json`, `verification.json`, `preview/`, the review document)
- `../scripts/build_cap_bpad.py`: builds the documents and runs the comparisons
- `../scripts/bpad_sheet.py`: formula emitter, `BpEngine` and the XML writers
- `../pier_cap/bpad_distill.py`, `../pier_cap/bpad_export.py`: the notebook's export of the current case
- `../pier_cap/figure_data.py`: the numbers Figures 1 and 2 are drawn from (shared with the Mathcad figures)
- `../scripts/bpad_preview.py`: independent HTML and PNG preview
- `../tests/test_cap_bpad.py`: staleness and verification tests
