# Cap width/depth and steel study

Open `Pier_Cap_Design_Optimizer.ipynb`, Run all, and use **Cap section and steel study**. The interactive study starts at widths 44, 48 and 52 in; depths 36, 42, 48, 54 and 60 in; and strength D/C ≤ 0.90. All bounds and increments are editable. These are exploration ranges, not approved project dimensions.

## Workflow

1. Confirm physical pile-head embedment and bar clearance under Geometry → Pile head. Set independent top, continuous bottom and ADDITIONAL span sizes and counts in the main workbench. The study uses those lists and its per-section case limit.
2. Select geometry ranges, additional project minimum dimensions, and a total candidate budget. The grid is limited to 225 sections and the budget to 500,000 evaluations per run. Rejected or untested sections remain visible.
3. Choose the force basis and run the study. Fixed-force sensitivity is the default. Analysis-matched mode requires a source case at each section; add actual analyzed case JSON files through the analysis-library uploader.
4. Change the strength D/C target to filter completed results. Each heatmap cell shows **concrete volume and steel weight together**. Hover for quantities, the concrete/steel/forms cost breakdown, and differences from the cheapest explored match. Use **Cell labels** to show component costs instead. Dense grids use hover labels to avoid overlapping text. Click any cell or plot point, or use the section dropdown.
5. Browse **all** matching cages in the cage selector. The selected cage's drawing, capacity plots, spacing breakdown and check register update together. The map still represents the lightest cage, and the selected-cage summary reports that selected cage's own weight and cost.
6. **Refine around this section** restricts the bounds to neighboring coarse points and halves the increments. Press Run again. Identical section/case/search calculations are reused from an in-memory cache; changing target or prices only changes the view. Changing main case inputs, steel choices or grid parameters clears the old view.
7. Load a selected case into the main calculator or export the study. Fixed-force selections retain the old analysis geometry. The main **Search steel layouts** button automatically continues width/depth trials with the current forces, labels their force basis, and supports applying and exporting layouts. An updated analysis is still needed for the final cap size to reflect changed self-weight and stiffness. Changes to pile layout or cap ends continue to require matching forces before searching.

## Force provenance

**Fixed-force sensitivity** holds every strength and service force constant while width/depth vary. It does not update self-weight, stiffness, load distribution, pile forces or concurrent action combinations. Only available sectional calculations and the trial cage screen are evaluated. It is a way to compare section response before obtaining new analysis, not a new verified analysis case.

**Analysis-matched cases** use loads and readiness flags from the supplied case at each section. The saved input geometry must agree with its analysis record. Pile layout, materials, covers and other non-reinforcement/non-force inputs must agree with the study. A supplied analysis at the starting section supersedes the automatic starting case; conflicting uploads at one section are rejected. Fixed-force study exports cannot masquerade as new analyses. Reimport actual workbook forces, or explicitly record a completed new analysis in the main calculator, to replace that provenance.

Geometry matching checks the declared case data; it does not independently prove the analysis model or the source of its forces. Whether forces may be reused for different reinforcing layouts depends on the analysis's stiffness assumptions. Automated FB-MultiPier execution and direct `.out` parsing are not implemented. Changes to the pile layout require new corresponding force inputs before either mode can proceed.

## Quantities, constraints and objective

The outer grid changes width and depth. Pile count, pile spacing, pile size, material strengths, covers, cap end allowances and force basis are frozen from the study's starting case. Cap length remains derived from pile geometry and adopted end allowances.

The transverse width screen is `pile width + 2 × (adopted actual clearance + pile-location tolerance)`, also respecting any larger entered project minimum. The starting inputs produce 44 in. The extra **longitudinal end allowance** (`E_detail`) affects cap length, not this side-clearance screen. For the supplied `Pier_MinTip.XML`, its 15.44 in end extension therefore does not require a 50.88 in cap width: the adopted side screen remains 44 in, or 48 in when the project minimum is set to 48 in. The live panel shows this calculation. This uses the existing project's adopted allowance, not a newly asserted universal FDOT rule. Enter other bearing/geometry requirements through the project minimums and review the actual detail. No new minimum depth rule is invented. If geometry limits exclude every section, the study explicitly reports that no steel candidates were evaluated.

