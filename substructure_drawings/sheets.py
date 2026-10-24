"""Paper-space sheets: 11 x 17 border, title block, viewport and tables.

The border is the FDOT 11 x 17 structures sheet border cell of the project's
MicroStation sheet model (2026-10-24, ``BORDER_TEMPLATE``), copied unchanged
into every sheet: the border block with its project information (engineer of
record, initials, road, county, financial project ID, project name, bridge
number, the 61G15-23.004 statement) and its attributes, and the sheet number /
title block, which gets the sheet's own number, title and file line.
"""
import hashlib
import math
from pathlib import Path

import ezdxf
from ezdxf.addons.importer import Importer
from ezdxf.enums import TextEntityAlignment
from ezdxf.math import Vec3

from . import fdot
from .cad import ATTACH, text_extent

W_IN, H_IN = 17.0, 11.0
FRAME = (0.80, 0.30, 16.20, 10.70)          # inches
TITLE_TOP = 1.10                           # top of title-block band
DRAW = (0.95, 1.30, 16.05, 10.55)          # usable drawing window
CLIP_MARGIN = 0.08                          # viewport clip beyond DRAW
# Model space (STYLE_GUIDE E9, 2026-10-20): everything is drawn 1:1 in feet;
# each sheet's views stand together in one group (its zones side by side,
# ZONE_GAP_FT apart) inside a labelled box, the groups MODEL_PITCH_FT apart
# in one row, so the model can be imported into the DGN and each group placed
# on its sheet at the scale wanted.  While the views are being placed the
# zones sit at provisional origins (k * 600 ft up); ``Sheet.group_zones``
# moves them together once the sheet is complete.
MODEL_PITCH_FT = 60.0                      # model-space spacing between the sheet groups
ZONE_GAP_FT = 2.0                          # between the zones of one group
BOX_MARGIN_FT = 1.0                        # the group box beyond its zones
# (the group label is the title style at the sheet's largest scale factor,
# the zone notes the text style at their zone's scale: model-space text is
# always an FDOT style height times an FDOT scale, as the symbology test
# requires)

# The sheet border cell (2026-10-24): the user's MicroStation sheet model
# (SheetModelExample.dxf, the sheet "B4-5 TYPICAL SECTION", kept byte for
# byte).  Its border block lies 0.25 in lower left of FRAME at the same
# 15.4 x 10.4 in size and is moved onto FRAME (``border_offset``).  The cell
# keeps its own levels, line weights and text styles, as the sheet model has
# them: ``build.symbology_audit`` counts its entities as the documented
# exception BORDER_CELL_OVERRIDE, and only the fonts of its text styles are
# named (BORDER_CELL_FONTS; the export leaves them to MicroStation).
BORDER_TEMPLATE = Path(__file__).resolve().parent / "data" / "sheet_border_template.dxf"
BORDER_BLOCK = "11x17 Structures Sheet Border"
NUMBER_TITLE_BLOCK = "Structures Sheet Number-Title"
TEMPLATE_SHEET = ("B4-5", "TYPICAL SECTION")     # the template's own sheet number and title
BORDER_CELL_LEVELS = {"TextStructuresLabel", "TextMisc", "ActivePts-ConstElements"}   # not in fdot.LEVELS
BORDER_CELL_FONTS = {"Style-FDOT Bold": "FDOT Bold", "Style-FDOT Mono": "FDOT Mono",
                     "Style-FDOT Imprint Bold": "FDOT Imprint Bold"}
BORDER_CELL_STYLES = set(BORDER_CELL_FONTS) | {"Style-Arial"}
BORDER_CELL_OVERRIDE = "FDOT sheet border cell (levels, weights and text styles of the project's sheet model)"
_TEMPLATE = {}


def border_template():
    """The sheet border template document (read once)."""
    if "doc" not in _TEMPLATE:
        _TEMPLATE["doc"] = ezdxf.readfile(BORDER_TEMPLATE)
    return _TEMPLATE["doc"]


def border_record():
    """The template file and its SHA-256, for the manifests."""
    return {"template": "substructure_drawings/data/" + BORDER_TEMPLATE.name,
            "sha256": hashlib.sha256(BORDER_TEMPLATE.read_bytes()).hexdigest(),
            "blocks": [BORDER_BLOCK, NUMBER_TITLE_BLOCK]}


def is_border_cell(block_name):
    """True for the border block and the sheets' number / title blocks."""
    return block_name in (BORDER_BLOCK, NUMBER_TITLE_BLOCK) or block_name.startswith(NUMBER_TITLE_BLOCK + " ")


def template_insert(name):
    """The template sheet's INSERT of block ``name``."""
    src = border_template()
    return next(e for lay in src.layouts if lay.name != "Model" for e in lay.query("INSERT") if e.dxf.name == name)


