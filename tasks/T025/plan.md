# T025 — Project stamp of the hand-authored calculations in multiline cells

Follow-up of T024 (same user request, 20 October 2026: every calculation
carries the project information table). The seven hand-authored calculations
(C001, C002, C003, C004, C006, C015, C016) already open with the live
`ProjectStamp` table, but its value cells (`<c formula="ProjectInfo.<Key>">`)
clip the project name natively. They become the form of the generated
editions: multiline cells holding a result-only definition
`Stamp_<Key> = ProjectInfo.<Key>` with the cached text.

- Base journal: the T024 revision (`255ce8e3…`).
- Permitted components: the seven reports above and `DecisionLog`.
  Byte-surgical (`tasks/T025/build_components.py`): exactly eight value cells
  per report are replaced; every other byte of each report is unchanged, so
  every existing definition, cache, canvas and resource is kept. Eight
  definitions are added per report; none removed. The stamp text is the
  cached text the cells already held (the `ProjectInfo` strings).
- Conservative all-component dependency fallback. No prerequisite task.
  Native recalculation, appearance and engineering reviews not performed.
