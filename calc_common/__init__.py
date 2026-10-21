"""Shared machinery of the journal-calculation packages (C001 to C004, C006, C015 and C016).

Each package (`wind_superstructure/`, `fence_wind/`, `bridge_movement/`, `superstructure_uplift/`, `pier_wall_fins/`,
`mse_wall_exclusion/`, `bearing_design/`) holds its data (`data/*.json`, `data/journal_blocks.xml`) and thin modules
that bind this framework: the same engine, report, exports, notebook UI and Blockpad builder as the backwall
package, driven by the package's definition list instead of hand-written code.
"""