def border_offset():
    """(dx, dy) paper feet that move the template's border onto FRAME."""
    poly = border_template().blocks.get(BORDER_BLOCK).query("LWPOLYLINE").first
    xs, ys = zip(*poly.get_points("xy"))
    return FRAME[0] / 12.0 - min(xs), FRAME[1] / 12.0 - min(ys)


def border_bridge_block():
    """The BRIDGE NO. text of the border cell over the title block, (x0, y0,
    x1, y1) paper inches, which notes and views must keep clear."""
    dx, dy = border_offset()
    ins = template_insert(BORDER_BLOCK).dxf.insert
    for e in border_template().blocks.get(BORDER_BLOCK).query("MTEXT"):
        s = e.plain_text().strip()
        if s.startswith("BRIDGE NO."):
            h = e.dxf.char_height * 12.0
            w = text_extent(s, h)
            col, row = (e.dxf.attachment_point - 1) % 3, (e.dxf.attachment_point - 1) // 3
            x = (e.dxf.insert.x + ins.x + dx) * 12.0 - w * col / 2.0
            y = (e.dxf.insert.y + ins.y + dy) * 12.0 - h * (2 - row) / 2.0
            return (x, y, x + w, y + h)
    raise ValueError("no BRIDGE NO. text in %s" % BORDER_TEMPLATE.name)


