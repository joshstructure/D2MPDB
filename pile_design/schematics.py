"""Per-equation QC schematics for the pile calculation report (inline SVG).

Every formula definition of both pile families (prestressed concrete and steel pipe, and both
branches of the biaxial route) maps to a small drawing built from the current case: the geometry
it measures, the load or resistance it represents, or the relation it evaluates. The drawing
carries only short symbols; the panel beside it states the result (red) and how it is composed
from the current values, so a reviewer can check the number against the picture.

Layout, colors and the drawing primitives follow end_bent_walls/schematics.py; the symbol table
follows pile_design/notation.py so the SVG symbols match the MathML.
"""
import math
import re
from html import escape
import numpy as np

INK = '#213649'; GREY = '#8a99a6'; FAINT = '#c4cdd6'; CONC = '#e3e9ee'; SOIL = '#f1e6cc'; HL = '#c8322b'
BLUE = '#1f5b91'; STRAP = '#7a3e9d'; TEAL = '#167b75'; AMBER = '#c77d16'; PAD = '#30475e'; SLAB = '#d7e0e8'
LIGHT = '#9fb3c8'
GREEK = {'phi': 'φ', 'gamma': 'γ', 'beta': 'β', 'theta': 'θ', 'alpha': 'α', 'eps': 'ε', 'lambda': 'λ', 'delta': 'δ',
         'mu': 'μ', 'rho': 'ρ', 'Gamma': 'Γ', 'Delta': 'Δ'}
SPECIAL = {'fc': ('f′', 'c'), 'fy': ('f', 'y'), 'Es': ('E', 's'), 'dT': ('Δ', 'T'),
           'K1': ('K', '1'), 'K2': ('K', '2'), 'EL': ('EL', '')}
W, H, PX = 760, 360, 474          # canvas and the x of the info panel


def sym(name):
    """SVG text markup for a formula name: base letter plus subscript (same split as notation.symbol)."""
    parts = name.split('_')
    base, subs = parts[0], parts[1:]
    if base in SPECIAL:
        glyph, first = SPECIAL[base]
        subs = ([first] if first else []) + subs
    else:
        glyph = GREEK.get(base, base)
    out = escape(glyph)
    subs = [GREEK.get(s, s) for s in subs]
    if subs:
        out += f'<tspan baseline-shift="sub" font-size="75%">{escape(",".join(subs))}</tspan>'
    return out


def sub(base, low):
    return f'{escape(base)}<tspan baseline-shift="sub" font-size="75%">{escape(low)}</tspan>'


def _dash(dash):
    return f' stroke-dasharray="{dash}"' if dash else ''


