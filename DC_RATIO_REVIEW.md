# Review of the apparent 0.97 D/C floor

The floor comes from combining strength and detailing ratios into one maximum. It is reproduced by the original single-hoop geometry and the inherited transverse-spacing formula. This focused review does not establish that every engineering assumption in the source worksheet is adequate.

## Trace to the original worksheet

In `20. Cap Design.xmcd`, region 38551 (global) and region 41839 (low interval) define `S.w` using SDG 4.1.4.C. The low-stress branch returns 42 in. The notebook's `Sw_G` and `Sw_L` preserve that source branch. The source computes its stress from the factored shear divided by the resistance factor, web width and effective shear depth; this stress-basis assumption was not changed by this review.

The FDOT historical [Structures Design Bulletin 16-05, page 2](https://www.fdot.gov/docs/default-source/design/bulletins/SDB16-05.pdf) identifies 42 in as a **transverse stirrup-leg spacing** limit in its lowest stress range. It also shows smaller limits for higher stress ranges. This reference identifies the type of check; it is not a determination of the governing project code edition or a blanket approval of the source stress-basis assumption.

For the starting 48 in cap width, 3 in clear cover to the outside of the hoop and one #6 outer hoop:

```
Center-to-center distance between legs = 48 − 2(3) − 0.75 = 41.25 in
Across-cap spacing utilization        = 41.25 / 42       = 0.982142857
```

With #4 and #5 hoops the same ratios are 0.988095238 and 0.985119048. The default search considers only these three hoop sizes and a single outer hoop. That fixes its best possible all-check result at or above 0.982142857, even when strength ratios are much lower.

Each combined hoop-spacing register row reports:

```
max(along-cap hoop spacing / allowed along-cap spacing,
    across-cap leg spacing / allowed across-cap leg spacing)
```

Changing longitudinal bar counts or placing successive hoops closer together does not change the across-cap leg distance. A different transverse cage arrangement would need an explicit geometry/detailing model; multiple-loop topology remains outside the automatic search.

## Reproduced results with the supplied starting case

| Target | All available checks | Strength checks only |
|---|---:|---:|
| ≤ 0.97 | 0 | 306 |
| ≤ 0.90 | 0 | 210 |

All 1,944 default combinations were evaluated; 324 passed the available checks and trial cage screen. The lowest strength D/C is approximately 0.547069 for 8 #9 top bars, 8 #9 bottom bars, #6 hoops at 6 in and 7 #5 skin bars per side. Its all-check maximum remains 0.982143, from transverse leg spacing. This is an illustration of the distinction, not a recommendation of that heavier cage.

The starting cage's strength D/C is 0.831656 and its all-check utilization is 0.985119. The strength maximum covers flexure, shear/section bound, combined shear/torsion steel and longitudinal steel. Its individual components are documented in the register; it is not a universal multiplier for how much all loads may be increased. All other available checks retain their original requirements, and Service III/fatigue remain pending.

## Notebook corrections

The workbench now defaults to the strength target, shows separate strength and all-check summary values, displays both match counts at the selected target, and provides a live table for the two spacing directions. The detailed register and all-check filter remain available. The calculation equations, source loads, candidate eligibility, and Python API's existing default all-check scope are unchanged.
