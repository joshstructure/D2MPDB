"""Build the end bent and pier DXF (one file, 9 sheets) from the snapshot.

Usage: see ``scripts/build_substructure_dxf.py``.
"""
import csv
import hashlib
import json
import math
from pathlib import Path

from . import bars as barlib
from . import cad, fdot
from .sheets import DRAW, Sheet
from .support import STATION_FFBW_EB1, Support
from .views import Builder, z_on_edges

GENERATOR_VERSION = "2.0.0"
DXF_NAME = "B4_Substructure_EndBents_Pier.dxf"

INFO = {
    "project": "D2 I-95 PEDESTRIAN BRIDGE - B4",
    "bridge_name": "B4 PEDESTRIAN BRIDGE",
    "bridge_no": "",
    "road": "",
    "county": "",
    "fpid": "",
    "status": "PRELIMINARY - NOT FOR CONSTRUCTION - GENERATED FROM THE CURRENT FREECAD MODEL",
    "eor_lines": ["ENGINEER OF RECORD:", "", "", ""],
    "sheet_prefix": "B4-",
}

# Values in the selected CAD-tables workbook (D-041) used as independent
# cross-checks of the model geometry; differences are reported, not hidden.
WORKBOOK_CHECKS = {
    "station_pier": 1700.57, "station_ffbw_eb2": 1805.47,
    "cap_top_eb1": 43.23769223221814, "cap_top_eb2": 43.24969214402966, "cap_top_pier": 43.76493990975892,
    "backwall_end_eb1": 47.13183333333333, "backwall_pgl_eb1": 47.327666666666666,
    "backwall_end_eb2": 47.14383333333333, "backwall_pgl_eb2": 47.339666666666666,
}

