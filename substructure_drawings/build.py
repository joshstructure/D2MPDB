"""Build the end bent and pier DXF (one file, 14 sheets) from the snapshot.

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

GENERATOR_VERSION = "1.0.0"
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

RIGHT_COL = 11.95     # paper x where the table/notes column starts on plan sheets
MAIN = (DRAW[0], DRAW[1], 11.8, DRAW[3])


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
        p = self.info["sheet_prefix"]
        n = iter(range(1, 100))
        self.numbers = {k: [p + str(next(n)) for _ in range(c)] for k, c in (("EB1", 5), ("PIER", 4), ("EB2", 5), ("BARS", 1))}

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
        return "FOR REINFORCING BAR LIST SEE SHEET %s." % self.numbers["BARS"][0]

    # --------------------------------------------------- plan + elevation
    def plan_elevation(self, key):
        s = self.sup[key]
        nums = self.numbers[key]
        sh = self.new_sheet(nums[0], s.title)
        zone = sh.zone(MAIN, "3/8")
        b = Builder(s, self.doc)
        plan = b.plan(zone)
        zb = (s.cap_bot - 2.0, s.wall_bot + 0.5, 1.0, s.wall_bot - 1.25) if s.kind == "PIER" else None
        elev = b.elevation(zone, zb)
        L = -min(plan.local_bbox[0], elev.local_bbox[0])
        R = max(plan.local_bbox[2], elev.local_bbox[2])
        width = (L + R) / zone.sf * 12
        xc = MAIN[0] + max(0.0, (MAIN[2] - MAIN[0] - width) / 2) + L / zone.sf * 12
        plan.place(0.0, plan.local_bbox[3], xc, MAIN[3] - 0.05)
        ph = self.paper_size(plan)[1]
        eh = self.paper_size(elev)[1]
        gap = max(0.1, (MAIN[3] - MAIN[1] - 0.1 - ph - eh) / 2)
        elev.place(0.0, elev.local_bbox[3], xc, MAIN[3] - 0.05 - ph - gap)
        self.check(sh, plan)
        self.check(sh, elev)
        self._pe_tables(sh, s, b, top=DRAW[3] - 0.05)
        self.finish(sh)

    def _pe_tables(self, sh, s, b, top):
        x = RIGHT_COL
        y = top
        rows = [(l, d, fdot.elev(z)) for l, d, u, z in b.elev_points]
        y = sh.table(x, y, "TABLE OF ELEVATIONS", [("POINT", "LOCATION", "ELEVATION")], rows, [0.45, 2.35, 0.95])
        y -= 0.12
        if s.kind == "EB":
            body = []
            for row in s.pedestal_table():
                p = row["pedestal"]
                lines = row["lines"]
                back = max(lines, key=lambda t: t[0])
                front = min(lines, key=lambda t: t[0])
                bid = s.beam_id(s.bearings[0]["span"], p["line"])
                body.append((bid, fdot.elev(back[1]), fdot.elev(front[1]), fdot.elev(back[1]), fdot.elev(front[1])))
            y = sh.table(x, y, "TOP OF PEDESTAL ELEVATIONS", [("BEAM NO.", "EL. A", "EL. B", "EL. C", "EL. D")],
                         body, [0.75] * 5)
            sh.ptext((x, y - 0.06), "A, C AT FFBW EDGE; B, D AT SPAN EDGE; LEVEL TRANSVERSELY.", 0.065, "TOP_LEFT", "TextStructures")
        else:
            body = []
            for row in s.pedestal_table():
                p = row["pedestal"]
                zs = [z for _, z in sorted(row["lines"], key=lambda t: t[0])]
                body.append(("1-%d / 2-%d" % (p["line"], p["line"]),) + tuple(fdot.elev(z) for z in zs[:4]))
            y = sh.table(x, y, "TOP OF PEDESTAL ELEVATIONS", [("BEAMS", "EL. A", "EL. E", "EL. F", "EL. B")],
                         body, [0.95, 0.7, 0.7, 0.7, 0.7])
            sh.ptext((x, y - 0.06), "A AT SPAN 1 EDGE, B AT SPAN 2 EDGE, E/F PAD-END BREAKS.", 0.065, "TOP_LEFT", "TextStructures")
        y -= 0.3
        body = [(p["no"], "%.1f" % (math.floor(p["top"] * 10 + 0.5) / 10.0), fdot.ft_in(p["offset"], 0.125))
                for p in s.piles]
        y = sh.table(x, y, "PILE CUTOFF ELEVATIONS", [("PILE NO.", "CUTOFF EL.", "OFFSET FROM PGL")], body, [0.8, 1.2, 1.75])
        nums = self.numbers[s.key]
        notes = list(dict.fromkeys(b.notes))
        notes.append("FOR REINFORCEMENT ELEVATION SEE SHEET %s." % nums[1])
        if s.kind == "EB":
            notes.append("FOR SECTIONS A-A AND B-B SEE SHEET %s; FOR SECTION C-C AND PEDESTAL DETAILS SEE SHEET %s; "
                         "FOR VIEWS D-D AND E-E SEE SHEET %s." % (nums[2], nums[3], nums[4]))
            notes.append("THE SOIL REINFORCEMENT ATTACHED TO THE BACKWALL SHALL BE DESIGNED BY A SPECIALTY ENGINEER "
                         "FOR A SERVICE LOAD OF ___ K/FT AND A FACTORED LOAD OF ___ K/FT USING THE DESIGN CRITERIA FOR "
                         "PERMANENT MSE WALLS. COST OF FURNISHING AND INSTALLING THE SOIL REINFORCEMENT IS CONSIDERED "
                         "INCIDENTAL TO THE COST OF THE END BENT.")
        else:
            notes.append("FOR SECTIONS A-A, B-B AND C-C SEE SHEET %s; FOR PEDESTAL DETAILS AND VIEW D-D SEE SHEET %s."
                         % (nums[2], nums[3]))
            notes.append("PIER WALL IS PROVISIONAL (3'-0\" THICK); ITS REINFORCEMENT IS NOT SHOWN.")
        notes.append(self.bar_list_ref())
        notes.append("PILE OFFSETS ARE FROM THE PGL, + TO THE RIGHT LOOKING UP-STATION. CUTOFF ELEVATIONS ARE TO THE NEAREST 0.1 FT.")
        for q in self.qc():
            if q["status"] != "PASS" and s.title in q["check"].upper():
                notes.append("MODEL CHECK (REMOVE BEFORE ISSUE): %s IS %.3f IN THE CAD MODEL AND %.3f IN THE SELECTED "
                             "GEOMETRY CAD TABLES; RECONCILE BEFORE ISSUE." % (q["check"].upper(), q["model"], q["reference"]))
        sh.notes(x, y - 0.2, "NOTES:", notes, width_in=4.0)

    # ------------------------------------------------- reinforcement sheet
    def reinforcement(self, key):
        s = self.sup[key]
        nums = self.numbers[key]
        title = s.title + " REINFORCEMENT"
        sh = self.new_sheet(nums[1], title)
        zone = sh.zone(DRAW, "1/2")
        b = Builder(s, self.doc)
        v = b.reinforcement_elevation(zone)
        w, h = self.paper_size(v)
        # align the PGL (local x = 0) near the sheet centre, keep inside
        L = -v.local_bbox[0] / zone.sf * 12
        x = DRAW[0] + max(0.0, (DRAW[2] - DRAW[0] - w) / 2) + L
        v.place(0.0, v.local_bbox[3], x, DRAW[3] - 0.05)
        self.check(sh, v)
        notes = list(dict.fromkeys(b.notes)) + [
            "REINFORCEMENT IS SHOWN REPRESENTATIVELY: THE FIRST AND LAST BAR OF EACH SERIES ARE DRAWN.",
            "FOR SECTIONS A-A, B-B AND C-C SEE SHEETS %s AND %s." % (nums[2], nums[3]) if s.kind == "EB"
            else "FOR SECTIONS A-A, B-B AND C-C SEE SHEET %s." % nums[2],
            "FOR PEDESTAL REINFORCEMENT SEE SHEET %s." % nums[3],
            self.bar_list_ref()]
        sh.notes(11.3, min(3.0, self.paper_bbox(v)[1] - 0.15), "NOTES:", notes, width_in=4.6)
        self.finish(sh)

    # -------------------------------------------------------------- details
    def eb_details(self, key):
        s = self.sup[key]
        nums = self.numbers[key]
        b = Builder(s, self.doc)
        sh = self.new_sheet(nums[2], s.title + " DETAILS (1 OF 3)")
        z = sh.zone(DRAW, "3/4")
        va = b.section(z, "between_piles", "A", "(BETWEEN PILES)")
        vb = b.section(z, "at_pile", "B", "(AT PILE)")
        self.row(sh, [va, vb], DRAW[3] - 0.05, DRAW[0], DRAW[2], gap=0.1)
        # notes in the open corner above the bridge-side (MSE wall) half
        nx = 12.9 if key == "EB1" else 1.0
        sh.notes(nx, DRAW[3] - 0.05, "NOTES:", [
            "FOR LOCATION OF SECTIONS SEE SHEET %s." % nums[0],
            "ALL BARS ARE SHOWN IN SECTIONS; BARS IN THE SECTION PLANE ARE THE NEAREST BAR OF THEIR SERIES BEYOND THE CUT.",
            self.bar_list_ref()], width_in=3.1)
        self.finish(sh)
        sh = self.new_sheet(nums[3], s.title + " DETAILS (2 OF 3)")
        z = sh.zone(DRAW, "3/4")
        vc = b.section(z, "at_beam", "C", "(AT CL BEAM)")
        self.place_tl(vc, DRAW[0] + 0.2, DRAW[3] - 0.05)
        self.check(sh, vc)
        x_r = self.paper_bbox(vc)[2] + 0.5
        pp = b.pedestal_plan(z, s.pedestals[0])
        self.place_tl(pp, x_r, DRAW[3] - 0.05)
        pe = b.pedestal_elevation(z, s.pedestals[0])
        self.place_tl(pe, x_r, self.paper_bbox(pp)[1] - 0.3)
        self.check(sh, pp)
        self.check(sh, pe)
        sh.notes(x_r, self.paper_bbox(pe)[1] - 0.25, "NOTES:", [
            "FOR LOCATION OF SECTION C-C SEE SHEET %s." % nums[0],
            "PEDESTAL AT BEAM LINE 2 IS SIMILAR; BAR MARKS AS NOTED.",
            self.bar_list_ref()], width_in=4.0)
        self.finish(sh)
        sh = self.new_sheet(nums[4], s.title + " DETAILS (3 OF 3)")
        z = sh.zone(DRAW, "3/4")
        vd = b.cheek_view(z, s.cheeks[0], "D")
        ve = b.cheek_view(z, s.cheeks[-1], "E")
        self.row(sh, [vd, ve], DRAW[3] - 0.05, DRAW[0], 12.6, gap=0.8)
        sh.notes(12.95, DRAW[3] - 0.1, "NOTES:", [
            "FOR LOCATION OF VIEWS D-D AND E-E SEE SHEET %s." % nums[0],
            "WELDED WIRE REINFORCEMENT (WWR) 4x4-W1.4xW1.4 IN THE CHEEK LUGS (SHADED AREAS) SHALL BE TIED TO THE "
            "END BENT REINFORCING STEEL.",
            "FOR CHEEK TOP ELEVATIONS SEE THE TABLE OF ELEVATIONS, SHEET %s." % nums[0],
            self.bar_list_ref()], width_in=3.0)
        self.finish(sh)

    def pier_details(self):
        s = self.sup["PIER"]
        nums = self.numbers["PIER"]
        b = Builder(s, self.doc)
        sh = self.new_sheet(nums[2], "PIER DETAILS (1 OF 2)")
        z = sh.zone(DRAW, "3/4")
        va = b.section(z, "between_piles", "A", "(BETWEEN PILES)")
        vb = b.section(z, "at_pile", "B", "(AT PILE)")
        vc = b.section(z, "at_beam", "C", "(AT CL BEAM)")
        bottom = self.row(sh, [va, vb, vc], DRAW[3] - 0.05, DRAW[0], DRAW[2], gap=0.1)
        sh.notes(11.4, min(bottom - 0.2, 3.0), "NOTES:", [
            "FOR LOCATION OF SECTIONS SEE SHEET %s." % nums[0],
            "ALL BARS ARE SHOWN IN SECTIONS; BARS IN THE SECTION PLANE ARE THE NEAREST BAR OF THEIR SERIES BEYOND THE CUT.",
            "PIER WALL IS PROVISIONAL; ITS REINFORCEMENT IS NOT SHOWN.",
            self.bar_list_ref()], width_in=4.5)
        self.finish(sh)
        sh = self.new_sheet(nums[3], "PIER DETAILS (2 OF 2)")
        z = sh.zone(DRAW, "3/4")
        pp = b.pedestal_plan(z, s.pedestals[0])
        pe = b.pedestal_elevation(z, s.pedestals[0])
        zb = (s.cap_bot - 2.0, s.wall_bot + 0.5, 1.0, s.wall_bot - 1.25)
        ev = b.end_view(z, "D", zb)
        self.row(sh, [pp, pe, ev], DRAW[3] - 0.05, DRAW[0], DRAW[2], gap=0.5)
        sh.notes(DRAW[0] + 0.2, 3.6, "NOTES:", [
            "FOR LOCATION OF VIEW D-D SEE SHEET %s." % nums[0],
            "PEDESTAL AT BEAM LINE 2 IS SIMILAR; BAR MARKS AS NOTED.",
            "PIER WALL IS PROVISIONAL; ITS REINFORCEMENT IS NOT SHOWN.",
            self.bar_list_ref()], width_in=6.0)
        self.finish(sh)

    # -------------------------------------------------------------- bar list
    def bar_list(self):
        sh = self.new_sheet(self.numbers["BARS"][0], "REINFORCING BAR LIST")
        sh.zone(DRAW, "3/4")
        widths = [0.35, 0.4, 0.38, 0.62, 0.98, 0.5, 0.5, 0.5, 0.5, 0.55, 1.65]
        hdr = [("SIZE", "DES", "NO.", "LENGTH", "SHAPE", "A", "B", "C", "D", "E", "LOCATION")]
        cols = [(0.95, ["EB1", "EB2"]), (8.6, ["PIER"])]
        foot = []
        for x, keys in cols:
            y = 10.45
            for key in keys:
                s = self.sup[key]
                rows = []
                for mark, e in s.table.items():
                    dims = self.shape_dims(e)
                    if e["varies"]:
                        length = "VARIES"
                        foot.append("%s %s: %s." % (s.title, mark, ", ".join(
                            "%d @ %s" % (n, fdot.bar_len(int(k))) for k, n in sorted(e["lengths_in"].items(), key=lambda t: int(t[0])))))
                    else:
                        length = fdot.bar_len(int(next(iter(e["lengths_in"]))))
                    rows.append((e["size"], e["des"], e["count"], length, barlib.shape_name(e))
                                + tuple(dims + [""] * (5 - len(dims))) + (e["description"],))
                y = sh.table(x, y, "%s (1 REQUIRED)" % s.title, hdr, rows, widths, row_h=0.17)
                y -= 0.2
        self._bending_diagrams(sh, 8.7, 6.75)
        notes = ["BAR DIMENSIONS ARE OUT-TO-OUT (SDM 4.3.10.C); LENGTHS ARE THE MODEL CENTERLINE LENGTHS ROUNDED TO THE NEAREST INCH.",
                 "DIMENSION LETTERS REFER TO THE BENDING DIAGRAMS ON THIS SHEET. STANDARD PLANS INDEX 415-001 BAR TYPE NUMBERS "
                 "ARE NOT ASSIGNED; ASSIGN THEM WITH THE FDOT REBAR PROGRAM BEFORE ISSUE.",
                 "H IS THE STRAIGHT TAIL BEYOND EACH 135?? HOOK. OPEN STIRRUP LEGS A AND E ARE TURNED IN PLAN TO CLEAR THE PILE.",
                 ("VARYING LENGTHS: " + " ".join(foot)) if foot else "",
                 "PILES AND THE CHEEK LUG WELDED WIRE REINFORCEMENT ARE NOT INCLUDED IN THIS LIST."]
        sh.notes(8.7, 4.75, "NOTES:", [n for n in notes if n], width_in=7.2)
        self.finish(sh)

    @staticmethod
    def shape_dims(e):
        d = e["bend_dims"]
        name = barlib.shape_name(e)
        f = lambda x: fdot.ft_in(x / 12.0, 0.25)  # noqa: E731
        if name == "STRAIGHT":
            return [f(d[0]["len_in"])]
        if name == "CLOSED HOOP":
            # legs bounded by two 90-degree bends are the full out-to-out sides
            full = [x["len_in"] for x in d[1:-1] if not x["hook"]]
            return [f(full[0]), f(full[1]), "", "", "H=" + f(d[0]["len_in"])]
        return [f(x["len_in"]) for x in d[:5]]

    def _bending_diagrams(self, sh, x, y):
        """Schematic bending diagrams with dimension letters (not to scale)."""
        sh.ptext((x, y + 0.15), "BENDING DIAGRAMS (NOT TO SCALE)", 0.10, "BOTTOM_LEFT", "TextStructures")
        L = "Rebar"
        t = lambda p, s, a: sh.ptext(p, s, 0.08, a, "TextStructures")  # noqa: E731
        ox, oy = x + 0.3, y - 1.0
        sh.pline([(ox, oy + 0.7), (ox, oy), (ox + 1.2, oy), (ox + 1.2, oy + 0.7)], L)
        t((ox - 0.08, oy + 0.35), "A", "MIDDLE_RIGHT")
        t((ox + 0.6, oy - 0.08), "B", "TOP_CENTER")
        t((ox + 1.28, oy + 0.35), "C", "MIDDLE_LEFT")
        t((ox + 0.6, oy - 0.3), "U-BAR", "TOP_CENTER")
        ox = x + 2.3
        sh.pline([(ox, oy), (ox + 0.25, oy), (ox + 0.25, oy + 0.75), (ox + 1.25, oy + 0.75), (ox + 1.25, oy), (ox + 1.5, oy)], L)
        for p, s_, a in (((ox + 0.12, oy - 0.08), "A", "TOP_CENTER"), ((ox + 0.17, oy + 0.38), "B", "MIDDLE_RIGHT"),
                         ((ox + 0.75, oy + 0.83), "C", "BOTTOM_CENTER"), ((ox + 1.33, oy + 0.38), "D", "MIDDLE_LEFT"),
                         ((ox + 1.38, oy - 0.08), "E", "TOP_CENTER")):
            t(p, s_, a)
        t((ox + 0.75, oy - 0.3), "OPEN STIRRUP", "TOP_CENTER")
        ox = x + 4.7
        sh.pline([(ox + 0.3, oy + 0.6), (ox + 0.12, oy + 0.78), (ox, oy + 0.78), (ox, oy), (ox + 1.3, oy),
                  (ox + 1.3, oy + 0.78), (ox + 0.1, oy + 0.78), (ox + 0.28, oy + 0.6)], L)
        t((ox + 0.65, oy - 0.08), "A", "TOP_CENTER")
        t((ox + 1.38, oy + 0.39), "B", "MIDDLE_LEFT")
        t((ox + 0.42, oy + 0.55), "H", "MIDDLE_LEFT")
        t((ox + 0.65, oy - 0.3), "CLOSED HOOP (135?? HOOKS)", "TOP_CENTER")
        t((x + 0.3, oy - 0.55), "STRAIGHT BARS: A = LENGTH.", "TOP_LEFT")

    # ------------------------------------------------------------------ run
    def build(self):
        for key in ("EB1", "PIER", "EB2"):
            self.plan_elevation(key)
            self.reinforcement(key)
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
