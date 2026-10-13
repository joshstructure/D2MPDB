# Ring-supported pier wall calculation

[Open the notebook in Colab](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Ring_Supported_Wall_STM.ipynb).
Choose **Runtime → Run all** to open the live workbench with starting results.
The maintained `ring_wall/` package is embedded with a SHA-256 checksum. Colab
setup installs ipywidgets 7.7.1 and Plotly 5.24.1, matching the cap notebook.
No manual installation, repository clone, Drive mount or credentials are needed.
Local Jupyter needs ipywidgets and Plotly; Plotly 6 also requires anywidget.

The calculation starts with minimum steel each way in both broad faces and
matching end U-bars. It then evaluates a tied-arch gravity model between 20-in
pipe piles, multiple ring tiers, vertical collectors, ring reactions, preliminary
concrete and plate screens, and a ring-spacing comparison. The report follows
the existing end-wall and cap presentation: discussion/input/output boxes,
equations with substituted values, drawings and a D/C register.

## Working in the notebook

The labeled panel buttons explicitly display the selected content, avoiding
Colab's native tab-selection behavior. The active button is blue and the panel
name appears above its content. If an older copy stays on Live layout, save the
case, reopen the published notebook linked above, and **Run all**. An already-open
copy contains its own embedded package and does not automatically update.

1. Edit the **Wall & loads**, **Reinforcement**, **Rings & STM**, and **Factors**
   tabs inside **Inputs**. The wall elevation and end-pile plan update with inputs.
2. Click the floating **Recalc** button. The starting case calculates when the
   workbench opens; later input edits clear results until Recalc. Green **Calc
   done** means results are current, regardless of design failures or open checks.
3. Review the interactive **Ring forces** reaction heatmap and row-filtered
   output table; **Struts & ties** demand/capacity plots, band table and equilibrium
   residuals; and **Reinforcement** output table and end U-bar drawing.
   **Cone transfer** adds a live 3-D envelope and trial transfer-force tables.
4. In **D/C checks**, select all checks, largest D/C first, failures first,
   failures only, or pending only. Equation/value disclosures retain the model's
   governing formulas, substituted input values, intermediate results, units,
   and the final demand/capacity comparison. The notebook and exported report
   use the same derivations. Filtering never changes the calculation.
5. Use **Ring spacing** to compare reaction and tie forces with the grid and
   failure table for each spacing. This remains an assumed strength allocation.
6. When ready, expand **Report and exports**. **Generate calculation report**
   downloads the standalone HTML report. **Export case + checks ZIP** includes
   the report, case/results JSON, check/ring-force CSV, and spacing-study JSON/HTML.

Running all cells does not write exports. New exports require current results;
each successful export uses a separate folder. Saved-download buttons refer to
the last successful export even after inputs change. Use **Load saved case** to
restore `ring_wall_case.json`, then Recalc. Rerunning the workbench retains active
inputs and the previous saved export. Save downloads before ending a Colab runtime.

## Initial case

The earlier C006 wall snapshot supplies 213 × 36 × 172.375 in, four piles at
60-in centers, 5.5-ksi concrete and Grade 60 reinforcement. Current repository
`project_current/cap_design/pier/selected_case.json`, read at commit
`37bf40f4e274d4a55661ae13424bd6733f153b74`, confirms pile count, spacing, diameter
and material strengths. The current cap's 3-in pile-placement tolerance is used
instead of the earlier wall study's 2 in. Wall geometry is an explicit study
snapshot, not a current CAD import.

- Five ring tops at 6, 42, 78, 114 and 150 in above the wall bottom.
- Trial ring ID 20.125 in, OD 23 in, thickness 0.75 in; no availability claim.
- Required STM grid: **0.648 in²/ft per face each way**. With the shallowest
  assigned band, the default #5 selection becomes **#5 at 5 in each way each
  broad face**, plus matching #5 end U-bars at 5 in vertically.
- S&T envelope: 0.3336 in²/ft per face. #5 at 5 in supplies 0.744 in²/ft.
- #5 straight top-bar development: 54.634 in with no confinement credit;
  Class B lap allowance 71.024 in. Trial U legs are 72 in from bend tangents.
- Additional primary ties/collectors are sized separately. Minimum grid steel
  is not counted again as primary tie steel.
- Gross wall weight 114.737 kip; factored gravity 143.421 kip at γDC = 1.25.
- **Default fit failures:** ring end cover is 2 in versus 3 in required, and
  ring-to-inner-face-grid clearance is −0.75 in at the entered tolerance.
- With **Broad-face cone transfer (trial)** selected, the node base is raised
  4.333 in. The arches plus finite strut half-width then fail band fit in rows
  1–4. These additional failures are retained as design results.

The example outputs in `ring_wall/examples/` are generated from these inputs.
They are a reproducible study, not an issued construction design.

## Mechanics and bounds

### Broad-face cone transfer trial