class Svg:
    def __init__(self, label, width=W, height=H, title=''):
        self.w, self.h, self.label, self.items = width, height, label, []
        if title:
            self.text(12, 18, escape(title), 11, INK, 'start', 'bold')

    def rect(self, x, y, w, h, fill='none', stroke=INK, sw=1.0, dash=None, op=1.0):
        if w < 0:
            x, w = x + w, -w
        if h < 0:
            y, h = y + h, -h
        self.items.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" fill-opacity="{op}" '
                          f'stroke="{stroke}" stroke-width="{sw}"{_dash(dash)}/>')

    def line(self, x1, y1, x2, y2, stroke=INK, sw=1.0, dash=None):
        self.items.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"{_dash(dash)}/>')

    def poly(self, points, fill='none', stroke=INK, sw=1.0, op=1.0, dash=None, closed=True):
        tag = 'polygon' if closed else 'polyline'
        pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
        self.items.append(f'<{tag} points="{pts}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="{sw}"{_dash(dash)}/>')

    def circle(self, x, y, r, fill=INK, stroke='none', sw=1.0, op=1.0, dash=None):
        self.items.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" '
                          f'stroke-width="{sw}"{_dash(dash)}/>')

    def ring(self, cx, cy, r_out, r_in, fill=CONC, stroke=INK, sw=1.0, op=1.0):
        """Annulus (even-odd path)."""
        def circ(r):
            return f'M{cx - r:.1f},{cy:.1f} a{r:.1f},{r:.1f} 0 1,0 {2 * r:.1f},0 a{r:.1f},{r:.1f} 0 1,0 {-2 * r:.1f},0 Z'
        self.items.append(f'<path d="{circ(r_out)} {circ(r_in)}" fill-rule="evenodd" fill="{fill}" fill-opacity="{op}" '
                          f'stroke="{stroke}" stroke-width="{sw}"/>')

    def text(self, x, y, markup, size=10.5, color=INK, anchor='middle', weight='normal', rotate=None):
        transform = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ''
        self.items.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}" '
                          f'font-weight="{weight}" font-family="Arial, sans-serif"{transform}>{markup}</text>')

    def tag(self, x, y, markup, color=INK, anchor='middle'):
        """Short label on a white halo so it stays legible over geometry."""
        self.items.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="9.5" fill="{color}" text-anchor="{anchor}" font-weight="bold" '
                          f'font-family="Arial, sans-serif" stroke="#ffffff" stroke-width="3" paint-order="stroke">{markup}</text>')

    def arrow(self, x1, y1, x2, y2, color=INK, sw=1.8, head=7.0):
        length = math.hypot(x2 - x1, y2 - y1)
        if length < 1e-6:
            return
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        head = min(head, length * 0.6)
        bx, by = x2 - ux * head, y2 - uy * head
        self.line(x1, y1, bx, by, color, sw)
        self.poly([(x2, y2), (bx - uy * head * 0.45, by + ux * head * 0.45), (bx + uy * head * 0.45, by - ux * head * 0.45)],
                  fill=color, stroke=color, sw=0.5)

    def dim(self, x1, y1, x2, y2, markup='', color=HL, side=1, offset=10):
        """Dimension line, arrowheads both ends, short label beside it."""
        length = math.hypot(x2 - x1, y2 - y1)
        if length < 6:
            self.line(x1, y1, x2, y2, color, 2.4)
        else:
            self.arrow((x1 + x2) / 2, (y1 + y2) / 2, x1, y1, color, 1.2, 5)
            self.arrow((x1 + x2) / 2, (y1 + y2) / 2, x2, y2, color, 1.2, 5)
        if markup:
            vertical = abs(x2 - x1) < abs(y2 - y1)
            if vertical:
                self.tag((x1 + x2) / 2 + 5 * side, (y1 + y2) / 2 + 4, markup, color, 'start' if side > 0 else 'end')
            elif length < 40:
                self.tag(max(x1, x2) + 6, (y1 + y2) / 2 + 4, markup, color, 'start')
            else:
                self.tag((x1 + x2) / 2, (y1 + y2) / 2 + (offset + 3 if side > 0 else -offset + 3), markup, color)

    def panel(self, result, rows=(), heading='This equation', y=46, x=PX):
        """Right-hand panel: result in red, then the values it is built from."""
        self.line(x - 14, 30, x - 14, self.h - 14, FAINT, 1)
        self.text(x, y, escape(heading), 10, GREY, 'start', 'bold')
        self.text(x, y + 22, result, 13, HL, 'start', 'bold')
        yy = y + 46
        for row in rows:
            if isinstance(row, tuple):
                markup, color = row
            else:
                markup, color = row, INK
            self.text(x, yy, markup, 10.5, color, 'start')
            yy += 18
        return yy

    def render(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'role="img" aria-label="{escape(self.label, quote=True)}" style="max-width:100%;height:auto;background:#fff">'
                f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>' + ''.join(self.items) + '</svg>')


class Frame:
    """Model coordinates (y up) to SVG pixels at equal scale, centered in a box."""

    def __init__(self, x0, x1, y0, y1, left, top, width, height):
        self.k = min(width / (x1 - x0), height / (y1 - y0))
        self.left = left + (width - (x1 - x0) * self.k) / 2
        self.top = top + (height - (y1 - y0) * self.k) / 2
        self.x0, self.y1 = x0, y1

    def X(self, x):
        return self.left + (x - self.x0) * self.k

    def Y(self, y):
        return self.top + (self.y1 - y) * self.k

    def L(self, d):
        return d * self.k


def nice_ticks(lo, hi, n=5):
    """About n round tick values inside [lo, hi]."""
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / max(n - 1, 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw - 1e-12)
    first = math.ceil(lo / step - 1e-9) * step
    out, t = [], first
    while t <= hi + step * 1e-9:
        out.append(round(t, 10))
        t += step
    return out


def tick_text(t):
    if abs(t) >= 1000:
        return f'{t:,.0f}'
    text = f'{t:.4g}'
    return '0' if text in ('-0', '0') else text


class Axes:
    """Plot box with ticks; X() and Y() map data to pixels. Curves and markers are clamped to the box."""

    def __init__(self, s, x0, x1, y0, y1, xlabel='', ylabel='', left=70, top=44, width=PX - 120, height=240, ticks=5):
        self.s, self.x0, self.x1, self.y0, self.y1 = s, x0, x1, y0, y1
        self.left, self.top, self.width, self.height = left, top, width, height
        s.line(left, top + height, left + width, top + height, INK)
        s.line(left, top, left, top + height, INK)
        for xv in nice_ticks(x0, x1, ticks):
            s.line(self.X(xv), top + height, self.X(xv), top + height + 3, INK)
            s.text(self.X(xv), top + height + 14, tick_text(xv), 9, GREY)
        for yv in nice_ticks(y0, y1, ticks):
            s.line(left - 3, self.Y(yv), left, self.Y(yv), INK)
            s.text(left - 6, self.Y(yv) + 3, tick_text(yv), 9, GREY, 'end')
        if xlabel:
            s.text(left + width / 2, top + height + 32, xlabel, 10, INK)
        if ylabel:
            s.text(18, top + height / 2, ylabel, 10, INK, rotate=-90)

    def X(self, x):
        return self.left + (x - self.x0) / (self.x1 - self.x0) * self.width

    def Y(self, y):
        return self.top + self.height - (y - self.y0) / (self.y1 - self.y0) * self.height

    def cx(self, x):
        return min(max(self.X(x), self.left), self.left + self.width)

    def cy(self, y):
        return min(max(self.Y(y), self.top), self.top + self.height)

    def curve(self, xs, ys, color=BLUE, sw=2, dash=None, clip=False):
        """Polyline through the data; with clip=True points outside the box break the line instead of being clamped."""
        if not clip:
            self.s.poly([(self.cx(x), self.cy(y)) for x, y in zip(xs, ys)], stroke=color, sw=sw, closed=False, dash=dash)
            return
        run = []
        for x, y in zip(xs, ys):
            if self.y0 <= y <= self.y1 and self.x0 <= x <= self.x1:
                run.append((self.X(x), self.Y(y)))
                continue
            if len(run) > 1:
                self.s.poly(run, stroke=color, sw=sw, closed=False, dash=dash)
            run = []
        if len(run) > 1:
            self.s.poly(run, stroke=color, sw=sw, closed=False, dash=dash)

    def hline(self, y, label='', color=AMBER, dash='5 3', anchor='end'):
        self.s.line(self.left, self.cy(y), self.left + self.width, self.cy(y), color, 1.2, dash)
        if label:
            self.s.tag(self.left + self.width - 4 if anchor == 'end' else self.left + 4, self.cy(y) - 5, label, color, anchor)

    def vline(self, x, label='', color=GREY, dash='3 3'):
        self.s.line(self.cx(x), self.top, self.cx(x), self.top + self.height, color, 0.9, dash)
        if label:
            self.s.tag(self.cx(x) + 3, self.top + 10, label, color, 'start')

    def point(self, x, y, color=HL, label='', anchor='start', dx=8, dy=-8, r=5):
        px, py = self.cx(x), self.cy(y)
        self.s.circle(px, py, r, fill=color)
        if label:
            self.s.tag(px + (dx if anchor == 'start' else -dx), py + dy, label, color, anchor)


# ----------------------------------------------------------------------------- shared helpers
def _val(e, name, places=3):
    return escape(e.text(name, places))


def _eq(e, name, places=3):
    return f'{sym(name)} = {_val(e, name, places)}'


def _spread(values, gap):
    """Shift sorted callout positions apart by at least `gap`, keeping their mean."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [values[i] for i in order]
    for i in range(1, len(out)):
        out[i] = max(out[i], out[i - 1] + gap)
    shift = (sum(values) - sum(out)) / len(out) if out else 0
    result = [0.0] * len(values)
    for rank, i in enumerate(order):
        result[i] = out[rank] + shift
    return result


def _g(x, places=3):
    """Number text without trailing zeros (for formula rows)."""
    text = f'{x:.{places}f}'
    return (text.rstrip('0').rstrip('.') if '.' in text else text) or '0'


def _inp(e, name):
    return e.case['inputs'][name]


def _unit_text(e, name):
    return escape(e.text(name, 3))


def _plot(e, name, series, xlabel, ylabel, points, title, x_range=None, y_range=None, hlines=(), vlines=(), rows=(), places=3):
    """Curves vs a variable with the current point(s); points[0] is the quantity of this equation."""
    s = Svg(title, title=title)
    xs_all = [x for xs, _, _ in series for x in xs] + [p[0] for p in points]
    ys_all = [y for _, ys, _ in series for y in ys] + [p[1] for p in points] + [h[0] for h in hlines]
    x0, x1 = x_range or (min(xs_all), max(xs_all))
    y0, y1 = y_range or (min(0.0, min(ys_all)), max(ys_all) * 1.1 + 1e-9)
    ax = Axes(s, x0, x1, y0, y1, escape(xlabel), escape(ylabel))
    for xs, ys, color in series:
        ax.curve(xs, ys, color)
    for y, lab in hlines:
        ax.hline(y, escape(lab))
    for x, lab in vlines:
        ax.vline(x, escape(lab))
    for i, (x, y, lab) in enumerate(points):
        ax.point(x, y, HL if i == 0 else INK, escape(lab), 'start' if ax.X(x) < ax.left + ax.width * 0.6 else 'end')
    s.panel(_eq(e, name, places), list(rows))
    return s


def _draw_bars(s, items, hl, label_x, xa, xb, y0=40, step=28, places=3, colors=None):
    """Horizontal bars (signed values allowed) between xa and xb; labels end at label_x."""
    vals = [x for _, x in items]
    lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
    scale = (xb - xa) / max(hi - lo, 1e-9)
    x0 = xa + (-lo) * scale
    s.line(x0, y0 - 6, x0, y0 + step * len(items) - 4, GREY, 0.9)
    for i, (label, x) in enumerate(items):
        y = y0 + step * i
        on = i in hl
        color = HL if on else (colors[i] if colors else LIGHT)
        w = abs(x) * scale
        s.text(label_x, y + 14, label, 10, HL if on else INK, 'end', 'bold' if on else 'normal')
        s.rect(x0 if x >= 0 else x0 - w, y + 3, max(w, 1), 17, fill=color, stroke='none')
        s.text(x0 + (w if x >= 0 else 0) + 5, y + 16, f'{x:.{places}f}', 10, HL if on else INK, 'start', 'bold' if on else 'normal')


def _bars(e, name, items, unit, title, highlight=None, extra=(), places=3, height=None, note=None):
    """Horizontal bars (signed values allowed). items: (label markup, value). highlight: index or set of indices."""
    hl = {highlight} if isinstance(highlight, int) else set(highlight or ())
    s = Svg(title, height=height or max(200, 74 + 28 * len(items)), title=escape(title))
    signed = min(x for _, x in items) < 0
    _draw_bars(s, items, hl, 214 if signed else 194, 225 if signed else 205, 395 if signed else 400, places=places)
    rows = list(extra) + [(f'bars in {escape(unit)}; red = value of this equation', GREY)]
    if note:
        rows.append((note, GREY))
    s.panel(_eq(e, name, places), rows)
    return s


class Sec:
    """Square (optionally voided) prestressed pile section at pixel centre (cx, cy), `size` px for the extent `span` inches.

    angle rotates the section so the compression face of a bending axis at `angle` (rad) points up."""

    def __init__(self, s, e, cx, cy, size, angle=0.0, span=None):
        self.s, self.e, self.cx, self.cy, self.a = s, e, cx, cy, angle
        self.D = float(_inp(e, 'D_pile'))
        self.void = float(e.value('d_void', 'in')) if 'd_void' in e.units else 0.0
        ca, sa = abs(math.cos(angle)), abs(math.sin(angle))
        self.span = span or self.D
        self.k = size / (self.span * (ca + sa))

    def P(self, x, y):
        a = self.a
        xr, yr = x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)
        return self.cx + self.k * xr, self.cy - self.k * yr

    def L(self, d):
        return d * self.k

    def draw(self, fill=CONC, stroke=INK, op=1.0, sw=1.2):
        h = self.D / 2
        self.s.poly([self.P(-h, -h), self.P(h, -h), self.P(h, h), self.P(-h, h)], fill=fill, stroke=stroke, sw=sw, op=op)
        if self.void > 0:
            x, y = self.P(0, 0)
            self.s.circle(x, y, self.L(self.void / 2), fill='#ffffff', stroke=GREY, sw=1.0)

    def strand_points(self):
        return [tuple(p) for p in self.e.details['layout']]

    def strands(self, color=INK, colors=None, r=None):
        r = r or max(2.4, self.k * 0.3)
        for i, (x, y) in enumerate(self.strand_points()):
            px, py = self.P(x, y)
            self.s.circle(px, py, r, fill=(colors[i] if colors else color))


def _psc_title(e):
    plan = e.details['plan']
    return f'Index {e.case["psc"]["index"]} · {e.case["psc"]["pattern"]} · {plan["size_in"]:g} in square' + (' (void)' if e.value('d_void', 'in') > 0 else '')


# ============================================================================= 1. pile row plan
def row_plan(e, name):
    v, p = e.value, e.case['inputs']
    D, S, N = float(p['D_pile']), v('S_pile', 'in'), int(round(p['N_pile']))
    n = min(N, 8)
    pipe = e.family == 'pipe'
    s = Svg('Plan of the pile row: pile count N at the provided center-to-center spacing, against the 3-diameter minimum.',
            title=f'Plan of the pile row · {N} piles at {S:g} in')
    extent = (n - 1) * S + D
    k = min((PX - 80) / extent, 90 / D)
    x1 = 40 + ((PX - 80) - extent * k) / 2 + D * k / 2
    y0 = 135
    for i in range(n):
        cx = x1 + i * S * k
        if pipe:
            s.circle(cx, y0, D * k / 2, fill=CONC, stroke=INK, sw=1.4)
            s.circle(cx, y0, D * k / 2 - 3, fill='#ffffff', stroke=GREY, sw=0.8)
        else:
            s.rect(cx - D * k / 2, y0 - D * k / 2, D * k, D * k, fill=CONC, stroke=INK, sw=1.4)
        s.line(cx, y0 - D * k / 2 - 8, cx, y0 + D * k / 2 + 8, GREY, 0.8, '4 3')
    if N > n:
        s.tag(x1 + (n - 1) * S * k + D * k / 2 + 6, y0 + 4, f'… {N} piles', GREY, 'start')
    top = y0 - D * k / 2
    s.dim(x1 - D * k / 2, top - 18, x1 + D * k / 2, top - 18, f'{sym("D_pile")} = {D:g} in', GREY, side=-1)
    yb = y0 + D * k / 2
    sp_hl = name == 's_over_D'
    s.dim(x1, yb + 30, x1 + S * k, yb + 30, f'{sym("S_pile")} = {S:g} in', HL if sp_hl else INK, side=1)
    smin = v('S_min', 'in')
    s.line(x1 + smin * k, yb + 6, x1 + smin * k, yb + 76, HL if name == 'S_min' else GREY, 1, '4 3')
    s.dim(x1, yb + 64, x1 + smin * k, yb + 64, f'{sym("S_min")} = 3·{sym("D_pile")}', HL if name == 'S_min' else GREY, side=1)
    s.tag(x1 + smin * k + 4, yb + 78, 'minimum', HL if name == 'S_min' else GREY, 'start')
    ok = S >= smin - 1e-9
    if name == 'S_min':
        rows = [f'= 3 × {sym("D_pile")}', f'= 3 × {D:g} in', f'provided {S:g} in {"≥" if ok else "&lt;"} minimum', ('SDG 3.5.4: 3.0 diameters minimum', GREY)]
    else:
        rows = [f'= {sym("S_pile")} / {sym("D_pile")}', f'= {S:g} in / {D:g} in', f'{"≥" if ok else "&lt;"} 3.0 required', ('SDG 3.5.4: 3.0 diameters minimum', GREY)]
    s.panel(_eq(e, name, 3), rows)
    return s


# ============================================================================= 2. drag load
def drag(e, name):
    v, p = e.value, e.case['inputs']
    dd = v('DD', 'kip')
    s = Svg('One pile in elevation: the drag load DR acts downward on the shaft above the neutral plane, in addition to the FBMP head load.',
            title='Drag load on one pile (schematic depths)')
    xc, yg, yn, ybot = 190, 172, 262, 334
    s.rect(60, yg, 260, ybot - yg, fill=SOIL, stroke='none', op=0.7)
    s.rect(xc - 74, 70, 148, 26, fill=CONC, stroke=INK)
    s.text(xc, 87, 'pile cap', 10, GREY)
    s.rect(xc - 15, 96, 30, ybot - 96, fill=CONC, stroke=INK, sw=1.4)
    s.line(60, yg, 320, yg, '#9b8456', 1.4)
    s.tag(66, yg - 5, f'ground EL {p["EL_ground"]:.2f} ft', '#9b8456', 'start')
    s.tag(xc - 80, 90, f'cutoff EL {p["EL_cutoff"]:.2f} ft', GREY, 'end')
    s.line(60, yn, 320, yn, GREY, 1, '5 3')
    s.tag(66, yn - 5, 'neutral plane', GREY, 'start')
    s.tag(xc + 22, yn + 14, 'skin friction resists below', GREY, 'start')
    s.arrow(xc, 36, xc, 69, GREY, 2.2)
    s.tag(xc + 8, 52, f'P{escape("")}<tspan baseline-shift="sub" font-size="75%">FBMP</tspan>', GREY, 'start')
    hl = name in ('DD', 'DR_str', 'DR_ser')
    if dd > 0:
        color = HL if hl else GREY
        for side in (-1, 1):
            for j in range(3):
                ya = yg + 10 + j * 26
                s.arrow(xc + side * 30, ya, xc + side * 30, ya + 21, color, 2.2)
        s.line(xc + 36, yg + 8, xc + 36, yn - 12, color, 1)
        label = sym(name)
        s.tag(xc + 42, (yg + yn) / 2 + 3, label, color, 'start')
        if name != 'DD':
            gname = 'gamma_DR_str' if name == 'DR_str' else 'gamma_DR_ser'
            s.tag(xc + 42, (yg + yn) / 2 + 18, f'= {sym(gname)} × {sym("DD")}', color, 'start')
        else:
            s.tag(xc + 42, (yg + yn) / 2 + 18, '(nominal)', GREY, 'start')
    else:
        s.tag(xc + 40, (yg + yn) / 2, 'no downdrag at this support', GREY, 'start')
    if name == 'DD':
        rows = [f'= {sym("DD_tons")} × 2 kip/ton', f'= {p["DD_tons"]:g} tons × 2 kip', ('nominal drag load per pile', GREY),
                ('geotechnical engineer; no downdrag here' if dd <= 0 else 'from the geotechnical engineer', GREY)]
    else:
        gname = 'gamma_DR_str' if name == 'DR_str' else 'gamma_DR_ser'
        limit = 'strength limit states' if name == 'DR_str' else 'Service I'
        rows = [f'= {sym(gname)} · {sym("DD")}', f'= {p[gname]:g} × {dd:.3f} kip', (f'LRFD Table 3.4.1-1, {limit}', GREY),
                ('added to P_FBMP at every station', GREY), ('not in the Factored Design Load', GREY)]
    s.panel(_eq(e, name, 3), rows)
    return s


# ============================================================================= 3. geotechnical
def geotech(e, name):
    v, p = e.value, e.case['inputs']
    fdl, scour, dd = v('FDL_fbmp', 'kip'), v('R_scour_net', 'kip'), v('DD', 'kip')
    total, req, phi = fdl + scour + dd, v('R_n_req', 'kip'), p['phi_geo']
    psc = e.family == 'psc'
    limit = v('R_drive_max', 'kip') if psc else None
    s = Svg('SDG Eq. 3-1 as a stack: factored design load plus net scour resistance plus downdrag, divided by the resistance factor, against the Table 3.5.13-1 limit.',
            title='Required nominal bearing resistance, SDG Eq. 3-1')
    top = max(total, req, limit or 0.0, 1.0) * 1.12
    base, hgt = 322, 250
    Y = lambda val: base - val / top * hgt
    ax, bx, bw = 70, 330, 70
    s.line(40, base, 440, base, INK)
    segs = [('FDL_fbmp', fdl, LIGHT, name == 'FDL_tons'), ('R_scour_net', scour, '#8fc9c4', name == 'R_scour_net'), ('DD', dd, '#e3b873', False)]
    y = 0.0
    centers = []
    for key, val, color, hl in segs:
        h0, h1 = Y(y), Y(y + val)
        if val > 0:
            s.rect(ax, h1, bw, h0 - h1, fill=HL if hl else color, stroke=INK, sw=0.8)
        else:
            s.line(ax - 4, h0, ax + bw + 4, h0, HL if hl else GREY, 2.4)
        centers.append((h0 + h1) / 2)
        y += val
    ys = _spread(centers, 14)
    for (key, val, color, hl), yc, yo in zip(segs, ys, centers):
        s.tag(ax + bw + 8, yc + 3, f'{sym(key)} = {val:.1f}', HL if hl else INK, 'start')
    s.tag(ax + bw / 2, Y(total) - 8, f'Σ = {total:.1f} kip', INK)
    ya = Y(req / 2)
    s.arrow(bx - 70, ya, bx - 8, ya, INK, 1.6)
    s.tag(bx - 39, ya - 8, f'÷ {sym("phi_geo")}', INK)
    hl_b = name in ('R_n_req', 'NBR_tons')
    s.rect(bx, Y(req), bw, base - Y(req), fill=HL if hl_b else LIGHT, stroke=INK, sw=0.8)
    s.tag(bx + bw / 2, Y(req) - 8, f'{sym("R_n_req")} = {req:.1f} kip', HL if hl_b else INK)
    s.tag(bx + bw / 2, base + 14, f'{req / 2:.1f} tons', HL if hl_b else GREY)
    if psc:
        hl_l = name == 'R_drive_max'
        s.line(40, Y(limit), 440, Y(limit), HL if hl_l else AMBER, 1.6, '6 3')
        s.tag(436, Y(limit) - 8, f'{sym("R_drive_max")} = {limit:.0f} kip · Table 3.5.13-1', HL if hl_l else AMBER, 'end')
    else:
        s.tag(436, 60, 'no Table 3.5.13-1 value for steel pipe', GREY, 'end')
    s.tag(ax + bw / 2, base + 14, 'demand stack', GREY)
    if name == 'FDL_tons':
        rows = [f'= {sym("FDL_fbmp")} / (2 kip)', f'= {fdl:.3f} kip / 2', ('strength head compression, no downdrag', GREY)]
    elif name == 'R_scour_net':
        rows = [f'= {sym("R_scour_net_tons")} × 2 kip', f'= {p["R_scour_net_tons"]:g} tons × 2', ('scour handoff pending', GREY)]
    elif name == 'R_n_req':
        rows = [f'= ({sym("FDL_fbmp")} + {sym("R_scour_net")} + {sym("DD")}) / {sym("phi_geo")}', f'= ({fdl:.2f} + {scour:.2f} + {dd:.2f}) / {phi:g}',
                ('SDG Eq. 3-1; DD added nominally', GREY)]
    elif name == 'NBR_tons':
        rows = [f'= {sym("R_n_req")} / (2 kip)', f'= {req:.3f} kip / 2', ('Pile Data Table column C', GREY)]
    else:
        rows = [f'= {sym("R_drive_tons")} × 2 kip', f'= {v("R_drive_tons"):g} tons × 2', (f'{p["D_pile"]:g} in pile, Table 3.5.13-1', GREY)]
    s.panel(_eq(e, name, 3), rows)
    return s


# ============================================================================= 4. PSC section and prestress
def _strand_bars(s, e, x, y, name):
    """Strand stress bars: jacking, losses, effective."""
    v = e.value
    fpj, fpe = v('f_pj', 'ksi'), v('f_pe', 'ksi')
    sc = 135 / max(fpj, 1e-9)
    s.tag(x, y - 6, 'strand stress (ksi)', GREY, 'start')
    rows = [(sym('f_pj') + f' = {fpj:.1f}', 0, fpj * sc, LIGHT, name == 'f_pj'),
            (f'losses = {sym("loss_frac")}·{sym("f_pj")} = {fpj - fpe:.1f}', fpe * sc, (fpj - fpe) * sc, '#e3b873', False),
            (sym('f_pe') + f' = {fpe:.1f}', 0, fpe * sc, LIGHT, name in ('f_pe', 'P_e'))]
    for i, (label, off, w, color, on) in enumerate(rows):
        yy = y + i * 40
        s.tag(x, yy + 6, label, HL if on else INK, 'start')
        s.rect(x + off, yy + 11, max(w, 1), 14, fill=HL if on else color, stroke='none')


def _strain_profile(s, e, sec, name):
    v = e.value
    pe, ce, cu = v('eps_pe'), v('eps_ce'), v('eps_cu')
    kx = 14000.0
    x0 = 332
    ytop, ybot = sec.cy - sec.L(sec.D) / 2, sec.cy + sec.L(sec.D) / 2
    ys = sec.P(0, -(sec.D / 2 - float(_inp(e, 'd_edge'))))[1]
    s.line(x0, ytop - 8, x0, ybot + 8, INK, 1.2)
    s.tag(x0, ytop - 14, 'strain at the section', GREY)
    c = HL if name == 'eps_cu' else INK
    s.arrow(x0, ytop + 2, x0 - cu * kx, ytop + 2, c, 2.6)
    s.tag(x0 - cu * kx - 4, ytop + 6, sym('eps_cu'), c, 'end')
    s.text(x0 + 6, ytop + 16, 'compression fiber', 9, GREY, 'start')
    c1 = HL if name == 'eps_pe' else INK
    c2 = HL if name == 'eps_ce' else INK
    s.arrow(x0, ys, x0 + pe * kx, ys, c1, 2.6)
    s.tag(x0 + pe * kx / 2, ys + 17, sym('eps_pe'), c1)
    s.arrow(x0 + pe * kx, ys - 6, x0 + pe * kx + max(ce * kx, 4), ys - 6, c2, 2.6)
    s.tag(x0 + pe * kx + max(ce * kx, 4) + 3, ys - 10, sym('eps_ce'), c2, 'start')
    s.arrow(x0 + pe * kx + max(ce * kx, 4) + 3, ys + 4, x0 + pe * kx + 38 + ce * kx, ys + 4, GREY, 1.4)
    s.tag(x0 + pe * kx + 26, ys + 24, f'{sym("eps_cu")}(d − c)/c', GREY)
    s.tag(x0 + 8, ybot + 24, 'strand strain = sum of three', GREY, 'start')


def psc_section(e, name):
    v, p = e.value, e.case['inputs']
    D, void = float(p['D_pile']), v('d_void', 'in')
    s = Svg(f'Prestressed pile section with the strand pattern ({_psc_title(e)}); the quantity of this equation is red.',
            title=f'Prestressed pile section · {_psc_title(e)}')
    sec = Sec(s, e, 150, 188, 186)
    sec.draw(fill='#f0b9b5' if name == 'A_g' else CONC)
    strand_hl = name in ('A_ps', 'f_pj', 'f_pe', 'P_e')
    sec.strands(HL if strand_hl else INK)
    xl, yb = sec.P(-D / 2, -D / 2)
    xr, _ = sec.P(D / 2, -D / 2)
    xt, yt = sec.P(D / 2, D / 2)
    s.dim(xl, yb + 22, xr, yb + 22, f'{sym("D_pile")} = {D:g} in', HL if name == 'A_g' else GREY, side=1)
    cxp, cyp = sec.P(0, 0)
    if name == 'A_g' and void > 0:
        s.dim(cxp - sec.L(void / 2), cyp, cxp + sec.L(void / 2), cyp, f'{sym("d_void")}', HL, side=-1, offset=6)
    if name in ('I_g', 'S_g'):
        s.line(xl - 10, cyp, xr + 10, cyp, HL, 1.8, '7 3')
        s.tag(xr + 12, cyp + 14, 'centroidal axis', HL, 'start')
    if name == 'S_g':
        s.dim(xr + 18, cyp, xr + 18, yt, 'D/2', HL)
    if name == 'I_g':
        s.tag(cxp, cyp + 14, 'x', HL)
    if name == 'A_ps':
        s.tag(cxp, cyp - 6, f'{sym("N_str")} × {sym("A_str")}', HL)
        s.tag(cxp, cyp + 8, f'{v("N_str"):g} × {v("A_str", "in^2"):.3f} in²', HL)
    if name == 'f_pc_eff':
        for t in (-0.28, 0.28):
            for (px, py, qx, qy) in ((t * D, D / 2 + 3.5, t * D, D / 2 - 1.0), (t * D, -D / 2 - 3.5, t * D, -D / 2 + 1.0),
                                     (D / 2 + 3.5, t * D, D / 2 - 1.0, t * D), (-D / 2 - 3.5, t * D, -D / 2 + 1.0, t * D)):
                (ax_, ay_), (bx_, by_) = sec.P(px, py), sec.P(qx, qy)
                s.arrow(ax_, ay_, bx_, by_, HL, 1.8, 5)
        s.tag(cxp, cyp + 4, sym('f_pc_eff'), HL)
    if name in ('f_pj', 'f_pe', 'P_e'):
        _strand_bars(s, e, 290, 98, name)
    if name == 'A_ps':
        s.text(290, 92, 'area, in²', 10, GREY, 'start', 'bold')
        _draw_bars(s, [(sym('A_str') + ' (one)', v('A_str', 'in^2')), (sym('A_ps') + ' (all)', v('A_ps', 'in^2'))], {1}, 336, 344, 400, y0=100, step=28, places=3)
    if name in ('eps_pe', 'eps_ce', 'eps_cu'):
        _strain_profile(s, e, sec, name)
    Ag, Aps = v('A_g', 'in^2'), v('A_ps', 'in^2')
    rows = {
        'A_ps': [f'= {sym("N_str")} × {sym("A_str")}', f'= {v("N_str"):g} × {v("A_str", "in^2"):.3f} in²', ('strand pattern from Standard Plans', GREY)],
        'f_pj': [f'= {sym("P_jack")} / {sym("A_str")}', f'= {v("P_jack", "kip"):g} kip / {v("A_str", "in^2"):.3f} in²', ('jacking force per strand, Index 455', GREY)],
        'f_pe': [f'= {sym("f_pj")} (1 − {sym("loss_frac")})', f'= {v("f_pj", "ksi"):.2f} × (1 − {p["loss_frac"]:g}) ksi', ('loss fraction calibrated to the FBMP prestress', GREY)],
        'P_e': [f'= {sym("A_ps")} · {sym("f_pe")}', f'= {Aps:.3f} in² × {v("f_pe", "ksi"):.2f} ksi'],
        'A_g': [f'= {sym("D_pile")}² − π/4·{sym("d_void")}²', f'= {D:g}² − 0.7854 × {void:g}² in²', ('chamfers ignored; void subtracted', GREY)],
        'I_g': [f'= {sym("D_pile")}⁴/12 − π/64·{sym("d_void")}⁴', f'= {D:g}⁴/12 − 0.0491 × {void:g}⁴ in⁴', ('about a centroidal axis; chamfers ignored', GREY)],
        'S_g': [f'= {sym("I_g")} / (D/2)', f'= {v("I_g", "in^4"):.1f} in⁴ / {D / 2:g} in', ('extreme fiber, centroidal axis', GREY)],
        'f_pc_eff': [f'= {sym("P_e")} / {sym("A_g")}', f'= {v("P_e", "kip"):.1f} kip / {Ag:.1f} in²', ('uniform prestress on the gross area', GREY)],
        'eps_pe': [f'= {sym("f_pe")} / {sym("E_p")}', f'= {v("f_pe", "ksi"):.2f} ksi / {p["E_p"]:g} ksi', ('strain already in the strand after losses', GREY)],
        'eps_ce': [f'= {sym("f_pc_eff")} / {sym("E_c")}', f'= {v("f_pc_eff", "ksi"):.3f} ksi / {v("E_c", "ksi"):.0f} ksi', ('concrete strain to decompress', GREY)],
        'eps_cu': ['constant, LRFD 5.6.2.1', ('concrete crushing strain', GREY), ('sets the strain profile of the sweep', GREY)],
    }[name]
    places = 5 if name in ('eps_pe', 'eps_ce', 'eps_cu') else 3
    s.panel(_eq(e, name, places), rows)
    return s


# ============================================================================= 5. concrete relations
def concrete_relation(e, name):
    v, p = e.value, e.case['inputs']
    fc = p['fc']
    xs = [3.0 + i * 0.25 for i in range(53)]
    label = f'f′c = {fc:g} ksi'
    if name == 'beta_1':
        return _plot(e, name, [(xs, [min(0.85, max(0.65, 0.85 - 0.05 * (x - 4))) for x in xs], BLUE)], 'f′c (ksi)', 'β1',
                     [(fc, v(name), label)], 'Stress block factor β1 vs f′c (LRFD 5.6.2.2)', y_range=(0.6, 0.9),
                     rows=[f'= 0.85 − 0.05 (f′c − 4 ksi)', f'= 0.85 − 0.05 × ({fc:g} − 4)', ('limited to 0.65 to 0.85', GREY)])
    if name == 'E_c':
        wc, k1 = p['w_c'], p['K_1']
        return _plot(e, name, [(xs, [120000 * k1 * wc ** 2 * x ** 0.33 for x in xs], BLUE)], 'f′c (ksi)', 'Ec (ksi)',
                     [(fc, v(name, 'ksi'), label)], 'Concrete modulus vs f′c (LRFD 5.4.2.4)',
                     rows=[f'= 120000 {sym("K_1")} {sym("w_c")}² f′c^0.33', f'{sym("w_c")} = {wc:g} kcf, {sym("K_1")} = {k1:g}'], places=1)
    return _plot(e, name, [(xs, [min(0.85, max(0.75, 0.85 - 0.02 * max(x - 10, 0))) for x in xs], BLUE)], 'f′c (ksi)', 'kc',
                 [(fc, v(name), label)], 'Concrete stress ratio kc vs f′c (LRFD 5.6.4.4)', y_range=(0.7, 0.9),
                 rows=['= 0.85 − 0.02 (f′c − 10 ksi)', f'= 0.85 − 0.02 × max({fc:g} − 10, 0)', ('limited to 0.75 to 0.85', GREY)])


# ============================================================================= 6. axial
def axial(e, name):
    v, p = e.value, e.case['inputs']
    Ag, Aps, kc, fc = v('A_g', 'in^2'), v('A_ps', 'in^2'), v('k_c'), p['fc']
    fpe, Ep, ecu = v('f_pe', 'ksi'), p['E_p'], v('eps_cu')
    conc = kc * fc * (Ag - Aps)
    strand = Aps * (fpe - Ep * ecu)
    Po, Pn, Pr, Pbi = v('P_o', 'kip'), v('P_n_max', 'kip'), v('P_r_max', 'kip'), v('P_bi_lim', 'kip')
    s = Svg('Axial resistance of the section: concrete block at 0.85 kc f′c over the net area less the strand terms, then the spiral and phi reductions.',
            title='Axial resistance at zero eccentricity')
    sec = Sec(s, e, 96, 108, 116)
    sec.draw(fill='#f3dcb2')
    sec.strands(HL if name == 'P_o' else INK)
    cx, cy = sec.P(0, 0)
    s.tag(cx, cy + 3, f'0.85·{sym("k_c")}·f′c', INK)
    s.tag(cx, sec.P(0, -sec.D / 2)[1] + 16, 'uniform block on the net area', GREY)
    top_right = max(sec.strand_points(), key=lambda q: (q[1], q[0]))
    sx, sy = sec.P(*top_right)
    s.line(sx, sy, 178, 76, GREY, 0.8)
    s.tag(180, 80, f'strand force {sym("A_ps")}({sym("f_pe")} − {sym("E_p")}{sym("eps_cu")})', INK, 'start')
    if name == 'P_o':
        items = [(f'{sym("k_c")}f′c({sym("A_g")} − {sym("A_ps")})', conc), (f'−{sym("A_ps")}({sym("f_pe")} − {sym("E_p")}{sym("eps_cu")})', -strand), (sym('P_o'), Po)]
        hl = {2}
        rows = [f'= {sym("k_c")}·f′c·({sym("A_g")} − {sym("A_ps")})', f'  − {sym("A_ps")}·({sym("f_pe")} − {sym("E_p")}·{sym("eps_cu")})',
                f'= {conc:.1f} − {strand:.1f} kip', ('LRFD 5.6.4.4, strand term reduces Po', GREY)]
    elif name == 'P_n_max':
        items, hl = [(sym('P_o'), Po), (sym('P_n_max'), Pn)], {1}
        rows = [f'= 0.85 × {sym("P_o")}', f'= 0.85 × {Po:.1f} kip', ('spiral-reinforced member', GREY)]
    elif name == 'P_r_max':
        items, hl = [(sym('P_n_max'), Pn), (sym('P_r_max'), Pr)], {1}
        rows = [f'= {sym("phi_c")} × {sym("P_n_max")}', f'= {p["phi_c"]:g} × {Pn:.1f} kip', ('compression-controlled φ', GREY)]
    else:
        items, hl = [(sym('P_bi_lim'), Pbi), (f'{sym("P_u_bi")} (governing)', v('P_u_bi', 'kip'))], {0}
        rows = [f'= 0.10 · {sym("phi_c")} · f′c · {sym("A_g")}', f'= 0.10 × {p["phi_c"]:g} × {fc:g} × {Ag:.1f}',
                ('P_u ≥ limit: Eq. 5.6.4.5-1', GREY), ('P_u below it: Eq. 5.6.4.5-3', GREY)]
    _draw_bars(s, items, hl, 296, 304, 395, y0=204, step=26, places=1)
    s.panel(_eq(e, name, 3), rows)
    return s


# ============================================================================= 7. interaction routes
def interaction(e, name):
    v, p = e.value, e.case['inputs']
    d = e.details
    eq1 = d['branch'] == 'eq1'
    resultant = name == 'DC_rs'
    curve = e.curve['resultant'] if resultant else e.curve
    Mr, Pr = np.asarray(curve['Mr'], float), np.asarray(curve['Pr'], float)
    if resultant:
        title = f'Resultant bending axis ({v("alpha_rs", "deg"):.1f}°): demand ray to the φ-curve'
    elif eq1:
        title = 'Uniaxial φ-curve: LRFD Eq. 5.6.4.5-1 (axial resistance at the eccentricities)'
    else:
        title = 'Uniaxial φ-curve: LRFD Eq. 5.6.4.5-3 (moment resistance at P = 0)'
    short = not resultant and not eq1
    s = Svg(title + '. Demand in black, capacity points in color, the quantity of this equation in red.', title=escape(title))
    mx = [Mr.max()]
    if resultant:
        mx += [v('M_u_rs', 'kip*ft'), v('M_r_rs', 'kip*ft')]
    elif eq1:
        mx += [v('M_ux_bi', 'kip*ft'), v('M_uy_bi', 'kip*ft'), v('P_rx', 'kip') * v('e_y', 'in') / 12, v('P_ry', 'kip') * v('e_x', 'in') / 12]
    else:
        mx += [v('M_ux_bi', 'kip*ft'), v('M_uy_bi', 'kip*ft'), v('M_rx', 'kip*ft')]
    ymax, ymin = max(Pr.max(), 1.0) * 1.1, min(Pr.min(), 0.0) * 1.12
    ax = Axes(s, 0, max(mx) * 1.1, ymin, ymax, 'M (kip-ft)', 'P (kip, compression +)', height=170 if short else 240)
    ax.curve(Mr, Pr, BLUE, 2)
    s.line(ax.left, ax.Y(0), ax.left + ax.width, ax.Y(0), GREY, 0.8, '3 3')
    tag_l = lambda t, c=INK: f'<tspan fill="{c}">{t}</tspan>'
    if resultant:
        dem = (v('M_u_rs', 'kip*ft'), v('P_u_rs', 'kip'))
        cap = (v('M_r_rs', 'kip*ft'), v('P_r_rs', 'kip'))
        far = (cap[0] * 1.0, cap[1] * 1.0)
        ax.curve([0, far[0]], [0, far[1]], GREY, 1.2, '5 3')
        ax.point(dem[0], dem[1], INK, 'demand', 'end', 8, 16)
        ax.point(cap[0], cap[1], HL, 'capacity', 'end', 10, -8)
        rows = [f'= M_u / M_r (ray) = {dem[0]:.1f} / {cap[0]:.1f}', f'P_u = {dem[1]:.1f} kip, P_r = {cap[1]:.1f} kip',
                f'bending axis {v("alpha_rs", "deg"):.1f}° from a face', ('ray from the origin through the demand', GREY)]
    elif eq1:
        Pu, ey, ex = v('P_u_bi', 'kip'), v('e_y', 'in'), v('e_x', 'in')
        Prx, Pry, Prxy = v('P_rx', 'kip'), v('P_ry', 'kip'), v('P_rxy', 'kip')
        mrx, mry = Prx * ey / 12, Pry * ex / 12
        ax.curve([0, mrx], [0, Prx], BLUE, 1.2, '5 3')
        ax.curve([0, mry], [0, Pry], TEAL, 1.2, '5 3')
        ax.point(mrx, Prx, BLUE, sym('P_rx'), 'start', 8, -6, 4)
        ax.point(mry, Pry, TEAL, sym('P_ry'), 'start', 8, 24, 4)
        ax.point(v('M_ux_bi', 'kip*ft'), Pu, INK, '', r=3.5)
        ax.point(v('M_uy_bi', 'kip*ft'), Pu, INK, '', r=3.5)
        hl_dc, hl_pr = name in ('DC_bi', 'P_rxy'), name in ('DC_bi', 'P_rxy')
        ax.hline(Pu, f'{sym("P_u_bi")} = {Pu:.1f}', HL if name == 'DC_bi' else GREY, '6 3', 'start')
        ax.hline(Prxy, f'{sym("P_rxy")} = {Prxy:.1f}', HL if hl_pr else AMBER, '6 3', 'start')
        rows = [f'= {sym("P_u_bi")} / {sym("P_rxy")}', f'= {Pu:.2f} / {Prxy:.2f} kip', 'LRFD Eq. 5.6.4.5-1',
                (f'P_rx {Prx:.1f} · P_ry {Pry:.1f} kip', GREY)] if name == 'DC_bi' else \
               [f'= 1 / (1/{sym("P_rx")} + 1/{sym("P_ry")} − 1/(φ{sym("P_o")}))', f'= 1 / (1/{Prx:.1f} + 1/{Pry:.1f} − 1/{d["phi_Po"]:.1f})',
                (f'e_y = {ey:.2f} in, e_x = {ex:.2f} in', GREY), ('P_rx, P_ry read on the φ-curve at e_y, e_x', GREY)]
    else:
        Mux, Muy, Mrx, Mry = v('M_ux_bi', 'kip*ft'), v('M_uy_bi', 'kip*ft'), v('M_rx', 'kip*ft'), v('M_ry', 'kip*ft')
        ax.point(Mrx, 0, HL, f'{sym("M_rx")} = {sym("M_ry")} = {Mrx:.0f}', 'end', 8, -8)
        ax.point(Mux, 0, INK, sym('M_ux_bi'), 'start', 4, 16, 3.5)
        ax.point(Muy, 0, INK, sym('M_uy_bi'), 'start', 4, 16, 3.5)
        # stacked demand/capacity bar
        y0, x0, wd = 282, ax.left, ax.width
        top = max(1.0, v('DC_bi')) * 1.15
        a, b = Mux / Mrx / top * wd, Muy / Mry / top * wd
        s.rect(x0, y0, a, 18, fill=LIGHT, stroke='none')
        s.rect(x0 + a, y0, b, 18, fill=TEAL, stroke='none', op=0.55)
        s.line(x0 + wd / top, y0 - 6, x0 + wd / top, y0 + 24, HL if name == 'DC_bi' else AMBER, 1.6, '4 2')
        s.tag(x0 + wd / top, y0 + 36, 'limit 1.0', AMBER)
        s.tag(x0 + 2, y0 + 34, f'{sym("M_ux_bi")}/{sym("M_rx")} = {Mux / Mrx:.3f}', INK, 'start')
        s.tag(x0 + 2, y0 + 48, f'{sym("M_uy_bi")}/{sym("M_ry")} = {Muy / Mry:.3f}', TEAL, 'start')
        s.tag(x0 + 130, y0 + 41, f'sum = {sym("DC_bi")} = {v("DC_bi"):.3f}', HL if name == 'DC_bi' else INK, 'start')
        rows = [f'= {sym("M_ux_bi")}/{sym("M_rx")} + {sym("M_uy_bi")}/{sym("M_ry")}', f'= {Mux:.1f}/{Mrx:.1f} + {Muy:.1f}/{Mry:.1f} kip-ft', 'LRFD Eq. 5.6.4.5-3',
                (f'{sym("P_u_bi")} = {v("P_u_bi", "kip"):.1f} kip below the {sym("P_bi_lim")} limit', GREY)]
    s.panel(_eq(e, name, 3), rows)
    return s


def eccentricity(e, name):
    v = e.value
    Pu, Mux, Muy = v('P_u_bi', 'kip'), v('M_ux_bi', 'kip*ft'), v('M_uy_bi', 'kip*ft')
    ey, ex = v('e_y', 'in'), v('e_x', 'in')
    D = float(_inp(e, 'D_pile'))
    s = Svg('Plan of the pile section: the governing axial load acts at (e_x, e_y) from the centroid, e = M / P for each axis.',
            title='Eccentricity of the governing load (biaxial route)')
    span = max(D, 2 * max(ex, ey) * 1.25)
    sec = Sec(s, e, 170, 190, 230, span=span)
    sec.draw()
    sec.strands(GREY)
    cx, cy = sec.P(0, 0)
    ext = sec.L(span / 2) + 10
    s.line(cx - ext, cy, cx + ext, cy, GREY, 0.9, '5 3')
    s.line(cx, cy - ext, cx, cy + ext, GREY, 0.9, '5 3')
    s.tag(cx + ext, cy + 12, 'x', GREY, 'end')
    s.tag(cx + 6, cy - ext + 8, 'y', GREY, 'start')
    px, py = sec.P(ex, ey)
    s.circle(px, py, 6, fill=HL)
    s.circle(px, py, 2, fill='#ffffff')
    s.tag(px + 9, py - 8, f'{sym("P_u_bi")}', HL, 'start')
    hx, hy = name == 'e_x', name == 'e_y'
    s.dim(cx, py + 16, px, py + 16, sym('e_x'), HL if hx else INK, side=1)
    s.dim(px + 16, cy, px + 16, py, sym('e_y'), HL if hy else INK, side=1)
    s.line(px, py, px, py + 20, FAINT, 0.8)
    s.line(px, py, px + 20, py, FAINT, 0.8)
    if name == 'e_y':
        rows = [f'= {sym("M_ux_bi")} / {sym("P_u_bi")}', f'= {Mux:.2f} kip-ft × 12 / {Pu:.2f} kip', ('moment about the x axis ↔ offset in y', GREY)]
    else:
        rows = [f'= {sym("M_uy_bi")} / {sym("P_u_bi")}', f'= {Muy:.2f} kip-ft × 12 / {Pu:.2f} kip', ('moment about the y axis ↔ offset in x', GREY)]
    s.panel(_eq(e, name, 3), rows)
    return s


# ============================================================================= 8. tension
def tension(e, name):
    v, p = e.value, e.case['inputs']
    Tu = v('T_u', 'kip')
    if e.family == 'pipe':
        Ag, Fy = v('A_g', 'in^2'), p['Fy']
        items = [(f'{sym("Fy")}·{sym("A_g")}', Fy * Ag), (f'{sym("P_r_t")} = {sym("phi_y")}{sym("Fy")}{sym("A_g")}', v('P_r_t', 'kip')), (f'{sym("T_u")} (FBMP uplift)', Tu)]
        hl = {'P_r_t': {1}, 'DC_t': {1, 2}}[name]
        rows = {'P_r_t': [f'= {sym("phi_y")} · {sym("Fy")} · {sym("A_g")}', f'= {p["phi_y"]:g} × {Fy:g} ksi × {Ag:.3f} in²', ('LRFD Eq. 6.8.2.1-1, gross yielding', GREY)],
                'DC_t': [f'= {sym("T_u")} / {sym("P_r_t")}', f'= {Tu:.2f} / {v("P_r_t", "kip"):.2f} kip', ('largest strength uplift in the model', GREY)]}[name]
        return _bars(e, name, items, 'kip', 'Pipe tension resistance and demand', hl, rows)
    Aps, fpy, fpe = v('A_ps', 'in^2'), p['f_py'], v('f_pe', 'ksi')
    yield_, alt, Pn, Pr = v('P_t_yield', 'kip'), Aps * (fpe + 60.0), v('P_n_t', 'kip'), v('P_r_t', 'kip')
    items = [(f'{sym("A_ps")}·{sym("f_py")}', yield_), (f'{sym("A_ps")}({sym("f_pe")} + 60 ksi)', alt), (sym('P_n_t'), Pn),
             (f'{sym("P_r_t")} = {sym("phi_t")}{sym("P_n_t")}', Pr), (f'{sym("T_u")} (FBMP uplift)', Tu)]
    hl = {'P_t_yield': {0}, 'P_n_t': {2}, 'P_r_t': {3}, 'DC_t': {3, 4}}[name]
    rows = {'P_t_yield': [f'= {sym("A_ps")} · {sym("f_py")}', f'= {Aps:.3f} in² × {fpy:g} ksi', ('upper bound, strand yield', GREY)],
            'P_n_t': [f'= {sym("A_ps")} · min({sym("f_py")}, {sym("f_pe")} + 60 ksi)', f'= {Aps:.3f} × min({fpy:g}, {fpe + 60:.2f}) ksi', ('LRFD Eq. 5.8.2.4.1-1, no mild steel', GREY)],
            'P_r_t': [f'= {sym("phi_t")} · {sym("P_n_t")}', f'= {p["phi_t"]:g} × {Pn:.2f} kip', ('bonded prestressing, φ = 1.0', GREY)],
            'DC_t': [f'= {sym("T_u")} / {sym("P_r_t")}', f'= {Tu:.2f} / {Pr:.2f} kip', ('largest strength uplift in the model', GREY)]}[name]
    return _bars(e, name, items, 'kip', 'Pile tension resistance (strand only) and demand', hl, rows)


# ============================================================================= 9. shear (prestressed concrete)
def shear_section(e, name):
    from .sections import _clip
    v, p = e.value, e.case['inputs']
    a = e.details['shear']['angle']
    D, void = float(p['D_pile']), v('d_void', 'in')
    d_e, d_v, b_v = v('d_e', 'in'), v('d_v', 'in'), v('b_v', 'in')
    s = Svg('Section with the bending axis at the resultant angle: strands on the flexural tension half (red) define Aps,t and the depth d_e.',
            title=f'Shear section · bending axis {math.degrees(a):.1f}° · compression face up')
    sec = Sec(s, e, 150, 188, 190, angle=a)
    h = D / 2
    sec.draw()
    if name == 'A_ct':
        half = _clip([(-h, -h), (h, -h), (h, h), (-h, h)], math.sin(a), -math.cos(a), 0.0)
        s.poly([sec.P(*q) for q in half], fill=HL, stroke='none', op=0.2)
    colors = [HL if (-x * math.sin(a) + y * math.cos(a)) < -1e-9 else INK for x, y in sec.strand_points()]
    sec.strands(colors=colors)
    smax = h * (abs(math.cos(a)) + abs(math.sin(a)))
    cx, cy = sec.cx, sec.cy
    ytop = cy - sec.k * smax
    ye, yv = ytop + sec.L(d_e), ytop + sec.L(d_v)
    xr = cx + sec.k * smax
    s.line(cx - sec.k * smax - 6, cy, xr + 6, cy, GREY, 0.9, '6 3')
    s.tag(cx - sec.k * smax - 8, cy - 4, 'centroid', GREY, 'end')
    s.line(cx - sec.k * smax - 6, ye, xr + 26, ye, AMBER, 1.2, '5 3')
    s.dim(xr + 14, ytop, xr + 14, ye, sym('d_e'), GREY)
    s.dim(xr + 52, ytop, xr + 52, yv, sym('s_x') if name == 's_x' else sym('d_v'), HL if name in ('d_v', 's_x') else GREY)
    s.line(xr + 14, yv, xr + 52, yv, FAINT, 0.8, '3 2')
    s.line(xr + 14, ytop, xr + 52, ytop, FAINT, 0.8, '3 2')
    bl, br = sec.P(-h, 0), sec.P(h, 0)
    s.dim(bl[0], bl[1], br[0], br[1], sym('b_v'), HL if name == 'b_v' else GREY, side=1, offset=-14)
    s.tag(cx, ytop - 8, 'extreme compression fiber', GREY)
    s.tag(cx, cy + sec.k * smax + 14, f'{sym("A_ps_t")} = {v("A_ps_t", "in^2"):.3f} in² (red strands)', INK)
    rows = {
        'b_v': [f'= {sym("D_pile")} − {sym("d_void")}', f'= {D:g} − {void:g} in', ('web width, voids subtracted', GREY)],
        'd_v': [f'= max(0.9 {sym("d_e")}, 0.72 {sym("D_pile")})', f'= max(0.9 × {d_e:.3f}, 0.72 × {D:g}) in', ('d_e: compression fiber to Aps,t centroid', GREY)],
        's_x': [f'= {sym("d_v")}', ('no longitudinal crack-control steel', GREY)],
        'A_ct': [f'= {sym("A_g")} / 2', f'= {v("A_g", "in^2"):.1f} in² / 2', ('concrete on the flexural tension side', GREY)],
    }[name]
    s.panel(_eq(e, name, 3), rows)
    return s


def shear_sxe(e, name):
    v, p = e.value, e.case['inputs']
    sx, sxe = v('s_x', 'in'), v('s_xe', 'in')
    items = [(sym('s_x'), sx), (f'{sym("s_xe")} = {sym("s_x")}·1.38/({sym("a_g")} + 0.63)', sxe), ('lower limit', 12.0), ('upper limit', 80.0)]
    raw = sx * 1.38 / (p['a_g'] + 0.63)
    rows = [f'= min(80 in, max(12 in, {sym("s_x")}·1.38/({sym("a_g")} + 0.63)))', f'= min(80, max(12, {sx:.3f} × 1.38 / ({p["a_g"]:g} + 0.63))) in',
            (f'unclamped {raw:.2f} in; {sym("a_g")} = {p["a_g"]:g} in', GREY), (f'LRFD Eq. 5.7.3.4.2-7; used only if {sym("A_v")} &lt; {sym("A_v_min")}', GREY)]
    return _bars(e, name, items, 'in', 'Equivalent crack spacing', 1, rows)


def shear_forces(e, name):
    v, p = e.value, e.case['inputs']
    Mu, Vu, Pu = v('M_u_sh', 'kip*ft'), v('V_u_sh', 'kip'), v('P_u_sh', 'kip')
    dv, Aps_t, fpo = v('d_v', 'in'), v('A_ps_t', 'in^2'), v('f_po', 'ksi')
    if name == 'M_u_v':
        items, unit = [(sym('M_u_sh'), Mu), (f'{sym("V_u_sh")}·{sym("d_v")}', Vu * dv / 12), (sym('M_u_v'), v('M_u_v', 'kip*ft'))], 'kip-ft'
        hl, rows = {2}, [f'= max({sym("M_u_sh")}, {sym("V_u_sh")}·{sym("d_v")})', f'= max({Mu:.2f}, {Vu:.2f} × {dv:.3f} / 12) kip-ft', ('LRFD 5.7.3.4.2: moment not below Vu dv', GREY)]
    elif name == 'N_u':
        items, unit = [(f'{sym("P_u_sh")} (compression +)', Pu), (f'{sym("N_u")} (tension +)', -Pu)], 'kip'
        hl, rows = {1}, [f'= −{sym("P_u_sh")}', f'= −({Pu:.3f}) kip', ('sign flip: tension positive', GREY)]
    elif name == 'f_po':
        items, unit = [(sym('f_pu'), p['f_pu']), (f'{sym("f_po")} = 0.7 {sym("f_pu")}', fpo)], 'ksi'
        hl, rows = {1}, [f'= 0.7 × {sym("f_pu")}', f'= 0.7 × {p["f_pu"]:g} ksi', ('locked-in strand stress parameter', GREY)]
    else:
        terms = [(f'{sym("M_u_v")}/{sym("d_v")}', v('M_u_v', 'kip*ft') * 12 / dv), (f'0.5 {sym("N_u")}', 0.5 * v('N_u', 'kip')),
                 (sym('V_u_sh'), Vu), (f'−{sym("A_ps_t")} {sym("f_po")}', -Aps_t * fpo), (sym('F_long'), v('F_long', 'kip'))]
        items, unit, hl = terms, 'kip', {4}
        rows = [f'= {sym("M_u_v")}/{sym("d_v")} + 0.5 {sym("N_u")} + {sym("V_u_sh")}', f'  − {sym("A_ps_t")} {sym("f_po")}',
                f'= {terms[0][1]:.1f} {terms[1][1]:+.1f} {terms[2][1]:+.1f} {terms[3][1]:+.1f} kip', ('numerator of Eq. 5.7.3.4.2-4', GREY)]
    return _bars(e, name, items, unit, 'Longitudinal force demand for the shear strain' if name in ('F_long', 'M_u_v', 'N_u') else 'Strand stress parameter', hl, rows)


def shear_strain(e, name):
    v = e.value
    e0, e1, es = v('eps_s0'), v('eps_s1'), v('eps_s')
    Fl, EpA = v('F_long', 'kip'), e.case['inputs']['E_p'] * v('A_ps_t', 'in^2')
    EcA = v('E_c', 'ksi') * v('A_ct', 'in^2')
    s = Svg('Longitudinal strain at mid-depth of the shear section: three candidates on a strain scale, and the denominators that separate them.',
            title='Longitudinal strain εs, LRFD Eq. 5.7.3.4.2-4 (strain × 10⁻³)')
    lo = min(e0, e1, es, -0.0004, 0.0)
    hi = max(e0, e1, es, 0.0)
    span = max(hi - lo, 0.0008)
    lo, hi = lo - 0.12 * span, hi + 0.12 * span
    xa, xb, y = 44, 436, 112
    X = lambda t: xa + (t - lo) / (hi - lo) * (xb - xa)
    s.line(xa, y, xb, y, INK, 1.2)
    for i in range(5):
        t = lo + (hi - lo) * i / 4
        s.line(X(t), y - 3, X(t), y + 3, INK)
        s.text(X(t), y + 15, f'{t * 1000:.2f}', 9, GREY)
    s.line(X(0), y - 30, X(0), y + 4, GREY, 0.9, '3 3')
    s.tag(X(0) + 3, y - 32, '0', GREY, 'start')
    s.line(X(-0.0004), y - 22, X(-0.0004), y + 22, AMBER, 1.2, '4 3')
    left_clamp = -0.0004 < e1
    s.tag(X(-0.0004) + (-3 if left_clamp else 3), y + 36, 'limit −0.40', AMBER, 'end' if left_clamp else 'start')
    marks = [('eps_s0', e0, 'start', -14, name == 'eps_s0'), ('eps_s1', e1, 'end' if not left_clamp else 'start', 28, name == 'eps_s1'),
             ('eps_s', es, 'start', -14, name == 'eps_s')]
    placed = []
    for key, val, anchor, dy, on in marks:
        s.circle(X(val), y, 6 if on else 4, fill=HL if on else INK)
        yy = y + dy - (14 if (key == 'eps_s' and abs(val - e0) < 0.0008 * 1.5) else 0)
        s.tag(X(val) + (6 if anchor == 'start' else -6), yy, f'{sym(key)} = {val * 1000:.3f}', HL if on else INK, anchor)
    s.text(xa, 165, 'denominators and numerator of the strain, kip', 10, GREY, 'start', 'bold')
    items = [(sym('F_long'), Fl), (f'{sym("E_p")}·{sym("A_ps_t")}', EpA), (f'{sym("E_c")}·{sym("A_ct")}', EcA)]
    _draw_bars(s, items, set(), 150, 190, 380, y0=178, step=28, places=0, colors=[LIGHT, TEAL, STRAP])
    s.text(xa, 280, f'{sym("eps_s0")} = {sym("F_long")} / ({sym("E_p")} {sym("A_ps_t")})   ·   {sym("eps_s1")} = {sym("F_long")} / ({sym("E_p")} {sym("A_ps_t")} + {sym("E_c")} {sym("A_ct")})', 9.5, INK, 'start')
    s.text(xa, 296, f'{sym("eps_s")} = max({sym("eps_s1")} if {sym("eps_s0")} &lt; 0 else {sym("eps_s0")}, −0.40×10⁻³)', 9.5, INK, 'start')
    rows = {
        'eps_s0': [f'= {sym("F_long")} / ({sym("E_p")} {sym("A_ps_t")})', f'= {Fl:.1f} kip / {EpA:.0f} kip', ('used when positive (tension)', GREY)],
        'eps_s1': [f'= {sym("F_long")} / ({sym("E_p")} {sym("A_ps_t")} + {sym("E_c")} {sym("A_ct")})', f'= {Fl:.1f} / ({EpA:.0f} + {EcA:.0f}) kip', (f'used when {sym("eps_s0")} is negative', GREY)],
        'eps_s': [f'= max({sym("eps_s1") if e0 < 0 else sym("eps_s0")}, −0.40×10⁻³)', f'= max({(e1 if e0 < 0 else e0) * 1000:.3f}, −0.400)×10⁻³', ('lower limit −0.40×10⁻³', GREY)],
    }[name]
    s.panel(_eq(e, name, 5), rows)
    return s


def shear_spiral(e, name):
    v, p = e.value, e.case['inputs']
    D, pitch = float(p['D_pile']), p['spiral_pitch']
    s = Svg('Elevation of the pile: spiral wire at the pitch, two legs cut by a shear plane (Av), against the minimum area (Av,min).',
            title='Spiral reinforcement crossing the shear plane')
    k = 118 / D
    x0, y0, y1 = 84, 52, 300
    wcol = D * k
    s.rect(x0, y0, wcol, y1 - y0, fill=CONC, stroke=INK, sw=1.2)
    pk = pitch * k
    y = y0 + 8
    count = 0
    while y + pk <= y1 - 4:
        s.line(x0, y, x0 + wcol, y + pk / 2, STRAP, 2.0)
        s.line(x0 + wcol, y + pk / 2, x0, y + pk, STRAP, 1.0, '3 2')
        y += pk
        count += 1
    ycut = (y0 + y1) / 2 + 3
    s.line(x0 - 14, ycut, x0 + wcol + 14, ycut, HL if name == 'A_v' else GREY, 1.6, '6 3')
    for xx in (x0, x0 + wcol):
        s.circle(xx, ycut, 4.5, fill=HL if name == 'A_v' else INK)
    s.tag(x0 + wcol / 2, ycut - 7, 'shear plane: 2 legs' if name == 'A_v' else 'shear plane', HL if name == 'A_v' else GREY)
    s.dim(x0 - 16, y0 + 8, x0 - 16, y0 + 8 + pk, f's = {pitch:g} in', HL if name == 'A_v_min' else GREY, side=-1)
    Av, Avm = v('A_v', 'in^2'), v('A_v_min', 'in^2')
    s.text(232, 74, 'transverse steel area, in²', 10, GREY, 'start', 'bold')
    _draw_bars(s, [(sym('A_v'), Av), (sym('A_v_min'), Avm)], {0 if name == 'A_v' else 1}, 290, 300, 395, y0=86, step=28, places=4)
    ok = Av >= Avm
    s.tag(232, 160, f'{sym("A_v")} {"≥" if ok else "&lt;"} {sym("A_v_min")}: Eq. 5.7.3.4.2-{"1" if ok else "2"}', INK, 'start')
    s.tag(232, 176, 'β without the s_xe factor' if ok else f'β reduced by 51/(39 + {sym("s_xe")})', GREY, 'start')
    rows = {
        'A_v': [f'= 2 × {sym("spiral_wire_area")}', f'= 2 × {p["spiral_wire_area"]:g} in²', ('two legs cross the shear plane', GREY)],
        'A_v_min': [f'= 0.0316 {sym("lambda_c")} √f′c {sym("b_v")} s / {sym("f_y_spiral")}', f'= 0.0316 × {p["lambda_c"]:g} × √{p["fc"]:g} × {v("b_v", "in"):g} × {pitch:g} / {p["f_y_spiral"]:g}', ('LRFD 5.7.2.5, in², s = spiral pitch', GREY)],
    }[name]
    s.panel(_eq(e, name, 4), rows)
    return s


def shear_curves(e, name):
    v, p = e.value, e.case['inputs']
    es = v('eps_s')
    x1 = max(3.0, es * 1000 * 1.3)
    xs = [-0.5 + (x1 + 0.5) * i / 60 for i in range(61)]
    ok = v('A_v', 'in^2') >= v('A_v_min', 'in^2')
    if name == 'beta_v':
        base = [4.8 / (1 + 750 * x / 1000) for x in xs]
        series = [(xs, base, BLUE)]
        rows = [f'= 4.8 / (1 + 750 {sym("eps_s")})' + ('' if ok else f' × 51/(39 + {sym("s_xe")})'), f'= 4.8 / (1 + 750 × {es:.5f})' + ('' if ok else f' × 51/(39 + {v("s_xe", "in"):.2f})'),
                (f'A_v {"≥" if ok else "&lt;"} A_v,min: Eq. 5.7.3.4.2-{"1" if ok else "2"}', GREY)]
        if not ok:
            series.append((xs, [b * 51.0 / (39.0 + v('s_xe', 'in')) for b in base], TEAL))
        return _plot(e, name, series, 'longitudinal strain εs (×10⁻³)', 'β', [(es * 1000, v(name), f'εs = {es * 1000:.3f}×10⁻³')],
                     'Shear parameter β vs εs (LRFD 5.7.3.4.2)', x_range=(-0.5, x1), y_range=(0, 8), rows=rows)
    rows = [f'= (29 + 3500 {sym("eps_s")})°', f'= 29 + 3500 × {es:.5f}', ('LRFD Eq. 5.7.3.4.2-3', GREY)]
    return _plot(e, name, [(xs, [29 + 3500 * x / 1000 for x in xs], BLUE)], 'longitudinal strain εs (×10⁻³)', 'θ (deg)',
                 [(es * 1000, v(name, 'deg'), f'εs = {es * 1000:.3f}×10⁻³')], 'Crack angle θ vs εs (LRFD 5.7.3.4.2)', x_range=(-0.5, x1), y_range=(25, 45), rows=rows)


def shear_strength(e, name):
    v, p = e.value, e.case['inputs']
    Vc, Vs, Vn, Vr, Vu = v('V_c', 'kip'), v('V_s', 'kip'), v('V_n', 'kip'), v('V_r', 'kip'), v('V_u_sh', 'kip')
    cap = 0.25 * p['fc'] * v('b_v', 'in') * v('d_v', 'in')
    s = Svg('Shear strength build-up: concrete and spiral contributions, the 0.25 f′c bv dv cap, the nominal and factored resistance, and the demand.',
            title='Shear resistance build-up (kip)')
    top = max(Vc + Vs, cap, Vn, Vr, Vu, 1.0)
    scale = 190 / top
    x0, label_x = 214, 204
    rows_y = [48 + 36 * i for i in range(5)]
    s.line(x0, 40, x0, rows_y[-1] + 28, GREY, 0.9)
    labels = [f'{sym("V_c")} + {sym("V_s")}', f'0.25 f′c {sym("b_v")} {sym("d_v")}', sym('V_n'), f'{sym("V_r")} = {sym("phi_v")} {sym("V_n")}', f'{sym("V_u_sh")} (demand)']
    on = {'V_c': 0, 'V_s': 0, 'V_n': 2, 'V_r': 3}[name]
    for i, (y, label) in enumerate(zip(rows_y, labels)):
        s.text(label_x, y + 14, label, 10, HL if i == on and name in ('V_n', 'V_r') else INK, 'end', 'bold' if i == on and name in ('V_n', 'V_r') else 'normal')
    s.rect(x0, rows_y[0] + 3, Vc * scale, 17, fill=HL if name == 'V_c' else LIGHT, stroke='none')
    s.rect(x0 + Vc * scale, rows_y[0] + 3, max(Vs * scale, 0), 17, fill=HL if name == 'V_s' else STRAP, stroke='none', op=1.0 if name == 'V_s' else 0.6)
    s.text(x0 + (Vc + Vs) * scale + 5, rows_y[0] + 16, f'{Vc:.1f} + {Vs:.1f} = {Vc + Vs:.1f}', 10, INK, 'start')
    for i, val, color in ((1, cap, AMBER), (2, Vn, LIGHT), (3, Vr, LIGHT), (4, Vu, INK)):
        hot = (name == 'V_n' and i == 2) or (name == 'V_r' and i == 3)
        s.rect(x0, rows_y[i] + 3, val * scale, 17, fill=HL if hot else color, stroke='none', op=0.55 if (color == AMBER or color == INK) else 1.0)
        s.text(x0 + val * scale + 5, rows_y[i] + 16, f'{val:.1f}', 10, HL if hot else INK, 'start', 'bold' if hot else 'normal')
    s.tag(x0 + 4, rows_y[0] - 6, f'{sym("V_c")} blue · {sym("V_s")} purple', GREY, 'start')
    rows = {
        'V_c': [f'= 0.0316 {sym("beta_v")} {sym("lambda_c")} √f′c {sym("b_v")} {sym("d_v")}',
                f'= 0.0316 × {v("beta_v"):.3f} × {p["lambda_c"]:g} × √{p["fc"]:g} × {v("b_v", "in"):g} × {v("d_v", "in"):.3f}'],
        'V_s': [f'= {sym("A_v")} {sym("f_y_spiral")} {sym("d_v")} / (tan {sym("theta_v")} · s)',
                f'= {v("A_v", "in^2"):.3f} × {p["f_y_spiral"]:g} × {v("d_v", "in"):.3f} / (tan {v("theta_v", "deg"):.2f}° × {p["spiral_pitch"]:g})'],
        'V_n': [f'= min({sym("V_c")} + {sym("V_s")}, 0.25 f′c {sym("b_v")} {sym("d_v")})', f'= min({Vc + Vs:.2f}, {cap:.2f}) kip', ('LRFD Eq. 5.7.3.3-1, -2', GREY)],
        'V_r': [f'= {sym("phi_v")} · {sym("V_n")}', f'= {p["phi_v"]:g} × {Vn:.2f} kip', (f'demand {sym("V_u_sh")} = {Vu:.2f} kip', GREY)],
    }[name]
    s.panel(_eq(e, name, 3), rows)
    return s


# ============================================================================= 10. service stresses
def service(e, name):
    v, p = e.value, e.case['inputs']
    if name == 'f_pc_min':
        return _bars(e, name, [(sym('f_pc_min'), v('f_pc_min', 'ksi')), (sym('f_pc_eff'), v('f_pc_eff', 'ksi'))], 'ksi', 'Minimum effective prestress', 0,
                     [f'= 0.7 ksi (constant)', ('LRFD 5.12.9.4: uniform compression after losses', GREY), (f'provided {sym("f_pc_eff")} = {v("f_pc_eff", "ksi"):.3f} ksi', GREY)])
    if name == 'D_min':
        env = int(p['environment'])
        extra = ([f'= max({sym("min_size_policy")}, 18 in)', f'= max({p["min_size_policy"]:g}, 18) in'] if env == 3 else [f'= {sym("min_size_policy")}', f'= {p["min_size_policy"]:g} in'])
        extra += [('SDG Table 3.5.1-1: 14 in pedestrian bridge;', GREY), ('18 in with carbon-steel strand, Extremely Aggressive', GREY)]
        return _bars(e, name, [(sym('D_min'), v('D_min', 'in')), (f'{sym("D_pile")} provided', p['D_pile'])], 'in', 'Minimum pile size, SDG Table 3.5.1-1', 0, extra)
    rec = 'sc' if name in ('sig_c', 'sig_c_lim') else 'st'
    fpc, Ag, Sg = v('f_pc_eff', 'ksi'), v('A_g', 'in^2'), v('S_g', 'in^3')
    P, Mx, My = v(f'P_{rec}', 'kip'), v(f'Mx_{rec}', 'kip*ft'), v(f'My_{rec}', 'kip*ft')
    base = fpc + P / Ag
    flex = (abs(Mx) + abs(My)) * 12.0 / Sg
    top, bot = base + flex, base - flex
    clim, tlim, fc = v('sig_c_lim', 'ksi'), v('f_t_lim', 'ksi'), p['fc']
    s = Svg('Stress across the section at the governing Service I record: effective prestress plus axial stress, plus and minus the flexural stress at the corners.',
            title=f'Service I corner stresses · {"compression" if rec == "sc" else "tension"} record (ksi, compression +)')
    lo, hi = min(bot, -tlim, 0.0), max(top, clim, 0.0)
    pad = 0.12 * (hi - lo)
    lo, hi = lo - pad, hi + pad
    xa, xb, y1, y2 = 40, 440, 66, 262
    X = lambda t: xa + (t - lo) / (hi - lo) * (xb - xa)
    s.poly([(X(top), y1), (X(bot), y2), (X(0), y2), (X(0), y1)], fill=AMBER, op=0.28, stroke=AMBER, sw=1.4)
    s.line(X(0), y1 - 8, X(0), y2 + 8, INK, 1.2)
    if name == 'f_t_net' and top > 0 > bot:
        yz = y1 + top / (top - bot) * (y2 - y1)
        s.poly([(X(0), yz), (X(bot), y2), (X(0), y2)], fill=HL, stroke='none', op=0.45)
    elif name == 'f_t_net' and bot >= 0:
        s.tag(X(0) + 8, y2 - 30, 'no net tension at the corner', HL, 'start')
    s.line(X(base), y1 - 8, X(base), y2 + 8, GREY, 1, '4 3')
    s.tag(X(base), y2 + 54, f'{sym("f_pc_eff")} + P/{sym("A_g")} = {base:.3f}', GREY)
    s.line(xa, y2 + 24, xb, y2 + 24, GREY, 0.8)
    for tv in nice_ticks(lo, hi, 7):
        s.line(X(tv), y2 + 24, X(tv), y2 + 28, GREY, 0.8)
        s.text(X(tv), y2 + 39, tick_text(tv), 9, GREY)
    hl_cl, hl_tl = name == 'sig_c_lim', name == 'f_t_lim'
    s.line(X(clim), y1 - 8, X(clim), y2 + 8, HL if hl_cl else AMBER, 1.6 if hl_cl else 1.2, '6 3')
    s.tag(X(clim) - 3, y1 - 22, f'0.6 f′c = {clim:.2f}', HL if hl_cl else AMBER, 'end')
    s.line(X(-tlim), y1 - 8, X(-tlim), y2 + 8, HL if hl_tl else AMBER, 1.6 if hl_tl else 1.2, '6 3')
    s.tag(X(-tlim) + 3, y1 - 22, f'tension limit −{tlim:.3f}', HL if hl_tl else AMBER, 'start')
    s.circle(X(top), y1, 5, fill=HL if name == 'sig_c' else INK)
    s.circle(X(bot), y2, 5, fill=HL if name == 'sig_t' else INK)
    s.tag(X(top) + 8, y1 + 3, f'{top:.3f}', HL if name == 'sig_c' else INK, 'start')
    s.tag(X(bot) - 8, y2 + 4, f'{bot:.3f}', HL if name == 'sig_t' else INK, 'end')
    s.tag(X(0) + 6, y1 - 8, 'compression corner', GREY, 'start')
    s.tag(X(0) + 6, y2 + 14, 'tension corner', GREY, 'start')
    envrow = f'min(0.3 ksi, 0.0948 λ √f′c)' if int(p['environment']) == 3 else 'min(0.6 ksi, 0.19 λ √f′c)'
    rows = {
        'sig_c': [f'= {sym("f_pc_eff")} + {sym("P_sc")}/{sym("A_g")} + (|{sym("Mx_sc")}|+|{sym("My_sc")}|)/{sym("S_g")}',
                  f'= {fpc:.3f} + {P / Ag:.3f} + {flex:.3f} ksi', ('record with the largest compression stress', GREY)],
        'sig_c_lim': [f'= 0.6 × f′c', f'= 0.6 × {fc:g} ksi', ('LRFD 5.9.2.3.2a, solid section (φw = 1)', GREY)],
        'sig_t': [f'= {sym("f_pc_eff")} + {sym("P_st")}/{sym("A_g")} − (|{sym("Mx_st")}|+|{sym("My_st")}|)/{sym("S_g")}',
                  f'= {fpc:.3f} + {P / Ag:.3f} − {flex:.3f} ksi', ('negative = tension; record with largest tension', GREY)],
        'f_t_net': [f'= max(−{sym("sig_t")}, 0 ksi)', f'= max({-v("sig_t", "ksi"):.3f}, 0) ksi', ('net tensile stress at the corner', GREY)],
        'f_t_lim': [f'= {envrow}', f'λ = {p["lambda_c"]:g}, f′c = {fc:g} ksi', (f'environment {int(p["environment"])}: LRFD Table 5.9.2.3.2b-1', GREY)],
    }[name]
    s.panel(_eq(e, name, 3), rows)
    return s


# ============================================================================= 11. pipe section
def pipe_ring(e, name):
    v, p = e.value, e.case['inputs']
    D, t, tc, td, Di = v('D_out', 'in'), v('t_wall', 'in'), v('t_corr', 'in'), v('t_des', 'in'), v('D_i', 'in')
    s = Svg('Cross-section of the steel pipe: outside diameter, design wall after the corrosion allowance (loss shaded), and the quantity of this equation.',
            title=f'Pipe section · {D:g} in × {t:g} in wall · corrosion allowance {tc:g} in')
    cx, cy = 160, 188
    k = 190 / D
    ro = k * D / 2
    grow = max(1.0, 7.0 / (k * t))          # wall drawn at least 7 px thick so the ring is legible
    ri0, ri = ro - k * t * grow, ro - k * td * grow
    wall_fill = '#f0b9b5' if name == 'A_g' else CONC
    s.ring(cx, cy, ro, ri, fill=wall_fill, stroke=INK, sw=1.4)
    if tc > 0:
        s.ring(cx, cy, ri, ri0, fill=AMBER, stroke=AMBER, sw=0.6, op=0.65)
        s.tag(cx + 24, cy + 28, 'corrosion loss (inside)', AMBER, 'start')
    else:
        s.circle(cx, cy, ri0, fill='none', stroke=GREY, sw=0.6)
    if name == 'I_g' or name == 'S_g' or name == 'Z_p':
        s.line(cx - ro - 12, cy, cx + ro + 12, cy, HL, 1.8, '7 3')
        s.tag(cx + ro + 16, cy + 16, 'plastic neutral axis' if name == 'Z_p' else 'centroidal axis', HL, 'start')
    if name == 'S_g':
        s.dim(cx + ro + 22, cy, cx + ro + 22, cy - ro, 'D/2', HL)
    if name == 'Z_p':
        s.arrow(cx - 30, cy - ro * 0.55, cx + 30, cy - ro * 0.55, HL, 2.2)
        s.arrow(cx + 30, cy + ro * 0.55, cx - 30, cy + ro * 0.55, HL, 2.2)
        s.tag(cx, cy - ro * 0.55 - 6, f'{sym("Fy")} (tension)', HL)
        s.tag(cx, cy + ro * 0.55 + 14, f'{sym("Fy")} (compression)', HL)
    if name == 'r_g':
        s.circle(cx, cy, k * v('r_g', 'in'), fill='none', stroke=HL, sw=1.6, dash='6 3')
        s.dim(cx, cy, cx + k * v('r_g', 'in') * 0.7071, cy - k * v('r_g', 'in') * 0.7071, sym('r_g'), HL)
    hl_d = name in ('D_t',)
    s.dim(cx - ro, cy + ro + 24, cx + ro, cy + ro + 24, f'{sym("D_out")} = {D:g} in', HL if hl_d else GREY, side=1)
    if name == 'D_i':
        s.dim(cx - ri, cy + 18, cx + ri, cy + 18, f'{sym("D_i")}', HL, side=1)
    s.dim(cx + ri, cy - 0.0, cx + ro, cy - 0.0, '', HL if name in ('t_des', 'D_t') else GREY)
    if grow > 1.0:
        s.tag(cx, cy + ro + 54, 'wall thickness exaggerated', GREY)
    s.tag(cx + ro + 8, cy - 8, f'{sym("t_des")} = {td:g} in', HL if name in ('t_des', 'D_t') else INK, 'start')
    A = v('A_g', 'in^2')
    rows = {
        't_des': [f'= {sym("t_wall")} − {sym("t_corr")}', f'= {t:g} − {tc:g} in', ('design wall after corrosion', GREY)],
        'D_i': [f'= {sym("D_out")} − 2 {sym("t_des")}', f'= {D:g} − 2 × {td:g} in', ('wall loss taken off the inside', GREY)],
        'A_g': [f'= π/4 ({sym("D_out")}² − {sym("D_i")}²)', f'= 0.7854 × ({D:g}² − {Di:.3f}²) in²'],
        'I_g': [f'= π/64 ({sym("D_out")}⁴ − {sym("D_i")}⁴)', f'= 0.0491 × ({D:g}⁴ − {Di:.3f}⁴) in⁴'],
        'S_g': [f'= {sym("I_g")} / ({sym("D_out")}/2)', f'= {v("I_g", "in^4"):.2f} in⁴ / {D / 2:g} in', ('elastic section modulus', GREY)],
        'Z_p': [f'= ({sym("D_out")}³ − {sym("D_i")}³) / 6', f'= ({D:g}³ − {Di:.3f}³) / 6 in³', ('plastic section modulus', GREY)],
        'r_g': [f'= √({sym("I_g")} / {sym("A_g")})', f'= √({v("I_g", "in^4"):.1f} / {A:.3f}) in', ('radius of gyration', GREY)],
        'D_t': [f'= {sym("D_out")} / {sym("t_des")}', f'= {D:g} / {td:g}', ('local buckling ratio', GREY)],
    }[name]
    s.panel(_eq(e, name, 3), rows)
    return s


# ============================================================================= 12. pipe column
def pipe_elev(e, name):
    v, p = e.value, e.case['inputs']
    Lu, Lf, K, KL = max(v('L_unsupported', 'ft'), 0.1), v('L_fix', 'ft'), p['K_eff'], v('KL', 'ft')
    s = Svg('Pile in elevation: length above ground, depth to fixity below ground, and the effective length factor K.',
            title='Effective length of the pipe pile')
    k = 205 / (Lu + Lf)
    xc, ytop = 214, 76
    yg, yf = ytop + Lu * k, ytop + (Lu + Lf) * k
    s.rect(70, yg, 290, yf + 28 - yg, fill=SOIL, stroke='none', op=0.55 if name != 'E_soil' else 0.9)
    s.rect(xc - 62, ytop - 26, 124, 26, fill=CONC, stroke=INK)
    s.text(xc, ytop - 9, 'pile cap', 10, GREY)
    s.rect(xc - 11, ytop, 22, yf - ytop + 22, fill=CONC, stroke=INK, sw=1.3)
    s.line(70, yg, 360, yg, '#9b8456', 1.4)
    s.tag(364, yg + 4, f'ground', '#9b8456', 'start')
    s.line(xc - 34, yf, xc + 34, yf, HL if name == 'L_fix' else INK, 2.2)
    for i in range(-3, 4):
        s.line(xc + i * 9, yf, xc + i * 9 - 5, yf + 8, INK, 1)
    s.tag(364, yf + 4, 'depth to fixity', INK, 'start')
    s.dim(xc - 54, ytop, xc - 54, yg, f'{sub("L", "u")} = {Lu:.2f} ft', GREY, side=-1)
    s.dim(xc - 54, yg, xc - 54, yf, f'{sym("L_fix")} = {Lf:.2f} ft', HL if name == 'L_fix' else INK, side=-1)
    s.dim(xc + 50, ytop, xc + 50, yf, f'KL = {KL:.2f} ft', HL if name in ('KL', 'KL_r') else INK, side=1)
    s.tag(xc + 56, (ytop + yf) / 2 + 18, f'K = {K:g}', INK, 'start')
    if name == 'E_soil':
        s.tag(xc + 64, yg + 28, f'{sym("E_soil")} = 0.465 {sym("S_u")}', HL, 'start')
        s.tag(xc + 64, yg + 42, 'clay only' if int(p['soil_type']) == 1 else 'sand: n_h is used instead', GREY, 'start')
    if name == 'KL_r':
        s.tag(xc + 64, yf - 20, f'{sym("r_g")} = {v("r_g", "in"):.3f} in', INK, 'start')
    E, Iw = p['E_s'], v('I_g', 'in^4') / 12 ** 4
    clay = int(p['soil_type']) == 1
    rows = {
        'E_soil': [f'= 0.465 {sym("S_u")}', f'= 0.465 × {p["S_u"]:g} ksf (result in ksi)', ('LRFD C10.7.3.13.4, clay', GREY),
                   ('used only when soil type = clay', GREY)],
        'L_fix': ([f'= 1.4 ({sym("E_s")} {sym("I_g")} / {sym("E_soil")})^0.25', f'= 1.4 × ({E:g} × {Iw:.5f} / {v("E_soil", "ksi"):.3f})^0.25 ft'] if clay else
                  [f'= 1.8 ({sym("E_s")} {sym("I_g")} / {sym("n_h")})^0.2', f'= 1.8 × ({E:g} × {Iw:.5f} / {p["n_h"]:g})^0.2 ft']) +
                 [(f'{"clay" if clay else "sand"}: LRFD C10.7.3.13.4', GREY)],
        'KL': [f'= {sym("K_eff")} ({sub("L", "u")} + {sym("L_fix")})', f'= {K:g} × ({Lu:.3f} + {Lf:.3f}) ft', ('effective length for the column check', GREY)],
        'KL_r': [f'= {sym("KL")} / {sym("r_g")}', f'= {KL * 12:.1f} in / {v("r_g", "in"):.3f} in', ('slenderness ratio, limit 120', GREY)],
    }[name]
    s.panel(_eq(e, name, 3), rows)
    return s


def pipe_slender(e, name):
    v, p = e.value, e.case['inputs']
    E, Fy = p['E_s'], p['Fy']
    if name == 'lam_r':
        items = [(sym('D_t'), v('D_t')), (f'{sym("lam_r")} = 0.11 {sym("E_s")}/{sym("Fy")}', v('lam_r')), (f'0.45 {sym("E_s")}/{sym("Fy")} (limit)', 0.45 * E / Fy)]
        rows = [f'= 0.11 × {sym("E_s")} / {sym("Fy")}', f'= 0.11 × {E:g} / {Fy:g}', (f'{sym("D_t")} {"≤" if v("D_t") <= v("lam_r") else ">"} {sym("lam_r")}: {"nonslender" if v("D_t") <= v("lam_r") else "slender"}', GREY)]
        return _bars(e, name, items, '(dimensionless)', 'Local buckling: D/t against the nonslender limit', 1, rows, places=2)
    Ag, Aeff = v('A_g', 'in^2'), v('A_eff', 'in^2')
    items = [(sym('A_g'), Ag), (sym('A_eff'), Aeff)]
    slender = v('D_t') > v('lam_r')
    rows = ([f'= (0.038 {sym("E_s")}/({sym("Fy")} {sym("D_t")}) + 2/3) {sym("A_g")}', f'= {(0.038 * E / (Fy * v("D_t")) + 2 / 3):.4f} × {Ag:.3f} in²'] if slender else
            [f'= {sym("A_g")}  (D/t ≤ {sym("lam_r")})', f'= {Ag:.3f} in²', ('nonslender: full area effective', GREY)])
    return _bars(e, name, items, 'in²', 'Effective area for local buckling', 1, rows)


def pipe_column(e, name):
    v, p = e.value, e.case['inputs']
    E, A = p['E_s'], v('A_g', 'in^2')
    Po, Pe, Pn, KLr = v('P_o', 'kip'), v('P_e', 'kip'), v('P_n', 'kip'), v('KL_r')
    pa, pc = p['phi_c_axial'], p['phi_c_comb']
    s = Svg('Column curve of LRFD 6.9.4.1.1: nominal axial resistance against slenderness, with the Euler load and the squash load.',
            title='Pipe column resistance vs slenderness KL/r (LRFD 6.9.4.1.1)')
    x1 = max(120.0, KLr * 1.25)
    ymax = 1.45 * Po
    xs = [x1 * i / 120 for i in range(1, 121)]
    pe = lambda l: math.pi ** 2 * E * A / l ** 2
    pn = lambda l: 0.658 ** (Po / pe(l)) * Po if pe(l) / Po >= 0.44 else 0.877 * pe(l)
    ax = Axes(s, 0, x1, 0, ymax, 'KL/r', 'P (kip)')
    ex = [l for l in xs if pe(l) <= ymax * 1.02]
    ax.curve(ex, [pe(l) for l in ex], GREY, 1.4, '5 3')
    ax.curve(xs, [pn(l) for l in xs], BLUE, 2.2)
    if name == 'P_r_axial':
        ax.curve(xs, [pa * pn(l) for l in xs], BLUE, 1.6, '6 3')
    if name == 'P_r_comb':
        ax.curve(xs, [pc * pn(l) for l in xs], BLUE, 1.6, '6 3')
    ax.hline(Po, sym('P_o'), HL if name == 'P_o' else AMBER, '6 3', 'end')
    ax.hline(0.44 * Po, '0.44 P_o', GREY, '3 3', 'end')
    ax.vline(KLr, '', GREY)
    ax.point(KLr, Pn, HL if name == 'P_n' else INK, sym('P_n'), 'start', 8, -8, 4.5 if name != 'P_n' else 5.5)
    if name in ('P_e', 'Pe_Po'):
        if Pe <= ymax:
            ax.point(KLr, Pe, HL, sym('P_e'), 'start', 8, -8)
        else:
            s.arrow(ax.cx(KLr), ax.top + 24, ax.cx(KLr), ax.top + 3, HL, 2.2)
            s.tag(ax.cx(KLr) + 6, ax.top + 18, f'{sym("P_e")} = {Pe:.0f} (off scale)', HL, 'start')
    if name == 'P_r_axial':
        ax.point(KLr, pa * Pn, HL, sym('P_r_axial'), 'start', 8, 14)
    if name == 'P_r_comb':
        ax.point(KLr, pc * Pn, HL, sym('P_r_comb'), 'start', 8, 14)
    ratio = Pe / Po
    rows = {
        'P_o': [f'= {sym("Fy")} · {sym("A_eff")}', f'= {p["Fy"]:g} ksi × {v("A_eff", "in^2"):.3f} in²', ('squash load, full yield', GREY)],
        'P_e': [f'= π² {sym("E_s")} {sym("A_g")} / {sym("KL_r")}²', f'= 9.8696 × {E:g} × {A:.3f} / {KLr:.2f}²', ('elastic (Euler) buckling load', GREY)],
        'Pe_Po': [f'= {sym("P_e")} / {sym("P_o")}', f'= {Pe:.1f} / {Po:.1f}', (f'{"≥" if ratio >= 0.44 else "&lt;"} 0.44: {"inelastic 0.658 branch" if ratio >= 0.44 else "elastic 0.877 Pe branch"}', GREY)],
        'P_n': ([f'= 0.658^({sym("P_o")}/{sym("P_e")}) · {sym("P_o")}', f'= 0.658^({Po:.1f}/{Pe:.1f}) × {Po:.1f} kip'] if ratio >= 0.44
                else [f'= 0.877 · {sym("P_e")}', f'= 0.877 × {Pe:.1f} kip']) + [('LRFD Eqs. 6.9.4.1.1-1, -2', GREY)],
        'P_r_axial': [f'= {sym("phi_c_axial")} · {sym("P_n")}', f'= {pa:g} × {Pn:.1f} kip', ('axial compression alone', GREY)],
        'P_r_comb': [f'= {sym("phi_c_comb")} · {sym("P_n")}', f'= {pc:g} × {Pn:.1f} kip', ('used in combined axial and flexure', GREY)],
    }[name]
    s.panel(_eq(e, name, 3), rows)
    return s


# ============================================================================= 13. pipe flexure
def pipe_flex(e, name):
    v, p = e.value, e.case['inputs']
    E, Fy, Dt = p['E_s'], p['Fy'], v('D_t')
    lp, lnc, Mp, Mn, Mr = v('lam_p'), v('lam_nc'), v('M_p', 'kip*ft'), v('M_n', 'kip*ft'), v('M_r', 'kip*ft')
    S, Z = v('S_g', 'in^3'), v('Z_p', 'in^3')
    s = Svg('Flexural resistance of the round tube against D/t: compact, noncompact and slender ranges (LRFD 6.12.2.2.3).',
            title='Pipe flexural resistance vs D/t')
    x1 = max(0.45 * E / Fy, Dt * 1.2)
    xs = [10 + (x1 - 10) * i / 140 for i in range(141)]
    def ratio(x):
        if x <= lp:
            return 1.0
        if x <= lnc:
            return min(1.0, (0.021 * E / x + Fy) * S / (Fy * Z))
        return 0.33 * E / x * S / (Fy * Z)
    ax = Axes(s, 10, x1, 0, 1.15, 'D/t', 'Mn / Mp')
    ax.curve(xs, [ratio(x) for x in xs], BLUE, 2.2)
    ax.vline(lp, f'{sym("lam_p")} = {lp:.1f}', HL if name == 'lam_p' else GREY)
    ax.vline(lnc, f'{sym("lam_nc")} = {lnc:.1f}', HL if name == 'lam_nc' else GREY)
    ax.hline(1.0, f'{sym("M_p")} = {sym("Fy")}·{sym("Z_p")}', HL if name == 'M_p' else AMBER, '6 3', 'end')
    cur = ratio(Dt)
    ax.point(Dt, cur, HL if name in ('M_n', 'M_r') else INK, f'{sym("M_n")}/{sym("M_p")} = {cur:.3f}', 'start', 12, 26, 5)
    if name == 'M_r':
        ax.point(Dt, p['phi_f'] * cur, HL, f'{sym("M_r")} = {sym("phi_f")}{sym("M_n")}', 'start', 12, 42, 4)
    cls = 'compact' if Dt <= lp else 'noncompact' if Dt <= lnc else 'slender'
    rows = {
        'lam_p': [f'= 0.07 {sym("E_s")} / {sym("Fy")}', f'= 0.07 × {E:g} / {Fy:g}', ('compact limit', GREY)],
        'lam_nc': [f'= 0.31 {sym("E_s")} / {sym("Fy")}', f'= 0.31 × {E:g} / {Fy:g}', ('noncompact limit', GREY)],
        'M_p': [f'= {sym("Fy")} · {sym("Z_p")}', f'= {Fy:g} ksi × {Z:.2f} in³ / 12', ('plastic moment, kip-ft', GREY)],
        'M_n': [f'= {sym("M_p")}  (D/t ≤ {sym("lam_p")})' if cls == 'compact' else f'= min(M_p, (0.021 E/(D/t) + F_y) S)' if cls == 'noncompact' else '= 0.33 E/(D/t) · S',
                f'{sym("D_t")} = {Dt:.2f}: {cls}', (f'= {Mn:.1f} kip-ft', GREY)],
        'M_r': [f'= {sym("phi_f")} · {sym("M_n")}', f'= {p["phi_f"]:g} × {Mn:.1f} kip-ft', (f'{cls} section', GREY)],
    }[name]
    s.panel(_eq(e, name, 3), rows)
    return s


# ============================================================================= 14. pipe interaction and shear
def pipe_envelope(e, name):
    v, p = e.value, e.case['inputs']
    Prc_c, Prt, Mr = v('P_r_comb', 'kip'), v('P_r_t', 'kip'), v('M_r', 'kip*ft')
    Pu, Mu = v('P_u_comb', 'kip'), v('M_u_comb', 'kip*ft')
    s = Svg('Bilinear interaction envelope of LRFD 6.9.2.2.1 with its corner at 0.9 Mr and 0.2 Pr, and the governing demand point.',
            title='Combined axial load and flexure, LRFD 6.9.2.2.1')
    ax = Axes(s, 0, max(Mr, Mu) * 1.12, -Prt * 1.15, Prc_c * 1.15, 'M (kip-ft)', 'P (kip, compression +)')
    verts = [(0, Prc_c), (0.9 * Mr, 0.2 * Prc_c), (Mr, 0), (0.9 * Mr, -0.2 * Prt), (0, -Prt)]
    s.poly([(ax.cx(m), ax.cy(q)) for m, q in verts], fill=LIGHT, stroke=BLUE, sw=2, op=0.25)
    s.line(ax.left, ax.Y(0), ax.left + ax.width, ax.Y(0), GREY, 0.8, '3 3')
    s.tag(ax.cx(0.9 * Mr) + 4, ax.cy(0.2 * Prc_c) - 6, '0.9 Mr, 0.2 Pr', GREY, 'start')
    pr_match = Prc_c if Pu >= 0 else -Prt
    hot_p = name in ('P_rc',)
    if name in ('P_rc', 'Pu_Pr'):
        ax.hline(pr_match, f'{sym("P_rc")} = {abs(pr_match):.1f}', HL if hot_p else AMBER, '6 3', 'end')
    if name in ('P_abs', 'Pu_Pr'):
        s.line(ax.cx(Mu), ax.Y(0), ax.cx(Mu), ax.cy(Pu), HL, 2.4)
        s.tag(ax.cx(Mu) + 6, (ax.Y(0) + ax.cy(Pu)) / 2, f'{sym("P_abs")} = {abs(Pu):.1f}', HL, 'start')
    ax.point(Mu, Pu, HL if name == 'DC_comb' else INK, f'demand ({Mu:.1f} kip-ft, {Pu:.1f} kip)', 'start' if Mu < Mr * 0.5 else 'end', 8, -10, 5.5)
    ratio = abs(Pu) / (Prc_c if Pu >= 0 else Prt)
    br = '6.9.2.2.1-1' if ratio >= 0.2 else '6.9.2.2.1-2'
    rows = {
        'P_abs': [f'= |{sym("P_u_comb")}|', f'= |{Pu:.3f}| kip', ('compression or tension magnitude', GREY)],
        'P_rc': [f'= {sym("P_r_comb")}  (if P_u ≥ 0)' if Pu >= 0 else f'= {sym("P_r_t")}  (net uplift)', f'= {abs(pr_match):.2f} kip', ('matching axial resistance', GREY)],
        'Pu_Pr': [f'= {sym("P_abs")} / {sym("P_rc")}', f'= {abs(Pu):.2f} / {abs(pr_match):.2f} kip', (f'{"≥" if ratio >= 0.2 else "&lt;"} 0.2: Eq. {br}', GREY)],
        'DC_comb': ([f'= {sym("Pu_Pr")} + 8/9 · {sym("M_u_comb")} / {sym("M_r")}', f'= {ratio:.3f} + 8/9 × {Mu:.1f} / {Mr:.1f}'] if ratio >= 0.2 else
                    [f'= {sym("Pu_Pr")}/2 + {sym("M_u_comb")} / {sym("M_r")}', f'= {ratio:.3f}/2 + {Mu:.1f} / {Mr:.1f}']) + [(f'Eq. {br}', GREY)],
    }[name]
    s.panel(_eq(e, name, 3), rows)
    return s


def pipe_shear_curve(e, name):
    v, p = e.value, e.case['inputs']
    E, Fy, Dt, D = p['E_s'], p['Fy'], v('D_t'), v('D_out', 'in')
    Lv = v('L_v', 'ft') * 12
    cap = 0.58 * Fy
    s = Svg('Shear buckling stress of the round tube against D/t: the two LRFD 6.12.1.2.3b formulas, the larger one, and the 0.58 Fy cap.',
            title='Pipe shear buckling stress Fcr vs D/t (LRFD 6.12.1.2.3b)')
    x0, x1 = max(5.0, Dt * 0.45), Dt * 2.4
    xs = [x0 + (x1 - x0) * i / 100 for i in range(101)]
    f1 = lambda x: 1.6 * E / (math.sqrt(Lv / D) * x ** 1.25)
    f2 = lambda x: 0.78 * E / x ** 1.5
    ymax = max(cap * 3.0, v('F_cr2', 'ksi') * 1.15, 1.0)
    ax = Axes(s, x0, x1, 0, ymax, 'D/t', 'Fcr (ksi)')
    ax.curve(xs, [f1(x) for x in xs], BLUE, 1.8, clip=True)
    ax.curve(xs, [f2(x) for x in xs], TEAL, 1.8, clip=True)
    ax.hline(cap, f'0.58 {sym("Fy")} = {cap:.1f}', HL if name == 'F_cr' else AMBER, '6 3', 'end')
    F1, F2, Fc = v('F_cr1', 'ksi'), v('F_cr2', 'ksi'), v('F_cr', 'ksi')
    s.line(ax.left + ax.width - 150, ax.top + 16, ax.left + ax.width - 130, ax.top + 16, BLUE, 1.8)
    s.tag(ax.left + ax.width - 126, ax.top + 19, f'{sym("F_cr1")} (length-dependent)', BLUE, 'start')
    s.line(ax.left + ax.width - 150, ax.top + 32, ax.left + ax.width - 130, ax.top + 32, TEAL, 1.8)
    s.tag(ax.left + ax.width - 126, ax.top + 35, f'{sym("F_cr2")}', TEAL, 'start')
    ax.point(Dt, min(F1, ymax), HL if name == 'F_cr1' else BLUE, f'{sym("F_cr1")} = {F1:.1f}' + (' (off scale)' if F1 > ymax else ''), 'start', 8, -6, 4.5)
    ax.point(Dt, F2, HL if name == 'F_cr2' else TEAL, f'{sym("F_cr2")} = {F2:.1f}', 'start', 8, 14, 4.5)
    ax.point(Dt, Fc, HL if name == 'F_cr' else INK, f'{sym("F_cr")} = {Fc:.1f}', 'end', 8, -8, 5)
    rows = {
        'F_cr1': [f'= 1.6 {sym("E_s")} / (√(L_v/D) · (D/t)^1.25)', f'= 1.6 × {E:g} / (√({Lv:.1f}/{D:g}) × {Dt:.2f}^1.25)', ('LRFD Eq. 6.12.1.2.3b-2', GREY)],
        'F_cr2': [f'= 0.78 {sym("E_s")} / (D/t)^1.5', f'= 0.78 × {E:g} / {Dt:.2f}^1.5', ('LRFD Eq. 6.12.1.2.3b-3', GREY)],
        'F_cr': [f'= min(max({sym("F_cr1")}, {sym("F_cr2")}), 0.58 {sym("Fy")})', f'= min(max({F1:.1f}, {F2:.1f}), {cap:.2f}) ksi', ('governed by the yield cap' if abs(Fc - cap) < 1e-9 else 'governed by buckling', GREY)],
    }[name]
    s.panel(_eq(e, name, 3), rows)
    return s


def pipe_shear_bars(e, name):
    v, p = e.value, e.case['inputs']
    Vu, Fc, A = v('V_u_sh', 'kip'), v('F_cr', 'ksi'), v('A_g', 'in^2')
    items = [(f'{sym("V_u_sh")} (demand)', Vu), (sym('V_n'), v('V_n', 'kip')), (f'{sym("V_r")} = {sym("phi_v_steel")} {sym("V_n")}', v('V_r', 'kip'))]
    rows = {'V_n': [f'= 0.5 {sym("F_cr")} {sym("A_g")}', f'= 0.5 × {Fc:.2f} ksi × {A:.3f} in²', ('LRFD Eq. 6.12.1.2.3b-1', GREY)],
            'V_r': [f'= {sym("phi_v_steel")} · {sym("V_n")}', f'= {p["phi_v_steel"]:g} × {v("V_n", "kip"):.2f} kip', (f'demand {Vu:.2f} kip', GREY)]}[name]
    return _bars(e, name, items, 'kip', 'Pipe shear resistance and demand', {'V_n': 1, 'V_r': 2}[name], rows)


# ============================================================================= registry
COMMON = {'S_min': row_plan, 's_over_D': row_plan, 'DD': drag, 'DR_str': drag, 'DR_ser': drag,
          'FDL_tons': geotech, 'R_scour_net': geotech, 'R_n_req': geotech, 'NBR_tons': geotech, 'R_drive_max': geotech}
PSC = {}
PSC.update({n: psc_section for n in ('A_ps', 'f_pj', 'f_pe', 'P_e', 'A_g', 'I_g', 'S_g', 'f_pc_eff', 'eps_pe', 'eps_ce', 'eps_cu')})
PSC.update({n: concrete_relation for n in ('beta_1', 'E_c', 'k_c')})
PSC.update({n: axial for n in ('P_o', 'P_n_max', 'P_r_max', 'P_bi_lim')})
PSC.update({n: interaction for n in ('DC_bi', 'P_rxy', 'DC_rs')})
PSC.update({n: eccentricity for n in ('e_y', 'e_x')})
PSC.update({n: tension for n in ('P_n_t', 'P_r_t', 'P_t_yield', 'DC_t')})
PSC.update({n: shear_section for n in ('b_v', 'd_v', 's_x', 'A_ct')})
PSC.update({n: shear_forces for n in ('M_u_v', 'N_u', 'f_po', 'F_long')})
PSC.update({n: shear_strain for n in ('eps_s0', 'eps_s1', 'eps_s')})
PSC['s_xe'] = shear_sxe
PSC.update({n: shear_spiral for n in ('A_v', 'A_v_min')})
PSC.update({n: shear_curves for n in ('beta_v', 'theta_v')})
PSC.update({n: shear_strength for n in ('V_c', 'V_s', 'V_n', 'V_r')})
PSC.update({n: service for n in ('sig_c', 'sig_c_lim', 'sig_t', 'f_t_net', 'f_t_lim', 'f_pc_min', 'D_min')})
PIPE = {}
PIPE.update({n: pipe_ring for n in ('t_des', 'D_i', 'A_g', 'I_g', 'S_g', 'Z_p', 'r_g', 'D_t')})
PIPE.update({n: pipe_slender for n in ('lam_r', 'A_eff')})
PIPE.update({n: pipe_column for n in ('P_o', 'P_e', 'Pe_Po', 'P_n', 'P_r_axial', 'P_r_comb')})
PIPE.update({n: pipe_elev for n in ('E_soil', 'L_fix', 'KL', 'KL_r')})
PIPE.update({n: pipe_flex for n in ('lam_p', 'lam_nc', 'M_p', 'M_n', 'M_r')})
PIPE.update({n: tension for n in ('P_r_t', 'DC_t')})
PIPE.update({n: pipe_envelope for n in ('P_abs', 'P_rc', 'Pu_Pr', 'DC_comb')})
PIPE.update({n: pipe_shear_curve for n in ('F_cr1', 'F_cr2', 'F_cr')})
PIPE.update({n: pipe_shear_bars for n in ('V_n', 'V_r')})
STATIC = {'psc': {**COMMON, **PSC}, 'pipe': {**COMMON, **PIPE}}


def drawer(e, name):
    return STATIC[e.family].get(name)


def schematic(e, name):
    """(svg markup, one-line description of the drawing) for a formula definition, or (None, None)."""
    fn = drawer(e, name)
    if fn is None:
        return None, None
    svg = fn(e, name)
    return svg.render(), svg.label


# ============================================================================= plain-language meaning
NAME_MEANING = {
    'S_min': 'Smallest center-to-center pile spacing allowed: three pile diameters (SDG 3.5.4).',
    's_over_D': 'Provided pile spacing expressed in pile diameters, compared with the 3.0 minimum.',
    'DD': 'Downdrag (drag load) per pile from the geotechnical engineer, converted from tons to kip; nominal, not factored.',
    'DR_str': 'Drag load multiplied by its load factor for the strength limit states; added to the FBMP axial force for the structural checks.',
    'DR_ser': 'Drag load at Service I (factor 1.0); added to the FBMP axial force for the service stress checks.',
    'FDL_tons': 'Factored Design Load for the Pile Data Table: the largest strength head compression from FBMP, without downdrag, in tons.',
    'R_scour_net': 'Net scour resistance (soil resistance lost to scour that the pile must still provide), converted to kip.',
    'R_n_req': 'Required nominal bearing resistance, SDG Eq. 3-1: factored design load plus net scour resistance plus downdrag, divided by the resistance factor.',
    'NBR_tons': 'Required nominal bearing resistance in tons, as reported in the Pile Data Table.',
    'R_drive_max': 'Largest driving resistance permitted for this pile size (SDG Table 3.5.13-1), converted to kip.',
    'A_g': 'Gross cross-sectional area of the pile section.',
    'I_g': 'Moment of inertia of the gross pile section about a centroidal axis.',
    'S_g': 'Elastic section modulus of the gross section at the extreme fiber.',
    'P_o': 'Axial resistance of the section at zero eccentricity (squash load).',
    'P_e': 'Elastic buckling load of the section, Euler load for the effective length.',
    'V_n': 'Nominal shear resistance of the section.',
    'V_r': 'Factored shear resistance, the resistance factor times the nominal value.',
    'P_r_t': 'Factored tension (uplift) resistance of the pile.',
    'DC_t': 'Demand/capacity ratio for tension: the largest strength uplift divided by the factored tension resistance.',
    # prestressed concrete
    'A_ps': 'Total area of the prestressing strand in the Standard Plans pattern.',
    'f_pj': 'Jacking stress in each strand: jacking force divided by the strand area.',
    'f_pe': 'Effective stress in the strand after prestress losses.',
    'f_pc_eff': 'Uniform compressive stress on the gross section from the effective prestress force.',
    'beta_1': 'Ratio of the stress block depth to the neutral axis depth for this concrete strength.',
    'E_c': 'Modulus of elasticity of the pile concrete from unit weight and strength.',
    'eps_cu': 'Concrete crushing strain at the extreme compression fiber (0.003).',
    'k_c': 'Ratio of the maximum concrete stress to f′c used for the squash load (0.85 up to 10 ksi).',
    'eps_pe': 'Strain in the strand after losses: effective stress divided by the strand modulus.',
    'eps_ce': 'Strain that decompresses the concrete: effective prestress stress divided by the concrete modulus.',
    'P_n_max': 'Maximum nominal axial resistance of a spiral-reinforced member, 85 percent of the squash load.',
    'P_r_max': 'Maximum factored axial resistance: the compression-controlled resistance factor times the maximum nominal resistance.',
    'P_bi_lim': 'Axial load that separates LRFD Eq. 5.6.4.5-1 (above) from Eq. 5.6.4.5-3 (below) for biaxial flexure.',
    'e_y': 'Eccentricity of the governing axial load in the y direction: moment about the x axis divided by the axial load.',
    'e_x': 'Eccentricity of the governing axial load in the x direction: moment about the y axis divided by the axial load.',
    'P_rxy': 'Factored axial resistance in biaxial flexure from the reciprocal formula, LRFD Eq. 5.6.4.5-1.',
    'DC_bi': 'Demand/capacity ratio of the LRFD 5.6.4.5 biaxial flexure check (Eq. 5.6.4.5-1 or -3).',
    'DC_rs': 'Demand/capacity ratio on the resultant bending axis: the demand ray measured against the strain-compatibility curve.',
    'P_n_t': 'Nominal tension resistance carried by the strand alone, LRFD Eq. 5.8.2.4.1-1.',
    'P_t_yield': 'Upper bound on the tension resistance: strand area times strand yield stress.',
    'b_v': 'Effective web width for shear: the pile size less any void diameter.',
    'd_v': 'Effective shear depth: the larger of 0.9 d_e and 0.72 times the pile size.',
    'M_u_v': 'Factored moment used in the shear strain, not less than V_u times d_v.',
    'N_u': 'Factored axial force in the shear strain equation, with tension taken as positive.',
    'f_po': 'Stress parameter of the locked-in strand: 0.7 times the strand tensile strength.',
    'F_long': 'Longitudinal force demand in the numerator of the shear strain Eq. 5.7.3.4.2-4.',
    'eps_s0': 'Longitudinal strain at mid-depth of the shear section, strand stiffness only in the denominator.',
    'A_ct': 'Area of concrete on the flexural tension half of the section.',
    'eps_s1': 'Longitudinal strain with the concrete on the tension side added to the denominator, used when the first value is negative.',
    'eps_s': 'Longitudinal strain used for β and θ, not less than −0.40×10⁻³.',
    's_x': 'Crack spacing parameter, equal to the shear depth when there is no longitudinal crack-control steel.',
    's_xe': 'Equivalent crack spacing that accounts for aggregate size, between 12 and 80 inches.',
    'A_v': 'Spiral steel area crossing the shear plane: two legs of the spiral wire.',
    'A_v_min': 'Minimum transverse reinforcement area required by LRFD 5.7.2.5 for the web width and spiral pitch.',
    'beta_v': 'Concrete shear parameter β: how much shear the cracked concrete carries, from the longitudinal strain.',
    'theta_v': 'Angle of the diagonal compression field, from the longitudinal strain.',
    'V_c': 'Shear resistance provided by the concrete.',
    'V_s': 'Shear resistance provided by the spiral reinforcement.',
    'sig_c': 'Largest compressive stress at a section corner at Service I, after losses.',
    'sig_c_lim': 'Compression stress limit at Service I: 0.60 f′c.',
    'sig_t': 'Corner stress on the tension side at Service I after losses (negative means tension).',
    'f_t_net': 'Net tensile stress at the corner: the tension part of the stress, zero if the corner stays in compression.',
    'f_t_lim': 'Tension stress limit at Service I for the environment (LRFD Table 5.9.2.3.2b-1).',
    'f_pc_min': 'Minimum uniform prestress required after losses.',
    'D_min': 'Smallest square pile size allowed for the environment (SDG Table 3.5.1-1).',
    # steel pipe
    't_des': 'Design wall thickness: nominal wall less the corrosion allowance.',
    'D_i': 'Inside diameter of the design wall.',
    'Z_p': 'Plastic section modulus of the pipe.',
    'r_g': 'Radius of gyration of the pipe section.',
    'D_t': 'Diameter-to-thickness ratio, which controls local buckling and flexure class.',
    'lam_r': 'Slenderness limit 0.11 E/Fy: above it the pipe is slender for axial compression.',
    'A_eff': 'Effective area for compression: the full area if nonslender, reduced for local buckling if slender.',
    'E_soil': 'Soil modulus for clay used for the depth to fixity: 0.465 times the undrained shear strength.',
    'L_fix': 'Depth below ground to the point of fixity of the pile (LRFD C10.7.3.13.4).',
    'KL': 'Effective length of the pile: K times the length above ground plus the depth to fixity.',
    'KL_r': 'Slenderness ratio KL/r of the pile.',
    'Pe_Po': 'Ratio of the elastic buckling load to the squash load; 0.44 separates the inelastic and elastic formulas.',
    'P_n': 'Nominal axial compression resistance from the column curve (LRFD 6.9.4.1.1).',
    'P_r_axial': 'Factored axial resistance for axial compression alone.',
    'P_r_comb': 'Factored axial resistance used in the combined axial and flexure check (larger resistance factor).',
    'lam_p': 'D/t limit 0.07 E/Fy below which the pipe is compact in flexure.',
    'lam_nc': 'D/t limit 0.31 E/Fy below which the pipe is noncompact in flexure.',
    'M_p': 'Plastic moment of the pipe: yield stress times the plastic section modulus.',
    'M_n': 'Nominal flexural resistance, reduced from the plastic moment when the pipe is not compact.',
    'M_r': 'Factored flexural resistance of the pipe.',
    'P_abs': 'Magnitude of the governing axial force, compression or tension.',
    'P_rc': 'Axial resistance that matches the sign of the governing force: compression resistance, or tension resistance for net uplift.',
    'Pu_Pr': 'Ratio of the axial force to its matching resistance; 0.2 selects the interaction equation.',
    'DC_comb': 'Demand/capacity ratio of the combined axial load and flexure interaction, LRFD Eq. 6.9.2.2.1-1 or -2.',
    'F_cr1': 'Shear buckling stress of the round tube from the length-dependent formula.',
    'F_cr2': 'Shear buckling stress of the round tube from the length-independent formula.',
    'F_cr': 'Governing shear buckling stress: the larger of the two formulas, not above 0.58 Fy.',
}
FAMILY_MEANING = {
    'psc': {
        'A_g': 'Gross area of the square pile section; the void of a hollow pile is subtracted.',
        'I_g': 'Moment of inertia of the gross square section about a centroidal axis; the void is subtracted.',
        'S_g': 'Elastic section modulus of the gross square section.',
        'P_o': 'Axial resistance of the section at zero eccentricity: concrete block at k_c f′c less the strand term.',
        'P_e': 'Effective prestress force in the strand after losses.',
        'V_n': 'Nominal shear resistance: concrete plus spiral, not above 0.25 f′c bv dv.',
        'V_r': 'Factored shear resistance, φ times the nominal value.',
        'P_r_t': 'Factored tension resistance of the pile: resistance factor times the strand tension capacity.',
        'DC_t': 'Demand/capacity ratio for tension: the largest strength uplift divided by the factored strand tension resistance.',
    },
    'pipe': {
        'A_g': 'Gross area of the steel ring of the design wall.',
        'I_g': 'Moment of inertia of the steel ring about a diameter.',
        'S_g': 'Elastic section modulus of the steel ring.',
        'P_o': 'Squash load: yield stress times the effective area.',
        'P_e': 'Elastic buckling load of the column for the effective length.',
        'V_n': 'Nominal shear resistance of the round tube: half of the shear buckling stress times the area.',
        'V_r': 'Factored shear resistance of the round tube.',
        'P_r_t': 'Factored tension resistance of the pipe: yielding of the gross section.',
        'DC_t': 'Demand/capacity ratio for tension: the largest strength uplift divided by the factored yielding resistance.',
    },
}


def meaning(name, family=None):
    """One plain-language sentence saying what the equation represents (family selects the wording of repeated names)."""
    if family in FAMILY_MEANING and name in FAMILY_MEANING[family]:
        return FAMILY_MEANING[family][name]
    return NAME_MEANING.get(name)
