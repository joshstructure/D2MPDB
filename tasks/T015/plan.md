# T015 - Pile design reports in the journal

Objective: add the distilled pile-design reports (End Bent 1, End Bent 2, Pier;
the 19 October 2026 cases, decision D-054) to the journal as registered modules
and index them in `PedBridge`. Execute in an isolated task copy and build a
candidate, then promote it (the user's 19 October 2026 instruction authorizes
the promotion; the promotion policy makes native and engineering reviews
optional).

Current journal base SHA-256:
`119261e3e7cc86d67bdde67052ca2953cdb81c24d559e468032f32d072c1e01b` (T014).

## Exclusions

- No other module, resource, style, include or document-shell change. No
  reordering. The journal itself is not edited directly.
- `PierCapDesign` was removed under T014; the cap-design reports (T012) and
  `FBMPEndBent` are untouched. The pile reports do not replace or repoint any
  existing pile record (`PileProperties`, `FBMPEndBent`, `FBMPPier`,
  `FoundationModeling`): those remain as recorded and are not reconciled here.
- No FBMP re-run, no Mathcad or notebook change, no native Blockpad recalculation.

## Permitted component keys (registered scope)

`--add report:PileDesignEndBentOne --add report:PileDesignEndBentTwo
--add report:PileDesignPier --write report:PedBridge`

Added modules are appended in registered key order (alphabetical). All existing
components are watched as dependencies (registered topology addition).

## Read dependencies

None. The three reports read no journal module. Every input is a literal from
the notebook case (the D-049 FBMP records, the D-050 downdrag, the Standard
Plans strand pattern, material properties and the design factors), written into
the report as an amber input with its source. Every `PileDesign*.Name` reference
resolves to a definition in the same report. The verification step searches the
whole candidate for references to any other module and fails if one is found.

## Source documents

`pile_bpad/fragments/PileDesignEndBentOne.xml`, `PileDesignEndBentTwo.xml` and
`PileDesignPier.xml` (bare `<report>` elements built by
`scripts/build_pile_bpad.py` from `pile_design/bpad.py`), with
`pile_bpad/verification.json` (package revision, FBMP file and hash, comparison
counts, SHA-256 of each `.bpad` document). Case reports and cases:
`project_current/pile_design/` 10-19 (D-054). The build compares every
definition and external of the case with the notebook to 1 part in 10^9 and the
sheet with the Mathcad edition; the fragments are tied to package revision
`32d46a79afd4...` (`pile_design.mathcad.package_revision()`).

## Assumptions and conventions

- The reports are the Blockpad edition of the notebook cases listed in
  D-054: End Bent 1 and End Bent 2 (18 in square prestressed concrete piles,
  Standard Plans Index 455-018, 12 x 0.6 in strands, 18 tons of downdrag per pile
  as a drag load, D-050) and the Pier (20 in x 0.48 in steel pipe piles, no
  downdrag). FBMP results are the D-049 fixed-run exports.
- Vectors become scalar names ending `_1`... (Blockpad has no vector variables);
  the two interaction sweeps are native canvases drawn from the notebook's curve
  points and do not move when an input changes (see `pile_bpad/README.md`).
  Values the Mathcad sheet finds by a search (`M_r_P0`, `P_r_rs`, `M_r_rs`) are
  amber inputs read from the notebook.
- Pass/fail strings, styles and table colour rules follow
  `standards/BPAD_Ref_V5.txt` sections 8, 11 and 16.2; the document-level `PASS`
  and `FAIL` rules and the `Result only` style already exist in the journal.
- Units: kip, ft, in, ksi as the notebook; ratios dimensionless.
- Added reports are bare fragments (LF line endings, 2-space indent) appended
  unchanged, as in T012; the rest of the journal is CRLF. `PedBridge` keeps its
  CRLF line endings.

## Output contract

Each report publishes `Status` (`✓ All Checks Pass` / `⊗ There are FAILURES`, the
journal's strings) and the `DC_*` demand/capacity ratios, each defined in its
report with a `Chk_*` result string. At the 19 October 2026 cases all three read
`✓ All Checks Pass` (structural D/C 0.550 End Bent 1, 0.557 End Bent 2, 0.457
Pier). That covers only the recomputed numerical checks. It is not design
acceptance: downdrag source documentation, pile-to-cap connection, pipe steel
grade and corrosion, minimum tip, scour, drivability, environment
classification and FBMP export currency remain open (listed in each report).

`PedBridge`: three index paragraphs after the `CapDesignPier` link under
"Specific calculations and foundations".

## Edits to existing modules (byte surgery, assert-once)

`PedBridge` only: insert the three link paragraphs immediately after the
`CapDesignPier` link paragraph, in the markup of the cap links (same font, size,
spacing and indent). The anchor occurs exactly once; no target is already linked.
Everything else is byte identical.

## Downstream calculations and external analyses

No existing component reads the new names. FBMP models and results are unchanged
and were not re-run; the sheets read the D-049 exports through the notebook, not
live. Currency of the FBMP analysis against the pile design is not asserted
beyond the pending prerequisite `FBMP export current` listed in each report.

## Prerequisites

None.

## Acceptance criteria

Numerical: the fragments equal the committed sheets (`tests.test_pile_bpad`)
and `pile_bpad/verification.json` is tied to the current package revision; the
`Status` strings equal the notebook; every internal `PileDesign*` reference
resolves.

Structural: `check` passes; the candidate differs from the current journal only
in the four registered components; no new structural issues or stored errors; the
three index links occur once each; component order is the base plus the three
added keys; the `PedBridge` diff is exactly the three link paragraphs.

## Optional review plans (not required by the promotion policy)

Native Blockpad: open the candidate with its References folder, recalculate each
report and confirm the points listed under "Points to confirm natively in
Blockpad" in `pile_bpad/README.md` (amber inputs in table cells, subscripted
names with a trailing digit group, compound-unit literals, `Tan`/`Sin` of an angle
in degrees, fractional powers of dimensioned quantities, dashed `lines` and
`PlotLines` with formula coordinates, `null` in `PlotLines`, long `Max(...)`
argument lists). Engineering: confirm the case selections and the pending items.

## Stop conditions

Changed fragments after hashing, a stale `verification.json`, an upstream journal
change, an out-of-scope diff, a new stored error or structural issue, a reference
that does not resolve, a reference to another journal module, or any mismatch
between the fragments and the committed `.bpad` documents.
