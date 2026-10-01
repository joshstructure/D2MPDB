# Cap and pile design

The existing `Pier_Cap_Design_Optimizer.ipynb` now presents one **Cap and pile design explorer** for pier and end-bent caps supported directly on a single pile row. The cap-type selector labels the saved case. It does not generate end-bent loads or change the sectional calculation. Cap import retains its existing restrictions: uniform rectangular cap, straight horizontal global-X alignment, equally spaced round/square piles, and matching static FBMP 6.1.0 English-unit results. Backwalls, wingwalls, earth-pressure load generation, column/footing caps and strut-and-tie design remain outside the calculation.

## Workflow

1. Apply the normal cap XML preview. When complete pile data is available, the same file automatically populates **FBMP pile review**, above the reinforcement controls. **Review pile XML** also loads a foundation run independently of the cap importer. A visible source message distinguishes matching and different files, including changed cap geometry.
2. Review the pile-head matrix and governing compression, uplift, any-depth compression, model D/C and lateral displacement by exact limit state. The export preserves every tied governor and its concurrent force record.
3. Select a combination and pile for displacement, moment magnitude, axial, model D/C and elastic stress profiles. Auto selects the pile with the highest model D/C in that combination. Reported FBMP material stress extrema remain separate and identify the actual governing pile. Enter a project cutoff elevation to change the vertical plot from distance along the pile to project elevation.
4. Review the analyzed section, exported area/inertias, prestress and optional confirmed manual elastic properties. Model D/C and material stresses remain unchanged by an elastic-property override.
5. Paste the five minimum-tip trial columns or load a CSV/TSV. Evaluate the curves, select the engineering critical embedment and record its basis. Enter design ground/scour elevation and, when total length is needed, pile cutoff elevation. Choose fixed extension or the lesser of an extension and a penetration fraction. These are explicit project assumptions, not an automatic determination of the applicable design provision.
6. Enter optional nominal weight, pipe diameter, toe condition and project coordination notes in **Geotech handoff**. Download the pile review. Its ZIP contains `pile_review.json` for reuse, raw force/displacement tables, all governing records, reported and calculated stresses, the trial results, and an interactive HTML report. The ordinary cap export includes a separate pile-review folder. Keep both cap and pile JSON files when saving both workflows. Rerunning the workbench cell preserves the loaded pile review and its controls.

## Source mapping

The supplied spreadsheets are calculation references, not notebook instructions.

| Reference | Notebook replacement |
|---|---|
| `FBMP_Pile_Review (1).xlsx` — Pile Section; OUT Summary | XML pile section properties, section drawing, separate reported material extrema and native summary CSV |
| Pile Head Axial; Pile Head Matrix | All-pile/all-combination signed matrix, separate compression and uplift, governors and kip/short-ton export |
| Service Crack Check; Steel Review | Both element ends, actual station distance, elastic stress range and stress/Fy, model D/C, material stress extrema and tensile-curve peak when available |
| Min Tip Paste | Unlimited-length CSV/TSV/paste table, ordered trials, displacement/change/D/C plots, extension and tip calculations |
| Geotech Handoff | Section/EA, analyzed lengths, compression/uplift and selected trial result in the report; no inferred nominal resistance |
| `Pier Lateral Analysis-Graph.xlsx` — PP30_BB217R; Pier 2 | DX/DY versus project elevation; trial displacement and D/C plots; explicit cutoff/ground datums; engineering-selected critical embedment; optional whole-foot rounding |

The 25 trial rows extracted from **Min Tip Paste A15:E39** are available separately with the delivered notebook. They are reference study inputs, not automatically associated with `Pier_MinTip.XML`: the workbook's pasted OUT describes an 18-inch concrete end-bent model, while the available XML describes a 20-inch steel-pipe model.

## Calculation and data basis

