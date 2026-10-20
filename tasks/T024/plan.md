# T024 — Project stamp on every calculation; calculations grouped in numerical order

User request (20 October 2026): every calculation carries the project
information table at the top, and the modules are organised so that all the
calculations sit together in numerical order.

## Scope

- Base journal: the T023 revision (`3ccc6316…`).
- `report:PileDesignEndBentOne`, `report:PileDesignEndBentTwo`,
  `report:PileDesignPier`: replaced by the journal edition of the pile
  generator (`scripts/build_pile_bpad.py`, `pile_bpad/journal/`), which now
  opens with the live project stamp (`Stamp_<Key> = ProjectInfo.<Key>` in
  multiline cells, as the cap and backwall editions do). Every other
  definition, value cell, cache and canvas is unchanged. The standalone pile
  sheets carry the stamp as static text.
- `report:PedBridge`: the index lists the calculations C001 to C016 in one
  group in numerical order (each code-reference packet after its calculation);
  the basis modules keep their groups; revision note.
- `report:DecisionLog`: entry.
- Registered component order (`tasks/T024/component_order.json`, workflow `--order`,
  new in `tools/bpad_workflow.py`): the modules are permuted among the module
  slots; references, styles, includes and resources keep their slots and
  every component's bytes are unchanged. Order: index, project information,
  materials, geometry, access, pile section properties, gravity loads, general
  loads, wind basis, load combinations, FBMP entries, foundation modeling,
  C001 (+ references), C002 (+ references), C003 (+ references), C004
  (+ references), C006, C007 to C016, quantities, decision log, notes, general
  reference index, archives.
- Conservative all-component dependency fallback. No prerequisite task.
  Native recalculation, appearance and engineering reviews not performed.

## Acceptance

- The 16 numbered calculations each start with the `ProjectStamp` table
  (multiline cells; live references to `ProjectInfo`).
- Candidate order equals `order.json`; every component outside the write
  scope is byte-identical to the current journal; the three pile reports keep
  every formula and cache (only the eight `Stamp_*` definitions are added).
- Workflow `check` and `assemble` pass; promotion under the current policy.
