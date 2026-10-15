# Current project record

Start here for the D2 I-95 pedestrian bridge's current source files, adopted
decisions and outstanding coherence items. Initial inventory: **9 October 2026**. Source update: **15 October 2026**.
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
| Current editable FreeCAD model and live quantities | [Open the bridge model](geometry/freecad/README.md) — raised cheeks, deep return barriers, rear-lug coping stops, deck-edge details and reinforcement; calculation reconciliation remains open |
| Geometry notebook | [Bridge geometry](../Bridge_Geometry_2%20Beam_V2.ipynb) and [roadway XML](../Geometry%20Report.xml) |
| Pier cap | [Report](cap_design/pier/Pier%20Cap%20Design%2010-12.html), [saved case](cap_design/pier/selected_case.json), [FBMP export](fbmp/pier/Pier_Fixed.XML) |
| End Bent 1 cap | [Report](cap_design/end_bents/End%20Bent%201%20Cap%20Design%2010-14.html), [saved case](cap_design/end_bents/selected_case.json) |
| End Bent 2 cap | [Report](cap_design/end_bent_2/End%20Bent%202%20Cap%20Design%2010-14.html), [saved case](cap_design/end_bent_2/selected_case.json) |
| Selected backwall and cheekwall design | [12 October report](cap_design/backwall/Backwall%20Design%2010-12.html) — provisional dimensions; trial reinforcement; pending detailing |
| FBMP source variants | [All four fixed/minimum-tip exports](fbmp/README.md) |
| Mathcad | [Span 1](mathcad/PrestressedBeamV6.2_Pedestrian_2Beam_Span1.xmcd), [Span 2](mathcad/PrestressedBeamV6.2_Pedestrian_2Beam_Span2.xmcd) — 12 October beam runs; [changes and downstream review](mathcad/README.md) |
| Calculation tool | [Cap and pile notebook](../Cap_and_Pile_Design.ipynb) |
| End-bent backwall, cheek walls and tie-back straps | [Backwall notebook](../End_Bent_Backwall_Design.ipynb) and [calculation basis](../BACKWALL_DESIGN.md); decisions D-014 to D-019 |
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
| End-bent cages and source results | Registered separate End Bent 1 and End Bent 2 report/cases | Current cages share a configuration; actions and source identities remain separate |
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

The 10 October review has **19 outstanding items**: 13 open, three awaiting
source and three deferred. Three closed rows remain for history. The review
adopts the two supplied 10 October reports and their embedded cases, adds the
exact matching `Pier_Fixed.XML`, and reconciles the existing T006 journal receipt
and recorded responses. Earlier reports and the archived prior pier minimum-tip XML remain historical.

Both reports flag end-face U-grid pile clearance. Each report's two FAIL entries
are that failure and its aggregate summary. The subsequent four-file FBMP import supplies the exact matching end-bent XML.
Fixed and minimum-tip variants are now [registered separately](fbmp/README.md).
CAP-TOOL remains changed against its registered revision. Report pending
counts are 67 for the pier and 50 for End Bent 1; these are report entries, not
tracker item counts. Service III remains N/A by D-007 despite its pending report
label. See the [source update review](coherence/evidence/2026-10-10/review.md).
This is a bounded data-coherence review, not a new native calculation or complete
design audit. Prior recorded decisions and deferrals remain in effect.

The subsequent FBMP import updates source identity checks only. Tracker status
and responses are unchanged: COH-013's raw-export gap is now resolved, while its
native-run documentation and workbook disposition remain outstanding. See the
[FBMP source receipt](coherence/evidence/2026-10-10-fbmp/source_receipt.json).

## 12 October source and reinforcement update

The four supplied reports are now selected with their embedded cap cases. Both end-bent cases disable the end-face U-grid (67 to 57 modeled cap bars each); pier steel remains 90 bars. Wall Figure B8 specifies #5 vertical and #4 horizontal at 12 in each face. Existing cheekwall dimensions match the report and retain their full precision. The 16 in dowels in that figure are explicitly schematic, not approved development lengths.

The new reports reference different raw FBMP hashes: the two prior registered XMLs are preserved and do not match, and the End Bent 2 XML is missing. No analysis rerun or tracker closure is implied. The existing workbook is preserved. See [source receipt](coherence/evidence/2026-10-12/source_update.json).

## 12 October beam source update

