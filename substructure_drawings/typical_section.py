"""The superstructure typical section as one DXF sheet from the model cut.

Usage: see ``scripts/build_typical_section_dxf.py``.  The snapshot
(``freecad_typical_section_extract.py``) holds the slice wires of the deck,
the haunches, the two FIB-36 beams and the two deck barriers at mid-span 1,
looking ahead station.  Model space holds the section at full size (feet),
one 11 x 17 layout ("S-1 TYPICAL SECTION") shows it at 3/8" = 1'-0" with the
FDOT border; symbology, levels, lettering and the annotation rules follow the
substructure sheets (STYLE_GUIDE.md).

What the sheet shows is what the model holds: the pedestrian fence
enclosure over the walkway is not modelled, so it is not drawn and a MODEL
CHECK note says so.
"""
import hashlib
import json
import math
from collections import OrderedDict
from pathlib import Path

from . import build, cad, fdot
from .sheets import DRAW, Sheet
from .support import STATION_FFBW_EB1

GENERATOR_VERSION = "1.0.0"
DXF_NAME = "B4_Typical_Section.dxf"
MANIFEST_NAME = "typical_section_manifest.json"
SHEET_NUMBER = "S-1"
SHEET_TITLE = "TYPICAL SECTION"
SHEET_SCALE = "1/2"
ROLE_LEVELS = {"deck": "SupstrConc", "haunch": "BeamConc", "beam": "BeamConc", "barrier": "TrafBarrierConc",
               "unknown": "SupstrConc"}
IN = 1.0 / 12.0


def _crossings(pts, closed, u):
    """z values where the vertical line at ``u`` crosses the polyline."""
    out = []
    n = len(pts)
    m = n if closed else n - 1
    for i in range(m):
        a, b = pts[i], pts[(i + 1) % n]
        if (a[0] <= u <= b[0]) or (b[0] <= u <= a[0]):
            if abs(b[0] - a[0]) < 1e-12:
                out.extend([a[1], b[1]])
            else:
                out.append(a[1] + (b[1] - a[1]) * (u - a[0]) / (b[0] - a[0]))
    return out


