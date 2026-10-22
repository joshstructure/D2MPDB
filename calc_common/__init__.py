"""Shared machinery of the journal-calculation packages (C001 to C004, C015 and C016; the pier cheek walls C018).

Each package (`wind_superstructure/`, `fence_wind/`, `bridge_movement/`, `superstructure_uplift/`,
`mse_wall_exclusion/`, `bearing_design/`, `pier_cheek_wall/`; the sequestered `sequestered/pier_wall_fins/`, C006, is
not built) holds its data (`data/*.json`, `data/journal_blocks.xml`) and thin modules
that bind this framework: the same engine, report, exports, notebook UI and Blockpad builder as the backwall
package, driven by the package's definition list instead of hand-written code.
"""
