# Current project record

Start here for the D2 I-95 pedestrian bridge's current source files, adopted
decisions and outstanding coherence items. Initial inventory: **9 October 2026**. Source update: **19 October 2026**.
"Current" identifies the selected source. Each source retains its own review and
design-completion status.

## Open the working files

| Record | Current location |
| --- | --- |
| Outstanding items and responses | [Coherence tracker](coherence/Coherence_Tracker.xlsx) |
| Latest baseline/check report | [Latest review](coherence/latest_review.md) |
| Exact source revisions and missing files | [Source register](source_register.csv) |
| Small gaps, placeholders, assumptions and judgments | [Assumptions register](coherence/assumptions.json) — one entry per item with its magnitude, disposition and the register hashes it was judged against; shown in the design atlas and checked by the coherence review |
| Recorded decisions and ownership | [Decisions](decisions.md) |
| Native project journal | [D2 I-95 Project Journal](../journal/D2_I95_Project_Journal.bpad) with [References](../journal/References/) |
| Current editable FreeCAD model and live quantities | [Open the bridge model](geometry/freecad/README.md) — square bridge edges, end-bent MSE copings, 2% closure slabs and seven schematic geotechnical straps per backwall (D-044/D-045), plus fitted standard cheek horizontal hooks (D-046); calculation/detailing reconciliation remains open |
| Geometry notebook | [Bridge geometry](../Bridge_Geometry_2%20Beam_V2.ipynb) and [roadway XML](../Geometry%20Report.xml) — owns the end caps, backwalls, cheek webs and lugs (D-036); both backwall tops and ramp connections updated under D-053 |
| Geometry interactive report | [Prior station explorer snapshot](geometry/reports/Bridge_Geometry_Interactive_Report_physical_v2_622e5ca1bf.html) â€” 19 October export of notebook model 622e5ca1bf (D-052) |
| Geometry CAD tables | [Selected workbook](geometry/tables/B4_Geometry_CAD_Tables.xlsx) — FDOT CAD tables, method tabs and live charts recalculated from the geometry notebook (D-041; [how to rebuild](../geometry_tables/README.md)) |
| Pier cap | [Report](cap_design/pier/Pier%20Cap%20Design%2010-22.html), [saved case](cap_design/pier/selected_case.json), [FBMP export](fbmp/pier/Pier_Fixed.XML) — 22 October rerun with the 22 October fixed XML (D-077; pier wall members ending at the soil surface); the 21 October rerun (D-073, 45 ksi pile material) and the 19 October rerun (D-051) are retained |
| End Bent 1 cap | [Report](cap_design/end_bents/End%20Bent%201%20Cap%20Design%2010-20.html), [saved case](cap_design/end_bents/selected_case.json) — 19 October rerun with the latest fixed XML (D-051) |
| End Bent 2 cap | [Report](cap_design/end_bent_2/End%20Bent%202%20Cap%20Design%2010-20.html), [saved case](cap_design/end_bent_2/selected_case.json) — 19 October rerun with the latest fixed XML (D-051) |
| End Bent 1 piles | [Report](pile_design/end_bent_1/End%20Bent%201%20Pile%20Design%2010-22.html), [saved case](pile_design/end_bent_1/selected_case.json), [Pile Data Table](pile_design/end_bent_1/End%20Bent%201%20Pile%20Data%20Table%2010-22.xlsx) — 18 in prestressed pile, 18-ton downdrag, 19 October basis (D-054) re-exported 22 October with identical checks (D-077); Blockpad edition in the journal (C011) |
| End Bent 2 piles | [Report](pile_design/end_bent_2/End%20Bent%202%20Pile%20Design%2010-22.html), [saved case](pile_design/end_bent_2/selected_case.json), [Pile Data Table](pile_design/end_bent_2/End%20Bent%202%20Pile%20Data%20Table%2010-22.xlsx) — 19 October basis (D-054) re-exported 22 October with identical checks (D-077) |
| Pier piles | [Report](pile_design/pier/Pier%20Pile%20Design%2010-22.html), [saved case](pile_design/pier/selected_case.json), [Pile Data Table](pile_design/pier/Pier%20Pile%20Data%20Table%2010-22.xlsx) — 20 in steel pipe pile, 22 October run on the D-077 export (structural D/C 0.464, governing below the pier wall at element 11; FDL from the pile head); the Fy reconciliation closed under D-073 |
| Selected backwall and cheekwall design | [20 October report](cap_design/backwall/Backwall%20Design%2010-20.html) and [saved case](cap_design/backwall/selected_case.json) — one centered #4 mat at 10 in each way; analysis and detailing prerequisites remain pending |
| Pier wall on annular pile rings | [Report](pier_wall/Pier%20Wall%20Design%2010-22b.html), [saved case](pier_wall/selected_case.json) — welded-ring support concept, D-070 moment basis, CAD wall geometry (219 × 36 × 194.8625 in, D-075), 1/2-in ring plate (D-078), second 22 October run; Blockpad edition C017 in the journal (T028/T029/T034/T037); the CAD rings (D-076) are still 3/4 in; the C006 fin-plate concept is not superseded |
| Report cards (D-068) | All seven calculation reports above were re-exported on 20 October 2026 with definition and citation cards (report_cards; commits 18b47cb and a866e6b): hover a variable for its definition, a code reference for the highlighted provision. Results unchanged; 19 October reports retained; see [receipt](coherence/evidence/2026-10-20-report-cards/source_receipt.json) |
| FBMP source variants | [Three current fixed exports and two minimum-tip variants](fbmp/README.md) |
| Mathcad | [Span 1](mathcad/PrestressedBeamV6.2_Pedestrian_2Beam_Span1.xmcd), [Span 2](mathcad/PrestressedBeamV6.2_Pedestrian_2Beam_Span2.xmcd) — 12 October beam runs; [changes and downstream review](mathcad/README.md) |
| Calculation tool | [Cap and pile notebook](../Cap_and_Pile_Design.ipynb) |
| Pile analysis and design | [Pile notebook](../Pile_Design.ipynb) and [calculation basis](../PILE_DESIGN.md); decisions D-050, D-054; Mathcad and Blockpad editions in `pile_mathcad/` and `pile_bpad/` |
| End-bent backwall, cheek walls and tie-back straps | [Backwall notebook](../End_Bent_Backwall_Design.ipynb) and [calculation basis](../BACKWALL_DESIGN.md); decisions D-014 to D-019 |
| PSBeam packages | [Awaiting source files](psbeam/README.md) |

