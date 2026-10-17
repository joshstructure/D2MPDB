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
Each sketch illustrates the equation's concept and lists up to eight current
operands, or a check's recorded demand/limit components when the check has no
formula operands. Concept families (the `data-concept` attribute) are: beam
(cap length from pile spacing, pile width, tolerance and end extensions);
section (bar areas, row coordinates with cover, hoop and s_row, centroid dc and
effective depth d); flexure (stress block a, C = α1 fc a b, T = As fy, neutral
axis c = a/β1); gross (M·yt/Ig cracking, Ig = b h³/12); strain (linear profile
scaled from the current c); cracked (transformed n·As section, ccr, fc and
fs/fo stresses); spacing (crack-control s ≤ 700γe/(βs fs) − 2dc, with a
pile-region variant showing Pile_left, Pile_right, P_center_gap, P_side_span
and C_pile); legs (transverse leg spacing S_leg ≤ Sw across the cap width);
shear (inclined field, dv, pitch s and the dv·cotθ window, with an
end-distance variant for the end-coverage check); torsion (closed shear-flow
path, Ag/Pcp or Aoh/ph/Ao); longitudinal (M/(φ dv) + axial + shear/torsion
tension with dv); fatigue; development (anchorage length, with a hook variant
showing hook height, bend diameter and 12db tail); clearance (centre spacing,
clear gap, cover, with a layer-alignment variant); face (skin steel over d/2
and s ≤ min(d/6, 12 in), with shrinkage rates per face); quantity and gate.
Pending equations show their concept without adopting dormant load values.
Drawings are conceptual, not construction details.

The report embeds these diagrams and its plotting library for offline use.
Its existing expand, collapse and print controls include the new disclosures.

## Verification

`tests/test_service_limits.py` checks the inverted boundaries against forward
evaluation of the original service equations, Service III stress conversion,
zero demand, applicability gates, bar extents, pile-gap treatment, step-boundary
hover and load-state visibility. `tests/test_equation_schematics.py` verifies
coverage, family routing, well-formed accessible SVG, parameter labels, current
values, component operands, the hook and pile variants, pending handling and
escaped user text. Existing force, calculation, report and widget tests remain
applicable. Refresh the portable package with
`python scripts/build_portable_notebook.py` after source changes.
