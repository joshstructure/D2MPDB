# T020 — Record the level pier pedestal override

## Objective and authorization

On 20 October 2026 the user requested an override based on the T019 bearing
calculation, then directed that it be recorded in the journal and atlas.
Record the adopted design direction under Bearings and Support Details /
Bearing Pads. Refresh the existing atlas from the journal and source register.

## Bounded contract

- Write only `report:BearingDesign` in the native journal.
- Add a named `PierLevelSeatOverride` section with literal design-direction
  inputs and narrative scope. Preserve every existing formula, result cache,
  resource, reference, component and document-shell byte.
- The two pier pedestal tops are to be horizontal, 0 longitudinal and transverse
  slope, serving pier bearings B1/B2 and B3/B4. This is an adopted geometry
  direction, not final combined bearing approval.
- No new numerical pedestal elevation is selected in this record. The existing
  notebook, B4 workbook, CAD model and drawings remain unchanged; their common
  elevation per pedestal and pad/beam interfaces must be reconciled when the
  geometry override is implemented. End-bent seats are outside scope.
- Register the change as D-064. Preserve other source records and all coherence
  workbook responses/statuses. Publish through the existing atlas refresh.

## Reads, basis and conventions

Use the conservative all-component dependency fallback. The current journal
SHA-256 is 515256c187b7cac03afb47c6f92153441fdbb441ac6ef55799104ea85405de05.
Read the T019 `PierLevelSeatCheck`, its native verification and selected saved
Mathcad source results, D-063 and the current source register.
The existing check uses signed end rotations, zero transverse beam tilt and
standard Type F pads. Do not rerun or alter external analyses.
The original check remains live and governs the override's applicability.
Recheck after changes to grade, beam analysis, pad geometry or support details.

## Output and downstream effects

Named journal literals identify D-064, the adopted zero slopes and pending
geometry reconciliation; the atlas indexes those exact source definitions.
The journal owns this explicit design exception to calculated geometry.
The notebook retains ownership of geometry calculations under D-036.
Do not imply that source adoption applies an override to existing geometry.
Combined lateral shear, uplift/contact, source/load reconciliation and final
support/plate detailing remain open.

## Verification and stop conditions

Confirm only the registered report changes; removing the added section must
restore the exact original report bytes. Confirm prior formula/cache count and
values are retained, new symbols are unique, no stored errors are introduced,
and `check`, `assemble` and `promote` pass. Record file-integrity evidence.
Native recalculation, visual pagination and engineering review are optional
under current policy and are not claimed for this documentary update.
Verify the prepared atlas contains the override and its pending geometry status,
then verify successful publication and current refresh status.
Stop on source conflicts or an invalid inherited calculation; do not fabricate
results or overwrite concurrent changes.