The inner search uses independent top, continuous bottom and ADDITIONAL span sizes and counts, with one row per group and one outer hoop. Pile-region bars respect physical embedment, clear gap and existing placement allowance. Both positive cross sections appear in the selected-cage preview. Additional hoop topology, bearing/load introduction, anchorage, pile-head details, D-region applicability and other stated source-method limits are not completed by this study. All candidate checks remain active. The strength target covers the existing strength subset; remaining checks keep their original pass thresholds. Service III/fatigue remain pending until actual inputs and applicability are established.

Concrete is gross `width × depth × cap length`, reported in yd³. Form area includes both side faces, both ends and the soffit, with no top, falsework or pile deductions. Steel counts continuous bars once and adds span bars with the drawn 90-degree bends and tails. It excludes end anchorage, laps, hoop bends and waste. Hook development/cutoffs and pile-head hoop stationing remain pending. Optional comparison cost is:

```
concrete yd³ × concrete rate + gross steel lb × steel rate + form ft² × form rate
```

No market prices are supplied. Use consistent currency and an appropriate labor basis in your rates. A zero rate intentionally excludes that item. This is a comparison estimate rather than a takeoff or bid estimate. The concrete/steel Pareto frontier identifies points for which no explored point uses no more of either material and strictly less of one. It does not optimize formwork or construction effort. Partial searches produce an observed frontier only; even an exhaustive grid does not prove a global optimum outside its listed choices.

### Reading the cost view

Enable **Use my comparison unit rates** and enter rates. This switches the map to **Cost above cheapest (%)**: zero is the lowest estimated cost among explored target-matching cages. You can also color by total cost, steel, concrete or strength D/C. Cell labels independently show material quantities or concrete/steel/forms costs. A green cell outline marks the lowest cost; an amber dashed outline marks your selected section. The hover explains whether added concrete is offset by steel savings, including the quantity and cost differences from the cheapest section.

The cost summary identifies the lowest-cost section, its total and component shares, and the next higher cost. Any zero-rate items are explicitly listed as excluded. The stacked bar chart ranks up to ten leading sections by total concrete + steel + forms cost, plus your selection if it is outside those ten. **All sections ranked by estimated cost** retains the entire priced population, with amounts and percentages above the cheapest, strength D/C and search status. The section selector follows the same cost order. Click a bar or use **Select cheapest section + cage** to inspect its lightest matching cage; this does not apply it to the main calculator.

Changing rates or the strength target updates the view without running the search again. Your selected cage is preserved when it still meets the target. Its summary reports its own cost and premium above the cheapest explored section/cage. The map and ranking continue to use each section's lightest target-matching cage. The material-frontier graph remains in an expandable panel and is explicitly a quantity comparison, not a cost ranking. A partial study reports incomplete coverage; even a fully enumerated study does not imply a global or released design optimum.

## Outputs and reproducibility

Each new timestamped export includes:

- `sections.csv`: every geometry point, disposition/reason, target-match count, best matching cage, quantities, strength/all-check ratios, concrete/steel/forms and total costs if entered, cost rank and amount/percentage above the cheapest explored match, and observed material-frontier flag.
- `all_section_cages.csv`: every retained cage at every calculated section, including whether it meets the current target. IDs here are explicitly zero-based.
- `study.json`: the starting case, geometry and steel grids, limits, force mode, per-section analysis records/forces, target/rates, coverage and calculation-source hash.
- `analysis_requests.json`: geometry records to obtain or confirm in analysis; fixed-force mode lists all explored sections conservatively.
- `selected_case.json`: the chosen case when a cage is selected, including original force-source geometry and the study mode.

Original cases and project journals are not overwritten. Cache keys include the full case, steel search configuration, force mode and calculation-source hash. The cache lasts for the current notebook runtime; exports are review records and do not automatically resume a cached search.