class Zone:
    """A paper window of a sheet drawn at one scale through one viewport.

    The zone's model-space region mirrors the paper window at the zone scale,
    so views placed by paper coordinates appear exactly there on the sheet.
    ``views`` lists the views drawn in it (``cad.View`` registers itself), so
    the zone can be moved as one piece (``Sheet.group_zones``).
    """

    def __init__(self, sheet, k, window, scale_key):
        self.sheet, self.window, self.scale_key = sheet, window, scale_key
        self.sf = fdot.SCALES[scale_key]
        self.model_origin = (sheet.index * MODEL_PITCH_FT, k * 600.0)
        self.views = []

    def paper_to_model(self, px, py):
        return (self.model_origin[0] + px / 12.0 * self.sf, self.model_origin[1] + py / 12.0 * self.sf)

    def footprint(self):
        """The window's model-space box (x0, y0, x1, y1), feet."""
        x0, y0 = self.paper_to_model(self.window[0], self.window[1])
        x1, y1 = self.paper_to_model(self.window[2], self.window[3])
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def move_to(self, origin):
        """Move the zone (its views' entities) to a new model origin."""
        dx, dy = origin[0] - self.model_origin[0], origin[1] - self.model_origin[1]
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return
        for v in self.views:
            for e in v.ents:
                e.translate(dx, dy, 0)
            v.ox += dx
            v.oy += dy
        self.model_origin = (origin[0], origin[1])


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
        # the border cell's BRIDGE NO. above the title block (paper inches),
        # which notes and views at the lower right must keep clear
        self.bridge_block = border_bridge_block()

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

    # ------------------------------------------------------- model groups
    def group_zones(self):
        """Gather the sheet's zones into one group in model space (E9): the
        zones side by side in order, their footprints' tops aligned, 1:1 as
        drawn, with a box around the group on the Border level and the
        sheet's number and title above it; each zone's intended scale in its
        lower-left corner.  Called once the views are placed and before the
        viewports are made (their centres follow ``model_origin``).  A sheet
        whose zones hold no view (the bar list: paper-space tables) gets no
        group; ``group_box`` is the box drawn, or None."""
        zones = [z for z in self.zones if z.views]   # (the bar list's zone holds no view: no empty box)
        self.group_box = None
        if not zones:
            return
        x = self.index * MODEL_PITCH_FT
        y_top = 0.0
        boxes = []
        for z in zones:
            fp = z.footprint()
            w, h = fp[2] - fp[0], fp[3] - fp[1]
            z.move_to((z.model_origin[0] + x - fp[0], z.model_origin[1] + (y_top - h) - fp[1]))
            boxes.append(z.footprint())
            x += w + ZONE_GAP_FT
        msp = self.doc.modelspace()
        # the scale labels and the box stand outside the viewports' clip
        # (CLIP_MARGIN beyond the window, in paper inches): just under a zone
        # they plotted on the sheet, e.g. over the last note of B4-2 and at
        # the bottom of the 1" = 40' plan (2026-10-23)
        pads = [(CLIP_MARGIN + 0.04) * z.sf / 12.0 for z in zones]
        hns = [fdot.TEXT_STYLES[fdot.TEXT_STYLE][1] * z.sf for z in zones]
        m = max([BOX_MARGIN_FT] + [p + 1.5 * hn for p, hn in zip(pads, hns)])
        bx0, by0 = min(b[0] for b in boxes) - m, min(b[1] for b in boxes) - m
        bx1, by1 = max(b[2] for b in boxes) + m, max(b[3] for b in boxes) + m
        self.group_box = (bx0, by0, bx1, by1)
        msp.add_lwpolyline([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], close=True,
                           dxfattribs={"layer": "Border"})
        label = fdot.font_text("SHEET %s  %s" % (self.number, self.title))
        h = fdot.TEXT_STYLES[fdot.TITLE_STYLE][1] * max(z.sf for z in zones)
        e = msp.add_text(label, height=h, dxfattribs={"layer": "Border", "style": fdot.TITLE_STYLE})
        e.set_placement((bx0, by1 + 0.4 * h), align=TextEntityAlignment.BOTTOM_LEFT)
        for z, b, pad, hn in zip(zones, boxes, pads, hns):
            note = fdot.font_text(fdot.scale_label(z.scale_key))
            e = msp.add_text(note, height=hn, dxfattribs={"layer": "Border", "style": fdot.TEXT_STYLE})
            e.set_placement((b[0], b[1] - pad), align=TextEntityAlignment.TOP_LEFT)

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
        """The sheet border cell of the project's sheet model (see
        BORDER_TEMPLATE) moved onto FRAME: the border block inserted with
        the template's attribute values, and a copy of the sheet number /
        title block named after this sheet with its number, title and file
        line ("<dxf> : <layout>", in place of the template's DGN path; the
        $USER$ $DATE$ $TIME$ fields stay as the template has them, so a
        rebuild is byte-identical).  The draft status stands above the
        frame."""
        doc = self.doc
        dx, dy = border_offset()
        src = border_template()
        imp = Importer(src, doc)
        if BORDER_BLOCK not in doc.blocks:
            # the cell's levels and styles first, in name order (``finalize``
            # adds missing ones in set order, which changes the bytes from
            # run to run); existing ones are kept
            cell = [e for name in (BORDER_BLOCK, NUMBER_TITLE_BLOCK) for e in src.blocks.get(name)]
            levels = sorted({e.dxf.layer for e in cell})
            imp.import_table("layers", levels)
            imp.import_table("styles", sorted({e.dxf.style for e in cell if e.dxf.is_supported("style")}))
            # an imported level keeps the template's plot style and material
            # handles, which point nowhere here: this file's, as the FDOT levels
            ref = doc.layers.get("Border").dxf
            for name in levels:
                layer = doc.layers.get(name).dxf
                for key in ("plotstyle_handle", "material_handle"):
                    if ref.hasattr(key):
                        layer.set(key, ref.get(key))
                    else:
                        layer.discard(key)
            imp.import_block(BORDER_BLOCK, rename=False)
        name = imp.import_block(NUMBER_TITLE_BLOCK, rename=True)
        imp.finalize()
        own = "%s %s" % (NUMBER_TITLE_BLOCK, self.number)
        doc.blocks.rename_block(name, own)
        # the template leaves its fonts to MicroStation: name the FDOT fonts
        for style, font in BORDER_CELL_FONTS.items():
            if style in doc.styles:
                file, family, bold = fdot.FONTS[font]
                st = doc.styles.get(style)
                st.dxf.font = file
                st.set_extended_font_data(family, italic=False, bold=bold)
        # the border block with the template's attributes (project data)
        t = template_insert(BORDER_BLOCK)
        ins = self.psp.add_blockref(BORDER_BLOCK, Vec3(t.dxf.insert) + (dx, dy, 0), dxfattribs={"layer": t.dxf.layer})
        for a in t.attribs:
            attribs = a.dxfattribs(drop={"handle", "owner"})
            for key in ("insert", "align_point"):
                if key in attribs:
                    attribs[key] = Vec3(attribs[key]) + (dx, dy, 0)
            ins.add_attrib(attribs.pop("tag"), attribs.pop("text"), attribs.pop("insert"), dxfattribs=attribs)
        # this sheet's number and title block
        num, title = TEMPLATE_SHEET
        done = set()
        for e in doc.blocks.get(own).query("MTEXT"):
            if e.text == num:
                e.text = self.number
                done.add("number")
            elif e.text.endswith(title):
                e.text = e.text[:-len(title)] + self.title
                done.add("title")
            elif ".dgn : " in e.text:
                e.text = "%s : %s" % (self.info.get("file", ""), self.layout.name)
                done.add("file")
        if done != {"number", "title", "file"}:
            raise ValueError("%s: the template's number / title block changed (found %s)" % (self.number, sorted(done)))
        t = template_insert(NUMBER_TITLE_BLOCK)
        self.psp.add_blockref(own, Vec3(t.dxf.insert) + (dx, dy, 0), dxfattribs={"layer": t.dxf.layer})
        # draft status (not for construction)
        self.ptext((FRAME[0] + 0.05, FRAME[3] + 0.06), self.info.get("status", ""), None, "BOTTOM_LEFT")

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
