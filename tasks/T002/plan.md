# T002 — End-bent geometry, current cage and coherence reconciliation

Authorized by the user's 8 October 2026 request to update the project journal from
`End bent 1 Cap Design Report_10-8.html`. The user subsequently confirmed that the
geometry and current cage apply to both end bents. Analysis results remain specific
to End Bent 1. No commit or push is requested.

## Source and baseline

- Canonical journal: `journal/D2_I95_Project_Journal.bpad`, SHA-256
  `5611bee7a1b517f798521029bb9965f3c756941e564280fd8a37d09f81b7dfcd`.
- Supplied HTML report: SHA-256
  `42120857965352febea29e4a672b2ba93f45199430360a89f8e1e529d2df50ef`;
  generated 2026-10-08T15:27:00+00:00. Preserve its embedded case and report bytes.
- Report analysis identity: End Bent 1.XML, SHA-256
  `739f44c1d542464cfd536493ce1ed6cb240f98a75ed3e1188c6f6812742d6fe2`.
- The same-named XML currently in Downloads has a different hash
  `744048c5c0dfa398ddc50f9cf14e51fca2d2a3a985a6c0e73680a35cce2d5811`;
  do not substitute it for the report's analysis or claim a verified model pair.

## Bounded writes and ownership

Permitted components: `report:BridgeGeometry_2Beam`, `report:FBMPEndBent`,
`spreadsheet:QauntitiesBridge`, `report:FoundationModeling`,
`report:PileProperties`, `report:DecisionLog`, `report:PedBridge`.

BridgeGeometry_2Beam owns shared end-bent dimensions. FBMPEndBent records the
entered cage and source-specific force snapshot, with live references to shared
geometry. Quantity formulas reference geometry rather than duplicating inputs.
FoundationModeling and PileProperties explicitly distinguish the square end-bent
piles from the existing pier pipe-pile properties. Preserve historical decisions,
and add a dated supersession entry. Add navigation within the existing index.

## Dependencies and downstream effects

Use the all-component dependency fallback. Inspect actual geometry, load-entry
formulas, quantities, pile properties, bearing stack, source force provenance and
embedded drawings. Principal reads: BearingDesign, PedBridgeWeights_2Beams,
C001WindLoadOnPedBridgeSuperstructure, FenceWind, FBMPPier, LoadCombinations,
PierCapDesign, PierWallFins, FBMPMinTip, references and formatting standard.
The width change affects the centered pile line, bearing offset, pad edge
clearance, native schematics and end-bent eccentricity moments. It does not change
pier geometry, above-pad gravity loads, bridge spans or bearing spacing.

## Output contract and assumptions

Cap dimensions: 212 in along the pile row, 42 in along the bridge, 36 in deep.
Four square 18-in piles per cap, 54-in center spacing; 25-in end-to-first/last
center distances, 16-in nominal end-to-face distances. Stations in geometry and
cage tables begin at the left cap end; XML audit stations begin at the first pile
center and require adding 25 in. Embedment is physical, measured above underside.
Do not confuse the report's 1-in pile/bar gap with its 2-in bar/bar minimum.
Cover is 3 in to the outside of transverse bars.

The retained backwall/beam/bearing chain gives a 24-in bearing line from rear
face, 21-in centered pile line, 3-in spanward offset and 13-in pad-front clearance.
These assumptions are journal geometry, not independent proof of XML input
coordinates. Existing nodes 12/19 remain a legacy assignment requiring remapping
against the exact analyzed model; report force stations point to nodes 15/34.

Current reinforcement: 4 #6 top, 2 #8 continuous bottom, 2 additional #5 span
bars, 7 #4 skin bars per side, and the actual nine-run #4 hoop/U schedule at
6-in pitch. Zero extra main-bar rows and zero longitudinal U-leg credit.
Preserve the distinction between the dormant #8 longitudinal U input and actual
#4 transverse U-bars. Record fit coordinates and quantity exclusions as a dated
source snapshot, not live certified capacity or fabrication dimensions.

## Exclusions and unresolved items

No redesign, new analysis, code compliance approval, change to pier C005, pipe
wall thickness, other notebooks, workflow helpers or document topology. No new
modules/resources. Existing 48-in end-bent pedestal footprint remains unresolved
unless user supplies a replacement. Backwall quantity cannot be determined from
this cap-only report; separate cap quantity from the obsolete combined allowance.
End Bent 2 demand verification, Service III, fatigue, anchorage, four U-bar/pile
conflicts and complete source-model identity remain open. Keep these visible.

## Acceptance and stop conditions

Check source transcription, dimensional identities, 35 transverse stations
(19 closed hoops + 16 open-bottom U-bars), reinforcement areas, cap volume,
formula dependencies, units, native link structure and preservation of all
unassigned component/resource bytes. Run workflow check and assemble against the
current canonical journal. Review Blockpad recalculation and native appearance
on the exact candidate; record only observations actually performed. Promotion
requires those reviews and a bounded engineering data-coherence disposition.
Inherited 110 stored errors and 3 unresolved links are outside these changes and
must not be concealed. Stop promotion if exact-byte review is incomplete,
unassigned changes occur, dependencies change or unresolved assumptions would
be represented as accepted engineering results. No prerequisite task IDs.