The default now uses the user's requested two broad wall faces. The reference
CCD breakout sketch in [ACI's 2023 webinar, slide 2](https://www.concrete.org/portals/0/files/pdf/webinars/ws_F23_Worsford.pdf)
labels a 1.5 horizontal to 1 vertical projection as approximately 35 degrees.
The exact angle corresponding to 1.5 H:1 V is 33.690 degrees from horizontal.
The editable slope is a geometric assumption. Applying this anchor-breakout
geometry from an annular ring perimeter is an extrapolation; it is not an
ACI-specified compression spread or a verified ring breakout resistance.

At height z above a ring, the outer envelope radius is
`r(z) = ring_OD/2 + slope * (z - ring_top)`. For a centered pile, first contact
with either broad face occurs at `h_face = (wall_thickness/2 - ring_OD/2)/slope`.
The default gives `(18 - 11.5)/1.5 = 4.333 in`. At the ±3-in transverse placement
limit, near/far face reaches are 2.333/6.333 in. The outer-pile cone reaches the
wall end at 3.333 in, before reaching the broad face; end truncation stays open.

First face contact occurs directly above the pile center in the longitudinal
projection. It sets the trial node-region base, with the entered tie offset
locating the node centroid above that base. Bay span remains 60 in. The cone
does not create an external reaction, a rigid support, or a shorter arch span.
Arch fit is reevaluated at the raised elevation; gravity and ring equilibrium
retain the original load allocation and longitudinal end couples.

For an explicit symmetric ring-to-face force path, each trial face node receives
R/2. Compression links run from the ring outer perimeter to the face reference
nodes. With their run Δy and rise Δz, the transverse tie resultant is
`T = (R/2)*Δy/Δz`, link compression is `sqrt((R/2)^2 + T^2)`, and additional tie
area demand is `T/(phi_tie*fy)`. No grid or existing transverse steel is credited.
These equilibrium demands are not verified strengths: reference face nodes need
finite areas and cover inside the concrete, ties need routing/anchorage around
the hollow pipe, and offset-pile/3-D behavior and longitudinal end moments remain
unresolved. Every ring-transfer demand retains PENDING status.

Select **Original ring level** to compare the earlier model. Saved cases lacking
the two new cone inputs retain the original ring-level geometry when loaded.

### Gravity and connection model

Midpoints between ring elevations partition the wall into tributary bands.
Each bay uses a parabolic funicular polygon for uniform gravity, with half
tributary columns at the endpoints. Segment forces and dedicated horizontal
ties satisfy joint equilibrium. Dedicated vertical collectors are sized for
the full column load; transferring weight vertically to arch joints is not
assumed to happen without steel. All concrete below the bottom ring is included.

The wall-end overhang is kept separate from the bay arch. Its weight and moment
are handed to the outer ring and pile; explicit opposite end couples close
global equilibrium. Its complete local STM is an open design item.

Concrete node calculations use an equivalent width no larger than wall thickness
minus pipe diameter, a reduced annular bearing fraction, ν = 0.45 and no
confinement increase. These are **screening assumptions**, not a validated 3-D
annular node. No concrete tension, pipe bond/friction, cap suspension, soil
support or filled-pipe section is credited. The cone transfer trial adds no
external support and establishes no breakout resistance or rigid-cone behavior.

The elastic radial plate strip includes the ring-to-pipe fit gap in its lever
arm. The export includes ring axial force, end moment, pressure, required
elastic plate thickness, radial root moment and direct weld-line force.
The radial root moment/prying must be checked in addition to weld direct shear.

The report cannot return overall PASS. Compatibility and row engagement,
three-dimensional nodes/splitting/breakout, end-zone topology, all primary-tie
anchorage, welds, ring splices, pipe-shell response, applicable fatigue and other
project loads remain open. Changing row spacing is a strength study, not proof
of actual equal reaction sharing.

## Code basis

AASHTO LRFD Bridge Design Specifications, 10th edition (2024): 5.5.4.2;
5.8.2.2–5.8.2.6; 5.10.2; 5.10.3.1.1; 5.10.6; 5.10.8.2.1; 5.10.8.4.3.
The development equation uses the revised 10th-edition expression, consistent
with `pier_cap/lrfd_checks.py`. No beneficial confinement or excess-steel
development reduction is credited. The two orthogonal S&T sections are enveloped
for a uniform conservative cage. The minimum STM bar-spacing limit uses the
shallowest assigned band's effective depth; confirm that D-region interpretation
for the final topology. Confirm FDOT/project criteria, exposure and mix inputs.

[FHWA-NHI-17-071](https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf) supplies
background examples; it uses an older code edition. It is not the authority for
the notebook's 2024 equations.

## Maintenance and verification

```powershell
python scripts/build_ring_wall_notebook.py
python -m unittest discover -s tests -p "test_ring_wall*.py" -v
```

The targeted tests check joint equilibrium against independent beam moments,
whole-wall force/moment equilibrium, randomized layouts, code minima, manual
spacing failures, development, load/contact sensitivity, numerical integration
of plate-root moment, invalid inputs, exports, and execution of every notebook
code cell. They also verify that embedded sources exactly match the maintained
package and prevent stale-result export. Workbench tests exercise real widget
edits and button callbacks, live plot data, stale-state clearing, invalid inputs,
filters, saved-case loading, separate exports and preservation of prior downloads.
Local execution does not by itself verify Google-hosted Colab UI behavior.

After changing maintained source, rebuild the notebook and regenerate the example
outputs together. Existing cap/end-wall modules and accepted project records
are not inputs to be edited by this notebook.
