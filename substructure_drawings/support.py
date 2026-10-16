"""Derived geometry for one support (end bent or pier) from the snapshot."""
import math
import re
from collections import OrderedDict

from . import bars as barlib

# Profile start station at FFBW End Bent 1 (geometry notebook CONFIG
# profile.start_sta_ft, carried in the selected CAD-tables workbook as
# Inputs!Prof_Sta0).  Stations elsewhere follow from model distances.
STATION_FFBW_EB1 = 1593.22

ROLE_LAYERS = {
    "cap": ("SubStrConc", "SubStrConc_h"),
    "backwall": ("SubStrConc", "SubStrConc_h"),
    "pier_wall": ("SubStrConc", "SubStrConc_h"),
    "cheek": ("SubStrConc2", "SubStrConc2_h"),
    "pedestal": ("SubStrConc2", "SubStrConc2_h"),
    "pad": ("BearingPadMisc", "BearingPadMisc"),
    "pile_conc": ("PileConc", "PileConc_h"),
    "pile_steel": ("PileSteel", "PileSteel_h"),
    "mse": ("WallMSEPanel", "WallMSEPanel_h"),
    "landing": ("AppSlabConc", "AppSlabConc_h"),
    "unknown": ("SubStrConc", "SubStrConc_h"),
}


def layer_for(rec):
    vis, hid = ROLE_LAYERS.get(rec["role"], ROLE_LAYERS["unknown"])
    if rec["vis"]:
        return vis, None
    if hid == vis:  # level without a hidden twin: hidden linetype override
        return vis, "DGN Style 2"
    return hid, None