RIGHT_COL = 12.3      # paper x where the table/notes column starts on plan sheets
MAIN = (DRAW[0], DRAW[1], 12.15, DRAW[3])
# Sheets per support: plan and elevation with the reinforcement (pier: with
# the end view), then the details (EB: sections A-A, B-B, C-C; cheek views
# with the pedestal details; pier: sections with the pedestal details), then
# the bar list.
SHEETS = (("EB1", 3), ("PIER", 2), ("EB2", 3), ("BARS", 1))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Composer:
    def __init__(self, snap, info=INFO):
        self.snap = snap
        self.info = dict(info)
        ffbw = snap["structures"]["EB1"]["concrete"]["BridgeBackwallEB1"]["bb_ft"][1]
        self.sup = {k: Support(k, snap["structures"][k], ffbw) for k in ("EB1", "PIER", "EB2")}
        self.doc = cad.new_document()
        self.sheets = []
        self.warnings = []
        self.info["stamp"] = ["%s  (%s %s)" % (DXF_NAME, "substructure_drawings", GENERATOR_VERSION),
                              "FREECAD MODEL SHA-256 %s" % snap["model_sha256"][:16].upper()]
        p = self.info["sheet_prefix"]
        n = iter(range(1, 100))
        self.numbers = {k: [p + str(next(n)) for _ in range(c)] for k, c in SHEETS}

    # ---------------------------------------------------------------- utils
    def new_sheet(self, number, title):
        sh = Sheet(self.doc, len(self.sheets), number, title, self.info)
        self.sheets.append(sh)
        return sh

    @staticmethod
    def paper_size(view):
        b = view.local_bbox
        return (b[2] - b[0]) / view.sf * 12.0, (b[3] - b[1]) / view.sf * 12.0

    def paper_bbox(self, view):
        b = view.local_bbox
        z = view.sheet
        x0, y0 = b[0] + view.ox, b[1] + view.oy
        x1, y1 = b[2] + view.ox, b[3] + view.oy
        mo = z.model_origin
        return ((x0 - mo[0]) / z.sf * 12, (y0 - mo[1]) / z.sf * 12, (x1 - mo[0]) / z.sf * 12, (y1 - mo[1]) / z.sf * 12)

    def place_tl(self, view, px, py):
        """Place a view by the top-left of its bounding box."""
        b = view.local_bbox
        view.place(b[0], b[3], px, py)

    def check(self, sheet, view, area=None):
        a = area or view.sheet.window
        p = self.paper_bbox(view)
        if p[0] < a[0] - 0.05 or p[1] < a[1] - 0.05 or p[2] > a[2] + 0.05 or p[3] > a[3] + 0.05:
            self.warnings.append("%s / %s outside its window: (%.2f, %.2f)-(%.2f, %.2f) in" %
                                 ((sheet.number, view.name) + tuple(p)))
        # views on one sheet must not draw over each other (boxes of their
        # primitives and texts may not cross)
        placed = self.__dict__.setdefault("placed", {}).setdefault(sheet.number, [])
        mine = view.paper_boxes()
        for other, theirs in placed:
            n = cad.boxes_cross(mine, theirs)
            if n:
                self.warnings.append("%s / %s draws over %s (%d crossings)" % (sheet.number, view.name, other.name, n))
        placed.append((view, mine))

    def row(self, sheet, views, y_top, x0, x1, gap=0.3):
        widths = [self.paper_size(v)[0] for v in views]
        total = sum(widths) + gap * (len(views) - 1)
        x = x0 + max(0.0, (x1 - x0 - total) / 2)
        for v, w in zip(views, widths):
            self.place_tl(v, x, y_top)
            x += w + gap
            self.check(sheet, v)
        return y_top - max(self.paper_size(v)[1] for v in views)

    def finish(self, sheet):
        sheet.border()
        sheet.add_viewports()

    def bar_list_ref(self):
        return "FOR REINFORCING BAR LIST, SEE SHEET %s." % self.numbers["BARS"][0]

    # --------------------------------------------------- plan + elevation
    def plan_elevation(self, key):
        """Plan above the elevation (with the reinforcement), tables at the
        upper right, notes below them, legend at the lower left (FDOT End
        Bent / Pier sheet configuration)."""
        s = self.sup[key]
        nums = self.numbers[key]
        sh = self.new_sheet(nums[0], s.title)
        zone = sh.zone(DRAW, "3/8")   # views centred in MAIN; the pier end view may pass it
        b = Builder(s, self.doc)
        plan = b.plan(zone)
        zb = (s.cap_bot - 2.0, s.wall_bot + 0.5, 1.0, s.wall_bot - 1.25) if s.kind == "PIER" else None
        elev = b.elevation(zone, zb)
        b.draw_legend(elev)
        ev = b.end_view(zone, "D", zb) if s.kind == "PIER" else None
        L = -min(plan.local_bbox[0], elev.local_bbox[0])
        R = max(plan.local_bbox[2], elev.local_bbox[2])
        width = (L + R) / zone.sf * 12
        ew = self.paper_size(ev)[0] + 0.3 if ev else 0.0
        xc = MAIN[0] + max(0.0, (MAIN[2] - MAIN[0] - ew - width) / 2) + L / zone.sf * 12
        plan.place(0.0, plan.local_bbox[3], xc, MAIN[3] - 0.05)
        ph = self.paper_size(plan)[1]
        eh = self.paper_size(elev)[1]
        gap = max(0.1, (MAIN[3] - MAIN[1] - 0.1 - ph - eh) / 2)
        elev.place(0.0, elev.local_bbox[3], xc, MAIN[3] - 0.05 - ph - gap)
        self.check(sh, plan)
        self.check(sh, elev)
        if ev:  # beside the elevation, bottom-aligned with it (FDOT pier sheet, VIEW A-A)
            pb = self.paper_bbox(elev)
            self.place_tl(ev, pb[2] + 0.3, pb[1] + self.paper_size(ev)[1])
            self.check(sh, ev, DRAW)
        self._pe_tables(sh, s, b, top=DRAW[3] - 0.05)
        self.finish(sh)

    def _pe_tables(self, sh, s, b, top):
        x = RIGHT_COL
        rows = [(l, fdot.elev(z)) for l, d, u, z in b.elev_points]
        y1 = sh.table(x, top, "TABLE OF\\PELEVATIONS", [("POINT", "ELEVATION")], rows, [0.55, 0.85])
        body = [(p["no"], "%.1f" % (math.floor(p["top"] * 10 + 0.5) / 10.0), fdot.ft_in(p["offset"], 0.125))
                for p in s.piles]
        y2 = sh.table(x + 1.55, top, "PILE CUTOFF\\PELEVATIONS", [("PILE NO.", "CUTOFF EL.", "PGL OFFSET")], body,
                      [0.55, 0.75, 0.85])
        y = min(y1, y2)
        nums = self.numbers[s.key]
        notes = list(dict.fromkeys(b.notes))
        notes.append("REINFORCEMENT IS SHOWN REPRESENTATIVELY: THE FIRST AND LAST BAR OF EACH RUN ARE DRAWN.")
        if s.kind == "EB":
            notes.append("FOR SECTIONS A-A, B-B AND C-C, SEE SHEET %s. FOR VIEWS D-D AND E-E AND PEDESTAL DETAILS, "
                         "SEE SHEET %s." % (nums[1], nums[2]))
            notes.append("THE SOIL REINFORCEMENT ATTACHED TO THE BACKWALL SHALL BE DESIGNED BY A SPECIALTY ENGINEER "
                         "FOR A SERVICE LOAD OF ___ K/FT AND A FACTORED LOAD OF ___ K/FT USING THE DESIGN CRITERIA FOR "
                         "PERMANENT MSE WALLS. COST OF FURNISHING AND INSTALLING THE SOIL REINFORCEMENT IS CONSIDERED "
                         "INCIDENTAL TO THE COST OF THE END BENT.")
        else:
            notes.append("FOR SECTIONS A-A, B-B AND C-C AND PEDESTAL DETAILS, SEE SHEET %s. FOR LOCATION OF "
                         "VIEW D-D, SEE PLAN." % nums[1])
            notes.append("PIER WALL IS PROVISIONAL (3'-0\" THICK); ITS REINFORCEMENT IS NOT SHOWN.")
        notes.append(self.bar_list_ref())
        notes.append("PILE OFFSETS ARE FROM THE PGL, + TO THE RIGHT LOOKING UP-STATION. CUTOFF ELEVATIONS ARE TO THE "
                     "NEAREST 0.1 FT.")
        for q in self.qc():
            if q["status"] != "PASS" and s.title in q["check"].upper():
                notes.append("MODEL CHECK (REMOVE BEFORE ISSUE): %s IS %.3f IN THE CAD MODEL AND %.3f IN THE SELECTED "
                             "GEOMETRY CAD TABLES; RECONCILE BEFORE ISSUE." % (q["check"].upper(), q["model"], q["reference"]))
        sh.notes(x, y - 0.3, "NOTES:", notes, width_in=3.7)

    # -------------------------------------------------------------- details
    def _ped_table(self, sh, s, x, y_top):
        """TOP OF PEDESTAL ELEVATIONS in the sample's title/header style; our
        pedestal tops slope, so the corner elevations are listed."""
        body = []
        if s.kind == "EB":
            for row in s.pedestal_table():
                p = row["pedestal"]
                back = max(row["lines"], key=lambda t: t[0])
                front = min(row["lines"], key=lambda t: t[0])
                bid = s.beam_id(s.bearings[0]["span"], p["line"])
                body.append((bid, fdot.elev(back[1]), fdot.elev(front[1]), fdot.elev(back[1]), fdot.elev(front[1])))
            corners = ("A", "B", "C", "D")
            note = "A, C AT FFBW EDGE; B, D AT SPAN EDGE (LEVEL TRANSVERSELY)."
        else:
            for row in s.pedestal_table():
                p = row["pedestal"]
                zs = [z for _, z in sorted(row["lines"], key=lambda t: t[0])]
                body.append(("1-%d / 2-%d" % (p["line"], p["line"]),) + tuple(fdot.elev(z) for z in zs[:4]))
            corners = ("A", "E", "F", "B")
            note = "A AT SPAN 1 EDGE, B AT SPAN 2 EDGE, E AND F AT THE PAD-END BREAKS."
        hdr = [(("BEAM NO.", 1, 2), ("ELEVATION (FEET)", 4)), (None,) + corners]
        y = sh.table(x, y_top, "TOP OF PEDESTAL ELEVATIONS", hdr, body, [0.85, 0.7, 0.7, 0.7, 0.7])
        sh.ptext((x, y - 0.08), note, 0.07, "TOP_LEFT", "TextStructures")
        return y - 0.2

    def eb_details(self, key):
        s = self.sup[key]
        nums = self.numbers[key]
        b = Builder(s, self.doc)
        # (1 OF 2): sections A-A and B-B, pedestal plan and elevation, pedestal
        # table (FDOT End Bent Details sheet configuration)
        sh = self.new_sheet(nums[1], s.title + " DETAILS (1 OF 2)")
        z = sh.zone(DRAW, "3/4")
        va = b.section(z, "between_piles", "A", "(SECTION BETWEEN PILES)")
        vb = b.section(z, "at_pile", "B", "(SECTION AT PILES)")
        pp = b.pedestal_plan(z, s.pedestals[0])
        pe = b.pedestal_elevation(z, s.pedestals[0])
        wp = max(self.paper_size(pp)[0], self.paper_size(pe)[0])
        # EB1: sections then the pedestal column; EB2 (drawn mirrored, the
        # MSE wall on the left) is the mirror image of that arrangement
        if key == "EB1":
            self.row(sh, [va, vb], DRAW[3] - 0.05, DRAW[0], DRAW[2] - wp - 0.1, gap=0.1)
            x_r, x_t = DRAW[2] - wp, DRAW[2] - 3.5
            x_n, w_n = DRAW[0] + 0.1, DRAW[2] - 3.5 - DRAW[0] - 0.4
        else:
            ws = self.paper_size(va)[0] + self.paper_size(vb)[0] + 0.1
            self.row(sh, [vb, va], DRAW[3] - 0.05, DRAW[2] - ws, DRAW[2], gap=0.1)
            x_r, x_t = DRAW[0], DRAW[0] + 0.1
            x_n, w_n = DRAW[0] + 3.9, DRAW[2] - DRAW[0] - 3.9 - 3.6
        self.place_tl(pp, x_r + (wp - self.paper_size(pp)[0]) / 2, DRAW[3] - 0.05)
        # the pedestal elevation keeps to the outer edge, away from section B-B
        xe = x_r + wp - self.paper_size(pe)[0] if key == "EB1" else x_r
        self.place_tl(pe, xe, self.paper_bbox(pp)[1] - 0.15)
        for v in (pp, pe):
            self.check(sh, v)
        self._ped_table(sh, s, x_t, self.paper_bbox(pe)[1] - 0.15)
        # notes under the sections, beside the table
        y = min(self.paper_bbox(va)[1], self.paper_bbox(vb)[1]) - 0.1
        sh.notes(x_n, y, "NOTES:", [
            "FOR LOCATION OF SECTIONS, SEE SHEET %s." % nums[0],
            "ALL BARS ARE SHOWN IN SECTIONS; BARS IN THE SECTION PLANE ARE THE NEAREST BAR OF THEIR SERIES "
            "WITHIN 1'-3\" BEYOND THE CUT.",
            b.pedestal_marks_note(s.pedestals[0]),
            "PEDESTALS ARE CAST ON THE CAP; THE CAP TOP IS A CONSTRUCTION JOINT.",
            self.bar_list_ref()], width_in=w_n)
        self.finish(sh)
        # (2 OF 2): section C-C (3/4") and the cheek wall views (1/2")
        sh = self.new_sheet(nums[2], s.title + " DETAILS (2 OF 2)")
        z = sh.zone(DRAW, "3/4")
        vc = b.section(z, "at_beam", "C", "(SECTION AT CENTERLINE OF BEAM)")
        self.place_tl(vc, DRAW[0] + 0.05, DRAW[3] - 0.05)
        xs = self.paper_bbox(vc)[2] + 0.2
        z.window = (DRAW[0], DRAW[1], xs, DRAW[3])
        self.check(sh, vc)
        z2 = sh.zone((xs, DRAW[1], DRAW[2], DRAW[3]), "1/2")
        vd = b.cheek_view(z2, s.cheeks[0], "D", wwr_note=2)
        ve = b.cheek_view(z2, s.cheeks[-1], "E", wwr_note=2)
        bottom = self.row(sh, [vd, ve], DRAW[3] - 0.05, xs + 0.1, DRAW[2], gap=0.5)
        sh.notes(xs + 0.2, bottom - 0.25, "NOTES:", [
            "FOR LOCATION OF SECTION C-C AND VIEWS D-D AND E-E, SEE SHEET %s." % nums[0],
            "WELDED WIRE REINFORCEMENT (WWR) 4x4-W1.4xW1.4 IN THE CHEEK LUGS SHALL BE TIED TO THE "
            "END BENT REINFORCING STEEL.",
            "FOR CHEEK TOP ELEVATIONS, SEE THE TABLE OF ELEVATIONS, SHEET %s." % nums[0],
            self.bar_list_ref()], width_in=DRAW[2] - xs - 0.3)
        self.finish(sh)

    def pier_details(self):
        """Sections A-A, B-B and C-C in a row; pedestal plan, pedestal
        elevation, the pedestal table and the notes below."""
        s = self.sup["PIER"]
        nums = self.numbers["PIER"]
        b = Builder(s, self.doc)
        sh = self.new_sheet(nums[1], "PIER DETAILS")
        z = sh.zone(DRAW, "3/4")
        va = b.section(z, "between_piles", "A", "(SECTION BETWEEN PILES)")
        vb = b.section(z, "at_pile", "B", "(SECTION AT PILES)")
        vc = b.section(z, "at_beam", "C", "(SECTION AT CENTERLINE OF BEAMS)")
        self.row(sh, [va, vb, vc], DRAW[3] - 0.05, DRAW[0], DRAW[2], gap=0.15)
        pp = b.pedestal_plan(z, s.pedestals[0])
        pe = b.pedestal_elevation(z, s.pedestals[0])
        top = min(self.paper_bbox(va)[1], self.paper_bbox(vb)[1]) - 0.05
        self.place_tl(pp, DRAW[0] + 0.1, top)
        self.place_tl(pe, self.paper_bbox(pp)[2] + 0.35, top - 0.15)
        for v in (pp, pe):
            self.check(sh, v)
        xt = max(self.paper_bbox(pe)[2] + 0.35, self.paper_bbox(vc)[0])
        y = self._ped_table(sh, s, xt, self.paper_bbox(vc)[1] - 0.15)
        sh.notes(xt, y - 0.2, "NOTES:", [
            "FOR LOCATION OF SECTIONS, SEE SHEET %s." % nums[0],
            "ALL BARS ARE SHOWN IN SECTIONS; BARS IN THE SECTION PLANE ARE THE NEAREST BAR OF THEIR SERIES "
            "WITHIN 1'-3\" BEYOND THE CUT.",
            b.pedestal_marks_note(s.pedestals[0]),
            "PIER WALL IS PROVISIONAL; ITS REINFORCEMENT IS NOT SHOWN.",
            self.bar_list_ref()], width_in=DRAW[2] - xt - 0.05)
        self.finish(sh)

    # -------------------------------------------------------------- bar list
    BAR_COLS = [0.3, 0.38, 0.62, 0.38, 0.32, 0.16, 0.16] + [0.56] * 8 + [0.28, 0.34]
    BAR_HDR = [(("MARK", 2), "LENGTH", "NO", "TYP", ("STY", 2), "B", "C", "D", "E", "F", "H", "J", "K", "N", "Ø"),
               ("SIZE", "DES", "FT  IN", "BARS", "BAR", "A", "G") + ("FT  IN",) * 8 + ("NO", "ANG")]

    def bar_list(self):
        """Reinforcing bar list on the FDOT bar list form: two header rows,
        a component heading row between blank spacer rows, lengths and bend
        dimensions as FT-IN without unit marks."""
        sh = self.new_sheet(self.numbers["BARS"][0], "REINFORCING BAR LIST")
        sh.zone(DRAW, "3/4")
        cols = [(0.95, ["EB1", "EB2"]), (8.55, ["PIER"])]
        foot = []
        bottoms = {}
        for x, keys in cols:
            rows = []
            for key in keys:
                s = self.sup[key]
                rows += [("SPACER",), ("HEADING", "%s (1 REQUIRED)" % s.title), ("SPACER",)]
                for mark, e in s.table.items():
                    bar = next(b for b in s.bars if b["name"] == e["members"][0])
                    typ, sty_a, sty_g, dims = self.bar_fields(e, bar)
                    if e["varies"]:
                        ks = sorted(int(k) for k in e["lengths_in"])
                        length = "%s\\PTO\\P%s" % (fdot.ft_in_list(ks[0], 1), fdot.ft_in_list(ks[-1], 1))
                        if typ == "1":
                            dims["B"] = length
                        foot.append("%s %s: %s." % (s.title, mark, ", ".join(
                            "%d @ %s" % (n, fdot.bar_len(int(k))) for k, n in sorted(e["lengths_in"].items(),
                                                                                      key=lambda t: int(t[0])))))
                    else:
                        length = fdot.ft_in_list(int(next(iter(e["lengths_in"]))), 1)
                    cells = [dims.get(c, "") for c in ("B", "C", "D", "E", "F", "H", "J", "K")]
                    rows.append([e["size"], e["des"], length, e["count"], typ, sty_a, sty_g] + cells + ["", ""])
            bottoms[x] = sh.table(x, DRAW[3] - 0.05, None, self.BAR_HDR, rows, self.BAR_COLS, row_h=0.15)
        # the left form runs down to the sheet note, as on the FDOT bar list sheet
        x0 = cols[0][0]
        sh.blank_rows(x0, bottoms[x0], self.BAR_COLS, DRAW[1] + 0.4, 0.15)
        sh.ptext((x0, DRAW[1] + 0.3), "NOTE:", fdot.NOTE_IN, "TOP_LEFT", "TextStructures")
        sh.ptext((x0, DRAW[1] + 0.15), "FOR BAR BENDING DETAILS, REFER TO FDOT STANDARD PLANS INDEX 415-001.",
                 fdot.NOTE_IN, "TOP_LEFT", "TextStructures")
        xr = cols[1][0]
        y = bottoms[xr] - 0.35
        self._bending_diagrams(sh, xr, y)
        notes = ["TYP BAR AND STY ARE THE BAR TYPE AND HOOK STYLE OF STANDARD PLANS INDEX 415-001 (FY 2025-26): "
                 "TYPE 1 STRAIGHT (B = LENGTH), TYPE 4 CLOSED STIRRUP (B = HEIGHT, C = WIDTH), TYPE 11 U-BAR "
                 "(B = BASE, C AND D = LEGS); STYLE 5 = 135° STIRRUP HOOK.",
                 "OPEN STIRRUPS HAVE THEIR END LEGS TURNED IN PLAN TO CLEAR THE PILE AND MATCH NO STANDARD TYPE; "
                 "THEIR DIMENSION LETTERS REFER TO THE BENDING DIAGRAM ON THIS SHEET.",
                 "LENGTHS ARE THE MODEL CENTERLINE LENGTHS ROUNDED TO THE NEAREST INCH; BEND DIMENSIONS ARE "
                 "OUT-TO-OUT (SDM 4.3.10.C).",
                 ("VARYING LENGTHS: " + " ".join(foot)) if foot else "",
                 "PILES AND THE CHEEK LUG WELDED WIRE REINFORCEMENT ARE NOT INCLUDED IN THIS LIST."]
        sh.notes(xr, y - 1.45, "NOTES:", [n for n in notes if n], width_in=7.3)
        self.finish(sh)

    @staticmethod
    def bar_fields(e, bar):
        """(TYP BAR, STY A, STY G, {letter: FT-IN}) per Standard Plans Index
        415-001 (FY 2025-26): Type 1 straight, B = length; Type 11 U-bar,
        B = base, C and D = legs; Type 4 closed stirrup, B = height, C =
        width, hooks A and G style 5 (135 degrees).  Open stirrups with the
        end legs turned in plan match no standard type: no type, B to F along
        the bar as in the diagram on the sheet."""
        d = e["bend_dims"]
        name = barlib.shape_name(e)
        f = lambda x: fdot.ft_in_list(x, 0.25)  # noqa: E731
        if name == "STRAIGHT":
            return "1", "", "", {"B": fdot.ft_in_list(d[0]["len_in"], 1)}
        if name == "U-BAR":
            return "11", "", "", {"B": f(d[1]["len_in"]), "C": f(d[0]["len_in"]), "D": f(d[2]["len_in"])}
        if name == "CLOSED HOOP":
            # legs bounded by two 90-degree bends are the full out-to-out sides
            full = [x["len_in"] for x in d[1:-1] if not x["hook"]][:2]
            zs = [p[2] for p in bar["pts"]]
            height = (max(zs) - min(zs)) * 12.0 + bar["dia_in"]
            if abs(full[0] - height) > abs(full[1] - height):
                full = full[::-1]
            return "4", "5", "5", {"B": f(full[0]), "C": f(full[1])}
        return "", "", "", {c: f(x["len_in"]) for c, x in zip("BCDEF", d)}

    def _bending_diagrams(self, sh, x, y):
        """Bending diagram of the bars that match no Index 415-001 type."""
        sh.ptext((x, y), "OPEN STIRRUP (NOT TO SCALE)", fdot.NOTE_IN * 1.1, "TOP_LEFT", "TextStructures")
        L = "Rebar"
        t = lambda p, s, a: sh.ptext(p, s, 0.08, a, "TextStructures")  # noqa: E731
        ox, oy = x + 0.4, y - 1.05
        sh.pline([(ox, oy), (ox + 0.25, oy), (ox + 0.25, oy + 0.75), (ox + 1.25, oy + 0.75), (ox + 1.25, oy), (ox + 1.5, oy)], L)
        for p, s_, a in (((ox + 0.12, oy - 0.08), "B", "TOP_CENTER"), ((ox + 0.17, oy + 0.38), "C", "MIDDLE_RIGHT"),
                         ((ox + 0.75, oy + 0.83), "D", "BOTTOM_CENTER"), ((ox + 1.33, oy + 0.38), "E", "MIDDLE_LEFT"),
                         ((ox + 1.38, oy - 0.08), "F", "TOP_CENTER")):
            t(p, s_, a)
        t((ox + 1.9, oy + 0.5), "LEGS B AND F TURNED IN PLAN", "MIDDLE_LEFT")
        t((ox + 1.9, oy + 0.3), "TO CLEAR THE PILE", "MIDDLE_LEFT")

    # ------------------------------------------------------------------ run
    def build(self):
        for key in ("EB1", "PIER", "EB2"):
            self.plan_elevation(key)
            if key == "PIER":
                self.pier_details()
            else:
                self.eb_details(key)
        self.bar_list()
        if "Layout1" in self.doc.layouts:
            self.doc.layouts.delete("Layout1")
        return self.doc

    def qc(self):
        s1, sp, s2 = self.sup["EB1"], self.sup["PIER"], self.sup["EB2"]
        out = []

        def chk(name, model, ref, tol):
            out.append({"check": name, "model": round(model, 4), "reference": ref, "difference": round(model - ref, 4),
                        "tolerance": tol, "status": "PASS" if abs(model - ref) <= tol else "DIFFERS"})
        chk("Station CL pier", sp.station(sp.y0), WORKBOOK_CHECKS["station_pier"], 0.005)
        chk("Station FFBW End Bent 2", s2.station(s2.ffbw_y), WORKBOOK_CHECKS["station_ffbw_eb2"], 0.005)
        chk("Cap top End Bent 1", s1.cap_top, WORKBOOK_CHECKS["cap_top_eb1"], 0.001)
        chk("Cap top Pier", sp.cap_top, WORKBOOK_CHECKS["cap_top_pier"], 0.001)
        chk("Cap top End Bent 2", s2.cap_top, WORKBOOK_CHECKS["cap_top_eb2"], 0.001)
        for s, k in ((s1, "eb1"), (s2, "eb2")):
            chk("Backwall top at cap end %s" % s.title, s.backwall_top[0][1], WORKBOOK_CHECKS["backwall_end_" + k], 0.001)
            crown = z_on_edges(s.S["elev"], "backwall", 0.0)
            chk("Backwall top at PGL %s" % s.title, crown, WORKBOOK_CHECKS["backwall_pgl_" + k], 0.001)
        return out


