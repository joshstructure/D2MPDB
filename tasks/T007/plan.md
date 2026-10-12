# T007 — support terrain elevations

Objective: append a dated quick-reference terrain note and Project Index link.
Permitted components: report:Notes and report:PedBridge only.
Read dependencies: all current journal components and supporting files through
the unchanged conservative workflow fallback; verified CAD terrain lookup report.
Sources: saved registered B4 model, original Ex_I-95_Middle LandXML and the
2026-10-12 support-terrain-elevations.json, archived byte-identical in sources/.
Convention: each cap/pile centerline intersecting the bridge PGL centerline;
elevations in US survey feet, NAVD88; horizontal FL83/2011-EF confirmed by user.
Output: dated static measurement record with two-decimal display and links;
full numerical precision retained in the source JSON. No formula inputs added.
Exclusions: no shared terrain/design-variable replacement, formulas, caches,
upstream calculations, analysis files, structural conclusions or CAD saves.
Downstream: no recalculated design inputs; lookup note only. No prerequisites.
Acceptance: exact component scope, unchanged formula/cache/resource bytes,
valid new internal link, source-value comparison, native Blockpad opening and
appearance review of the index and note, evidence tied to exact candidate bytes.
Stop on stale dependencies, changed source identity, unintended formula changes,
new structural errors or unavailable native review. Use check/assemble/promote.
