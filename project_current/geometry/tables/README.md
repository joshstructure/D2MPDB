# Geometry CAD tables

[`B4_Geometry_CAD_Tables.xlsx`](B4_Geometry_CAD_Tables.xlsx) is the selected
geometry CAD-tables workbook (D-041, updated by D-053), registered as GEOMETRY-TABLES.

Both backwall tops now use two 2% slopes, level through their thickness,
4-1/4 in below the FFBW deck-top line. The ramp slabs thicken locally to
meet them. Model e9b41b8eaf agrees with the adopted CAD backwalls.

The pedestal tops here are the sloped seat planes of the notebook, kept as the
full-resolution seat record and grinding reference (D-086). The CAD model and
construction use the level as-cast tops of D-065, one elevation per pedestal at
its maximum corner. The difference is intended.

It recalculates the geometry notebook as live Excel formulas. It also fills the FGE,
Build-Up & Deflection, Table of Beam Variables, Bearing Plate and Pedestal
Elevation CAD tables, including the cap, pile-cutoff and end-bent wall
elevations. Each tab has a Method tab with equations and live charts.

The file stands alone. It has no macros or external links, and it needs nothing
else to open or recalculate. If an input is edited in Excel, the tables and charts
follow the edit. A banner on every Method tab then reports that the workbook no
longer matches the notebook build.

Change geometry in the [notebook](../../../Bridge_Geometry_2%20Beam_V2.ipynb),
then rebuild with `.venv\Scripts\python.exe scripts\build_geometry_cad_tables.py`.
The build writes this file. Its bytes then differ from the register, so record why
it was rebuilt and update the hash. The generator and its method notes are in
[geometry_tables](../../../geometry_tables/README.md). The selection record is the
[source receipt](../../coherence/evidence/2026-10-16-geometry-tables/source_receipt.json).

Selection is not issue approval. The BCC-template items flagged on the Method tabs,
and the open items on the Cover, still need review.
