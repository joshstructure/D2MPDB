# T039 — C018 PierCheekWalls moved after C017 (registered order)

Follow-up of T038, which appended `report:PierCheekWalls` (C018 - Pier Cap Cheek Wall Design) after the last component
because the addition path cannot carry a registered order. This task registers the order that places the module directly
after `report:PierWallRings` (C017), so the modules read basis → C001 to C018 (reference packets after their calculations)
→ quantities, decisions, notes, references and archives, as the PedBridge index lists them since T038.

- Base journal: the T038 revision (`f8352579…`).
- Registered order: every component key of the base journal, with `report:PierCheekWalls` moved from the last slot to the
  slot after `report:PierWallRings`; no other component moves. No component bytes change; no write scope.
- Verification: the candidate holds exactly the base components' bytes, in the registered order (tasks/T039/verify_order.py).
- Native recalculation, appearance and engineering reviews not performed; no engineering value changes.
- After promotion `tasks/T039/register_journal.py` moves the JOURNAL row of the project source register to this revision
  (covers T038; status: calculations C001 to C018 in order with project stamps; depends on CHEEK-CASE and CHEEK-TOOL).