def write_outputs(snapshot_path, out_dir):
    # Fixed ezdxf metadata (no creation/save timestamps or random GUIDs) so a
    # rebuild from the same snapshot is byte-identical and staleness is testable.
    import ezdxf
    keep = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    try:
        return _write_outputs(snapshot_path, out_dir)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = keep


def _write_outputs(snapshot_path, out_dir):
    snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    comp = Composer(snap)
    doc = comp.build()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dxf_path = out_dir / DXF_NAME
    # ezdxf adds DXF classes at save time from a set of entity types, whose
    # order follows the per-process string hash seed.  Register them now and
    # sort, so the CLASSES section (and the file) is reproducible.
    from collections import OrderedDict
    doc.classes.add_required_classes(doc.dxfversion)
    doc.classes.classes = OrderedDict(sorted(doc.classes.classes.items()))
    doc.saveas(dxf_path)
    reg = out_dir / "bar_mark_register.csv"
    with reg.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["support", "mark", "size", "designation", "description", "native_object", "native_label",
                    "model_mark", "centerline_length_in", "list_length_in"])
        for key, s in comp.sup.items():
            for b in sorted(s.bars, key=lambda b: (b["mark"], b["name"])):
                w.writerow([s.title, b["mark"], b["size"], b["des"], s.table[b["mark"]]["description"], b["name"],
                            b["label"], b["mark_model"], "%.3f" % b["length_in"], int(math.floor(b["length_in"] + 0.5))])
    layers = {}
    for e in doc.modelspace():
        layers[e.dxf.layer] = layers.get(e.dxf.layer, 0) + 1
    manifest = {
        "generator": "substructure_drawings.build", "version": GENERATOR_VERSION,
        "dxf": DXF_NAME, "dxf_sha256": sha256(dxf_path),
        "snapshot_sha256": sha256(snapshot_path), "model_sha256": snap["model_sha256"],
        "units": "international feet ($INSUNITS=2); model space 1:1",
        "station_reference": {"FFBW End Bent 1": STATION_FFBW_EB1},
        "sheets": [{"number": sh.number, "title": sh.title, "layout": sh.layout.name,
                    "scales": [k + "\" = 1'-0\"" for k in sh.scales]} for sh in comp.sheets],
        "levels_used": dict(sorted(layers.items())),
        "level_source": fdot.LEVEL_TABLE,
        "marks": {s.title: {m: {k: e[k] for k in ("size", "des", "description", "count", "lengths_in", "varies")}
                            for m, e in s.table.items()} for s in comp.sup.values()},
        "qc": comp.qc(),
        "layout_warnings": comp.warnings,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return dxf_path, manifest
