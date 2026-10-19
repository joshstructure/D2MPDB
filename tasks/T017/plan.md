# T017 - End-bent backwall report in the journal

Base journal SHA-256 `855e2cecf27db3de141d037a33dfce060014cc00b6f4c180326172b0e4acf1db` (T016).

## Objective

Add the distilled end-bent backwall, cheek-wall and tie-back strap report (`EndBentBackwallDesign`,
the 19 October 2026 notebook case, decision D-057) to the journal as a registered module with live
references to the journal's own inputs, index it in `PedBridge`, and replace the sentences that
record the 16 October report as outside the journal (`PedBridge`, `BridgeGeometry_2Beam`,
`FoundationModeling`). Record the decision in `DecisionLog`. Execute in an isolated task copy,
build a candidate and promote it (the user's 19 October 2026 instruction, relayed by the
journal-coherence session, authorizes the promotion; the promotion policy makes native and
engineering reviews optional).

## Registered scope (`prepare T017`)

`--add report:EndBentBackwallDesign --write report:PedBridge --write report:BridgeGeometry_2Beam
--write report:FoundationModeling --write report:DecisionLog`. The added module is appended; all
other components are watched as dependencies (all-component fallback). No deletion, resource,
style or shell change.

## Read dependencies

`EndBentBackwallDesign` reads `BridgeGeometry_2Beam` (EndBentCap_width, EndBentCap_depth,
EndBentCap_length, EndBentCage_envelope, EndBent_pileEmbed, EndBent_pileTolerance,
Backwall_thickness_shown, EndBent_bearingOffset, EndBentPedestal_ht, EndBentPedestal_width,
Bearing_pad_thickness, Bearing_pad_G, Bearing_pad_length, Bearing_pad_width,
Bearing_pad_internalLayers, Bearing_pad_internalThickness, Bearing_pad_cover, Span_1,
EndBent_cheekThickness, EndBent_backwallDrop), `Materials` (Substructure_fc, Rebar_fy, Rebar_Es)
and `ProjectInfo` (the eight stamp strings). Every other input is a literal from the notebook
case: the bearing actions of the D-049 export, the soil, surcharge, wind, cover and reinforcement
inputs, and the bearing spacing (102.99 in from the export's bearing stations, kept against the
journal's 8 ft 7 in beam spacing and reported in `coherence.json`).

## Sources

- `end_bent_walls/bpad/journal/EndBentBackwallDesign.xml` with `coherence.json` and
  `verification.json`, written by `scripts/build_backwall_bpad.py --journal` from the registered
  case (package 16ee4d414858): 23 journal references compared with the case to 1 part in 10^9
  before the build; 245 values compared with the notebook and 585 with the Mathcad edition.
- `project_current/cap_design/backwall/Backwall Design 10-19.html` and `selected_case.json`
  (D-057), `source_register.csv`, `decisions.md`,
  `coherence/evidence/2026-10-19-backwall-rerun/source_receipt.json`.

## Edits (byte-surgical; every anchor asserted; CRLF kept)

`tasks/T017/build_components.py` rebuilds the five component files from `base.bpad`:

- `EndBentBackwallDesign`: the fragment appended unchanged (LF, 2-space indent, as T012/T015).
- `PedBridge`: one index paragraph after the `PileDesignPier` link; the current-record paragraph
  names the backwall report (D-057) and tasks T014 to T017; a revision paragraph.
- `BridgeGeometry_2Beam`: the `EndBent_backwallDrop` caption names the report that reads it.
- `FoundationModeling`: the sentence recording the 16 October report as outside the journal is
  replaced by the rerun record.
- `DecisionLog`: section `CoherenceDecision20261019c` appended.

## Exclusions

No other component changes; no cache refresh; no FBMP re-run, no Mathcad or notebook change
inside the task; no native Blockpad recalculation. `project_current` is not edited by this task
(the register and decisions were updated under D-057 before it; the JOURNAL row follows promotion).

## Output contract

`EndBentBackwallDesign.Status` reads `✓ All Checks Pass` at the 19 October case (distilled
numerical checks only); the plan loads f_str_s = 3.089 kip/ft and f_str_u = 3.737 kip/ft; the
27 `DC_*` ratios with their `Chk_*` strings; `drop_bw` = BridgeGeometry_2Beam.EndBent_backwallDrop.
The six pending prerequisites of the notebook are listed in Section 12 and stay open.

## Acceptance

`check` and `assemble` pass with no new structural issue or stored error; `verify_task.py`
confirms the component set, byte identity of every other component, that every qualified
reference of the new report resolves to a definition in `BridgeGeometry_2Beam`, `Materials`,
`ProjectInfo` or itself, that the coherence rows match the candidate and the registered case,
the PedBridge diff, the text edits, the fragment identity against `verification.json` and the
current package revision, and the `Status` string against the notebook.

## Optional reviews (not required by the promotion policy)

Native Blockpad: open the candidate with its References folder, recalculate
`EndBentBackwallDesign` and confirm the points listed in `cap_bpad/README.md` ("Points to
confirm natively"), plus the live `drop_bw` reference and the `ProjectStamp` cells.
Engineering: the six pending prerequisites; the 102.99-in against 103-in bearing spacing.

## Stop conditions

A stale `verification.json` (package revision not the notebook's), a changed upstream
component, a reference that does not resolve, a coherence row that disagrees with the case, a
check rejection, a new stored error or structural issue.
