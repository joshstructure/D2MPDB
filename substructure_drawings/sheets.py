"""Paper-space sheets: 11 x 17 border, title block, viewport and tables.

The border follows the layout of the FDOT structures sheet border used in the
sample plan set (revisions, engineer of record, initials, DOT, sheet title,
project name, reference drawing and sheet number blocks; the 61G15-23.004
statement along the right edge).  It is an approximation for review: replace
it with the FDOT CADD structures border cell when the sheets are finalized in
MicroStation.  Fields not established in the project sources are left blank.
"""
import math

from ezdxf.enums import TextEntityAlignment

from . import fdot
from .cad import ATTACH, text_extent

W_IN, H_IN = 17.0, 11.0
FRAME = (0.80, 0.30, 16.20, 10.70)          # inches
TITLE_TOP = 1.10                           # top of title-block band
DRAW = (0.95, 1.30, 16.05, 10.55)          # usable drawing window
MODEL_PITCH_FT = 2000.0                    # model-space spacing between sheets


class Zone:
    """A paper window of a sheet drawn at one scale through one viewport.

    The zone's model-space region mirrors the paper window at the zone scale,
    so views placed by paper coordinates appear exactly there on the sheet.
    """

    def __init__(self, sheet, k, window, scale_key):
        self.sheet, self.window, self.scale_key = sheet, window, scale_key
        self.sf = fdot.SCALES[scale_key]
        self.model_origin = (sheet.index * MODEL_PITCH_FT, k * 600.0)

    def paper_to_model(self, px, py):
        return (self.model_origin[0] + px / 12.0 * self.sf, self.model_origin[1] + py / 12.0 * self.sf)