class Section:
    """Derived geometry of the cut (local feet: u right, z up)."""

    def __init__(self, snap):
        self.data = snap
        objs = snap["objects"]
        self.by_role = OrderedDict()
        for n, o in objs.items():
            self.by_role.setdefault(o["role"], []).append((n, o))
        deck = self.by_role["deck"][0][1]["wires"][0]
        self.deck = deck
        us = [p[0] for p in deck["pts"]]
        self.u_min, self.u_max = min(us), max(us)
        self.u_pgl = snap["pgl_u_ft"]
        zs = _crossings(deck["pts"], deck["closed"], self.u_pgl)
        self.z_top_pgl, self.z_bot_pgl = max(zs), min(zs)
        # deck top at each edge: the highest crossing just inside the edge
        self.z_edge = {}
        for side, u in (("L", self.u_min + 0.02), ("R", self.u_max - 0.02)):
            self.z_edge[side] = max(_crossings(deck["pts"], deck["closed"], u))
        # beams: centre, top, bottom, left and right extents
        self.beams = []
        for n, o in self.by_role.get("beam", []):
            w = o["wires"][0]
            bu = [p[0] for p in w["pts"]]
            bz = [p[1] for p in w["pts"]]
            self.beams.append({"name": n, "u": (min(bu) + max(bu)) / 2, "u0": min(bu), "u1": max(bu),
                               "z_top": max(bz), "z_bot": min(bz), "label": o["label"]})
        self.beams.sort(key=lambda b: b["u"])
        # barriers: inner face (toward the PGL) and top
        self.barriers = []
        for n, o in self.by_role.get("barrier", []):
            w = o["wires"][0]
            bu = [p[0] for p in w["pts"]]
            bz = [p[1] for p in w["pts"]]
            uc = (min(bu) + max(bu)) / 2
            inner = max(bu) if uc < self.u_pgl else min(bu)
            outer = min(bu) if uc < self.u_pgl else max(bu)
            self.barriers.append({"name": n, "u": uc, "inner": inner, "outer": outer, "z_top": max(bz),
                                  "z_base": min(bz), "u0": min(bu), "u1": max(bu)})
        self.barriers.sort(key=lambda b: b["u"])
        self.z_bar_top = max(b["z_top"] for b in self.barriers) if self.barriers else self.z_top_pgl
        self.z_beam_bot = min(b["z_bot"] for b in self.beams) if self.beams else self.z_bot_pgl
        # crossfall from the PGL to the deck edge (top surface)
        self.crossfall = {}
        for side, u in (("L", self.u_min + 0.5), ("R", self.u_max - 0.5)):
            z = max(_crossings(deck["pts"], deck["closed"], u))
            self.crossfall[side] = (self.z_top_pgl - z) / abs(u - self.u_pgl)
        cut = snap["cut"]
        self.station = STATION_FFBW_EB1 + (cut["ffbw_eb1_y_ft"] - cut["y_ft"])
        # drip grooves: notches in the deck soffit (a soffit point above the soffit line between beams)
        soffit = [p for p in deck["pts"] if p[1] < self.z_bot_pgl + 0.05]
        self.grooves = []
        if soffit:
            zb = min(p[1] for p in soffit)
            notch = [p for p in deck["pts"] if zb + 0.005 < p[1] < zb + 0.1 and (p[0] < self.u_min + 1.0 or p[0] > self.u_max - 1.0)]
            for side, pick in (("L", min), ("R", max)):
                cand = [p for p in notch if (p[0] < self.u_pgl) == (side == "L")]
                if cand:
                    self.grooves.append((side, pick(cand, key=lambda p: p[1])))

    def snap(self, p, roles=None):
        """The nearest point on a drawn outline (of ``roles``, or any) to ``p``:
        every leader tip stands on a drawn line (STYLE_GUIDE A27)."""
        best, best_d = p, math.inf
        for role, items in self.by_role.items():
            if roles and role not in roles:
                continue
            for _n, o in items:
                for w in o["wires"]:
                    pts = w["pts"]
                    n = len(pts)
                    for i in range(n if w["closed"] else n - 1):
                        a, b = pts[i], pts[(i + 1) % n]
                        dx, dy = b[0] - a[0], b[1] - a[1]
                        L2 = dx * dx + dy * dy
                        t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
                        q = (a[0] + t * dx, a[1] + t * dy)
                        d = math.dist(p, q)
                        if d < best_d:
                            best, best_d = q, d
        return best

    def facts(self):
        return {
            "station": fdot.station(self.station), "station_ft": round(self.station, 4),
            "deck_out_to_out_ft": round(self.u_max - self.u_min, 6),
            "clear_between_barriers_ft": round(self.barriers[-1]["inner"] - self.barriers[0]["inner"], 6) if len(self.barriers) == 2 else None,
            "slab_thickness_at_pgl_ft": round(self.z_top_pgl - self.z_bot_pgl, 6),
            "deck_top_el_at_pgl": round(self.z_top_pgl, 6),
            "beam_spacing_ft": round(self.beams[-1]["u"] - self.beams[0]["u"], 6) if len(self.beams) == 2 else None,
            "beam_depth_ft": round(self.beams[0]["z_top"] - self.beams[0]["z_bot"], 6) if self.beams else None,
            "overhang_ft": {"L": round(self.beams[0]["u"] - self.u_min, 6), "R": round(self.u_max - self.beams[-1]["u"], 6)} if self.beams else None,
            "barrier_height_ft": round(self.barriers[0]["z_top"] - self.barriers[0]["z_base"], 6) if self.barriers else None,
            "barrier_width_ft": round(self.barriers[0]["u1"] - self.barriers[0]["u0"], 6) if self.barriers else None,
            "crossfall": {k: round(v, 5) for k, v in self.crossfall.items()},
            "drip_grooves": len(self.grooves),
        }


