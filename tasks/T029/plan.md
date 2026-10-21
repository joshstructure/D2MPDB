# T029 — C017 PierWallRings moved after C016 (registered order)

Follow-up of T028, which appended `report:PierWallRings` (C017 - Pier Wall, Annular Pile Rings) after the last component
because the addition path cannot carry a registered order. This task registers the order that places the module directly
after `report:BearingDesign` (C016), so the modules read basis → C001 to C017 (reference packets after their calculations)
→ quantities, decisions, notes, references and archives, as the PedBridge index lists them since T028.

- Base journal: the T028 revision (`38df825b…`).
- Registered order: every component key of the base journal, with `report:PierWallRings` moved from the last slot to the
  slot after `report:BearingDesign`; no other component moves. No component bytes change; no write scope.
- Verification: the candidate holds exactly the base components' bytes, in the registered order (tasks/T029/verify_order.py).
- Native recalculation, appearance and engineering reviews not performed; no engineering value changes.
- After promotion `tasks/T029/register_journal.py` moves the JOURNAL row of the project source register to this revision
  (status: calculations C001 to C017 in order with project stamps).
