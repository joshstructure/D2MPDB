# Signed cap axial force and concurrent LRFD calculation

This update applies to the shared `pier_cap` package used by both
`Pier_Cap_Design_Optimizer.ipynb` and the embedded-package
`Cap_and_Pile_Design.ipynb`. The fixed-depth cap source and minimum-tip/pile
source remain separate. It does not modify the analysis, force factors,
geometry, reinforcement, or original Blockpad journal.

## Governing material inspected

The supplied **AASHTO LRFD Bridge Design Specifications, 10th Edition, 2024,
Bookmarked** PDF was read directly: printed 5-65/66 (minimum transverse steel),
5-71/72 (nominal resistance), 5-73 through 5-79 (both parameter procedures and
longitudinal steel), and 5-80/81 (torsion). Figures 5.7.3.4.2-1/-2/-3 and
C5.7.3.4.2-1/-2/-3/-4 were rendered and inspected. Printed 5-22, Article
5.4.2.7 and commentary, supplies the estimated concrete tensile threshold.
The [September 2025 errata](https://store.transportation.org/Common/DownloadContentFiles?id=2562)
does not amend these shear-parameter pages.

The January 2026 FDOT Structures Manual was inspected at SDG 4.1.4A-C,
printed 4-2 (combined PDF page 189). Actual twin legs inside a centered
`dv*cot(theta)` window determine stirrup contribution; open U-bars have no
closed torsion-path credit. The [official FDOT release](https://www.fdot.gov/Structures/StructuresManual/CurrentRelease)
identifies the edition. Project adoption and approved variations still govern.

## Axial import and saved cases

For the supported FBMP 6.1.0 static English-unit, straight horizontal,
increasing-global-X cap chain, **positive Nu is tension**:

```
Nu_I = -raw_AXIAL_I
Nu_J = +raw_AXIAL_J
```

Raw axial values, signed values, I/J/node/member IDs, coordinates, combination,
limit state, units, source SHA256, and convention/schema version remain in the
audit. Both signed axial extrema must match `STRUCTURE_PIER_CAP_MAX`.
Opposite raw end forces must balance within 0.010000001 kip (two independently
rounded 0.01-kip outputs). This is an import consistency tolerance, **not** an
allowable tensile demand. Numerical zero is separately 1e-10 kip; genuine
positive force above that roundoff floor disallows the ordinary simplified route.
Missing data, unsupported XML, units, axes, connectivity and failed equilibrium
stop import. No cap sign transformation is applied to pile data.

New signed cases carry LRFD settings version 3 so earlier notebooks reject
them instead of applying the obsolete absolute-axial calculation. Current
settings versions 1/2 still migrate without changing detailing choices.
Unversioned legacy `axial` fields remain intact and **unresolved**: reimport
the original solved fixed-depth XML. The importer accepts the saved case as its
base, preserving steel, cover, factors and detailing. Explicit raw-end provenance
can migrate once; it still must pass the independent signed summary checks.
Repeated loading cannot reverse signs again. Saved derived results are not
accepted as fresh calculations.

## Two separate decisions

1. **Simplified eligibility (5.7.3.4.1):** nonprestressed, no net axial tension,
   and at least minimum transverse steel or overall depth below 16 in. No
   footing exception is inferred. Its beta is 2, theta is 45 degrees, cotangent
   is 1, and epsilon is **not required**. A separately labeled diagnostic base
   strain is retained.
2. **Compression-face cracking (5.7.3.4.2):** positive Nu alone does not double
   strain. The implementation adopts the commentary's idealized axial flanges,
   with the concrete half areas and actual developed reinforcement, and tests
   the flexural compression flange against a finite tensile threshold.

For a nonprestressed rectangle, the compression-half flange resultant is
`Fc = -abs(Mactual)/dv + Nu/2 + Veff`. This is C5.7.3.4.2 Figure 3's flange
equilibrium, using the commentary's `0.5*cot(theta) = 1` simplification; with
investigated solid-section torsion the shear contribution uses Eq. 5's Veff.
The precracking flange concrete stress is
`fc,flange = Fc / (Ac,net + Es/Ec*As,compression,developed)`.
Steel and net concrete share the axial flange force at equal strain up to
first cracking, consistent with Figure 4's flange-stiffness model. The estimate
`fct = 0.213*lambda*sqrt(fc')` ksi is from **C5.4.2.7**, not the flexural modulus
of rupture. The multiplier is 2 only when Nu is positive and this stress reaches
fct. The trace includes force, areas, moduli, stress, threshold and comparison.

This is an explicitly adopted **commentary flange implementation**, not a
claim to perform a full nonlinear plane-section/MCFT analysis. It assumes
elastic flange materials up to first cracking and uses the code estimate of
splitting tensile strength; prior cracking, restrained shrinkage, special
material tensile-test data and nonrectangular/prestressed sections are outside
this model. Missing compression-half reinforcement information is a specific
unresolved prerequisite. Yield stress or tension-steel strain is not the trigger.

## Calculated strain and resistance

Use inches, kips and ksi; convert imported moments/torques from kip-ft once.
For the nonprestressed section:

```
M_for_epsilon = max(abs(Mactual), abs(Vu)*dv)
epsilon_base = (M_for_epsilon/dv + 0.5*Nu + Veff)/(Es*As_effective)
epsilon_s = max(0, epsilon_base) * cracking_multiplier
beta = 4.8/(1 + 750*epsilon_s)                  [minimum transverse steel]
theta_deg = 29 + 3500*epsilon_s
cot_theta = 1/tan(theta_deg*pi/180)
```

Without investigated torsion, Veff is abs(Vu). With investigated torsion,
Eq. 5.7.3.4.2-5 gives `sqrt(Vu^2 + (0.9*ph*Tu/(2*Ao))^2)` for a solid section.
The instruction replaces Vu in Eq. 4's shear term; the separately printed Mu
definition retains its `abs(Vu-Vp)*dv` floor, with Vp=0 here. Actual moment,
not this artificial minimum, enters the compression-flange and longitudinal
checks. Neither demand factoring nor resistance factors are inserted into
the strain equation.

As_effective includes only the relevant flexural tension half, with proportional
reduction for incomplete development as explicitly permitted by 5.7.3.4.2 and
C5.7.3.5. Negative base strain uses the permitted zero option (no compression
concrete credit is required). Strain is never clipped to 0.006: outside that
range there is no adopted resistance and the prerequisite remains unresolved.

Below minimum transverse reinforcement, beta also includes `51/(39+sxe)`.
Eligible developed longitudinal layers must each supply `0.003*b*sx`;
insufficient layers are removed to a stable set. `sx` is the lesser of dv and
the maximum retained layer gap. Terminal gaps extend conservatively to the
concrete faces instead of inferring an optimistic compression-zone boundary.
`sxe = clamp(1.38*sx/(ag+0.63), 12, 80)` in. Aggregate size must be confirmed
before that branch can be accepted. A diagnostic calculation using the entered
aggregate size is labeled pending, not a code exemption from minimum steel.

## Concurrent locations, windows and longitudinal tension

The authoritative calculation is `shear.parameters` plus `section_search.section`.
Imported M is recovered by the verified member quadratic; V, signed N and
sectional torsion are interpolated within that same member and combination.
Both ends of every member are independently investigated, including both sides
of jumps. Moment zeros/extrema and bar cutoff/development transitions split
the search domain. Forces and minimum steel from different locations are never
assembled into a synthetic governing state.

The general-procedure angle is independent of the minimum-steel beta branch.
The solver first checks simplified eligibility with the actual 45-degree window.
If that is unavailable, it computes the general angle, counts the resulting
actual legs, and chooses the minimum/no-minimum beta branch using that same
window. This explicit branch solution avoids oscillation and stale one-pass
classification; the general procedure is allowed even if its final window
would also meet the minimum-steel condition.
Minimum-steel eligibility conservatively requires both the adjacent-interval
nominal Av/s and the intersected-window rate to meet the minimum. A locally
dense window therefore cannot override a sparse adjacent interval.

Within each smooth input interval, the search starts at at most 0.5 in spacing,
refines at least twice (at most 0.125 in), requires two successive relative
D/C-envelope agreements within 0.0002, and resolves changing window/branch
events to 0.000001 in. Local interior peaks are polished within brackets.
Separate objectives include shear, longitudinal, torsion, minimum steel and
minimum resistance. The trace retains each objective's controller, endpoints,
branch representatives and event sides, with counts and convergence metadata.
Nonconvergence is pending. Regression testing compares an interior controller
against an independent 0.01-in scan. This is numerical convergence evidence,
not a mathematical proof for arbitrary unsupported force functions.

The same theta controls Vc/Vs, crack length, actual intersected legs and
5.7.3.5 longitudinal demand. Only developed transverse steel may reduce that
demand, with Vs credit capped at Vu/phi_v. Signed axial and the article's
resistance factors remain explicit. Combined torsion uses 5.7.3.6.3-1.
The 5.7.2.1 torsion-investigation threshold also uses the signed force:
`K = sqrt(max(0, 1 - Nu/(Ag*0.126*lambda*sqrt(fc'))))`. Verified compression
increases the threshold; tension reduces it. Plots use the controlling
threshold from the same source combinations instead of a zero-axial screen.
The direct-load exception keeps its load-path, splice, continuous-main-steel
and anchorage gates. Its extension check deliberately retains the conservative
maximum `dv*cot(29 degrees)` over the supported nonnegative-strain angle range;
this is a sufficient eligibility bound, not a fixed longitudinal design angle.

Uniform optimizer trials use this same solver and preserve the XML audit.
Their explicit reference placement starts at cover plus half the stirrup
diameter and uses the larger G/L pitch because G/L extents are not supplied.
This placement remains conditional until an actual schedule is entered; it
does not overwrite the case or its cage. Fast and detailed evaluations use
the same actions and calculation. Legacy cases with scalar envelopes only
retain archival C005 screens and an unresolved concurrent-axial-source status;
they cannot establish final acceptance. Actual schedules without a usable
source show only explicitly unresolved scalar diagnostics.

## Refresh and use

**Colab:** save the current notebook state/JSON first. Upload the delivered
`Cap_and_Pile_Design.ipynb` using File > Upload notebook. Restart the runtime,
reload the page, and Run all. This notebook embeds the updated package and
does not require a GitHub publication. Load notebook/case JSON, then reimport
the original solved **Fixed-depth cap XML** and Apply if axial status is
unresolved. Review the source receipt and LRFD station trace, rerun searches,
and export a fresh report. Loading the cap XML preserves the separate
minimum-tip XML, trials and reaction margin.

**Windows / local Jupyter:** keep the delivered notebook, `pier_cap`, `scripts`
and requirements files together. Open PowerShell in that folder. With the
project's existing Python environment, use:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\build_portable_notebook.py
.\.venv\Scripts\python.exe -m jupyter lab Pier_Cap_Design_Optimizer.ipynb
```

A fresh environment can install `requirements-pier-cap.txt`; pandas is also
needed by the unrelated bridge-geometry notebook tests. The repository-backed
notebook uses adjacent files locally; its Colab GitHub setup requires these
changes to be published first. Use the delivered portable notebook until then.
Do not use `--preserve-outputs` when building this update. Search caches include
the shared engine files, and package reload discards the bounded calculation
cache. Existing saved figures are not recalculated merely by opening a file.
Imported-source optimization now performs a converged station search for each
trial cage. Large candidate populations can take substantially longer than the
former independent-envelope screens; use the existing candidate budget to
bound an exploratory run, then review whether the search was exhaustive.

## Remaining project prerequisites

Existing end-cover zones, D-regions, pile/bearing load paths, actual closure,
splices, added-bar cutoff/extension details, torsion reinforcement distribution,
weak-axis/combined axial-biaxial flexure, service/fatigue inputs and analysis
compatibility remain separate checks. This update does not convert those
pending items into passes. The comparison supplied with the package uses the
identified saved XML fixture, not an independently running live Colab session.
