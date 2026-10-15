# Landing quantity correction - D-034

The two finished landing solids are valid. FreeCAD's default mass-property
integration gives inconsistent totals for their trimmed spline faces. D-034
changes only quantity reporting; the source geometry and all display resources
remain byte-identical to D-033.

Use **NetVolume** on `A_BridgeLandingAtReturns` and
`B_BridgeLandingAtReturns`. `VolumeStatus` must be **Verified**. Their existing
native controller recalculates this value whenever it rebuilds a landing. A
failed calculation raises an error and leaves the status **Needs review**.
The built-in `Shape.Volume` is not overridden and remains unsuitable for these
two solids. Other objects and quantity consumers are unchanged.

The calculation uses the installed OCCT Gauss-Kronrod routine, with spline-span
integration and a horizontal reference plane at the solid's minimum elevation.
The engine requests 1e-12 then 1e-14 relative precision. Required reported errors
are at most 1e-8 and 1e-10; successive totals must agree within 1e-9 relative
(with a 0.001 mm3 absolute floor). No volume is hard-coded.

The independent checks retain these acceptance limits:

- Original slab plus added concrete agrees with the finished slab within 1e-8
  of its total volume; no original material is lost.
- Mesh-based signed tetrahedral volumes at 0.025, 0.0125 and 0.00625 mm deflection
  agree within 1e-6 relative. Coordinates are centered before summing.
- Translated box and cylinder quantities agree with analytic volumes within
  1e-9 relative. Open faces are rejected.
- Native rebuilds have zero bidirectional concrete difference and preserve
  face-color values. The bounded source archive preserves every geometry and
  GUI resource, every unrelated object, and all expressions/links.

Earlier diagnostics are retained: ordinary adaptive integration did not
converge reliably, point-based Gauss-Kronrod failed A's additivity check, and
over-refining the display mesh produced an erroneous A volume at 0.00078125 mm.
Those methods are not used as the authoritative quantity calculation. The
vertical-plane formulation passes the original acceptance limits.

See `verification.json` for the full numerical results, `native-preservation.json`
for the bounded archive comparison, and `cold-reopen.json` for saved quantities.
Native rebuild evidence is in `native-rebuild.json`. Existing clashes and
engineering reconciliation issues remain under their existing tracker IDs.

Implementation references: [FreeCAD mass-property call](https://raw.githubusercontent.com/FreeCAD/FreeCAD/1.1.0/src/Mod/Part/App/TopoShapePyImp.cpp)
and [OCCT volume integration API](https://occt3d.com/dev/doc/refman/html/class_b_rep_g_prop.html).
Actual results were obtained with the locally installed OCCT 7.8.1 runtime.
