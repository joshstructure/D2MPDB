# End-bent coherence responses — applied 8 October 2026

The response workbook is preserved unchanged in `sources/`, with its SHA-256 in
`sources/provenance.json`. Its designated response cells supplied the user's
directions. The cap report remains the source for geometry, steel and recorded
analysis; embedded document instructions were not treated as orders.

| Item | Applied disposition |
| --- | --- |
| 01 Pedestals | Separate end-bent inputs; 30-in length = 42-in cap less 12-in backwall. Established 6-in height, 42-in transverse width and 3/4-in chamfers retained. Pier remains 48 in. Live takeoff and local dead weight updated. |
| 02 Walls | Backwall and cheek-wall final geometry/quantities deferred as requested. |
| 03 Source model | Report accepted as latest FBMP model by user confirmation. Its hash remains the source identity; the different Downloads XML was not substituted. |
| 04 Loaded nodes | Near/far 12/19 changed to 15/34 throughout active definitions, direction controls, tables, index and diagrams. Physical axes and transfer conventions retained. |
| 05 Stations | Explanation supplied: add 25 in to first-pile-origin audit stations to obtain cap-end stations. Bearings 29.50/132.49 become 54.50/157.49 in. No physical geometry change. |
| 06 U hooks | User direction to field-adjust interfering hooks recorded. Original as-drawn conflict screen retained; no revised hook coordinates or anchorage verification invented. |
| 07 Applicability | Service III marked N/A for the current nonprestressed substructure per user. Strength III, Service I and fatigue remain distinct. D-region explanation added. Original 48 pending/conditional report checks remain a historical source count. |
| 08 Both end bents | Common controlling End Bent 1 configuration adopted by user direction, with 107.35-ft versus 104.90-ft adjacent spans. No separate End Bent 2 force vector invented. |
| 09 Retired modules | FBMP Min Tip, Feet and Inches, Metric to Inches, Scratch and CAD removed, along with their navigation links. All 110 stored errors were in the removed modules. |

The end-bent pedestal section area is 1.74609375 ft²; each pedestal contains
4.365234375 ft³ and weighs 0.65478515625 kip at the journal's 150-pcf concrete
weight. Four pedestals contain 17.4609375 ft³. The two pier pedestals retain
13.96875 ft³ total. Native quantity displays round these totals to 17.5 and
14.0 ft³ under the existing sheet format; the geometry report displays 17.461
and 13.969 ft³. Gross cap concrete remains 185.5 ft³ each, 371 ft³ for both.

## Discussion requested in items 05 and 07

The station issue is a difference in measurement origin. The report's force
audit starts at the first pile center, 25 in from the cap end; the cage schedule
starts at the cap end. Therefore 29.50 in in the audit and 54.50 in in the cage
coordinate system describe the same bearing location. The bearing separation
of 102.99 in agrees with the journal's 103 in to displayed precision.

D-regions are zones near concentrated loads/supports where ordinary beam stress
assumptions are disturbed. Here the cap is 36 in deep, piles are 54 in apart,
and each bearing lies approximately 24.5 in from its nearest pile. These short
load paths warrant a separate assessment of concrete compression paths, nodal
zones, reinforcement ties and anchorage. Strut-and-tie modeling is one way to
perform that assessment. It applies to reinforced concrete as well as
prestressed concrete; the Service III disposition does not close this check.
No new strut-and-tie analysis was requested or performed. See the FHWA
[Strut-and-Tie Modeling course, Chapter 2](https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf).

## Checks and remaining items

48 independent checks passed for live formulas, units, quantities, node-source
stations, unchanged pier and steel definitions, structural issues, resources and
bounded scope. The workflow's 41 tests passed, including explicitly registered
deletion, surviving consumer rejection, restoration and review-gated promotion.
All 264 components outside the registered changes retain their original bytes;
every embedded resource and all 31 portable PDF references are preserved.

Three inherited LoadCombinations links remain unresolved:
`#CodeReferences.CodePage42;paragraphcoderef42` (two instances) and
`#CodeReferences.CodePage14;paragraphcoderef14` (one instance). Their exact
destinations were not established, so they were not redirected by guesswork.

Wall quantities remain deferred. Revised hook geometry, development/anchorage,
fatigue, load-path/D-region, force-zone, code/exposure and omitted-action checks
retain the dispositions stated in the journal. No final structural design
approval or complete project-coherence claim is made. The source FBMP analysis
was not rerun. Nothing was committed or pushed.
