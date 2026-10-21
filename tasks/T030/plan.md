# T030 — C017 PierWallRings: caption corrections (rebuilt journal edition)

Follow-up of T028/T029. The preview of the promoted module showed two caption defects of the generator: input captions
repeated the unit ("Wall length (in) [in]") and the input card title "Pile stiffness · ring moment basis (D-070)" had been
rewritten by the visible-text rule to "(former basis)", which misstates the basis. `scripts/build_ring_wall_bpad.py` now
keeps the workbench label alone when it carries its unit and strips the decision id from that title without renaming the
basis. No value, formula, status or structure changes; the 859 definitions and their caches are identical.

- Base journal: the T029 revision (`9c57082b…`).
- Permitted component: `report:PierWallRings` (replaced by the rebuilt `ring_wall/bpad/journal/PierWallRings.xml`,
  checked against its verification record; same name, title, definitions and formulas as the T028 module).
- Conservative all-component dependency fallback. No prerequisite. Native recalculation, appearance and engineering
  reviews not performed. The JOURNAL register row moves to this revision (tasks/T030/register_journal.py).
