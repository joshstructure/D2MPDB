"""Build the end bent and pier DXF (one file, 11 sheets) from the snapshot.

Usage: see ``scripts/build_substructure_dxf.py``.  The drawing rules are in
``STYLE_GUIDE.md`` (rule ids such as D5, E1 in the comments below).
"""
import csv
import hashlib
import json
import math
from pathlib import Path

from . import bars as barlib
from . import cad, details, fdot, strap_loads
from .sheets import DRAW, TITLE_TOP, Sheet
from .support import STATION_FFBW_EB1, Support
from .views import DELTA, Builder, z_on_edges

try:
    from . import anno_check
except ModuleNotFoundError as err:   # the annotation checker module is new; build without it if absent
    if err.name != __package__ + ".anno_check":
        raise
    anno_check = None

GENERATOR_VERSION = "2.5.0"
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
    # D-053 (2026-10-19): both backwall tops are two straight 2% slopes,
    # 4-1/4 in below the FFBW deck-top lines (B4_Geometry_CAD_Tables.xlsx,
    # Substructure, section F)
    "backwall_end_eb1": 47.111000000000004, "backwall_pgl_eb1": 47.30683333333334,
    "backwall_end_eb2": 47.123000000000005, "backwall_pgl_eb2": 47.31883333333334,
}

RIGHT_COL = 12.3      # paper x where the table/notes column starts on plan sheets
MAIN = (DRAW[0], DRAW[1], 12.15, DRAW[3])
# Sheets per support (E1): plan and elevation with the reinforcement (pier:
# with the end view), then the details (EB: (1 OF 3) sections A-A and B-B with
# the pedestal details, (2 OF 3) section C-C and the cheek views D-D and E-E,
# (3 OF 3) the cheek wall sections F-F and G-G and details "A" and "B"; pier:
# sections with the pedestal details), then the bar list.
SHEETS = (("EB1", 4), ("PIER", 3), ("EB2", 4), ("BARS", 1))
# TOP OF PEDESTAL ELEVATIONS table: column widths (BEAM NO., corners A-D), in
PED_COLS = [0.85, 0.7, 0.7, 0.7, 0.7]
NOTES_W = 5.0     # NOTES column beside a LEGEND column (sample B1-17), in
BRIDGE_X = 13.8   # the bridge number and name over the title block start here


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# The one documented exception to ByLevel symbology: hidden bearing pad edges
# keep the hidden linetype on BearingPadMisc, which has no hidden twin in the
# FDOT level table.
LINETYPE_OVERRIDES = {("BearingPadMisc", fdot.HIDDEN_LINETYPE)}


def dimension_blocks_by_level(doc):
    """ezdxf draws a dimension's lines, arrows and text into its block on
    layer 0 and adds definition points on Defpoints.  FDOT does not allow
    either for drawing elements (CADD Manual 5.10.1.3), so the block contents
    go onto the dimension's level, ByLayer, the arrowhead block onto the
    Dimension level, and the definition points (not plotted, not needed by
    AutoCAD or MicroStation) are dropped, as is the then empty Defpoints
    layer.  ezdxf also leaves zero-length LINE entities in the blocks (they
    plot as point markers, the "circles" of the B4-5 markup); they are
    deleted (rule F)."""
    for dim in doc.modelspace().query("DIMENSION"):
        blk = doc.blocks.get(dim.dxf.geometry)
        for e in list(blk):
            if e.dxftype() == "POINT" and e.dxf.layer == "Defpoints":
                blk.delete_entity(e)
                continue
            if e.dxftype() == "LINE" and (e.dxf.end - e.dxf.start).magnitude < 1e-9:
                blk.delete_entity(e)
                continue
            e.dxf.layer = dim.dxf.layer
            e.dxf.color = 256
            e.dxf.lineweight = -1
            e.dxf.linetype = "BYLAYER"
    # arrowhead blocks (_CLOSEDFILLED), inserted only by dimension blocks
    used = {e.dxf.name for blk in doc.blocks for e in blk.query("INSERT")}
    for blk in list(doc.blocks):
        if not blk.name.startswith("_"):
            continue
        if blk.name not in used:
            doc.blocks.delete_block(blk.name, safe=False)
            continue
        for e in blk:
            e.dxf.layer = "Dimension"
            e.dxf.color = 256
            e.dxf.lineweight = -1
            e.dxf.linetype = "BYLAYER"
    if "Defpoints" in doc.layers:
        doc.layers.remove("Defpoints")