GitHub may require downloading HTML reports and native calculation files to view
them. Open reports locally in a browser. The journal and notebooks retain their
established repository locations; this index points to those working copies.
Files under `tasks/` and `coherence/evidence/` are historical source/review records.
Use the paths in the register for current work.

## What controls each subject

The [16 October backwall notebook update](../BACKWALL_DESIGN.md) incorporates the
adopted cap/cheek geometry and verified landing quantities. Its proposed cheek
reinforcement is one centered mat of #4 bars at 10 in each way. Three source-backed
confirmations are checked; six remain pending. See [D-035 verification](coherence/evidence/2026-10-16-backwall/disposition.json).
The report and paired saved case from a fresh notebook run are selected under
[D-037](coherence/evidence/2026-10-16-backwall-export/source_receipt.json).
The 12 October report remains historical. Current analysis, anchorage and MSE
coordination remain open, and the CAD bar layout retains its earlier state.
This bounded update does not replace the dated full-project coherence review or
change tracker status.

| Subject | Controlling record | Treatment elsewhere |
| --- | --- | --- |
| Project assumptions, adopted geometry, decisions, live journal quantities | Current journal's designated modules | Compare notebook and report inputs with these modules |
| Geometry computations and elevation schedules | Current geometry notebook using identified project inputs and roadway XML | A difference from adopted journal geometry becomes an issue |
| Bridge geometry for CAD, including end caps, backwalls, cheek webs and lugs | Current geometry notebook (D-036) | The FreeCAD model is rebuilt from notebook exports. MSE walls, copings, barriers and landings stay DXF/CAD-owned; the cheek tops are their interface inputs |
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
   A small gap, placeholder, assumption or judgment that does not need a tracker
   row goes in the [assumptions register](coherence/assumptions.json) instead
   (see [Assumptions and gaps register](#assumptions-and-gaps-register)).
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

### Assumptions and gaps register

`coherence/assumptions.json` records the small engineering gaps, placeholders,
assumptions and judgments in one hand-edited, committed file (schema
`d2mpdb.assumptions-register`, version 1). Each entry has a stable `A-###` id,
a kind (`assumption`, `gap`, `placeholder`, `judgment`), the statement, where it
bites, the atlas nodes it is pinned to, the magnitude the judgment rests on
(`value`, `unit`, `sized_by`), the disposition (`accepted-negligible`, `pending`
or `closed` with its `D-0xx` decision and date), the owner, related `COH-###`
ids, reference paths, and `basis`: the register source ids with the SHA-256
each was judged against. The register keeps the magnitude only; the engineering
values stay with the journal and the reports that own them.

To add an entry, draft it in the design atlas (**Draft assumption** on the
related source fills in the current register hashes), paste it into `entries`,
and run the coherence check. The check validates ids, kinds, dispositions,
basis sources and tracker references, and reports an entry as **stale** when
the source register now adopts a different revision of a basis source; stale
and open entries are listed in `latest_review.md`. Re-check a stale entry and
record the new hashes with a dated disposition; never refresh the hashes to
silence the finding. The design atlas shows the entries on their nodes with
open-or-stale badges, and editing the register makes the hosted atlas
`refresh_required`. The 19 October seed (A-001 to A-011) carries the D-062
load-review items, the pipe-pile grade reconciliation, the MSE side-wall
criterion and the pile-report prerequisites.

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

## 16 October geometry notebook end-bent update (D-036)

The geometry notebook is the source of truth for all bridge geometry, and the CAD
model is built from it. The notebook now owns the adopted end-bent details:
- **Cap:** a 235-in cap body from the unchanged pile layout.
- **Cheeks:** 8-in cheek webs outside the cap ends, 251 in out-to-out, matching the D-027 cases. Each has 6 × 5.5-in bottom and rear lugs, with 0.5-in MSE joints.
- **Backwall:** top 4 in below the deck-top line at the FFBW.

The four D-033 barrier-return bases are entered as the cheek tops. They are the
only MSE-interface inputs. Seat, pedestal, cap-top and pile-cutoff elevations are
unchanged.

A byte-identical snapshot of the D-034 CAD model is now the native reference. It is archived at
`geometry/freecad/archive/B4-notebook-reconciliation-20261016.FCStd`. Against it:
- All 105 station cuts match: caps, piles, pedestals, pads and cheeks.
- Cheek volumes agree to 1e-12 ft³, and the EB2 backwall matches exactly.
- The CAD EB1 backwall seat follows the MSE landing and holds 0.117 ft³ more concrete. Rebuild it from the notebook.

Walls are also in the notebook's CAD export and in the interactive report. The
[CAD tables workbook](geometry/tables/B4_Geometry_CAD_Tables.xlsx) is rebuilt
and registered as GEOMETRY-TABLES. COH-023 stays Open for loads, quantities,
anchorage, lug steel, strap interfaces and the CAD rebuild. See the
[disposition](coherence/evidence/2026-10-16-geometry-end-bents/disposition.json).

## 16 October FBMP pile-head follow-up

Two FBMP items stay open by user direction:
- **COH-013 (awaiting source):** the exact exports behind the selected cap reports
  are not in the project source. The report-matching pier export was supplied for
  comparison only. The 14 October End Bent 1 and End Bent 2 exports are missing.
- **COH-028 (open):** the final FBMP runs must be repeated with pile heads at the
  current notebook cutoffs: pier 41.764940 ft, EB1 41.237692 ft, EB2 41.249692 ft.
  The report-matching pier model has them at 41.7717 ft. That is the cutoff from
  before the 12 October camber update (D-022/D-023), which lowered every cutoff
  by 0.084 in. D-036 changed no elevations.

No export, register row, report or case changed. See the
[pile-head record](coherence/evidence/2026-10-16-fbmp-pile-heads/pile_heads.json)
and the [FBMP sources](fbmp/README.md).

## 16 October geometry CAD tables selected (D-041)

The [geometry CAD-tables workbook](geometry/tables/README.md) is now a selected
project source. It is registered as GEOMETRY-TABLES and kept in `geometry/tables/`,
where the generator writes it.
- **Standalone:** the .xlsx has no macros or external links. Its tables and 15
  Method-tab charts are live formulas over the notebook CONFIG and saved Mathcad inputs.
- **Rebuilt at the new path:** from notebook model 622e5ca1bf. QC is 182 pass / 0 fail,
  and every calculation and CAD value equals the D-036 build.
- **Still for review before issue:** the BCC-template items (Dim L + R, bar
  constants, build-up case, beveled plates) and the Cover open items.

Its pile cutoffs are the notebook pile-head elevations for the COH-028 reruns.
See the [source receipt](coherence/evidence/2026-10-16-geometry-tables/source_receipt.json).

## 19 October FBMP source update

D-049 selects the supplied Pier, End Bent 1 and End Bent 2 fixed-run XMLs.
The previous pier and EB1 fixed exports are archived. All three new fingerprints
differ from the analyses in the selected cap reports/cases, which remain unchanged
pending downstream reconciliation. EB1 pile heads match the recorded 16 October
target at printed precision; Pier and EB2 remain about 0.08 in above their targets.
Tracker statuses/responses and minimum-tip variants are preserved. See the
[FBMP source overview](fbmp/README.md) and
[receipt](coherence/evidence/2026-10-19-fbmp/source_receipt.json).

## 19 October cap notebook rerun

Under D-051, all three cap designs were recalculated with the D-049 fixed
XMLs through the portable notebook's import, Recalc and built-in export workflow.
The new 10-19 HTML reports and JSON cases are selected, with prior cases archived.
All report/case/XML identities match. Geometry and reinforcement are preserved;
64 pier, 42 EB1 and 44 EB2 check ratios changed, with no status changes or new
failed checks. Existing detailing failures and pending reviews remain. Backwall,
CAD, journal, minimum-tip sources and tracker responses are unchanged.
See the [rerun receipt](coherence/evidence/2026-10-19-cap-rerun/source_receipt.json).
