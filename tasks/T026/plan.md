# T026 — Pile calculations C011–C013: journal edition without the package revision

Follow-up of T024. The pile journal edition's hidden provenance paragraph named
the pile package revision, which changes with every edit of the embedded
package (another session is editing it concurrently). The journal edition now
omits it (the same rule as the cap edition since T013 and the backwall edition
since T023) and is tied to its case alone; the revision stays in
`pile_bpad/journal/verification.json`.

- Base journal: the T025 revision (`51c4fb74…`).
- Permitted components: `report:PileDesignEndBentOne`, `report:PileDesignEndBentTwo`,
  `report:PileDesignPier`, copied from `pile_bpad/journal/` after their
  verification records are checked; exactly one hidden paragraph differs per
  report; every definition, value cell, cache and canvas unchanged.
- Conservative all-component dependency fallback. No prerequisite task.
  Native recalculation, appearance and engineering reviews not performed.
