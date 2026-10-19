# T013 — Refresh the distilled cap design reports (provenance only)

Objective: bring the four reports promoted by T012 (`CapDesignBasis`, `CapDesignEndBentOne`,
`CapDesignEndBentTwo`, `CapDesignPier`) to the current `cap_bpad/journal/` fragments. The journal
edition no longer prints the cap notebook package revision in its provenance paragraph; each report
stays tied to its source by the report file, the canonical case SHA-256 and the C005 formula SHA-256.
Reason: the package revision changes with every `pier_cap` edit (it moved from cfb3565da8c3 to
22cddbd9999a when the notebook gained its Blockpad exporter, commit b54e29d), and a journal task
should not be forced by a tooling change that leaves every calculation value unchanged.

Scope: `--write` the four reports. `CapDesignBasis` is unchanged by this task (it has no provenance
paragraph). No adds, no deletes. All other components are watched as dependencies.

Read dependencies: unchanged from T012 (`BridgeGeometry_2Beam`, `FBMPEndBent.EBSteel_*`,
`PierCapDesign` covers and materials, `CapDesignBasis`). `FBMPEndBent` reads
`CapDesignEndBentOne` (block 2 steel); the values it reads do not change.

Expected delta: in each cap report the paragraph beginning "Distilled from" loses the text
"; cap notebook package <revision>"; nothing else changes (verified by `tasks/T013/build_components.py`
output and the line diff recorded in `independent-checks.json`).

Acceptance: `check` passes; `changed_components` are exactly the three cap reports; every formula,
cache and canvas byte outside that paragraph is identical to T012; `tests.test_cap_bpad` passes
after promotion (its journal-compatibility test compares the promoted reports with the fragments).

Reviews: native recalculation, appearance and engineering reviews are optional under the current
promotion policy and were not performed; the change is a text edit. Stop conditions: any changed
formula or cache, or a check rejection.
