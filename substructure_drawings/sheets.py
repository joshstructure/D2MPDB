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
CLIP_MARGIN = 0.08                          # viewport clip beyond DRAW
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
        # the BRIDGE NO. / bridge name block above the title block (paper
        # inches), which notes and views at the lower right must keep clear
        h = fdot.TITLE_IN
        self.bridge_block = (FRAME[2] - 0.05 - max(text_extent(s, h) for s in self.bridge_lines()),
                             TITLE_TOP + 0.08, FRAME[2] - 0.05, TITLE_TOP + 0.08 + 2.45 * h)

    def bridge_lines(self):
        return ["BRIDGE NO. %s" % (self.info.get("bridge_no") or "______"), self.info.get("bridge_name", "")]

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

    def pline(self, pts, layer="Border", closed=False, width=None):
        """Paper-space polyline; ``width`` (inches) draws a heavy outline as
        a constant-width polyline, so the lineweight stays ByLevel."""
        e = self.psp.add_lwpolyline([self.P(*p) for p in pts], close=closed, dxfattribs={"layer": layer})
        if width:
            e.dxf.const_width = width / 12.0
        return e

    def ptext(self, p, s, h_in=None, align="BOTTOM_LEFT", layer="Border", rot=0.0, style=None):
        """Paper-space text in an FDOT text style (default FDOT Structures);
        the height is the style's unless ``h_in`` is given (border cell)."""
        style = style or fdot.TEXT_STYLE
        h_in = h_in or fdot.style_in(style)
        s = fdot.font_text(s)
        if "\\S" in s:
            return self.pmtext(p, s, h_in, ATTACH[align], layer=layer, style=style)
        e = self.psp.add_text(s, height=h_in / 12.0, rotation=rot, dxfattribs={"layer": layer, "style": style})
        e.set_placement(self.P(*p), align=TextEntityAlignment[align])
        return e

    def pmtext(self, p, s, h_in=None, attach=1, width_in=None, layer="TextStructures", style=None):
        style = style or fdot.TEXT_STYLE
        h_in = h_in or fdot.style_in(style)
        e = self.psp.add_mtext(fdot.font_text(s), dxfattribs={
            "layer": layer, "style": style, "char_height": h_in / 12.0, "attachment_point": attach,
            "line_spacing_factor": fdot.MTEXT_LINE_SPACING})
        e.dxf.insert = self.P(*p)
        if width_in:
            e.dxf.width = width_in / 12.0
        return e

    def heading(self, p, s, style=fdot.HEADING_STYLE):
        """Underlined heading (NOTES:, LEGEND:) at its top-left corner."""
        h_in = fdot.style_in(style)
        self.ptext(p, s, None, "TOP_LEFT", "TextStructures", style=style)
        w = text_extent(s, h_in)
        self.pline([(p[0], p[1] - h_in * 1.25), (p[0] + w, p[1] - h_in * 1.25)], "TextStructures")

    # ---------------------------------------------------------- viewports
    def add_viewports(self):
        """One viewport per zone.  Edges on the drawing-window boundary clip
        CLIP_MARGIN outside it (still inside the frame): the layout check
        lets a view pass its window by 0.05", and text widths are estimated."""
        for z in self.zones:
            x0, y0, x1, y1 = z.window
            m = CLIP_MARGIN
            x0, y0 = x0 - m * (abs(x0 - DRAW[0]) < 1e-9), y0 - m * (abs(y0 - DRAW[1]) < 1e-9)
            x1, y1 = x1 + m * (abs(x1 - DRAW[2]) < 1e-9), y1 + m * (abs(y1 - DRAW[3]) < 1e-9)
            c = ((x0 + x1) / 2, (y0 + y1) / 2)
            self.psp.add_viewport(center=self.P(*c), size=((x1 - x0) / 12.0, (y1 - y0) / 12.0),
                                  view_center_point=z.paper_to_model(*c),
                                  view_height=(y1 - y0) / 12.0 * z.sf,
                                  dxfattribs={"layer": "ClipBorder_dp"})

    # ------------------------------------------------------------ border
    def border(self):
        """Border cell: the cell lettering in FDOT Imprint (CADD Manual 5.12:
        "used mainly within the FDOT sheet border") sized to its cell; the
        fields in the FDOT_SHEET_* text styles."""
        info = self.info
        x0, y0, x1, y1 = FRAME
        self.pline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True, width=0.02)
        t = TITLE_TOP
        self.pline([(x0, t), (x1, t)], width=0.014)
        # column boundaries (inches) after the sample border proportions
        c_rev, c_eor, c_init, c_dot, c_title, c_no = 0.80, 6.60, 8.90, 9.50, 11.63, 15.58
        for c in (c_eor, c_init, c_dot, c_title, c_no):
            self.pline([(c, y0), (c, t)])
        s = 0.055
        cell = fdot.BORDER_STYLE

        def label(p, txt, h_in=s, align="BOTTOM_LEFT"):
            self.ptext(p, txt, h_in, align, style=cell)
        # revisions
        label(((c_rev + c_eor) / 2, t - 0.11), "REVISIONS", 0.07, "BOTTOM_CENTER")
        self.pline([(c_rev, t - 0.13), (c_eor, t - 0.13)])
        self.pline([(c_rev, t - 0.23), (c_eor, t - 0.23)])
        half = (c_rev + c_eor) / 2
        for base in (c_rev, half):
            for off, lab in ((0.25, "DATE"), (0.62, "BY"), (1.75, "DESCRIPTION")):
                label((base + off, t - 0.21), lab, s, "BOTTOM_CENTER")
            for dx in (0.5, 0.75):
                self.pline([(base + dx, y0), (base + dx, t - 0.13)])
        self.pline([(half, y0), (half, t - 0.13)])
        # engineer of record (61G15-23 block) - left blank for the EOR
        eor = info.get("eor_lines") or ["ENGINEER OF RECORD:", "", "", ""]
        for i, line in enumerate(eor):
            self.ptext((c_eor + 0.06, t - 0.16 - i * 0.15), line, style=fdot.SMALL_STYLE)
        # initials
        labels = ["DRAWN BY:", "CHECKED BY:", "DESIGNED BY:", "CHECKED BY:"]
        hh = (t - y0) / 4
        for i, lab in enumerate(labels):
            yy = t - i * hh
            self.pline([(c_init, yy), (c_dot, yy)])
            label(((c_init + c_dot) / 2, yy - 0.07), lab, 0.04, "BOTTOM_CENTER")
        # DOT block
        label(((c_dot + c_title) / 2, t - 0.20), "STATE OF FLORIDA", 0.065, "BOTTOM_CENTER")
        label(((c_dot + c_title) / 2, t - 0.34), "DEPARTMENT OF TRANSPORTATION", 0.065, "BOTTOM_CENTER")
        self.pline([(c_dot, t - 0.43), (c_title, t - 0.43)])
        self.pline([(c_dot, t - 0.53), (c_title, t - 0.53)])
        cols = [c_dot, c_dot + 0.55, c_dot + 1.25, c_title]
        for c in cols[1:-1]:
            self.pline([(c, y0), (c, t - 0.43)])
        for (a, b), lab, val, st in zip(zip(cols, cols[1:]), ("ROAD NO.", "COUNTY", "FINANCIAL PROJECT ID"),
                                        (info.get("road", ""), info.get("county", ""), info.get("fpid", "")),
                                        ("FDOT_SHEET_SR", "FDOT_SHEET_COUNTY", "FDOT_SHEET_FPID")):
            label(((a + b) / 2, t - 0.51), lab, 0.04, "BOTTOM_CENTER")
            self.ptext(((a + b) / 2, y0 + 0.12), val, None, "BOTTOM_CENTER", style=st)
        # sheet title / project name
        mid = (y0 + t) / 2
        self.pline([(c_title, mid), (c_no, mid)])
        label((c_title + 0.04, t - 0.08), "SHEET TITLE:")
        self.ptext(((c_title + c_no) / 2, mid + 0.10), self.title, None, "BOTTOM_CENTER", style=fdot.SHEET_TITLE_STYLE)
        label((c_title + 0.04, mid - 0.08), "PROJECT NAME:")
        self.ptext(((c_title + c_no) / 2, y0 + 0.10), info.get("project", ""), None, "BOTTOM_CENTER",
                   style=fdot.HEADING_STYLE)
        # ref dwg / sheet no
        self.pline([(c_no, mid), (x1, mid)])
        self.pline([(c_no, mid + 0.12), (x1, mid + 0.12)])
        self.pline([(c_no, y0 + 0.17), (x1, y0 + 0.17)])
        label(((c_no + x1) / 2, t - 0.08), "REF. DWG. NO.", 0.045, "BOTTOM_CENTER")
        label(((c_no + x1) / 2, mid - 0.08), "SHEET NO.", 0.045, "BOTTOM_CENTER")
        self.ptext(((c_no + x1) / 2, y0 + 0.04), self.number, None, "BOTTOM_CENTER", layer="TextStructShtNo",
                   style=fdot.TABLE_TITLE_STYLE)
        # bridge number and name above the title block (SDM 2.2.D), in the
        # block ``bridge_block`` the layout checks keep clear
        h = fdot.TITLE_IN
        lines = self.bridge_lines()
        self.ptext((x1 - 0.05, t + 0.08 + 1.45 * h), lines[0], None, "BOTTOM_RIGHT", style=fdot.TITLE_STYLE)
        self.ptext((x1 - 0.05, t + 0.08), lines[1], None, "BOTTOM_RIGHT", style=fdot.TITLE_STYLE)
        # 61G15-23.004 statement outside the right border
        self.ptext((x1 + 0.22, (y0 + y1) / 2),
                   "THE OFFICIAL RECORD OF THIS SHEET IS THE ELECTRONIC FILE DIGITALLY SIGNED AND SEALED UNDER RULE 61G15-23.004, F.A.C.",
                   None, "MIDDLE_CENTER", rot=90.0, style=fdot.SMALL_STYLE)
        # plot stamp outside the left border: file and source model (no clock
        # time, so a rebuild from the same snapshot is byte-identical)
        stamp = info.get("stamp") or []
        for i, line in enumerate(stamp):
            self.ptext((x0 - 0.12 - 0.11 * i, y0 + 0.05), line, None, "BOTTOM_LEFT", rot=90.0, style=fdot.STAMP_STYLE)
        # draft status (not for construction)
        self.ptext((x0 + 0.05, y1 + 0.06), info.get("status", ""), None, "BOTTOM_LEFT")

    # ------------------------------------------------------------ tables
    def _box(self, x0, y0, x1, y1, width=None):
        self.pline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "Tables", closed=True, width=width)

    def _cell_text(self, x0, x1, y0, y1, val, style, align="CENTER"):
        h_in = fdot.style_in(style)
        lines = str(val).split("\\P")
        n = len(lines)
        for i, line in enumerate(lines):
            yc = (y0 + y1) / 2 + ((n - 1) / 2 - i) * 1.45 * h_in
            if align == "LEFT":
                self.ptext((x0 + 0.06, yc), line, None, "MIDDLE_LEFT", "Tables", style=style)
            else:
                self.ptext(((x0 + x1) / 2, yc), line, None, "MIDDLE_CENTER", "Tables", style=style)

    def table(self, x, y_top, title, headers, rows, widths, row_h=0.15):
        """Boxed table in the FDOT sheet style (paper inches): a title box in
        FDOT Bold (Medium) (lines split with \\P), header rows in FDOT (Small),
        thin cell rules and centered values in FDOT Structures; the outline
        and the rule under the headers are heavy.  Returns the bottom y.

        A header cell is text, (text, colspan) or (text, colspan, rowspan);
        None marks a cell covered by a span.  A body row is a list of values
        (a value with \\P lines makes the row taller), ("HEADING", text) for a
        full-width component heading or ("SPACER",) for a blank row."""
        total = sum(widths)
        edges = [x]
        for w in widths:
            edges.append(edges[-1] + w)
        y = y_top
        heavy = 0.014
        h_in = fdot.style_in(fdot.TEXT_STYLE)
        if title:
            th = fdot.TABLE_TITLE_IN
            n = title.count("\\P") + 1
            hh = th * (1.45 * n + 0.6)
            self._box(x, y, x + total, y - hh, width=heavy)
            self._cell_text(x, x + total, y - hh, y, title, fdot.TABLE_TITLE_STYLE)
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
                    self._cell_text(x0, x1, y - (r + rs) * row_h, y - r * row_h, txt, fdot.SMALL_STYLE)
                c += cs
        y -= row_h * len(headers)
        if headers:
            self.pline([(x, y), (x + total, y)], "Tables", width=heavy)
        for row in rows:
            if row and row[0] == "SPACER":
                self._box(x, y, x + total, y - row_h)
                y -= row_h
                continue
            if row and row[0] == "HEADING":
                hh = row_h * 1.25
                self._box(x, y, x + total, y - hh)
                self._cell_text(x, x + total, y - hh, y, row[1], fdot.TABLE_TITLE_STYLE, "LEFT")
                y -= hh
                continue
            n = max(str(v).count("\\P") + 1 for v in row if v not in (None, "")) if any(
                v not in (None, "") for v in row) else 1
            hgt = max(row_h, row_h + (n - 1) * 1.45 * h_in)
            for (x0, x1), val in zip(zip(edges, edges[1:]), row):
                self._box(x0, y, x1, y - hgt)
                if val not in (None, ""):
                    self._cell_text(x0, x1, y - hgt, y, val, fdot.TEXT_STYLE)
            y -= hgt
        self._box(x, y_top, x + total, y, width=heavy)
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
        self.pline([(x, y_top), (x, y), (edges[-1], y), (edges[-1], y_top)], "Tables", width=0.014)
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

    # Average capital of the FDOT Structures font over the text height
    # (measured with the font: 0.90 to 0.94; rounded up), used to estimate
    # how many lines a note takes.
    NOTE_CHAR_W = 0.92

    def note_line_count(self, items, width_in, h_in=fdot.NOTE_IN, numbered=True):
        """Estimated number of lines of ``notes`` for the given width: greedy
        word wrap by NOTE_CHAR_W, with the hanging indent (2.6 text heights)
        on wrapped lines.  The estimate places the block below a note and
        checks that it fits; it never changes the text."""
        cw = self.NOTE_CHAR_W * h_in
        total = 0
        for i, it in enumerate(items, 1):
            text = ("%d. %s" % (i, it)) if numbered else it
            for part in text.split("\\P"):
                n, cur, avail = 1, 0.0, width_in
                for w in part.split(" "):
                    wl = cw * len(w)
                    if cur > 0 and cur + cw + wl > avail:
                        n, cur, avail = n + 1, wl, width_in - 2.6 * h_in
                    else:
                        cur += wl if cur == 0 else cw + wl
                total += n
        return total

    def notes_bottom(self, y_top, items, width_in, h_in=fdot.NOTE_IN, numbered=True):
        """Estimated bottom of a ``notes`` block whose heading is at y_top."""
        return y_top - 0.24 - self.note_line_count(items, width_in, h_in, numbered) * fdot.LINE_PITCH * h_in