- Required XML records: `PILE_GEOMETRY`, `PILE_GROUP/PILE_COORDINATES`, `PILE_DISPLACEMENTS`, `PILE_INTERNAL_FORCES`, load-combination definitions and complete static result records. One homogeneous section and one pile group are supported. Missing/duplicate stations, incorrect units, incomplete combinations and invalid connectivity stop import. XML entities are disabled.
- All original I/J force components remain in CSV. Axial tension is positive at I; J axial is reversed for a consistent section-force sign. Both ends stay separate at shared stations. Pile heads are the first I ends, not whichever station has maximum compression.
- Pile station distance follows the exported coordinates. FBMP Z increases downward in the reviewed export. Project elevation is `cutoff elevation − (Z − Z_head)/12`; no model Z coordinate is silently treated as a surveyed elevation.
- Elastic mean stress is `(P − Pp)/A`, in ksi. Rectangular/H symmetric-section bending uses `12 (|M2|/S2 + |M3|/S3)`. Circular bending uses `12 hypot(M2/S2, M3/S3)`. The maximum/minimum are mean ± bending. This reproduces the reference concrete method and circular-pipe biaxial method. Exported A and I are used because printed geometry can be rounded.
- Eccentric/grouped prestress, rotated, composite and unreviewed sections suppress the automatic homogeneous elastic screen. An explicit manual-property control provides a confirmed symmetric, concentric approximation; it does not run a composite/nonlinear section analysis.
- FBMP's model D/C is distinct from elastic stress/Fy. Pile 0 stress records identify absent materials and are omitted. The XML material extrema do not provide the OUT cracking-warning text or convergence report; those are labeled unavailable, not assumed to be NO or converged. No independent AASHTO pile-capacity or buckling check is added.
- A solved XML does not contain the shortened-pile trial sequence in the supplied references. The trial table remains separate. It accepts optional `series, dc, dx_in, dy_in, converged, iterations, tolerance_kip`; changing governing pile/combination across envelope trials is allowed. Separate independently analyzed series must be labeled. Missing convergence or D/C stays visible.
- Trials are sorted by embedment, so reversing pasted row order has no effect. Duplicate embedments within a series are rejected. The displacement-change candidate follows a continuous stable sequence from the deepest trial and stops at the first failed interval, nonconvergence or supplied D/C > 1. A later isolated flat pair cannot nominate an artificially shallow candidate. Variable trial spacing is flagged. An engineering-selected critical embedment and written basis are required before an adopted tip is calculated.
- Tip elevation uses the ground/scour datum minus required embedment; total length also uses the separate cutoff datum. Whole-foot tip rounding uses mathematical floor, including negative elevations. Length uses ceiling to the adopted rounded tip, keeping both reported quantities compatible when cutoff elevation has a fractional foot. This can add a foot compared with independently rounding length before tip. It also avoids Excel ROUNDDOWN's toward-zero behavior for negative tips.

The optional 5-ft/20% comparison comes from the supplied reference formulas; project applicability must be entered deliberately. The current manual is available from [FDOT Structures Manual](https://www.fdot.gov/Structures/StructuresManual/CurrentRelease). No edition-specific provision is automatically asserted by this tool. [BSI's product description](https://bsi.ce.ufl.edu/products/default.aspx/1000) describes the nonlinear analysis performed by FB-MultiPier; this notebook reviews exported results and does not replace that solver.

## Verification

Regression tests compare all 1,088 element-end records and 560 displacement records in the reviewed XML fixture against the source, check units/connectivity/missing data, retain uplift, and separate reported stresses from elastic calculations. Sixty concrete stress stations reproduce the supplied workbook's cached results. The 25 reference trials reproduce the 32.74-ft displacement-change candidate and, for an explicitly accepted 32.74-ft critical embedment with 5-ft extension and reference elevation 24.5 ft, the unrounded −13.24-ft tip. These reference calculations are separate from the steel XML run.

Run `python -m unittest tests.test_pile_review tests.test_pile_widgets -v` for focused checks. Existing cap mechanics, import, search and Colab widget tests remain applicable.
