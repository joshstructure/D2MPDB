# T012 - Cap design reports in the journal

Objective: add the distilled cap-design reports (shared basis, End Bent 1, End
Bent 2, Pier; the 19 October 2026 cases, decision D-051) to the journal as
registered modules, index them in `PedBridge`, and make the end-bent
longitudinal steel record in `FBMPEndBent` read the new owner instead of
repeating it. Execute in an isolated task copy and build a candidate. Do not
promote.

Current journal base SHA-256:
`7a0d47ab899b9eb91f9ead3b31a3c55c8bedfe5f5d05f4f26df093d79f4bd0f0` (T010).

## Exclusions

- No other module, resource, style, include or document-shell change. No
  reordering. The journal itself is not edited.
- `PierCapDesign` (C005) is read only and stays unchanged under decision D-003.
  Its duplication with `CapDesignPier` is recorded, not resolved.
- `BridgeGeometry_2Beam.EndBentCap_length` is not corrected (see incoherence
  below). Blocks 1 and 3 of the `FBMPEndBent` design record (the 8 October
  transverse schedule and recorded coordinates) are not refreshed.
- `EBSteel_fc`, `EBSteel_fy`, `EBSteel_Es` stay literal in `FBMPEndBent`; they
  are the owners the cap reports read.
- No FBMP re-run, no Mathcad or notebook change, no native Blockpad recalculation.

## Permitted component keys (registered scope)

`--add report:CapDesignBasis --add report:CapDesignEndBentOne
--add report:CapDesignEndBentTwo --add report:CapDesignPier
--write report:PedBridge --write report:FBMPEndBent`

Added modules are appended in registered key order (alphabetical). All existing
components are watched as dependencies (registered topology addition).

## Read dependencies

| Reader | Reads | Owner |
| --- | --- | --- |
| the three cap reports | cap width, depth; end-bent covers (top, bottom, side) | `BridgeGeometry_2Beam` |
| End Bent 1 and 2 | `EBSteel_fc`, `EBSteel_fy`, `EBSteel_Es` | `FBMPEndBent` |
| Pier | pier cap width, height, length | `BridgeGeometry_2Beam` |
| Pier | covers and materials (`C_t`, `C_b`, `C_s`, `fc`, `fy`, `Es`) | `PierCapDesign`, read only |
| all three | `phi_f`, `phi_v`, `gamma_e`, `lambda`, `phi_a`, `s_proj`, `Ab(k)`, `Db(k)` | `CapDesignBasis` |
| `FBMPEndBent` block 2 | `n_N1`, `Bar_N1`, `n_P1`, `Bar_P`, `n_B1`, `Bar_B`, `n_skin`, `Bar_skin` and `Ab(...)` | `CapDesignEndBentOne`, `CapDesignBasis` |

## Source documents

`cap_bpad/journal/CapDesignBasis.xml`, `CapDesignEndBentOne.xml`,
`CapDesignEndBentTwo.xml`, `CapDesignPier.xml` (bare `<report>` elements built by
`scripts/build_cap_bpad.py --journal`), with `coherence.json` (journal versus
case values) and `verification.json` (build verification counts, fragment
hashes). Case reports: `project_current/cap_design/` 10-19 reports. The build
ties each fragment to the printed case and C005 formula hashes.

## Assumptions and conventions

- Both end bents follow the End Bent 1 configuration (user direction recorded in
  the 8 October design record); the repointed `EBSteel_*` therefore read
  `CapDesignEndBentOne`. End Bent 2 has its own report; nothing in the journal
  reads it yet.
- Known incoherence, recorded not fixed: `BridgeGeometry_2Beam.EndBentCap_length`
  = 17 ft 8 in (212 in, 8 October record, `EndBent_endDetail` = 4 in) versus the
  235-in end caps of decisions D-026/D-027/D-036 and the 251-in cap plus cheek
  cage envelope (D-027: 235 in + two 8 in cheeks) that the cap cases use. The
  end-bent reports keep `L_cap = 251 in` as a literal (status
  `literal_incoherent_journal` in `coherence.json`).
- Pass/fail strings, styles and table colour rules follow `standards/BPAD_Ref_V5.txt`
  sections 8, 11 and 16.2: the document-level PASS/FAIL rules already exist.
- Units: bar areas in in^2 from `CapDesignBasis.Ab(bar number)`; counts are
  dimensionless.

## Output contract

- `CapDesignBasis`: `phi_f`, `phi_v`, `phi_a` (0.9), `gamma_e`, `lambda` (1.0),
  `s_proj` (12 in), `Ab(k)`, `Db(k)` for bar numbers 3 to 11.
- Each cap report publishes `Status` (`All Checks Pass` / `There are FAILURES`
  strings), the `DC_*` demand/capacity ratios (each defined in its report) and
  the bar-count and bar-number inputs. These are the 19 October 2026 case results from the distillation
  engine; the End Bent sheets read `There are FAILURES` (face bar spacing), the
  Pier reads `All Checks Pass`. That covers only the distilled numerical checks
  and is not design acceptance.
- `FBMPEndBent.EBSteel_topCount/bottomCount/addedCount/skinEachSide` and the four
  `*AreaEach` areas become live references; the derived `EBSteel_AsTop`,
  `AsPile`, `AsSpan`, `AsSkinSide` keep their formulas. Values change from the
  8 October record (1.76 / 1.58 / 2.2 / 1.4 in^2) to the current case
  (2.2 / 3.16 / 4.09 / 1.76 in^2).

## Edits to existing modules (byte surgery, assert-once)

`PedBridge`: four index paragraphs inserted after the C005 link under
"Specific calculations and foundations".

`FBMPEndBent`, section `EBCurrentDesignRecord` only: an intro paragraph under
the level-0 heading; block "2. Current longitudinal reinforcement" (eight inputs
repointed with captions and `Required Input` style dropped, derived caches
refreshed, `EBLongitudinalSummary` rebuilt with live count, bar number and area
columns, closing paragraph replaced). Everything else is byte identical.

## Downstream calculations and external analyses

No component other than `FBMPEndBent` reads `EBSteel_As*` (searched). Detected
downstream impact is reported by `check`. FBMP results and models are unchanged;
the longitudinal steel in the FBMP model is not re-derived here. Original FBMP
analysis currency is not asserted.

## Prerequisites

None.

## Acceptance criteria

Numerical: owner literals read by the cap reports equal `coherence.json`
journal values; `EBSteel_As*` caches equal count times area from the cap case
literals; the new cross-references resolve to definitions in the candidate.

Structural: `check` passes; the candidate differs from the current journal only
in the six registered components; no new structural issues or stored errors; the
four index links occur once each; component order is the base plus the four
added keys.

## Optional review plans (not required by the promotion policy)

Native Blockpad: open the candidate with its References folder, recalculate,
confirm unit handling of `Ab(...) to in^2`, amber table-cell definitions,
Unicode names with two underscores, and the two-way references between
`FBMPEndBent` and the cap reports. Engineering: confirm the End Bent 1 case
selection and the 251-in envelope.

## Stop conditions

Changed cap fragments after hashing, upstream journal change, an out-of-scope
diff, a new stored error or structural issue, a reference that does not resolve,
or any mismatch between the fragments and `verification.json`.