The newly supplied Span 1 and Span 2 Mathcad runs replace the previously selected
worksheets under D-022. Previous native files are archived unchanged. Both runs
use 9-in beam-end bearing distances and shorter beam lengths; their saved net
cambers are now 0.124592744 in and 0.567171463 in. Under the subsequent D-023
follow-up, those cambers now drive the geometry notebook and saved CAD model.
The notebook's beam lengths and bearing setbacks already match the new runs.
The journal, other calculation notebooks, design reports and all tracker
responses are preserved; backwall source provenance remains for review. See the [comparison](mathcad/README.md) and
[exact source receipt](coherence/evidence/2026-10-12-beams/source_receipt.json).

The [notebook/CAD verification](geometry/freecad/evidence/2026-10-12-cambers/update-summary.json)
records 36 passing geometry tests, 93 measured native support sections and the
saved-model reopen checks. Cap and pile elevations and dependent reinforcement
follow the new geometry; ramps, terrain and decks are preserved. Existing
detailing and bridge/MSE coordination failures remain recorded.


## 14 October CAD and DXF adoption

Under D-026, the main FreeCAD model now incorporates the reviewed copings,
barriers, cap extensions, cheek lugs, MSE offsets and mitres, raised wall tops,
half-inch joints, level returns and centered #4 cheek mats. All 12 piles and
170 elevations are retained; main ramps remain <=5%. The original working DXF
is registered as MSE-DETAIL-DXF. See the [current CAD source](geometry/freecad/README.md).

COH-023 records reconciliation with the selected cap/backwall calculations and
geometry notebook. The CAD layout supersedes the provisional wall geometry and
two-face cheek steel in the earlier report for modeling purposes. Calculation
sources, historical decisions and previous tracker responses retain their scope.

## 14 October end-cap reinforcement update

D-027 selects both reports and exact JSON cases from `Updated End Bent Cap
Designs.zip`. The 251 in out-to-out cage envelope is the existing 235 in cap
plus the two 8 in cheek webs. The concrete geometry is unchanged. Both end-cap
cages contain 62 bars with #6 transverse steel. The unchanged cheek mats clash
with the new steel; COH-024 and the saved CAD review views record those conflicts
for discussion. Cap cover, pile clearance and other steel findings remain open.
Earlier cases and model revisions are preserved. The new exact raw FBMP exports
were not supplied, and calculation/anchorage/fabrication acceptance is unchanged.


## 14 October cap/cheek coordination follow-up

D-028 removes one close vertical per cheek, moves the outer verticals just inside
the cap longitudinal bars, and moves the end hoops inward of the cheek mats.
Contact is allowed; positive solid overlap remains a failure. There are now four
verticals/eight horizontals per cheek (48 bars total); cap counts stay 62/90/62.
The requested changes pass 544 physical clearance checks. Cap/cheek flags reduce
from 40 to 8, all at unchanged horizontal cheek bars. COH-024 remains open.
Original design-case files and concrete are unchanged; editable CAD station
overrides, the updated model, evidence and prior-model backup are registered.


## Horizontal cheek-bar coordination (D-029)

MH03 is lowered 3/8 in at each cheek, resolving all eight cap/cheek intersections.
End stirrups remain at D-028 stations 6 and 245.875 in; every other bar and all
concrete are unchanged. Counts remain 62/90/62 cap bars and 48 cheek bars.
The user elected to move only MH03: the four resulting 12 3/8 in spacings exceed
the existing 12 in maximum and remain flagged under open item COH-024.
Native checks pass for geometry and clearance; the spacing findings remain FAIL.
The supplied design cases are unchanged. This revision remains local.


## 14 October cheek lug WWR adoption and stirrup deferral

D-030 installs the accepted 4x4 W1.4xW1.4 bottom/side lug mesh in the current
CAD source: eight sheets, 172 editable wires, bottom extension 8 7/8 in and
side lap 8 1/8 in. No new WWR clashes occur; minimum measured cover is 2 1/8 in.
The model preserves all existing concrete and steel. COH-025 defers the 14
existing U-bar/hoop overlap pairs for later review without treating them as clear.
COH-024's four 12 3/8 in spacing findings and the other existing findings remain.
The user authorized this model/source update and GitHub publication. See the
[adoption summary](geometry/freecad/evidence/2026-10-14-lug-wwr/update-summary.json).