class SectionComposer:
    def __init__(self, snap, info=build.INFO):
        self.snap = snap
        self.sec = Section(snap)
        self.info = dict(info)
        self.info["stamp"] = ["%s  (%s %s)" % (DXF_NAME, "substructure_drawings.typical_section", GENERATOR_VERSION),
                              "FREECAD MODEL SHA-256 %s" % snap["model_sha256"][:16].upper()]
        self.doc = cad.new_document()
        self.warnings = []
        self.overlaps = []

    def build(self):
        s, snap = self.sec, self.snap
        sh = Sheet(self.doc, 0, SHEET_NUMBER, SHEET_TITLE, self.info)
        zone = sh.zone(DRAW, SHEET_SCALE)
        v = cad.View(self.doc, zone, "TYPICAL SECTION")
        th, k = v.th, v.sf * IN
        # --- the cut: closed outlines of the deck, haunches, beams and barriers
        for role, items in s.by_role.items():
            layer = ROLE_LEVELS.get(role, ROLE_LEVELS["unknown"])
            for _n, o in items:
                for w in o["wires"]:
                    v.pl([tuple(p) for p in w["pts"]], layer, closed=w["closed"])
        # --- dimension rows above: clear width between the barriers, out to out of the deck
        yt1 = s.z_bar_top + 0.35 * k
        yt2 = yt1 + 0.32 * k
        if len(s.barriers) == 2:
            bl, br = s.barriers
            clear = br["inner"] - bl["inner"]
            v.dim((bl["inner"], bl["z_top"]), (br["inner"], br["z_top"]), yt1 - bl["z_top"],
                  text="%s\\PCLEAR" % fdot.ft_in(clear))
        v.dim((s.u_min, s.z_edge["L"]), (s.u_max, s.z_edge["R"]), yt2 - s.z_edge["L"])
        # --- the row below the beams: overhang, beam spacing, overhang
        yb = s.z_beam_bot - 0.35 * k
        xs = [s.u_min] + [b["u"] for b in s.beams] + [s.u_max]
        for a, b in zip(xs, xs[1:]):
            v.dim((a, s.z_beam_bot), (b, s.z_beam_bot), yb - s.z_beam_bot)
        # beam centrelines (CL_Minor) through the beams, 0.25 in past the row and into the haunch
        for b in s.beams:
            v.line((b["u"], yb - 0.25 * k), (b["u"], b["z_top"] + 0.15 * k), "CL_Minor")
        # --- centreline of the bridge (CL_Major): through the deck and the
        # walkway, stopping short of the dimension rows whose symmetric
        # values it would otherwise cross (A1); labelled inside the walkway
        z_cl0 = s.z_bot_pgl - 0.12 * k
        z_cl1 = yt1 - 0.15 * k
        v.line((s.u_pgl, z_cl0), (s.u_pgl, z_cl1), "CL_Major")
        v.leader([(s.u_pgl, s.z_top_pgl + 0.62 * k), (s.u_pgl - 0.3 * k, s.z_top_pgl + 0.85 * k),
                  (s.u_pgl - 0.5 * k, s.z_top_pgl + 0.85 * k)], "BRIDGE & PGL", "right", cl=True)
        # --- vertical column at the right: barrier height and beam depth
        u_col = s.u_max + 1.65 * k     # (room for the HAUNCH callout between the deck edge and the column)
        if s.barriers:
            br = s.barriers[-1]
            v.dim((br["outer"], br["z_base"]), (br["outer"], br["z_top"]), -(u_col - br["outer"]), angle=90.0)
        if s.beams:
            b = s.beams[-1]
            v.dim((b["u1"], b["z_bot"]), (b["u1"], b["z_top"]), -(u_col - b["u1"]), angle=90.0)
        # --- callouts (every tip snapped onto the drawn outline, A27)
        if s.beams:
            b = s.beams[0]
            tip = s.snap((b["u0"], (b["z_top"] + b["z_bot"]) / 2), ("beam",))
            v.leader([tip, (s.u_min - 0.3 * k, b["z_bot"] - 0.22 * k), (s.u_min - 0.5 * k, b["z_bot"] - 0.22 * k)],
                     "FIB-36 (TYP.)", "right")
            br_ = s.beams[-1]
            tip = s.snap((br_["u1"], br_["z_top"] + 0.05), ("haunch",))
            v.leader([tip, (s.u_max + 0.25 * k, br_["z_top"] - 0.3 * k), (s.u_max + 0.45 * k, br_["z_top"] - 0.3 * k)],
                     "HAUNCH (TYP.)", "left")
        if s.barriers:
            bl = s.barriers[0]
            tip = s.snap((bl["outer"], (bl["z_top"] + bl["z_base"]) / 2), ("barrier",))
            v.leader([tip, (bl["outer"] - 0.35 * k, bl["z_top"] + 0.1 * k), (bl["outer"] - 0.55 * k, bl["z_top"] + 0.1 * k)],
                     "PEDESTRIAN BARRIER (TYP.)", "right")
        tip = s.snap((s.u_pgl - 0.1 * k, s.z_bot_pgl), ("deck",))
        v.leader([tip, (s.u_pgl - 0.55 * k, s.z_bot_pgl - 0.22 * k), (s.u_pgl - 0.4 * k, s.z_bot_pgl - 0.22 * k)],
                 "%s C.I.P. DECK" % fdot.ft_in(s.z_top_pgl - s.z_bot_pgl), "left")
        grooves = [g for g in s.grooves if g[0] == "L"] or s.grooves[:1]
        for side, p in grooves:
            sgn = -1.0 if side == "L" else 1.0
            tip = s.snap((p[0], p[1]), ("deck",))
            v.leader([tip, (p[0] + sgn * 0.3 * k, p[1] - 0.2 * k), (p[0] + sgn * 0.5 * k, p[1] - 0.2 * k)],
                     "DRIP GROOVE (TYP.)", "right" if side == "L" else "left")
        # --- crossfall arrows on the deck top, each side of the crown
        for side, sgn in (("L", -1.0), ("R", 1.0)):
            u0 = s.u_pgl + sgn * 0.45 * k
            u1 = s.u_pgl + sgn * 1.25 * k
            z0 = max(_crossings(s.deck["pts"], s.deck["closed"], u0)) + 0.12 * k
            z1 = max(_crossings(s.deck["pts"], s.deck["closed"], u1)) + 0.12 * k
            v.line((u0, z0), (u1, z1), "Symbols")
            v.arrowhead((u1, z1), (u0, z0), "Symbols")
            v.text(((u0 + u1) / 2, (z0 + z1) / 2 + 0.6 * th), "%.1f%%" % (100 * s.crossfall[side]), None, "BOTTOM_CENTER")
        # --- elevation of the PGL at the cut, to the right of the crown
        v.elev_callout((s.u_pgl, s.z_top_pgl), "PGL EL. %s" % fdot.elev(s.z_top_pgl), side=1, rise=0.42 * k)
        # --- title under the row
        v.title((s.u_pgl, yb - 0.75 * k), "TYPICAL SECTION", "(LOOKING AHEAD STATION)", subject_cx=s.u_pgl)
        # sheet: the section at the left of the window, the notes at the right
        pw = (v.local_bbox[2] - v.local_bbox[0]) / v.sf * 12.0
        v.place(v.local_bbox[0], v.local_bbox[3], DRAW[0] + 0.35, DRAW[3] - 0.25)
        comp = build.Composer.__new__(build.Composer)
        comp.warnings, comp.__dict__["placed"] = self.warnings, {}
        comp.check(sh, v)
        self.overlaps = comp.__dict__.get("annotation_overlaps", [])
        f = s.facts()
        notes = [
            "SECTION OF THE REGISTERED FREECAD MODEL (SHA-256 %s) CUT NORMAL TO THE STATIONING AT STA. %s "
            "(MID-SPAN 1), LOOKING AHEAD STATION; MODEL SPACE IS AT FULL SIZE IN FEET." % (snap["model_sha256"][:16].upper(), f["station"]),
            "THE FINISHED SUPERSTRUCTURE COMPONENTS OF THE MODEL ARE DRAWN AS CUT: THE DECK WITH ITS CHAMFERS AND "
            "DRIP GROOVES, THE HAUNCHES, THE TWO FIB-36 BEAMS AND THE PEDESTRIAN BARRIERS. DIMENSIONS ARE MEASURED "
            "ON THE MODEL AT THE CUT.",
            "THE DECK CROSSFALL IS %s EACH WAY FROM THE CROWN ON THE PGL; THE DECK TOP ON THE PGL AT THE CUT IS "
            "EL. %s." % (" / ".join("%.1f%%" % (100 * s.crossfall[k2]) for k2 in ("L", "R")), fdot.elev(s.z_top_pgl)),
            "MODEL CHECK: THE PEDESTRIAN FENCE ENCLOSURE OVER THE WALKWAY AND THE HANDRAILS ARE NOT IN THE MODEL AND "
            "ARE NOT SHOWN.",
            "NOT SHOWN: REINFORCEMENT, BEARINGS, PEDESTALS, CAPS AND MODEL SOURCES, CHECKS AND SCHEDULES.",
            "STATIONS ARE FROM FFBW END BENT 1 = %s (SELECTED GEOMETRY CAD TABLES, D-041)." % fdot.station(STATION_FFBW_EB1),
            "THIS SHEET IS GENERATED FOR REVIEW OF THE MODEL AND IS NOT A CONTRACT DRAWING.",
        ]
        xn = DRAW[0] + 0.35 + pw + 0.45
        wn = DRAW[2] - 0.1 - xn
        bottom = sh.notes_bottom(DRAW[3] - 0.2, notes, wn)
        sh.notes(xn, DRAW[3] - 0.2, "NOTES:", notes, width_in=wn)
        comp.check_block(sh, "notes", (xn, bottom, xn + wn, DRAW[3] - 0.2))
        sh.border()
        sh.group_zones()
        sh.add_viewports()
        if "Layout1" in self.doc.layouts:
            self.doc.layouts.delete("Layout1")
        build.dimension_blocks_by_level(self.doc)
        self.sheet, self.view, self.facts = sh, v, f
        return self.doc


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_outputs(snapshot_path, out_dir):
    import ezdxf
    keep = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    try:
        snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
        comp = SectionComposer(snap)
        doc = comp.build()
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        dxf_path = out_dir / DXF_NAME
        doc.classes.add_required_classes(doc.dxfversion)
        doc.classes.classes = OrderedDict(sorted(doc.classes.classes.items()))
        doc.saveas(dxf_path)
        flat_path = out_dir / build.flat_name(DXF_NAME)
        n_flat = build.write_flat(dxf_path, flat_path)
        layers = {}
        for e in doc.modelspace():
            layers[e.dxf.layer] = layers.get(e.dxf.layer, 0) + 1
        manifest = {
            "generator": "substructure_drawings.typical_section", "version": GENERATOR_VERSION,
            "dxf": DXF_NAME, "dxf_sha256": sha256(dxf_path),
            "dxf_flat": build.flat_name(DXF_NAME), "dxf_flat_sha256": sha256(flat_path), "dimensions_flattened": n_flat,
            "snapshot_sha256": sha256(snapshot_path), "model_sha256": snap["model_sha256"],
            "units": "US survey feet ($INSUNITS=21; the model's feet, for the DGN import); model space 1:1 in the section frame",
            "frame": snap["frame"], "cut": snap["cut"],
            "sheet": {"number": SHEET_NUMBER, "title": SHEET_TITLE, "layout": comp.sheet.layout.name,
                      "scale": fdot.scale_label(SHEET_SCALE)},
            "section": comp.facts,
            "objects_by_role": {r: [n for n, _ in items] for r, items in comp.sec.by_role.items()},
            "levels_used": dict(sorted(layers.items())),
            "level_source": fdot.LEVEL_TABLE,
            "cadd_manual": fdot.CADD_MANUAL,
            "symbology_audit": build.symbology_audit(doc),
            "layout_warnings": comp.warnings,
            "annotation_overlaps": comp.overlaps,
            "extraction_log": snap.get("log", []),
        }
        (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
        return dxf_path, manifest
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = keep
