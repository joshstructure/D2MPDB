# Service plot limits and equation schematics

The cap workbench and exported calculation report use the same service-limit
helpers. Reopen `Cap_and_Pile_Design.ipynb` from GitHub and run its setup after an
update; regenerate an HTML report to obtain a new snapshot.

## Reading the plots

- In **Force diagrams**, select **Service I** or a confirmed **Service III**
  analysis. Orange traces are the steel-stress moment limit; dashed purple
  traces are the crack-spacing moment limit. The trace nearer zero governs.
- Hover a moment demand to see moment utilization, the controlling limit,
  and remaining moment in kip-ft and percent. Negative remaining moment means
  the plotted demand exceeds that sectional limit.
- The regional steel-stress charts show both the direct stress limit and the
  spacing limit converted to the plotted stress basis. Their demand hover
  retains the stress and spacing D/C components.
- Service shear and torsion retain their demand curves. This calculator has no
  corresponding service limits, so it does not draw strength resistance on
  those service panels.

## Calculation basis

The new display inverts the existing relations in
`pier_cap/data/c005_formulas.json`; it does not revise those design criteria.
With moments in kip-ft, dimensions in inches, and stress in ksi:

```
k_centroid = 12 n_mod / Ss
k_outer   = 12 n_mod (h - ccr - do) / Icr
f_spacing = 700 gamma_e / [bs (s + 2 dc)]

Service I:   M_stress = (0.8 fy) / k_centroid
Service III: M_stress = 24 / k_outer
Both:        M_spacing = f_spacing / k_centroid
             M_limit = min(M_stress, M_spacing)
             moment utilization = abs(M) / M_limit
             remaining moment = M_limit - abs(M)
```

The spacing `s` is the larger of the sectional check value and the actual
drawn outer-row pitch. Service III uses outer-bar stress for its stress check
but centroid stress for crack spacing. The purple line on its outer-stress
chart is consequently `M_spacing * k_outer`.

Moment utilization is a load-to-limit measure. It is **not** the spacing D/C
`s / S_allow`, whose denominator changes nonlinearly with moment. The existing
check register retains its original ratios and applicability gates.

Top steel supplies the negative-moment reference. Positive-moment limits use
continuous steel, with combined steel only over the common straight extents
of the drawn added bars. Outside those extents, the continuous reference also
checks the full-row spacing outside a pile footprint. The exclusion beside
an embedded pile is not extended across spans. At a step boundary, hover
uses the more restrictive adjacent limit.

Service I retains the `fy < 75 ksi` applicability gate. Service III limits
are unavailable until `Ready_III` is confirmed; an unconfirmed placeholder
never becomes zero demand or a passing limit. Station overlays are suppressed
when pile layout or cap-end dimensions no longer match the source analysis.
Development, cutoffs, fit, exposure and other existing conditions still apply.

## Equation disclosures

`pier_cap/equation_schematics.py` creates inline, accessible SVG diagrams for
report equations and the live/exported **Equation & values** disclosures.
The sketches illustrate the equation's concept and show current operands.
They cover gross-section cracking, strength, cracked-section service,
spacing, fatigue, shear windows, torsion, anchorage, clearance, face steel,
geometry and quantities. Pending equations show their concept without
adopting dormant load values. Drawings are conceptual, not construction details.

The report embeds these diagrams and its plotting library for offline use.
Its existing expand, collapse and print controls include the new disclosures.

## Verification

`tests/test_service_limits.py` checks the inverted boundaries against forward
evaluation of the original service equations, Service III stress conversion,
zero demand, applicability gates, bar extents, pile-gap treatment, step-boundary
hover and load-state visibility. `tests/test_equation_schematics.py` verifies
coverage, well-formed accessible SVG, current values, pending handling and
escaped user text. Existing force, calculation, report and widget tests remain
applicable. Refresh the portable package with
`python scripts/build_portable_notebook.py` after source changes.
