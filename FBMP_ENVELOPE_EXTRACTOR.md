# Standalone FBMP envelope extractor

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/FBMP_Envelope_Extractor.ipynb)

1. Open the notebook with the Colab badge after pushing it to GitHub's `main` branch.
2. Select **Runtime → Run all**. A standard CPU runtime is sufficient.
3. Choose an analyzed FB-MultiPier `.xml` file when prompted.
4. Read the **Strength** and **Service** tables displayed in the notebook, then download either table as CSV or the complete results ZIP.

All extraction and interface code is embedded in [FBMP_Envelope_Extractor.ipynb](FBMP_Envelope_Extractor.ipynb). It uses the standard pandas, ipywidgets, and matplotlib packages available in Colab. It does not require the pier-cap design notebook or its supporting package. Uploaded files and generated downloads are stored in the temporary Colab runtime; download results before ending the session.

## Results

The notebook displays **Strength** and **Service** tables automatically after upload, covering moment M2/M3, shear V2/V3, and torsion T for each exported member and exact limit state. Each row includes signed minimum/maximum, maximum absolute magnitude, units, and governing cases/combinations. These tables are calculated from the detailed XML element-end forces. Service I, II, III, etc. stay separate when exported; no Service result is inferred from Strength. In the supplied `Pier_MinTip.XML`, **Service I is load case 11, combination 4**.

For a single uploaded file, the tables are ordinary notebook cell output, displayed before the interactive explorer. They do not require clicking a download button or opening a widget tab.

The **Original FBMP summary** tab extracts the XML's `OUTPUT_SUMMARY`, an all-case envelope whose governing rows may all be Strength cases. It is kept separate from the limit-state tables because its force signs and member scope can differ. The absence of Service governors in that overall summary does not imply that Service case results are absent.

The **Element-end explorer** computes envelopes from the original XML I/J-end forces for the selected substructure, member, limit state, and cases. It preserves element/node/time-step IDs, concurrent forces, and ties. Its filters do not change the original FBMP summary.

Each component is enveloped independently. Separate maxima need not occur together. Missing values remain blank; units and original signs are preserved. The tool does not apply sign transformations, load factors, unit conversions, or new structural analysis. Plots use ordered element IDs rather than physical distances, and no interior peaks between exported ends are inferred.

The **Download Strength CSV** and **Download Service CSV** buttons export exactly the corresponding displayed table rows, with additional governing locations and ties. The ZIP includes these as `strength_envelopes.csv` and `service_envelopes.csv`, plus `limit_state_envelope_table.csv`, the native summary, detailed envelopes, member envelopes by limit state, raw forces, selected records, case coverage, source comparisons, and file provenance. Multiple uploaded files are processed independently.

## Discrepancies found in the supplied example

The reviewed `Pier_MinTip.XML` contains different maximum magnitudes in its pier-cap summary and detailed force block:

| Component | Reported summary | All exported element ends |
|---|---:|---:|
| M2 | 12.51 kip-ft | 129.44 kip-ft |
| V3 | 4.63 kip | 6.54 kip |

The tool preserves both sources and flags these differences without inferring a correction. Original I/J-end envelopes are not presented as a reproduction of FBMP's design-sign envelopes. BSI discusses design-table sign adjustments in its [Fall 2017 newsletter, page 10](https://bsi.ce.ufl.edu/newsletter/BSI-Newsletter-Fall-2017.pdf).

## Verification

The supplied FBMP 6.1.0 XML contained 4 analyzed case/combination records, 190 exported elements, 1,520 element-end records, and 20 native summary extrema for the five requested components. All 18 extraction checks passed, including an independent value-by-value source comparison, every detailed governor, concurrent values, ties, missing components, mixed units, multiple substructures/time steps, and invalid files.

The notebook's actual cells were executed in a fresh local notebook kernel. Upload/download actions were simulated; all controls and download buttons, summary-only files, invalid files, and switching between files passed. Live execution in Google's hosted Colab service was not performed.

The Strength/Service update passed 8 additional checks in `tests/test_fbmp_envelope_notebook.py`, covering exact limit-state separation, Service values when the native summary is governed by Strength, table/CSV agreement, and absent Service results. A full local notebook run verified all 5 download buttons and that the Service tables appear as ordinary cell output. The supplied file produces 25 Service I table rows: all 5 components for the pier cap and each of 4 piles.

The Colab badge targets `joshstructure/D2MPDB`, branch `main`. Update the badge if publishing the notebook under a different repository or branch.
