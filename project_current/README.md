# Current project record

Start here for the D2 I-95 pedestrian bridge's current source files, adopted
decisions and outstanding coherence items. Initial inventory: **9 October 2026**.
"Current" identifies the selected source. Each source retains its own review and
design-completion status.

## Open the working files

| Record | Current location |
| --- | --- |
| Outstanding items and responses | [Coherence tracker](coherence/Coherence_Tracker.xlsx) |
| Latest baseline/check report | [Latest review](coherence/latest_review.md) |
| Exact source revisions and missing files | [Source register](source_register.csv) |
| Recorded decisions and ownership | [Decisions](decisions.md) |
| Native project journal | [D2 I-95 Project Journal](../journal/D2_I95_Project_Journal.bpad) with [References](../journal/References/) |
| Geometry notebook | [Bridge geometry](../Bridge_Geometry_2%20Beam_V2.ipynb) and [roadway XML](../Geometry%20Report.xml) |
| Pier cap | [Report](cap_design/pier/Pier%20Cap%20Design%2010-9.html), [saved case](cap_design/pier/selected_case.json), [FBMP export](fbmp/pier/Pier_MinTip.XML) |
| End-bent cap | [Report](cap_design/end_bents/End%20bent%201%20Cap%20Design%20Report_10-8.html), [saved case](cap_design/end_bents/selected_case.json) |
| Mathcad | [Span 1](mathcad/PrestressedBeamV6.2_Pedestrian_2Beam_Span1.xmcd), [Span 2](mathcad/PrestressedBeamV6.2_Pedestrian_2Beam_Span2.xmcd) |
| Calculation tool | [Cap and pile notebook](../Cap_and_Pile_Design.ipynb) |
| PSBeam packages | [Awaiting source files](psbeam/README.md) |

GitHub may require downloading HTML reports and native calculation files to view
them. Open reports locally in a browser. The journal and notebooks retain their
established repository locations; this index points to those working copies.
Files under `tasks/` and `coherence/evidence/` are historical source/review records.
Use the paths in the register for current work.

## What controls each subject

| Subject | Controlling record | Treatment elsewhere |
| --- | --- | --- |
| Project assumptions, adopted geometry, decisions, live journal quantities | Current journal's designated modules | Compare notebook and report inputs with these modules |
| Geometry computations and elevation schedules | Current geometry notebook using identified project inputs and roadway XML | A difference from adopted journal geometry becomes an issue |
| Current pier cage, forces and cap calculation results | Registered pier report and saved case | C005 remains unchanged; it does not verify the current cage |
| Common end-bent cage and source results | Registered End Bent 1 report/case, with recorded user decisions | Shared configuration is adopted; analysis verification remains separately tracked |
| Span calculations in Mathcad | User-selected Span 1 and Span 2 sheets | Missing companion data and calculation review remain visible |
| PSBeam and FBMP analysis results | Exact identified input/output pair for each run | A report name or export date does not establish matching input identity |
| Open coherence items and responses | `coherence/Coherence_Tracker.xlsx` | CSV and Markdown outputs are generated views, never parallel editable logs |

These ownership rules cover this project-level register. Existing journal
component ownership and promotion rules in [the journal workflow](../workflow/README.md)
still apply when editing BPAD. Its older assumption/external registers are not
silently reinterpreted or modified by this setup.

## Add information and run a review

1. Put the file in the relevant folder. Use `incoming/` if it is a candidate whose
   authority is still undecided. Keep a calculation's native inputs, saved case,
   readable output, software version and run identity together when available.
2. Add or update its row in `source_register.csv`: stable source ID, repository
   path, review status, exact SHA-256, scope and dependencies. A missing file has
   a `Missing` or `Not selected` status. Do not replace a fingerprint merely to
   silence a changed-file finding; record the adoption decision and impacts first.
3. Add findings to the tracker using the next unused `COH-###` ID. Preserve IDs,
   previous responses and the distinction between original evidence and your
   instructions. Blank table rows are ready for additions. Counts and dropdowns
   cover 1,000 item rows (9-1008); extend those ranges if the log grows beyond that.
4. Run the check from the repository root:

   ```powershell
   python tools/project_coherence.py --write-report
   ```

   Alternatively, ask Codex: **"Run a project coherence review against
   project_current. Preserve my tracker responses and add new findings by ID."**

5. Review the report and update the tracker in place. `Deferred` remains an
   outstanding item. Close an item only with its resolution/evidence; keep the
   row for history. Adopt revised sources with a dated decision and commit the
   related changes together.

The command checks exact source identity, missing inputs/dependencies, journal
acceptance identity, case/report/XML relationships, selected geometry dimensions,
and tracker completeness. It regenerates `latest_review.md`, `machine_checks.json`
and `items_snapshot.csv`. It **does not edit the workbook**, accept new hashes,
rerun native design applications, or automatically close engineering findings.
Changed sources trigger a review of their registered consumers. Dependency lists
are an initial inventory, not proof that unlisted calculations are independent.

The register's `hash_basis` is `exact_bytes` for native files, reports and case
data. The two repository notebooks use `lf_text`, normalizing only Windows/Unix
line endings for portable content fingerprints without rewriting their files.
Exit code 0 means no automatic findings or outstanding items, 1 means an error or
changed source, and 2 means known missing sources/review items remain. A zero code
still applies only to the documented automated scope.

The initial workbook contains 18 outstanding items, including three awaiting
source items and one deferred item. This is an initial review of the available
records, not a complete code/design audit. Previously resolved pedestal, node
label, utility-module and Service III decisions have not been reopened.