class Support:
    def __init__(self, key, S, ffbw_eb1_y):
        self.key = key
        self.S = S
        self.kind = "PIER" if key == "PIER" else "EB"
        self.title = S["title"]
        self.e1 = S["e1"][0]
        self.up = S["plan_up"][1]
        self.x0, self.y0 = S["origin_ft"][0], S["origin_ft"][1]
        self.ffbw_eb1_y = ffbw_eb1_y
        cb = S["cap_bb_ft"]
        self.cap_bb = cb
        self.cap_top, self.cap_bot = cb[5], cb[2]
        self.cap_u = sorted((self.u(cb[0]), self.u(cb[3])))
        self.cap_v = sorted((self.v(cb[1]), self.v(cb[4])))
        self.cap_s = sorted((-cb[1], -cb[4]))
        self.objs = S["concrete"]
        self.table = barlib.assign_marks(self.kind, S["bars"])
        self.bars = S["bars"]
        for b in self.bars:
            b["pts"] = barlib.polyline3(b, 5.0)
            b["cls"] = barlib.direction_class(b)
            # Body = bar without its end legs and their bends (hook tails,
            # stirrup feet turned in plan around the piles).
            e = b["edges"]
            body = barlib.polyline3({"edges": e[2:-2] if len(e) >= 7 else e[1:-1] if len(e) > 3 else e}, 5.0)
            xs = sorted(p[0] for p in body)
            b["x_station"] = xs[len(xs) // 2]
            # Transverse bars lie (nearly) in a plane across the cap; closed hoops
            # drift about 1-1/4 in along the cap at their 135-degree closure.
            b["transverse"] = (xs[-1] - xs[0]) < 0.15
        self._piles()
        self._beams()
        self._pedestals()
        if self.kind == "EB":
            self._walls()
        else:
            self._pier_wall()

    # -------------------------------------------------------------- frames
    def u(self, x):
        return self.e1 * (x - self.x0)

    def v(self, y):
        return self.up * (y - self.y0)

    def offset(self, x):
        """Transverse offset from the PGL, + to the right looking up-station."""
        return -(x - self.x0)

    def station(self, y):
        return STATION_FFBW_EB1 + (self.ffbw_eb1_y - y)

    def P_elev(self, p):
        return (self.u(p[0]), p[2])

    def P_plan(self, p):
        return (self.u(p[0]), self.v(p[1]))

    @staticmethod
    def P_sec(p):
        return (-p[1], p[2])

    def by_role(self, role):
        return OrderedDict((n, m) for n, m in self.objs.items() if m["role"] == role)

    # ------------------------------------------------------------ elements
    def _piles(self):
        piles = []
        for n, m in list(self.by_role("pile_conc").items()) + list(self.by_role("pile_steel").items()):
            b = m["bb_ft"]
            xc, yc = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
            piles.append({"name": n, "x": xc, "y": yc, "offset": self.offset(xc), "u": self.u(xc),
                          "s": -yc, "v": self.v(yc), "width": b[3] - b[0], "top": b[5],
                          "shape": "square" if m["role"] == "pile_conc" else "pipe", "label": m["label"]})
        piles.sort(key=lambda p: p["offset"])
        for i, p in enumerate(piles, 1):
            p["no"] = i
        self.piles = piles

    def _beams(self):
        pads = []
        for n, m in self.by_role("pad").items():
            b = m["bb_ft"]
            pads.append({"name": n, "x": (b[0] + b[3]) / 2, "y": (b[1] + b[4]) / 2, "bb": b})
        xs = sorted({round(p["x"], 3) for p in pads}, key=lambda x: self.offset(x))
        self.beam_lines = []
        for j, x in enumerate(xs, 1):
            self.beam_lines.append({"line": j, "x": x, "u": self.u(x), "offset": self.offset(x)})
        # bearings: one CL bearing per span side present at this support
        ys = sorted({round(p["y"], 3) for p in pads}, reverse=True)  # span 1 (EB1 side) first
        self.bearings = []
        for y in ys:
            if self.key == "EB1":
                span = 1
            elif self.key == "EB2":
                span = 2
            else:
                span = 1 if y > self.y0 else 2
            self.bearings.append({"span": span, "y": y, "v": self.v(y), "s": -y})
        self.pads = pads

    def beam_id(self, span, line):
        return "%d-%d" % (span, line)

    def _pedestals(self):
        peds = []
        for n, m in self.by_role("pedestal").items():
            b = m["bb_ft"]
            xc = (b[0] + b[3]) / 2
            top = [v for v in m["vertices_ft"] if v[2] > self.cap_top + 0.01]
            peds.append({"name": n, "x": xc, "u": self.u(xc), "offset": self.offset(xc), "bb": b,
                         "top_vertices": top, "label": m["label"]})
        peds.sort(key=lambda p: p["offset"])
        for i, p in enumerate(peds, 1):
            p["line"] = i
        self.pedestals = peds

    def _walls(self):
        bw = list(self.by_role("backwall").values())[0]
        b = bw["bb_ft"]
        # FFBW: backwall face toward the bridge (EB1 at YMin, EB2 at YMax)
        self.ffbw_y = b[1] if self.key == "EB1" else b[4]
        self.ffbw_s = -self.ffbw_y
        self.ffbw_v = self.v(self.ffbw_y)
        verts = bw["vertices_ft"]
        front = [v for v in verts if abs(v[1] - self.ffbw_y) < 1e-3]
        top = sorted(((self.u(v[0]), v[2]) for v in front if v[2] > self.cap_top + 0.01), key=lambda t: t[0])
        self.backwall_top = top                       # (u, z) along FFBW top edge
        self.backwall_bb = b
        self.cheeks = []
        for n, m in self.by_role("cheek").items():
            cb = m["bb_ft"]
            uc = self.u((cb[0] + cb[3]) / 2)
            self.cheeks.append({"name": n, "u_lo": min(self.u(cb[0]), self.u(cb[3])), "u_hi": max(self.u(cb[0]), self.u(cb[3])),
                                "u": uc, "side": "left" if uc < 0 else "right", "top": cb[5], "bot": cb[2], "bb": cb,
                                "xmin_side": cb[3] <= self.cap_bb[0] + 0.01, "vertices": m["vertices_ft"]})
        self.cheeks.sort(key=lambda c: c["u"])
        self.outer_u = (self.cheeks[0]["u_lo"], self.cheeks[-1]["u_hi"])

    def _pier_wall(self):
        w = list(self.by_role("pier_wall").values())[0]
        b = w["bb_ft"]
        self.wall_bb = b
        self.wall_u = sorted((self.u(b[0]), self.u(b[3])))
        self.wall_top, self.wall_bot = b[5], b[2]
        self.wall_thk = b[4] - b[1]
        self.outer_u = tuple(self.cap_u)

    # ------------------------------------------------------------- reinforcement
    def bars_of(self, mark=None, family=None, subtype=None):
        out = []
        for b in self.bars:
            if mark and b["mark"] != mark:
                continue
            if family and b["family"] != family:
                continue
            if subtype and b["subtype"] != subtype:
                continue
            out.append(b)
        return out

    def transverse_groups(self):
        """Stirrup runs R1..Rn in order along the cap (from native names)."""
        groups = OrderedDict()
        for b in self.bars_of(family="cap_trans"):
            m = re.search(r"_R(\d+)_(\d+)$", b["name"])
            groups.setdefault(int(m.group(1)), []).append(b)
        out = []
        for run, members in groups.items():
            xs = sorted(members, key=lambda b: self.u(b["x_station"]))
            us = [self.u(b["x_station"]) for b in xs]
            out.append({"run": run, "bars": xs, "u": us, "mark": xs[0]["mark"]})
        out.sort(key=lambda g: g["u"][0])
        return out

    def elevation_points(self):
        """Key elevations for the table of elevations, lettered in drawing order."""
        pts = []
        if self.kind == "EB":
            cl, cr = self.cheeks[0], self.cheeks[-1]
            top = self.backwall_top
            crown = max(top, key=lambda t: t[1])
            pts += [("TOP OF CHEEK WALL", cl["u"], cl["top"]),
                    ("TOP OF BACKWALL AT END", top[0][0], top[0][1]),
                    ("TOP OF BACKWALL AT PGL", crown[0], crown[1]),
                    ("TOP OF BACKWALL AT END", top[-1][0], top[-1][1]),
                    ("TOP OF CHEEK WALL", cr["u"], cr["top"]),
                    ("TOP OF CAP AT END", self.cap_u[0], self.cap_top),
                    ("TOP OF CAP AT END", self.cap_u[1], self.cap_top),
                    ("BOTTOM OF CAP AT END", self.cap_u[0], self.cap_bot),
                    ("BOTTOM OF CAP AT END", self.cap_u[1], self.cap_bot),
                    ("BOTTOM OF CHEEK LUG", cl["u"], cl["bot"]),
                    ("BOTTOM OF CHEEK LUG", cr["u"], cr["bot"])]
        else:
            pts += [("TOP OF CAP AT END", self.cap_u[0], self.cap_top),
                    ("TOP OF CAP AT END", self.cap_u[1], self.cap_top),
                    ("BOTTOM OF CAP AT END", self.cap_u[0], self.cap_bot),
                    ("BOTTOM OF CAP AT END", self.cap_u[1], self.cap_bot),
                    ("BOTTOM OF PIER WALL", self.wall_u[0], self.wall_bot),
                    ("BOTTOM OF PIER WALL", self.wall_u[1], self.wall_bot)]
        letters = [c for c in "ABCDEFGHJKLMNPRSTUVWXYZ"]
        return [(letters[i], d, u, z) for i, (d, u, z) in enumerate(pts)]

    def pedestal_table(self):
        """Top-of-pedestal elevations: corners A, B (back edge) / C, D (front)."""
        rows = []
        for p in self.pedestals:
            tv = p["top_vertices"]
            if not tv:
                continue
            # distinct plan lines across the pedestal (v), each level transversely
            lines = OrderedDict()
            for v in sorted(tv, key=lambda q: self.v(q[1]), reverse=True):
                key = round(self.v(v[1]), 3)
                lines.setdefault(key, []).append(v[2])
            rows.append({"pedestal": p, "lines": [(k, max(zs)) for k, zs in lines.items()]})
        return rows
