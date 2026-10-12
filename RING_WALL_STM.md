# Ring-supported pier wall calculation

[Open the notebook in Colab](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Ring_Supported_Wall_STM.ipynb).
Choose **Runtime → Run all**. No installation, repository clone, Drive mount or
credentials are needed. The maintained `ring_wall/` package is embedded with a
SHA-256 checksum. The Colab form inputs are ordinary editable Python variables.

The calculation starts with minimum steel each way in both broad faces and
matching end U-bars. It then evaluates a tied-arch gravity model between 20-in
pipe piles, multiple ring tiers, vertical collectors, ring reactions, preliminary
concrete and plate screens, and a ring-spacing comparison. The report follows
the existing end-wall and cap presentation: discussion/input/output boxes,
equations with substituted values, drawings and a D/C register.

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

The example outputs in `ring_wall/examples/` are generated from these inputs.
They are a reproducible study, not an issued construction design.

## Mechanics and bounds

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
support or filled-pipe section is credited. A concrete cone is not a support.

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
python -m unittest discover -s tests -p test_ring_wall.py -v
```

The targeted tests check joint equilibrium against independent beam moments,
whole-wall force/moment equilibrium, randomized layouts, code minima, manual
spacing failures, development, load/contact sensitivity, numerical integration
of plate-root moment, invalid inputs, exports, and execution of every notebook
code cell. They also verify that embedded sources exactly match the maintained
package and prevent stale-result export. Local execution uses the same Python
engine and its non-IPython display fallback; Google-hosted Colab UI behavior is
not implied by those tests.

After changing maintained source, rebuild the notebook and regenerate the example
outputs together. Existing cap/end-wall modules and accepted project records
are not inputs to be edited by this notebook.