class Sheet:
    def __init__(self, doc, index, number, title, info):
        self.doc, self.index, self.number, self.title = doc, index, number, title
        self.info = info
        self.zones = []
        name = ("%s %s" % (number, title)).replace("/", "-")
        self.layout = doc.layouts.new(name)
        self.layout.page_setup(size=(W_IN, H_IN), margins=(0, 0, 0, 0), units="inch", scale=(12, 1),
                               name="FDOT_11x17")
        lay = self.layout.dxf_layout.dxf
        lay.limmin = (0, 0)
        lay.limmax = (W_IN / 12.0, H_IN / 12.0)
        for vp in self.layout.viewports():  # the paper-space main viewport
            vp.dxf.layer = "ClipBorder_dp"
        self.psp = self.layout

    def zone(self, window, scale_key):
        z = Zone(self, len(self.zones), window, scale_key)
        self.zones.append(z)
        return z

    @property
    def scales(self):
        return sorted({z.scale_key for z in self.zones}, key=lambda k: -fdot.SCALES[k])

    # ------------------------------------------------------------ helpers

    @staticmethod
    def P(px, py):
        return (px / 12.0, py / 12.0)

    def pline(self, pts, layer="Border", closed=False, lw=None):
        e = self.psp.add_lwpolyline([self.P(*p) for p in pts], close=closed, dxfattribs={"layer": layer})
        if lw is not None:
            e.dxf.lineweight = lw
        return e

    def ptext(self, p, s, h_in=fdot.TEXT_IN, align="BOTTOM_LEFT", layer="Border", rot=0.0, style=None, lw=None):
        if "\\S" in s:
            return self.pmtext(p, s, h_in, ATTACH[align], layer=layer)
        st = style or fdot.TEXT_STYLE
        e = self.psp.add_text(s, height=h_in / 12.0, rotation=rot,
                              dxfattribs={"layer": layer, "style": st,
                                          "oblique": 0.0 if st == fdot.SERIF_STYLE else fdot.OBLIQUE})
        e.set_placement(self.P(*p), align=TextEntityAlignment[align])
        if lw:
            e.dxf.lineweight = lw
        return e

    def pmtext(self, p, s, h_in=fdot.TEXT_IN, attach=1, width_in=None, layer="TextStructures"):
        e = self.psp.add_mtext(s, dxfattribs={"layer": layer, "style": fdot.TEXT_STYLE,
                                              "char_height": h_in / 12.0, "attachment_point": attach})
        e.dxf.insert = self.P(*p)
        if width_in:
            e.dxf.width = width_in / 12.0
        return e

    def heading(self, p, s, h_in=fdot.NOTE_IN * 1.25):
        """Underlined heading (NOTES:, LEGEND:) at its top-left corner."""
        self.ptext(p, s, h_in, "TOP_LEFT", "TextStructures")
        w = text_extent(s, h_in)
        self.pline([(p[0], p[1] - h_in * 1.25), (p[0] + w, p[1] - h_in * 1.25)], "TextStructures")

    # ---------------------------------------------------------- viewports
    def add_viewports(self):
        for z in self.zones:
            x0, y0, x1, y1 = z.window
            c = ((x0 + x1) / 2, (y0 + y1) / 2)
            self.psp.add_viewport(center=self.P(*c), size=((x1 - x0) / 12.0, (y1 - y0) / 12.0),
                                  view_center_point=z.paper_to_model(*c),
                                  view_height=(y1 - y0) / 12.0 * z.sf,
                                  dxfattribs={"layer": "ClipBorder_dp"})

    # ------------------------------------------------------------ border
    def border(self):
        info = self.info
        x0, y0, x1, y1 = FRAME
        self.pline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True, lw=50)
        t = TITLE_TOP
        self.pline([(x0, t), (x1, t)], lw=35)
        # column boundaries (inches) after the sample border proportions
        c_rev, c_eor, c_init, c_dot, c_title, c_no = 0.80, 6.60, 8.90, 9.50, 11.63, 15.58
        for c in (c_eor, c_init, c_dot, c_title, c_no):
            self.pline([(c, y0), (c, t)])
        s = 0.055
        # revisions
        self.ptext(((c_rev + c_eor) / 2, t - 0.11), "REVISIONS", 0.07, "BOTTOM_CENTER")
        self.pline([(c_rev, t - 0.13), (c_eor, t - 0.13)])
        self.pline([(c_rev, t - 0.23), (c_eor, t - 0.23)])
        half = (c_rev + c_eor) / 2
        for base in (c_rev, half):
            for off, lab in ((0.25, "DATE"), (0.62, "BY"), (1.75, "DESCRIPTION")):
                self.ptext((base + off, t - 0.21), lab, s, "BOTTOM_CENTER")
            for dx in (0.5, 0.75):
                self.pline([(base + dx, y0), (base + dx, t - 0.13)])
        self.pline([(half, y0), (half, t - 0.13)])
        # engineer of record (61G15-23 block) - left blank for the EOR
        eor = info.get("eor_lines") or ["ENGINEER OF RECORD:", "", "", ""]
        for i, line in enumerate(eor):
            self.ptext((c_eor + 0.06, t - 0.16 - i * 0.15), line, 0.07)
        # initials
        labels = ["DRAWN BY:", "CHECKED BY:", "DESIGNED BY:", "CHECKED BY:"]
        hh = (t - y0) / 4
        for i, lab in enumerate(labels):
            yy = t - i * hh
            self.pline([(c_init, yy), (c_dot, yy)])
            self.ptext(((c_init + c_dot) / 2, yy - 0.07), lab, 0.04, "BOTTOM_CENTER")
        # DOT block (upright serif, as the FDOT border cell)
        self.ptext(((c_dot + c_title) / 2, t - 0.20), "STATE OF FLORIDA", 0.075, "BOTTOM_CENTER",
                   style=fdot.SERIF_STYLE)
        self.ptext(((c_dot + c_title) / 2, t - 0.34), "DEPARTMENT OF TRANSPORTATION", 0.075, "BOTTOM_CENTER",
                   style=fdot.SERIF_STYLE)
        self.pline([(c_dot, t - 0.43), (c_title, t - 0.43)])
        self.pline([(c_dot, t - 0.53), (c_title, t - 0.53)])
        cols = [c_dot, c_dot + 0.55, c_dot + 1.25, c_title]
        for c in cols[1:-1]:
            self.pline([(c, y0), (c, t - 0.43)])
        for (a, b), lab, val in zip(zip(cols, cols[1:]), ("ROAD NO.", "COUNTY", "FINANCIAL PROJECT ID"),
                                    (info.get("road", ""), info.get("county", ""), info.get("fpid", ""))):
            self.ptext(((a + b) / 2, t - 0.51), lab, s, "BOTTOM_CENTER")
            self.ptext(((a + b) / 2, y0 + 0.12), val, 0.07, "BOTTOM_CENTER")
        # sheet title / project name
        mid = (y0 + t) / 2
        self.pline([(c_title, mid), (c_no, mid)])
        self.ptext((c_title + 0.04, t - 0.08), "SHEET TITLE:", s)
        self.ptext(((c_title + c_no) / 2, mid + 0.12), self.title, 0.10, "BOTTOM_CENTER")
        self.ptext((c_title + 0.04, mid - 0.08), "PROJECT NAME:", s)
        self.ptext(((c_title + c_no) / 2, y0 + 0.10), info.get("project", ""), 0.09, "BOTTOM_CENTER")
        # ref dwg / sheet no
        self.pline([(c_no, mid), (x1, mid)])
        self.pline([(c_no, mid + 0.12), (x1, mid + 0.12)])
        self.pline([(c_no, y0 + 0.17), (x1, y0 + 0.17)])
        self.ptext(((c_no + x1) / 2, t - 0.08), "REF. DWG. NO.", s, "BOTTOM_CENTER")
        self.ptext(((c_no + x1) / 2, mid - 0.08), "SHEET NO.", s, "BOTTOM_CENTER")
        self.ptext(((c_no + x1) / 2, y0 + 0.04), self.number, 0.10, "BOTTOM_CENTER", layer="TextStructShtNo")
        # bridge number and name above the title block (SDM 2.2.D)
        h = fdot.BRIDGE_NO_IN
        self.ptext((x1 - 0.05, t + 0.08 + 1.45 * h), "BRIDGE NO. %s" % (info.get("bridge_no") or "______"), h,
                   "BOTTOM_RIGHT")
        self.ptext((x1 - 0.05, t + 0.08), info.get("bridge_name", ""), h, "BOTTOM_RIGHT")
        # 61G15-23.004 statement outside the right border
        self.ptext((x1 + 0.22, (y0 + y1) / 2),
                   "THE OFFICIAL RECORD OF THIS SHEET IS THE ELECTRONIC FILE DIGITALLY SIGNED AND SEALED UNDER RULE 61G15-23.004, F.A.C.",
                   0.07, "MIDDLE_CENTER", rot=90.0)
        # plot stamp outside the left border: file and source model (no clock
        # time, so a rebuild from the same snapshot is byte-identical)
        stamp = info.get("stamp") or []
        for i, line in enumerate(stamp):
            self.ptext((x0 - 0.12 - 0.08 * i, y0 + 0.05), line, 0.04, "BOTTOM_LEFT", rot=90.0)
        # draft status (not for construction)
        self.ptext((x0 + 0.05, y1 + 0.06), info.get("status", ""), 0.08, "BOTTOM_LEFT")

    # ------------------------------------------------------------ tables
    def _box(self, x0, y0, x1, y1, lw=None):
        self.pline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "Tables", closed=True, lw=lw)

    def _cell_text(self, x0, x1, y0, y1, val, h_in, align="CENTER"):
        lines = str(val).split("\\P")
        n = len(lines)
        for i, line in enumerate(lines):
            yc = (y0 + y1) / 2 + ((n - 1) / 2 - i) * 1.45 * h_in
            if align == "LEFT":
                self.ptext((x0 + 0.06, yc), line, h_in, "MIDDLE_LEFT", "Tables")
            else:
                self.ptext(((x0 + x1) / 2, yc), line, h_in, "MIDDLE_CENTER", "Tables")

    def table(self, x, y_top, title, headers, rows, widths, row_h=0.15, h_in=fdot.TEXT_IN, title_h=None):
        """Boxed table in the FDOT sheet style (paper inches): a title box in
        larger italic lettering (lines split with \\P), header rows, thin cell
        rules and centered values.  Returns the bottom y.

        A header cell is text, (text, colspan) or (text, colspan, rowspan);
        None marks a cell covered by a span.  A body row is a list of values
        (a value with \\P lines makes the row taller), ("HEADING", text) for a
        full-width component heading or ("SPACER",) for a blank row."""
        total = sum(widths)
        edges = [x]
        for w in widths:
            edges.append(edges[-1] + w)
        y = y_top
        if title:
            th = title_h or fdot.TABLE_TITLE_IN
            n = title.count("\\P") + 1
            hh = th * (1.45 * n + 0.6)
            self._box(x, y, x + total, y - hh, lw=35)
            self._cell_text(x, x + total, y - hh, y, title, th)
            y -= hh
        covered = set()
        for r, hdr in enumerate(headers):
            c = 0
            for cell in hdr:
                if cell is None:  # position covered by a span from above
                    c += 1
                    continue
                while (r, c) in covered:
                    c += 1
                txt, cs, rs = (cell, 1, 1) if isinstance(cell, str) else (tuple(cell) + (1, 1))[:3]
                for dr in range(rs):
                    for dc in range(cs):
                        covered.add((r + dr, c + dc))
                x0, x1 = edges[c], edges[c + cs]
                self._box(x0, y - r * row_h, x1, y - (r + rs) * row_h)
                if txt:
                    self._cell_text(x0, x1, y - (r + rs) * row_h, y - r * row_h, txt, h_in * 0.9)
                c += cs
        y -= row_h * len(headers)
        if headers:
            self.pline([(x, y), (x + total, y)], "Tables", lw=35)
        for row in rows:
            if row and row[0] == "SPACER":
                self._box(x, y, x + total, y - row_h)
                y -= row_h
                continue
            if row and row[0] == "HEADING":
                hh = row_h * 1.25
                self._box(x, y, x + total, y - hh)
                self._cell_text(x, x + total, y - hh, y, row[1], fdot.TABLE_TITLE_IN * 0.9, "LEFT")
                y -= hh
                continue
            n = max(str(v).count("\\P") + 1 for v in row if v not in (None, "")) if any(
                v not in (None, "") for v in row) else 1
            hgt = max(row_h, row_h + (n - 1) * 1.45 * h_in)
            for (x0, x1), val in zip(zip(edges, edges[1:]), row):
                self._box(x0, y, x1, y - hgt)
                if val not in (None, ""):
                    self._cell_text(x0, x1, y - hgt, y, val, h_in)
            y -= hgt
        self._box(x, y_top, x + total, y, lw=35)
        return y

    def blank_rows(self, x, y_top, widths, y_min, row_h):
        """Empty form rows below a table down to y_min (FDOT bar list form)."""
        edges = [x]
        for w in widths:
            edges.append(edges[-1] + w)
        y = y_top
        while y - row_h >= y_min - 1e-9:
            for x0, x1 in zip(edges, edges[1:]):
                self._box(x0, y, x1, y - row_h)
            y -= row_h
        self.pline([(x, y_top), (x, y), (edges[-1], y), (edges[-1], y_top)], "Tables", lw=35)
        return y

    def notes(self, x, y_top, heading, items, width_in=4.4, h_in=fdot.NOTE_IN, numbered=True):
        """NOTES: (underlined heading) and numbered notes with hanging indent."""
        self.heading((x, y_top), heading)
        lines = []
        for i, it in enumerate(items, 1):
            lines.append(("%d. %s" % (i, it)) if numbered else it)
        # hanging indent: wrapped lines start under the note text; MTEXT
        # paragraph indents are multiples of the text height
        m = self.pmtext((x, y_top - 0.24), "\\pxi-2.6,l2.6;" + "\\P".join(lines), h_in, attach=1, width_in=width_in)
        return m
