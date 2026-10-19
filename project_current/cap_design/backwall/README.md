# Current backwall and cheek-wall calculation

The [19 October report](Backwall%20Design%2010-19.html) and
[selected case](selected_case.json) are the paired outputs of the
[backwall notebook](../../../End_Bent_Backwall_Design.ipynb) executed on
19 October 2026. D-057 selects these files as current project sources.

The run follows the registered 19 October sources: the D-049 fixed-run End Bent 1
export and the D-051 case built on it (bearing actions unchanged from 16 October),
the D-053/D-055 CAD model measured natively (`scripts/measure_backwall_cad.py`:
two planar 2% backwall tops 4.25 in below the deck-top line, crown 4.0691 ft and
edges 3.8733 ft above the cap top, backwall volume 77.770 ft3, landing tributary
length 17.155 ft) and the T016 journal. The design keeps one centered mat of #4
bars at 10 in each way in the cheek walls. Strap loads for the plans are
3.089 kip/ft service and 3.737 kip/ft factored (16 October: 3.094 / 3.746).
Numerical checks pass; nine check entries remain pending across the same six
unconfirmed prerequisites (settlement, strap elevation, environmental
classification, shrinkage, analysis confirmation, cheek anchorage/load path).
Decisions D-014 to D-019 are unchanged.

All four notebook code cells ran in a fresh in-process IPython session from the
embedded package; the report and case use the same completed recalculation and
the notebook's built-in exporters. Reloading the case reproduces every check ratio
and status. The Colab browser frontend was not exercised. See the
[execution and source receipt](../../coherence/evidence/2026-10-19-backwall-rerun/source_receipt.json)
for exact file identities, the native CAD measurement and downstream review.

The Blockpad edition of this case is in the journal as `EndBentBackwallDesign`
(task T017), with the end-bent geometry, bearing pad data, Span 1 length and
material strengths as live references to `BridgeGeometry_2Beam` and `Materials`;
see `end_bent_walls/bpad/journal/`.

The [16 October report](Backwall%20Design%2010-16.html) (D-037/D-038) and the
[12 October report](Backwall%20Design%2010-12.html) are preserved as history.
Source selection does not close COH-013, COH-023, COH-024 or COH-028.