def symbology_audit(doc):
    """ByLevel check of every entity in every block, layout and model space
    (CADD Manual 5.10.1.3): on an FDOT level (never 0 or Defpoints), color,
    lineweight and linetype ByLayer, apart from LINETYPE_OVERRIDES."""
    out = {"entities": 0, "not_on_fdot_level": [], "not_by_level": [], "documented_overrides": {}}
    for blk in doc.blocks:
        for e in blk:
            out["entities"] += 1
            layer = e.dxf.get("layer", "0")
            tag = "%s %s %s" % (blk.name, e.dxftype(), layer)
            if layer not in fdot.LEVELS:
                out["not_on_fdot_level"].append(tag)
            lt = e.dxf.get("linetype", "BYLAYER")
            if lt.upper() != "BYLAYER" and (layer, lt) in LINETYPE_OVERRIDES:
                key = "%s linetype %s (hidden pad edges; no FDOT hidden level)" % (layer, lt)
                out["documented_overrides"][key] = out["documented_overrides"].get(key, 0) + 1
            elif lt.upper() != "BYLAYER":
                out["not_by_level"].append(tag + " linetype " + lt)
            if e.dxf.get("color", 256) != 256 or e.dxf.hasattr("true_color"):
                out["not_by_level"].append(tag + " color")
            if e.dxf.get("lineweight", -1) != -1:
                out["not_by_level"].append(tag + " lineweight %d" % e.dxf.lineweight)
    out["layers"] = sorted(layer.dxf.name for layer in doc.layers)
    return out


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
        # E5: a title is centred on the thing it names (the view's
        # ``title_spec`` records the title position and, where the title has
        # a subject, the subject's centre, both in local feet)
        spec = getattr(view, "title_spec", None)
        if spec and spec.get("subject_cx") is not None:
            tol = 0.05 * view.sf / 12.0       # 0.05 in on paper
            off = spec["x"] - spec["subject_cx"]
            if abs(off) > tol:
                self.warnings.append("%s / %s: title off centre by %.2f in" %
                                     (sheet.number, view.name, abs(off) * 12.0 / view.sf))
        # annotation checks inside the view (STYLE_GUIDE A1, A2, A10, A11, B7,
        # B9, ...): every finding carries its rule id in brackets
        for message, count in view.audit():
            text = message.replace("\\P", " / ")
            if count > 1:
                text += " (%d)" % count
            self.__dict__.setdefault("annotation_overlaps", []).append(
                "%s / %s: %s" % (sheet.number, view.name, text))

    def _placed(self, sheet):
        return self.__dict__.setdefault("placed", {}).setdefault(sheet.number, [])

    def check_block(self, sheet, name, rect, margin=0.05, area=None):
        """Layout check of a paper-space block (notes, legend, table) given as
        (x0, y0, x1, y1) inches: inside the drawing window and ``margin``
        clear of the views and blocks placed before it (later views are
        checked against it by ``check``)."""
        a = area or DRAW
        if rect[0] < a[0] - 0.05 or rect[1] < a[1] - 0.05 or rect[2] > a[2] + 0.05 or rect[3] > a[3] + 0.05:
            self.warnings.append("%s / %s outside its window: (%.2f, %.2f)-(%.2f, %.2f) in" %
                                 ((sheet.number, name) + tuple(rect)))
        grown = (rect[0] - margin, rect[1] - margin, rect[2] + margin, rect[3] + margin)
        if cad.boxes_cross([grown], [sheet.bridge_block]):
            self.warnings.append("%s / %s runs into the BRIDGE NO. block" % (sheet.number, name))
        placed = self._placed(sheet)
        for other, theirs in placed:
            n = cad.boxes_cross([grown], theirs)
            if n:
                self.warnings.append("%s / %s is within %.2f in of %s (%d crossings)" %
                                     (sheet.number, name, margin, other.name, n))
        placed.append((type("Block", (), {"name": name})(), [tuple(rect)]))

    def slide_down(self, sheet, x0, x1, y_top, height, margin=0.2, step=0.05):
        """Highest top y at or below ``y_top`` where a block x0..x1 wide and
        ``height`` tall keeps ``margin`` from everything placed so far."""
        placed = self._placed(sheet)
        while y_top - height > DRAW[1]:
            grown = (x0 - margin, y_top - height - margin, x1 + margin, y_top + margin)
            if not any(cad.boxes_cross([grown], theirs) for _, theirs in placed):
                break
            y_top -= step
        return y_top

    def row(self, sheet, views, y_top, x0, x1, gap=0.3, align=True):
        """Place ``views`` side by side by their top-left corners, centred in
        x0..x1, and line their titles up on the lowest title baseline of the
        row (``align_titles``; ``align`` False leaves the titles where they
        are).  Returns the bottom y of the row."""
        widths = [self.paper_size(v)[0] for v in views]
        total = sum(widths) + gap * (len(views) - 1)
        x = x0 + max(0.0, (x1 - x0 - total) / 2)
        for v, w in zip(views, widths):
            self.place_tl(v, x, y_top)
            x += w + gap
        if align:
            self.align_titles(views)
        for v in views:
            self.check(sheet, v)
        return y_top - max(self.paper_size(v)[1] for v in views)

    @staticmethod
    def title_baseline(view):
        """Paper y (inches) of the baseline of a placed view's title, or None
        for a view without a title: the title's local y moved to the sheet
        (``View.title_spec``; same mapping as ``paper_bbox``)."""
        spec = getattr(view, "title_spec", None)
        if not spec:
            return None
        return (spec["y"] + view.oy - view.sheet.model_origin[1]) * 12.0 / view.sf

    def align_titles(self, views):
        """Line the titles of a row of views up vertically (markup
        2026-10-19, "Center the title on the drawing and line titles up
        vertically"; STYLE_GUIDE E5): every title goes down to the lowest
        title baseline of the row."""
        ys = [(v, self.title_baseline(v)) for v in views]
        ys = [(v, y) for v, y in ys if y is not None]
        if len(ys) < 2:
            return
        lowest = min(y for _, y in ys)
        for v, y in ys:
            if y - lowest > 1e-6:
                v.move_title((lowest - y) / 12.0 * v.sf)

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
        zb = (s.cap_bot - 2.0, s.wall_bot + 0.5, 0.7, s.wall_bot - 1.25) if s.kind == "PIER" else None
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
            notes.append("FOR SECTIONS A-A AND B-B AND DETAILS \"A\" AND \"B\", SEE SHEET %s. FOR SECTION C-C AND "
                         "VIEWS D-D AND E-E, SEE SHEET %s. FOR SECTIONS F-F AND G-G AND PEDESTAL DETAILS, SEE "
                         "SHEET %s." % (nums[1], nums[2], nums[3]))
            # the strap design paragraph is the LEGEND of the (1 OF 3) sheet,
            # once per bent (markup 2026-10-19: "Take out this note and only
            # have it once in the drawings per bent and in this case on the
            # next sheet"); here only the reference to it
            notes.append("FOR THE SOIL REINFORCEMENT (%s) LEGEND, SEE SHEET %s." % (DELTA, nums[1]))
        else:
            notes.append("FOR SECTIONS A-A, B-B AND C-C, SEE SHEET %s. FOR PEDESTAL DETAILS, SEE SHEET %s. FOR "
                         "LOCATION OF VIEW D-D, SEE PLAN." % (nums[1], nums[2]))
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
            # two lines: one would run past the table width (E2)
            note = "A AT SPAN 1 EDGE, B AT SPAN 2 EDGE,\\PE AND F AT THE PAD-END BREAKS."
        hdr = [(("BEAM NO.", 1, 2), ("ELEVATION (FEET)", 4)), (None,) + corners]
        y = sh.table(x, y_top, "TOP OF PEDESTAL ELEVATIONS", hdr, body, PED_COLS)
        lines = note.split("\\P")
        for i, line in enumerate(lines):
            sh.ptext((x, y - 0.08 - 0.11 * i), line, None, "TOP_LEFT", "TextStructures", style=fdot.SMALL_STYLE)
        return y - 0.2 - 0.11 * (len(lines) - 1)

    @staticmethod
    def _ped_table_height(s):
        """Height of the TOP OF PEDESTAL ELEVATIONS table with its note (title
        box, two header rows, one row per pedestal line, note lines)."""
        return (fdot.TABLE_TITLE_IN * (1.45 + 0.6) + 0.15 * (2 + len(s.pedestal_table())) + 0.2
                + (0.11 if s.kind == "PIER" else 0.0))

    def legend_notes(self, sh, b, x, y_top, x_end, items, min_w=NOTES_W, gap=0.3, legend=True):
        """NOTES: (left) and beside it, ``gap`` to its right and up to
        ``x_end``, the LEGEND: block of the Δ strap paragraph the views set in
        ``b.legend`` (D6; sample B1-17 has the legend beside the notes).  The
        width x..x_end is split where the taller block is shortest (the notes
        are at least ``min_w`` wide, the legend at least 3 in); without a
        strap legend, or with ``legend`` False (the legend is drawn once per
        bent, on its (1 OF 3) sheet), the notes take the full width.  The
        blocks may use the band down to 0.1 in above the title block.
        Returns the estimated bottom y."""
        area = (DRAW[0], TITLE_TOP + 0.1, DRAW[2], DRAW[3])
        leg = [DELTA + "  " + b.legend[DELTA]] if legend and DELTA in b.legend else []
        w = x_end - x
        if leg:
            total = x_end - x - gap
            best = None
            for k in range(int(round((total - 3.0 - min_w) / 0.1)) + 1):
                wn = round(min_w + 0.1 * k, 6)
                ln = sh.note_line_count(items, wn)
                ll = sh.note_line_count(leg, total - wn, numbered=False)
                if best is None or (max(ln, ll), ln + ll) < best[0]:
                    best = ((max(ln, ll), ln + ll), wn)
            if best is None:
                # too narrow for the two blocks side by side: the legend goes
                # under the notes, both at the full width
                bottom = sh.notes_bottom(y_top, items, w)
                sh.notes(x, y_top, "NOTES:", items, width_in=w)
                self.check_block(sh, "notes", (x, bottom, x + w, y_top), area=area)
                yl = bottom - 0.2
                lb = sh.notes_bottom(yl, leg, w, numbered=False)
                sh.notes(x, yl, "LEGEND:", leg, width_in=w, numbered=False)
                self.check_block(sh, "legend", (x, lb, x + w, yl), area=area)
                return lb
            w = best[1]
        bottom = sh.notes_bottom(y_top, items, w)
        sh.notes(x, y_top, "NOTES:", items, width_in=w)
        self.check_block(sh, "notes", (x, bottom, x + w, y_top), area=area)
        if leg:
            xl = x + w + gap
            lb = sh.notes_bottom(y_top, leg, x_end - xl, numbered=False)
            sh.notes(xl, y_top, "LEGEND:", leg, width_in=x_end - xl, numbered=False)
            self.check_block(sh, "legend", (xl, lb, x_end, y_top), area=area)
            bottom = min(bottom, lb)
        return bottom

    def eb_details(self, key):
        """The three details sheets of an end bent (E1): (1 OF 3) sections
        A-A and B-B with the pedestal details, (2 OF 3) section C-C and the
        cheek wall views, (3 OF 3) the cheek wall sections and details A, B."""
        s = self.sup[key]
        nums = self.numbers[key]
        b = Builder(s, self.doc)
        self._eb_sections(key, s, nums, b)
        self._eb_section_c(s, nums, b)
        self._eb_cheek_sections(s, nums, b)

    def _eb_sections(self, key, s, nums, b):
        # (1 OF 3): sections A-A and B-B, pedestal plan and elevation, pedestal
        # table (FDOT End Bent Details sheet configuration)
        # (1 OF 3): sections A-A and B-B with the closure context, and beside
        # them a column with DETAIL "A" (construction joint, 1 1/2") above
        # DETAIL "B" (V-groove and geotextile, 1"); the Δ legend under the
        # details, the notes under the sections.  EB2 (drawn mirrored, the MSE
        # wall on the left) is the mirror image of that arrangement.
        sh = self.new_sheet(nums[1], s.title + " DETAILS (1 OF 3)")
        z = sh.zone(DRAW, "3/4")
        va = b.section(z, "between_piles", "A", "(SECTION BETWEEN PILES)")
        vb = b.section(z, "at_pile", "B", "(SECTION AT PILES)")
        wd = 3.6      # the details column
        # (markup 2026-10-19 round 4, "Shift detail left to make room for the
        # annos in between the details" / "Shift detail over to make room for
        # annos in between detail": the sections' boxes stand 0.15 in apart
        # (the labels of one section and the dimension columns of the other
        # then keep 0.45 in between them); the details column starts 0.3 in
        # beyond the sections and takes what is left of the width, the
        # details centred in it and the legend wrapped to it, E1)
        gap = 0.15    # between the sections' bounding boxes
        sep = 0.3     # the details column to the sections
        if key == "EB1":
            self.row(sh, [va, vb], DRAW[3] - 0.05, DRAW[0], DRAW[2] - wd - 0.2, gap=gap)
            xs = max(self.paper_bbox(v)[2] for v in (va, vb)) + sep
            win_s = (DRAW[0], DRAW[1], xs, DRAW[3])
            xd0, xd1 = xs, DRAW[2]
        else:
            ws = self.paper_size(va)[0] + self.paper_size(vb)[0] + gap
            self.row(sh, [vb, va], DRAW[3] - 0.05, DRAW[2] - ws, DRAW[2], gap=gap)
            xs = min(self.paper_bbox(v)[0] for v in (va, vb)) - sep
            win_s = (xs, DRAW[1], DRAW[2], DRAW[3])
            xd0, xd1 = DRAW[0], xs
        z.window = win_s
        wA = (xd0, DRAW[3] - 3.5, xd1, DRAW[3])
        wB = (xd0, DRAW[3] - 6.6, xd1, DRAW[3] - 3.5)
        zA = sh.zone(wA, "1-1/2")
        da = details.detail_construction_joint(b, zA)
        self.place_tl(da, xd0 + (xd1 - xd0 - self.paper_size(da)[0]) / 2, DRAW[3] - 0.1)
        zB = sh.zone(wB, "1")
        db = details.detail_geotextile(b, zB, note=3)
        self.place_tl(db, xd0 + (xd1 - xd0 - self.paper_size(db)[0]) / 2, wB[3] - 0.15)
        for v in (da, db):
            self.check(sh, v)
        area = (DRAW[0], TITLE_TOP + 0.1, DRAW[2], DRAW[3])
        y = min(b0[1] for v in (va, vb) for b0 in v.paper_boxes()) - 0.06
        if DELTA in b.legend:
            leg = [DELTA + "  " + b.legend[DELTA]]
            yl, wl = self.paper_bbox(db)[1] - 0.3, xd1 - xd0 - 0.1
            lb = sh.notes_bottom(yl, leg, wl, numbered=False)
            sh.notes(xd0 + 0.05, yl, "LEGEND:", leg, width_in=wl, numbered=False)
            self.check_block(sh, "legend", (xd0 + 0.05, lb, xd1 - 0.05, yl), area=area)
            y = min(y, lb - 0.2)
        # the notes run the width of the sheet under the sections and the
        # details column, stopping short of the BRIDGE NO. block (E2)
        x_n = DRAW[0] + 0.1
        w_n = sh.bridge_block[0] - 0.2 - x_n
        items = [
            "FOR LOCATION OF SECTIONS, SEE SHEET %s." % nums[0],
            "ALL BARS ARE SHOWN IN SECTIONS; BARS IN THE SECTION PLANE ARE THE NEAREST BAR OF THEIR SERIES "
            "WITHIN 1'-3\" BEYOND THE CUT.",
            "ATTACH TYPE D-5 (SPECIFICATIONS SECTION 985) GEOTEXTILE FABRIC, 1'-0\" WIDE AND FULL HEIGHT OF FILL, TO "
            "THE BACK OF BACKWALL AT V-GROOVE LOCATIONS WITH AN ADHESIVE APPROVED BY THE ENGINEER.",
            "MODEL CHECK (REMOVE BEFORE ISSUE): DETAILS \"A\" AND \"B\" ARE SCHEMATIC; THE CONSTRUCTION JOINT KEY AND "
            "THE V-GROOVE LOCATIONS ARE NOT IN THE CAD MODEL.",
            # (the backwall cross-slope MODEL CHECK note is on the (2 OF 3)
            # sheet: this notes block fills the sheet to the title block)
            self.bar_list_ref()]
        bottom = sh.notes_bottom(y, items, w_n)
        sh.notes(x_n, y, "NOTES:", items, width_in=w_n)
        self.check_block(sh, "notes", (x_n, bottom, x_n + w_n, y), area=area)
        self.finish(sh)

    def _eb_section_c(self, s, nums, b):
        # (2 OF 3): section C-C (3/4") and the cheek wall views (1/2"); the
        # left cheek view D-D carries the flags of sections F-F and G-G (D8)
        sh = self.new_sheet(nums[2], s.title + " DETAILS (2 OF 3)")
        z = sh.zone(DRAW, "3/4")
        vc = b.section(z, "at_beam", "C", "(SECTION AT CENTERLINE OF BEAM)")
        self.place_tl(vc, DRAW[0] + 0.05, DRAW[3] - 0.05)
        xs = self.paper_bbox(vc)[2] + 0.2
        z.window = (DRAW[0], DRAW[1], xs, DRAW[3])
        self.check(sh, vc)
        # the cheek views at 3/8" (single-line bars, SDM 4.3.7.B): the two views
        # with their outside labels and section flags fit beside section C-C
        z2 = sh.zone((xs, DRAW[1], DRAW[2], DRAW[3]), "3/8")
        vd = b.cheek_view(z2, s.cheeks[0], "D", wwr_note=2, cuts=details.cheek_cut_marks(b, s.cheeks[0]))
        ve = b.cheek_view(z2, s.cheeks[-1], "E", wwr_note=2)
        bottom = self.row(sh, [vd, ve], DRAW[3] - 0.05, xs + 0.1, DRAW[2], gap=0.5)
        # the Δ strap LEGEND is drawn once per bent, on the (1 OF 3) sheet
        # (markup 2026-10-19); here a note refers to it
        self.legend_notes(sh, b, xs + 0.2, bottom - 0.25, DRAW[2] - 0.1, [
            "FOR LOCATION OF SECTION C-C AND VIEWS D-D AND E-E, SEE SHEET %s." % nums[0],
            "WELDED WIRE REINFORCEMENT (WWR) 4x4-W1.4xW1.4 IN THE CHEEK LUGS SHALL BE TIED TO THE "
            "END BENT REINFORCING STEEL.",
            "FOR CHEEK TOP ELEVATIONS, SEE THE TABLE OF ELEVATIONS, SHEET %s." % nums[0],
            "SECTIONS F-F AND G-G ARE LOCATED IN VIEW D-D; FOR SECTIONS F-F AND G-G, SEE SHEET %s." % nums[3],
            "FOR THE %s REINFORCING STRAP LEGEND, SEE SHEET %s." % (DELTA, nums[1]),
            # D14 (markup 2026-10-19 round 3 follow-up, "Check the model for all
            # the backwalls, there should be a slope of the top of the backwall
            # across the thickness of the wall"): the model's backwall tops
            # slope along the bent only; the sections draw the model.  (On this
            # sheet: the (1 OF 3) notes block fills its sheet to the title block.)
            "MODEL CHECK (REMOVE BEFORE ISSUE): THE BACKWALL TOP IS LEVEL ACROSS THE WALL THICKNESS IN THE CAD MODEL "
            "(ITS SLOPE RUNS ALONG THE BENT TO THE CROWN ONLY); THE SECTIONS SHOW THE MODEL. ADD THE CROSS SLOPE TO THE "
            "MODEL.",
            self.bar_list_ref()], legend=False)
        self.finish(sh)

    def _eb_cheek_sections(self, s, nums, b):
        # (3 OF 3): the cheek wall sections F-F and G-G (3/4") through the
        # left cheek wall, the pedestal plan right of them, the pedestal
        # elevation under G-G with the pedestal table beside it, the notes
        # below (the sections sheet has no room for the pedestal column)
        sh = self.new_sheet(nums[3], s.title + " DETAILS (3 OF 3)")
        top = DRAW[3] - 0.05
        z = sh.zone(DRAW, "3/4")
        vf = details.cheek_section_side(b, z, s.cheeks[0], "F", wwr_note=2)
        vg = details.cheek_section_top(b, z, s.cheeks[0], "G", wwr_note=2)
        pp = b.pedestal_plan(z, s.pedestals[0])
        pe = b.pedestal_elevation(z, s.pedestals[0])
        self.place_tl(vf, DRAW[0] + 0.1, top)
        xg = self.paper_bbox(vf)[2] + 0.4
        self.place_tl(vg, xg, top)
        xp = self.paper_bbox(vg)[2] + 0.4
        self.place_tl(pp, xp, top)
        self.place_tl(pe, xg, self.paper_bbox(vg)[1] - 0.3)
        for v in (vf, vg, pp, pe):
            self.check(sh, v)
        wt = sum(PED_COLS)
        x_t = max(xp, self.paper_bbox(pe)[2] + 0.3)
        h = self._ped_table_height(s)
        y_t = self.slide_down(sh, x_t, x_t + wt, self.paper_bbox(pp)[1] - 0.2, h, margin=0.2)
        y_b = self._ped_table(sh, s, x_t, y_t)
        if abs((y_t - y_b) - h) > 1e-6:
            self.warnings.append("%s / pedestal table height %.3f in, expected %.3f" % (sh.number, y_t - y_b, h))
        self.check_block(sh, "pedestal table", (x_t, y_b, x_t + wt, y_t), margin=0.2)
        y = min(self.paper_bbox(pe)[1], y_b) - 0.3
        w = DRAW[2] - xg - 0.1
        items = [
            "FOR LOCATION OF SECTIONS F-F AND G-G, SEE VIEW D-D, SHEET %s; SECTIONS F-F AND G-G SHOW THE LEFT CHEEK "
            "WALL, THE RIGHT CHEEK WALL IS SIMILAR (MIRRORED)." % nums[2],
            "WELDED WIRE REINFORCEMENT (WWR) 4x4-W1.4xW1.4 IN THE CHEEK LUGS SHALL BE TIED TO THE END BENT "
            "REINFORCING STEEL.",
            "CAP AND BACKWALL REINFORCEMENT IS NOT SHOWN IN SECTION F-F FOR CLARITY.",
            b.pedestal_marks_note(s.pedestals[0]),
            "PEDESTALS ARE CAST ON THE CAP; THE CAP TOP IS A CONSTRUCTION JOINT.",
            self.bar_list_ref()]
        # C9: backwall verticals standing inside a cheek wall next to its
        # verticals are drawn as modelled and reported for reconciliation
        clash = b.cage_clash_note()
        if clash:
            items.insert(-1, clash)
        bottom = sh.notes_bottom(y, items, w)
        sh.notes(xg, y, "NOTES:", items, width_in=w)
        self.check_block(sh, "notes", (xg, bottom, xg + w, y))
        self.finish(sh)

    def pier_details(self):
        """(1 OF 2): sections A-A, B-B and C-C in one row with their titles
        on one baseline (E5) and the notes below; (2 OF 2): the pedestal plan
        and elevation with the pedestal table (E1: the three sections with
        the common dimension rows of V18 fill the sheet height, so the
        pedestal details go to a further sheet instead of being squeezed)."""
        s = self.sup["PIER"]
        nums = self.numbers["PIER"]
        b = Builder(s, self.doc)
        sh = self.new_sheet(nums[1], "PIER DETAILS (1 OF 2)")
        z = sh.zone(DRAW, "3/4")
        va = b.section(z, "between_piles", "A", "(SECTION BETWEEN PILES)")
        vb = b.section(z, "at_pile", "B", "(SECTION AT PILES)")
        vc = b.section(z, "at_beam", "C", "(SECTION AT CENTERLINE OF BEAMS)")
        bottom = self.row(sh, [va, vb, vc], DRAW[3] - 0.05, DRAW[0], DRAW[2], gap=0.15)
        items = [
            "FOR LOCATION OF SECTIONS, SEE SHEET %s." % nums[0],
            "ALL BARS ARE SHOWN IN SECTIONS; BARS IN THE SECTION PLANE ARE THE NEAREST BAR OF THEIR SERIES "
            "WITHIN 1'-3\" BEYOND THE CUT.",
            "FOR PEDESTAL DETAILS, SEE SHEET %s." % nums[2],
            "PIER WALL IS PROVISIONAL; ITS REINFORCEMENT IS NOT SHOWN.",
            self.bar_list_ref()]
        x_n = DRAW[0] + 0.1
        w_n = sh.bridge_block[0] - 0.2 - x_n
        y = bottom - 0.3
        nb = sh.notes_bottom(y, items, w_n)
        sh.notes(x_n, y, "NOTES:", items, width_in=w_n)
        self.check_block(sh, "notes", (x_n, nb, x_n + w_n, y))
        self.finish(sh)
        # (2 OF 2): pedestal plan at the left, elevation beside it, the table
        # right of the elevation, the notes under the table
        sh = self.new_sheet(nums[2], "PIER DETAILS (2 OF 2)")
        z = sh.zone(DRAW, "3/4")
        pp = b.pedestal_plan(z, s.pedestals[0])
        pe = b.pedestal_elevation(z, s.pedestals[0])
        top = DRAW[3] - 0.1
        self.place_tl(pp, DRAW[0] + 0.1, top)
        self.place_tl(pe, self.paper_bbox(pp)[2] + 0.5, top - 0.15)
        for v in (pp, pe):
            self.check(sh, v)
        # the table under the pedestal elevation, the notes under the table
        wt = sum(PED_COLS)
        xt = self.paper_bbox(pe)[0]
        y_t = self.paper_bbox(pe)[1] - 0.35
        y = self._ped_table(sh, s, xt, y_t)
        items = [
            "FOR LOCATION OF THE PEDESTALS, SEE SHEET %s; FOR SECTIONS A-A, B-B AND C-C, SEE SHEET %s." % (nums[0], nums[1]),
            b.pedestal_marks_note(s.pedestals[0]),
            "PEDESTALS ARE CAST ON THE CAP; THE CAP TOP IS A CONSTRUCTION JOINT.",
            self.bar_list_ref()]
        w_n = min(7.0, DRAW[2] - xt - 0.05)
        nb = sh.notes_bottom(y - 0.25, items, w_n)
        sh.notes(xt, y - 0.25, "NOTES:", items, width_in=w_n)
        self.check_block(sh, "pedestal table", (xt, y, xt + wt, y_t), margin=0.2)
        self.check_block(sh, "notes", (xt, nb, xt + w_n, y - 0.25))
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
        sh.ptext((x0, DRAW[1] + 0.3), "NOTE:", None, "TOP_LEFT", "TextStructures")
        sh.ptext((x0, DRAW[1] + 0.15), "FOR BAR BENDING DETAILS, REFER TO FDOT STANDARD PLANS INDEX 415-001.",
                 None, "TOP_LEFT", "TextStructures")
        xr = cols[1][0]
        y = bottoms[xr] - 0.35
        notes = ["TYP BAR AND STY ARE THE BAR TYPE AND HOOK STYLE OF STANDARD PLANS INDEX 415-001 (FY 2026-27): "
                 "TYPE 1 STRAIGHT (B = LENGTH); TYPES 17 AND 18 STRAIGHT BARS WITH A STANDARD 90° HOOK (STYLE 3) AT "
                 "ONE OR BOTH ENDS (B = LENGTH OUT-TO-OUT); TYPE 11 U-BAR (B = BASE, C AND D = LEGS); TYPE 4 CLOSED "
                 "STIRRUP (B = HEIGHT, C = WIDTH); STYLES 4 AND 5 = 90° AND 135° STIRRUP HOOKS.",
                 "FIELD BEND OPEN STIRRUP HOOKS AS REQUIRED TO CLEAR PILE HEAD LOCATION.",
                 "LENGTHS ARE THE MODEL CENTERLINE LENGTHS ROUNDED TO THE NEAREST INCH; BEND DIMENSIONS ARE "
                 "OUT-TO-OUT (SDM 4.3.10.C).",
                 ("VARYING LENGTHS: " + " ".join(foot)) if foot else "",
                 "PILES AND THE CHEEK LUG WELDED WIRE REINFORCEMENT ARE NOT INCLUDED IN THIS LIST."]
        sh.notes(xr, y, "NOTES:", [n for n in notes if n], width_in=7.3)
        self.finish(sh)

    @staticmethod
    def bar_fields(e, bar):
        """(TYP BAR, STY A, STY G, {letter: FT-IN}) per Standard Plans Index
        415-001 (FY 2026-27), rule C6: every bar has a standard type.
        Type 1 straight, B = length; Type 17 straight bar with one standard
        90 degree hook (style 3 at A), B = out-to-out length of the long leg;
        Type 18 hooks at both ends (style 3 at A and G), B = out-to-out
        length between the hooks' legs; Type 11 U-bar, B = base, C and D =
        legs; Type 4 closed stirrup, B = height, C = width, hooks A and G
        style 5 (135 degrees).  An open stirrup is a Type 11 U-bar (B = top
        leg, C and D = the vertical legs) whose feet are standard 90 degree
        stirrup hooks (style 4 at A and G) field bent in plan to clear the
        pile; the feet are not dimensioned."""
        d = e["bend_dims"]
        name = barlib.shape_name(e)
        f = lambda x: fdot.ft_in_list(x, 0.25)  # noqa: E731
        if name == "STRAIGHT":
            return "1", "", "", {"B": fdot.ft_in_list(d[0]["len_in"], 1)}
        if name == "HOOKED":
            long_leg = d[1] if barlib._is_std_hook(e, 0) else d[0]
            return "17", "3", "", {"B": f(long_leg["len_in"])}
        if name == "HOOKED BOTH":
            return "18", "3", "3", {"B": f(d[1]["len_in"])}
        if name == "OPEN STIRRUP":
            return "11", "4", "4", {"B": f(d[2]["len_in"]), "C": f(d[1]["len_in"]), "D": f(d[3]["len_in"])}
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
        dimension_blocks_by_level(self.doc)
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
        "cadd_manual": fdot.CADD_MANUAL,
        "symbology_audit": symbology_audit(doc),
        "marks": {s.title: {m: {k: e[k] for k in ("size", "des", "description", "count", "lengths_in", "varies")}
                            for m, e in s.table.items()} for s in comp.sup.values()},
        "qc": comp.qc(),
        "layout_warnings": comp.warnings,
        # annotation findings, each "<sheet> / <view>: [rule id] message"; the
        # scripts print them as "NOTE (annotation check): ..." (STYLE_GUIDE A1)
        "annotation_overlaps": comp.__dict__.get("annotation_overlaps", []),
        "anno_rules_checked": list(anno_check.RULES) if anno_check is not None else [],
        # the loads in the Δ legend (data/strap_loads.json, from the selected backwall case)
        "strap_loads": strap_loads.load(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return dxf_path, manifest
