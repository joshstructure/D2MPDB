# Sequestered calculations

Calculations withdrawn from the project but kept intact so they can be revived. Nothing in
this folder is built, tested, registered, cited by the code-excerpt store, carried in the
journal or shown in the design atlas. Calculation numbers are permanent: a withdrawn
calculation keeps its number and the number is never reused (C005 and C006 are retired).

| Calculation | Withdrawn | Decision | Contents |
| --- | --- | --- | --- |
| C006 - Pier Wall, Hairpins and Fin Plates | 2026-10-22 | D-082 | `pier_wall_fins/` (data package on `calc_common`, hand-drawn schematics, standalone and journal Blockpad editions, committed report run) and `Pier_Wall_Fins.ipynb` (portable Colab notebook of that package) |

C006 sized the fin-plate and hairpin hanger concept for carrying the pier wall on its pipe
piles. The project carries the welded annular-ring concept instead (C017, `ring_wall/`,
matching the CAD model under D-076 and D-079), so the fin-plate calculation was removed from
the journal (task T040) and from every build list. Its last state is the one it had in the
journal revision before T040 (the T034 journal values, 82e7d3e1…; package run of
21 October 2026), with the CAD wall geometry of D-075.

## Reviving a sequestered calculation

1. Move the package back to the repository root (`git mv sequestered/pier_wall_fins
   pier_wall_fins`, `git mv sequestered/Pier_Wall_Fins.ipynb Pier_Wall_Fins.ipynb`); the
   notebook's setup cell expects the package beside the other packages.
2. Add the package back to `PACKAGES` in `scripts/build_journal_calc_notebooks.py`,
   `scripts/build_journal_calc_bpads.py`, `scripts/export_journal_calc_reports.py` and
   `tests/test_journal_calc_packages.py`, and its `references.json` to
   `code_excerpts/library.json`; rebuild the excerpt store (every notebook embeds it, so
   follow the D-080 / D-082 rebuild cascade: notebooks, Mathcad and Blockpad editions,
   re-register the tool notebooks).
3. Refresh `data/journal_import.json` against the current journal
   (`scripts/refresh_journal_import_values.py`) and rebuild the chain
   (`build_journal_calc_notebooks.py` → `build_journal_calc_bpads.py` → `--journal` →
   `export_journal_calc_reports.py`).
4. Put the module back in the journal with a task that registers `prepare --add
   report:PierWallFins`, then `prepare --order` to place it after C004 (the T028/T029
   pattern), and restore its index entry in `PedBridge`; the module keeps the title
   `C006 - Pier Wall, Hairpins and Fin Plates`.
5. Record the decision in `project_current/decisions.md`, map it in `DECISION_SOURCES` of
   `scripts/build_lineage_graph.py`, rebuild the lineage graph and run the atlas gate.
