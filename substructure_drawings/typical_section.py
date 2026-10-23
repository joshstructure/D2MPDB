"""The superstructure typical section and the section at the pier as one
DXF sheet from the model cuts.

Usage: see ``scripts/build_typical_section_dxf.py``.  The snapshot
(``freecad_typical_section_extract.py``, schema 2) holds the slice wires of
two cuts normal to the stationing, looking ahead station: ``typical`` at
mid-span 1 (deck, haunches, the two FIB-36 beams, the deck barriers) and
``pier`` at the Span 1 bearing line at the pier (the same superstructure on
its pads and pedestals, the pier cap and the pier wall).  Model space holds
both views at full size (feet); one 11 x 17 layout ("S-1 TYPICAL SECTION")
shows them side by side at 3/8" = 1'-0" with the FDOT border; symbology,
levels, lettering and the annotation rules follow the substructure sheets
(STYLE_GUIDE.md).

What the sheet shows is what the model holds: the pedestrian fence
enclosure over the walkway is not modelled, so it is not drawn and a MODEL
CHECK note says so; the pier cheek walls, piles and ring plates lie beyond
the pier cut and are not drawn either.
"""
import hashlib
import json
import math
from collections import OrderedDict
from pathlib import Path

from . import build, cad, fdot
from .sheets import DRAW, Sheet
from .support import STATION_FFBW_EB1

GENERATOR_VERSION = "1.1.0"
DXF_NAME = "B4_Typical_Section.dxf"
MANIFEST_NAME = "typical_section_manifest.json"
SHEET_NUMBER = "S-1"
SHEET_TITLE = "TYPICAL SECTION"
SHEET_SCALE = "3/8"       # the typical section
PIER_SCALE = "1/4"        # the section at the pier (the 19'-2" cap with its callouts does not fit beside the typical section at 3/8")
ROLE_LEVELS = {"deck": "SupstrConc", "haunch": "BeamConc", "beam": "BeamConc", "barrier": "TrafBarrierConc",
               "pad": "BearingPadMisc", "pedestal": "SubStrConc2", "cap": "SubStrConc", "pier_wall": "SubStrConc",
               "unknown": "SupstrConc"}
IN = 1.0 / 12.0
WALL_STUB_FT = 0.8        # the pier wall drawn this far below the cap, then a break line (as the pier elevation's cheek stubs)
VIEW_GAP_IN = 0.3         # between the two views on the sheet (the pier section under the typical section)


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


def _extent(wires):
    us = [p[0] for w in wires for p in w["pts"]]
    zs = [p[1] for w in wires for p in w["pts"]]
    return min(us), min(zs), max(us), max(zs)


class Cut:
    """Derived geometry of one cut (local feet: u right, z up)."""

    def __init__(self, snap, key):
        self.key = key
        sec = snap["sections"][key]
        self.y_ft, self.where = sec["y_ft"], sec["where"]
        self.by_role = OrderedDict()
        for n, o in sec["objects"].items():
            self.by_role.setdefault(o["role"], []).append((n, o))
        self.u_pgl = snap["pgl_u_ft"]
        self.station = STATION_FFBW_EB1 + (snap["ffbw_eb1_y_ft"] - self.y_ft)
        deck = self.by_role["deck"][0][1]["wires"][0]
        self.deck = deck
        us = [p[0] for p in deck["pts"]]
        self.u_min, self.u_max = min(us), max(us)
        zs = _crossings(deck["pts"], deck["closed"], self.u_pgl)
        self.z_top_pgl, self.z_bot_pgl = max(zs), min(zs)
        # deck top at each edge: the highest crossing just inside the edge
        self.z_edge = {}
        for side, u in (("L", self.u_min + 0.02), ("R", self.u_max - 0.02)):
            self.z_edge[side] = max(_crossings(deck["pts"], deck["closed"], u))
        # beams: centre, top, bottom, left and right extents
        self.beams = []
        for n, o in self.by_role.get("beam", []):
            u0, z0, u1, z1 = _extent(o["wires"])
            self.beams.append({"name": n, "u": (u0 + u1) / 2, "u0": u0, "u1": u1, "z_top": z1, "z_bot": z0})
        self.beams.sort(key=lambda b: b["u"])
        # barriers: inner face (toward the PGL) and top
        self.barriers = []
        for n, o in self.by_role.get("barrier", []):
            u0, z0, u1, z1 = _extent(o["wires"])
            uc = (u0 + u1) / 2
            inner, outer = (u1, u0) if uc < self.u_pgl else (u0, u1)
            self.barriers.append({"name": n, "u": uc, "inner": inner, "outer": outer, "z_top": z1, "z_base": z0,
                                  "u0": u0, "u1": u1})
        self.barriers.sort(key=lambda b: b["u"])
        self.z_bar_top = max(b["z_top"] for b in self.barriers) if self.barriers else self.z_top_pgl
        self.z_beam_bot = min(b["z_bot"] for b in self.beams) if self.beams else self.z_bot_pgl
        # crossfall from the PGL to the deck edge (top surface)
        self.crossfall = {}
        for side, u in (("L", self.u_min + 0.5), ("R", self.u_max - 0.5)):
            z = max(_crossings(deck["pts"], deck["closed"], u))
            self.crossfall[side] = (self.z_top_pgl - z) / abs(u - self.u_pgl)
        # drip grooves: notches in the deck soffit near the edges
        soffit = [p for p in deck["pts"] if p[1] < self.z_bot_pgl + 0.05]
        self.grooves = []
        if soffit:
            zb = min(p[1] for p in soffit)
            notch = [p for p in deck["pts"] if zb + 0.005 < p[1] < zb + 0.1 and (p[0] < self.u_min + 1.0 or p[0] > self.u_max - 1.0)]
            for side, pick in (("L", min), ("R", max)):
                cand = [p for p in notch if (p[0] < self.u_pgl) == (side == "L")]
                if cand:
                    self.grooves.append((side, pick(cand, key=lambda p: p[1])))
        # substructure (the pier cut): cap, pedestals, pads, pier wall
        self.cap = self.pedestals = self.pads = self.wall = None
        if "cap" in self.by_role:
            u0, z0, u1, z1 = _extent(self.by_role["cap"][0][1]["wires"])
            self.cap = {"u0": u0, "u1": u1, "z_top": z1, "z_bot": z0}
        if "pedestal" in self.by_role:
            self.pedestals = []
            for n, o in self.by_role["pedestal"]:
                u0, z0, u1, z1 = _extent(o["wires"])
                self.pedestals.append({"name": n, "u0": u0, "u1": u1, "z_top": z1, "z_bot": z0, "u": (u0 + u1) / 2})
            self.pedestals.sort(key=lambda p: p["u"])
        if "pad" in self.by_role:
            self.pads = []
            for n, o in self.by_role["pad"]:
                u0, z0, u1, z1 = _extent(o["wires"])
                self.pads.append({"name": n, "u0": u0, "u1": u1, "z_top": z1, "z_bot": z0, "u": (u0 + u1) / 2})
            self.pads.sort(key=lambda p: p["u"])
        if "pier_wall" in self.by_role:
            u0, z0, u1, z1 = _extent(self.by_role["pier_wall"][0][1]["wires"])
            self.wall = {"u0": u0, "u1": u1, "z_top": z1, "z_bot": z0}

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
        f = {
            "station": fdot.station(self.station), "station_ft": round(self.station, 4), "where": self.where,
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
        if self.cap:
            f.update({"cap_length_ft": round(self.cap["u1"] - self.cap["u0"], 6), "cap_depth_ft": round(self.cap["z_top"] - self.cap["z_bot"], 6),
                      "cap_top_el": round(self.cap["z_top"], 6)})
        if self.pedestals:
            f["pedestal_height_ft"] = {p["name"]: round(p["z_top"] - p["z_bot"], 6) for p in self.pedestals}
            f["pedestal_top_el"] = {p["name"]: round(p["z_top"], 6) for p in self.pedestals}
        if self.pads:
            f["pad_thickness_ft"] = round(self.pads[0]["z_top"] - self.pads[0]["z_bot"], 6)
            f["pad_width_ft"] = round(self.pads[0]["u1"] - self.pads[0]["u0"], 6)
        if self.wall:
            f["pier_wall_length_ft"] = round(self.wall["u1"] - self.wall["u0"], 6)
            f["pier_wall_bottom_el"] = round(self.wall["z_bot"], 6)
        return f


class SectionComposer:
    def __init__(self, snap, info=build.INFO):
        self.snap = snap
        self.typ = Cut(snap, "typical")
        self.pier = Cut(snap, "pier")
        self.info = dict(info)
        self.info["stamp"] = ["%s  (%s %s)" % (DXF_NAME, "substructure_drawings.typical_section", GENERATOR_VERSION),
                              "FREECAD MODEL SHA-256 %s" % snap["model_sha256"][:16].upper()]
        self.doc = cad.new_document()
        self.warnings = []
        self.overlaps = []

    # ------------------------------------------------------------- pieces
    @staticmethod
    def _outlines(v, cut, roles, box=None):
        for role, items in cut.by_role.items():
            if role not in roles:
                continue
            layer = ROLE_LEVELS.get(role, ROLE_LEVELS["unknown"])
            for _n, o in items:
                for w in o["wires"]:
                    pts = [tuple(p) for p in w["pts"]]
                    if box is None:
                        v.pl(pts, layer, closed=w["closed"])
                    else:
                        v.record({"t": "P", "p": [list(p) for p in pts + ([pts[0]] if w["closed"] else [])], "vis": 1},
                                 layer, None, box)

    def _centerline(self, v, s, z0, z1, label=True):
        """℄ BRIDGE & PGL through the deck and the walkway, stopping short of
        the dimension rows whose symmetric values it would cross (A1);
        labelled inside the walkway."""
        th, k = v.th, v.sf * IN
        v.line((s.u_pgl, z0), (s.u_pgl, z1), "CL_Major")
        if label:
            v.leader([(s.u_pgl, s.z_top_pgl + 0.62 * k), (s.u_pgl - 0.3 * k, s.z_top_pgl + 0.85 * k),
                      (s.u_pgl - 0.5 * k, s.z_top_pgl + 0.85 * k)], "BRIDGE & PGL", "right", cl=True)

    def _crossfall(self, v, s):
        th, k = v.th, v.sf * IN
        for side, sgn in (("L", -1.0), ("R", 1.0)):
            u0 = s.u_pgl + sgn * 0.45 * k
            u1 = s.u_pgl + sgn * 1.25 * k
            z0 = max(_crossings(s.deck["pts"], s.deck["closed"], u0)) + 0.12 * k
            z1 = max(_crossings(s.deck["pts"], s.deck["closed"], u1)) + 0.12 * k
            v.line((u0, z0), (u1, z1), "Symbols")
            v.arrowhead((u1, z1), (u0, z0), "Symbols")
            v.text(((u0 + u1) / 2, (z0 + z1) / 2 + 0.6 * th), "%.1f%%" % (100 * s.crossfall[side]), None, "BOTTOM_CENTER")

    def typical_view(self, zone):
        s = self.typ
        v = cad.View(self.doc, zone, "TYPICAL SECTION")
        th, k = v.th, v.sf * IN
        self._outlines(v, s, ("deck", "haunch", "beam", "barrier"))
        # dimension rows above: clear width between the barriers, out to out of the deck
        yt1 = s.z_bar_top + 0.35 * k
        yt2 = yt1 + 0.32 * k
        if len(s.barriers) == 2:
            bl, br = s.barriers
            v.dim((bl["inner"], bl["z_top"]), (br["inner"], br["z_top"]), yt1 - bl["z_top"],
                  text="%s\\PCLEAR" % fdot.ft_in(br["inner"] - bl["inner"]))
        v.dim((s.u_min, s.z_edge["L"]), (s.u_max, s.z_edge["R"]), yt2 - s.z_edge["L"])
        # the row below the beams: overhang, beam spacing, overhang; beam centrelines
        yb = s.z_beam_bot - 0.35 * k
        xs = [s.u_min] + [b["u"] for b in s.beams] + [s.u_max]
        for a, b in zip(xs, xs[1:]):
            v.dim((a, s.z_beam_bot), (b, s.z_beam_bot), yb - s.z_beam_bot)
        for b in s.beams:
            v.line((b["u"], yb - 0.25 * k), (b["u"], b["z_top"] + 0.15 * k), "CL_Minor")
        self._centerline(v, s, s.z_bot_pgl - 0.12 * k, yt1 - 0.15 * k)
        # vertical column at the right: barrier height and beam depth
        u_col = s.u_max + 1.65 * k     # (room for the HAUNCH callout between the deck edge and the column)
        if s.barriers:
            br = s.barriers[-1]
            v.dim((br["outer"], br["z_base"]), (br["outer"], br["z_top"]), -(u_col - br["outer"]), angle=90.0)
        if s.beams:
            b = s.beams[-1]
            v.dim((b["u1"], b["z_bot"]), (b["u1"], b["z_top"]), -(u_col - b["u1"]), angle=90.0)
        # callouts (every tip snapped onto the drawn outline, A27)
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
        self._crossfall(v, s)
        v.elev_callout((s.u_pgl, s.z_top_pgl), "PGL EL. %s" % fdot.elev(s.z_top_pgl), side=1, rise=0.42 * k)
        v.title((s.u_pgl, yb - 0.75 * k), "TYPICAL SECTION", "(LOOKING AHEAD STATION)", subject_cx=s.u_pgl)
        return v

    def pier_view(self, zone):
        """The section at the Span 1 bearing line at the pier: the beams on
        their pads and pedestals, the pier cap and the pier wall as a stub
        under the cap with a break line.  The deck, beam and barrier
        dimensions are on the typical section."""
        s = self.pier
        v = cad.View(self.doc, zone, "SECTION AT PIER")
        th, k = v.th, v.sf * IN
        z_break = s.cap["z_bot"] - WALL_STUB_FT
        u_lo = min(s.u_min, s.cap["u0"]) - 2.0
        u_hi = max(s.u_max, s.cap["u1"]) + 2.0
        self._outlines(v, s, ("deck", "haunch", "beam", "barrier", "pad", "pedestal", "cap"))
        self._outlines(v, s, ("pier_wall",), box=(u_lo, z_break, u_hi, s.cap["z_top"] + 1.0))
        v.break_line((s.wall["u0"] - 0.12 * k, z_break), (s.wall["u1"] + 0.12 * k, z_break))
        # the row below the stub: the cap length; the cap depth at the right
        yb = z_break - 0.3 * k
        v.dim((s.cap["u0"], s.cap["z_bot"]), (s.cap["u1"], s.cap["z_bot"]), yb - s.cap["z_bot"])
        u_col = s.cap["u1"] + 0.45 * k
        v.dim((s.cap["u1"], s.cap["z_bot"]), (s.cap["u1"], s.cap["z_top"]), -(u_col - s.cap["u1"]), angle=90.0)
        # the bridge centreline through the deck and the cap, stopping short
        # of the cap-length value under the stub (A1); labelled on the
        # typical section
        self._centerline(v, s, yb + 0.15 * k, s.z_top_pgl + 0.25 * k, label=False)
        # callouts: the cap, the wall stub and the cap top elevation at the
        # left; the pad on its pedestal at the right (one two-line callout)
        z_mid = (s.cap["z_top"] + s.cap["z_bot"]) / 2
        tip = s.snap((s.cap["u0"], z_mid), ("cap",))
        v.leader([tip, (s.cap["u0"] - 0.35 * k, z_mid), (s.cap["u0"] - 0.55 * k, z_mid)], "PIER CAP", "right")
        # the wall stub is called out at the right, under the cap depth
        # column (a left callout would cross the cap-length extension line)
        tip = s.snap((s.wall["u1"], z_break + 0.8 * WALL_STUB_FT), ("pier_wall",))
        v.leader([tip, (s.cap["u1"] + 0.6 * k, z_break + 0.1 * k), (s.cap["u1"] + 0.8 * k, z_break + 0.1 * k)],
                 "PIER WALL", "left")
        if s.pads and s.pedestals:
            p, ped = s.pads[-1], s.pedestals[-1]
            tip = s.snap((p["u1"], (p["z_top"] + p["z_bot"]) / 2), ("pad",))
            v.leader([tip, (s.cap["u1"] + 0.6 * k, p["z_top"] + 0.35 * k), (s.cap["u1"] + 0.8 * k, p["z_top"] + 0.35 * k)],
                     "%s TYPE F BEARING PAD\\PON %s PEDESTAL (TYP.)" % (fdot.ft_in(p["z_top"] - p["z_bot"], 1.0 / 16),
                                                                       fdot.ft_in(ped["z_top"] - ped["z_bot"])), "left")
        v.elev_callout((s.cap["u0"] + 0.4 * k, s.cap["z_top"]), "TOP OF CAP EL. %s" % fdot.elev(s.cap["z_top"]), side=-1, rise=0.9 * k)
        v.title((s.u_pgl, yb - 0.6 * k), "SECTION AT PIER", "(AT ¡ BEARING, SPAN 1; LOOKING AHEAD STATION)", subject_cx=s.u_pgl)
        return v

    # -------------------------------------------------------------- sheet
    def build(self):
        snap = self.snap
        sh = Sheet(self.doc, 0, SHEET_NUMBER, SHEET_TITLE, self.info)
        # two zones: the typical section at 3/8" at the top left with the
        # notes beside it, the section at the pier at 1/4" under it (the
        # 19'-2" cap with its callouts fits the sheet width at 1/4" only);
        # each zone's window follows its view once drawn
        zone1 = sh.zone(DRAW, SHEET_SCALE)
        v1 = self.typical_view(zone1)
        w1, h1 = build.Composer.paper_size(v1)
        x1, y1 = DRAW[0] + 0.3, DRAW[3] - 0.2
        ys = y1 - h1 - VIEW_GAP_IN / 2.0
        zone1.window = (DRAW[0], ys, x1 + w1 + 0.25, DRAW[3])
        zone2 = sh.zone((DRAW[0], DRAW[1], DRAW[2], ys), PIER_SCALE)
        v2 = self.pier_view(zone2)
        comp = build.Composer.__new__(build.Composer)
        comp.warnings, comp.__dict__["placed"] = self.warnings, {}
        comp.place_tl(v1, x1, y1)
        comp.place_tl(v2, x1, ys - VIEW_GAP_IN / 2.0)
        comp.check(sh, v1)
        comp.check(sh, v2)
        self.overlaps = comp.__dict__.get("annotation_overlaps", [])
        ft, fp = self.typ.facts(), self.pier.facts()
        notes = [
            "SECTIONS OF THE REGISTERED FREECAD MODEL (SHA-256 %s) CUT NORMAL TO THE STATIONING, LOOKING AHEAD "
            "STATION: THE TYPICAL SECTION AT STA. %s (MID-SPAN 1) AND THE SECTION AT THE PIER AT STA. %s (THE SPAN 1 "
            "BEARING LINE); MODEL SPACE IS AT FULL SIZE IN FEET." % (snap["model_sha256"][:16].upper(), ft["station"], fp["station"]),
            "THE FINISHED COMPONENTS OF THE MODEL ARE DRAWN AS CUT: THE DECK WITH ITS CHAMFERS AND DRIP GROOVES, THE "
            "HAUNCHES, THE TWO FIB-36 BEAMS, THE PEDESTRIAN BARRIERS AND, AT THE PIER, THE BEARING PADS, THE PEDESTALS, "
            "THE PIER CAP AND THE PIER WALL (BROKEN %s BELOW THE CAP). DIMENSIONS ARE MEASURED ON THE MODEL AT THE CUT."
            % fdot.ft_in(WALL_STUB_FT, mtext=False),
            "THE DECK CROSSFALL IS %s EACH WAY FROM THE CROWN ON THE PGL; THE DECK TOP ON THE PGL IS EL. %s AT MID-SPAN "
            "AND EL. %s AT THE PIER BEARING LINE." % (" / ".join("%.1f%%" % (100 * self.typ.crossfall[k2]) for k2 in ("L", "R")),
                                                     fdot.elev(self.typ.z_top_pgl), fdot.elev(self.pier.z_top_pgl)),
            "FOR THE DECK, BEAM AND BARRIER DIMENSIONS AT THE PIER SEE THE TYPICAL SECTION. THE PIER CHEEK WALLS, THE "
            "PILES AND THE ANNULAR RING PLATES LIE BEYOND THE PIER CUT AND ARE NOT DRAWN; SEE THE PIER SHEETS.",
            "MODEL CHECK: THE PEDESTRIAN FENCE ENCLOSURE OVER THE WALKWAY AND THE HANDRAILS ARE NOT IN THE MODEL AND "
            "ARE NOT SHOWN.",
            "NOT SHOWN: REINFORCEMENT AND MODEL SOURCES, CHECKS AND SCHEDULES.",
            "STATIONS ARE FROM FFBW END BENT 1 = %s (SELECTED GEOMETRY CAD TABLES, D-041)." % fdot.station(STATION_FFBW_EB1),
            "THIS SHEET IS GENERATED FOR REVIEW OF THE MODEL AND IS NOT A CONTRACT DRAWING.",
        ]
        # the notes beside the typical section, at the top right
        p1 = comp.paper_bbox(v1)
        xn = p1[2] + 0.45
        wn = DRAW[2] - 0.1 - xn
        y_top = DRAW[3] - 0.2
        bottom = sh.notes_bottom(y_top, notes, wn)
        sh.notes(xn, y_top, "NOTES:", notes, width_in=wn)
        comp.check_block(sh, "notes", (xn, bottom, xn + wn, y_top))
        sh.border()
        sh.group_zones()
        sh.add_viewports()
        if "Layout1" in self.doc.layouts:
            self.doc.layouts.delete("Layout1")
        build.dimension_blocks_by_level(self.doc)
        self.sheet, self.views, self.facts = sh, [v1, v2], {"typical": ft, "pier": fp}
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
            "frame": snap["frame"],
            "cuts": {key: {"y_ft": sec["y_ft"], "where": sec["where"]} for key, sec in snap["sections"].items()},
            "sheet": {"number": SHEET_NUMBER, "title": SHEET_TITLE, "layout": comp.sheet.layout.name,
                      "scale": fdot.scale_label(SHEET_SCALE), "scales": [fdot.scale_label(SHEET_SCALE), fdot.scale_label(PIER_SCALE)],
                      "views": [v.name for v in comp.views]},
            "section": comp.facts["typical"],
            "section_at_pier": comp.facts["pier"],
            "objects_by_role": {key: {r: [n for n, _ in items] for r, items in cut.by_role.items()}
                                for key, cut in (("typical", comp.typ), ("pier", comp.pier))},
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
