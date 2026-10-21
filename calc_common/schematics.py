"""'What it represents' blocks: per-equation QC drawings built from the current case.

Every package draws its own equations in ``<package>/schematics.py`` with the toolkit below: an ``Svg`` canvas with a
right-hand result panel (the defined quantity in red, the values it is built from beneath), a ``Frame`` that maps model
coordinates to pixels at one scale, and small primitives for dimensions, distributed loads, moments, bar comparisons and
demand/capacity gauges. ``schematic(spec, e, name)`` asks the package module for the drawer of ``name``; a package that
has none falls back to the generic term diagram (inputs and calculated terms flowing into the result).
"""
import importlib
import math
import re
from html import escape
from pier_cap.engine import parse
from .model import names_in

W, H, PX = 760, 360, 474          # canvas and the x of the info panel
INK, GREY, FAINT, HL = '#213649', '#8a99a6', '#c4cdd6', '#c8322b'
BLUE, TEAL, AMBER, PURPLE, OUT = '#1f5b91', '#167b75', '#c77d16', '#7a3e9d', '#167b75'
CONC, SOIL, STEEL, SLAB, PAD, WIND, SKY = '#e3e9ee', '#f1e6cc', '#cfd6dd', '#d7e0e8', '#30475e', '#dbe9f5', '#f4f8fb'
GREEK = {'phi': 'φ', 'gamma': 'γ', 'beta': 'β', 'theta': 'θ', 'alpha': 'α', 'eps': 'ε', 'lambda': 'λ', 'delta': 'δ',
         'mu': 'μ', 'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ', 'eta': 'η', 'omega': 'ω', 'Gamma': 'Γ', 'Delta': 'Δ',
         'Omega': 'Ω', 'pi': 'π'}


# ----------------------------------------------------------------------------- text helpers
def sym(name):
    """SVG text markup for a formula name: base glyph plus a comma-joined subscript."""
    parts = name.split('_')
    base, subs = parts[0], [GREEK.get(s, s) for s in parts[1:]]
    out = escape(GREEK.get(base, base))
    if subs:
        out += f'<tspan baseline-shift="sub" font-size="75%">{escape(",".join(subs))}</tspan>'
    return out


def sub(base, low):
    return f'{escape(base)}<tspan baseline-shift="sub" font-size="75%">{escape(low)}</tspan>'


def n(x, places=3):
    """Short number: fixed places with trailing zeros trimmed."""
    if isinstance(x, bool):
        return 'true' if x else 'false'
    if not isinstance(x, (int, float)):
        return escape(str(x))
    if places == 0:
        return f'{x:.0f}'
    return f'{x:.{places}f}'.rstrip('0').rstrip('.') or '0'


def val(e, name, places=3, unit=None):
    """Escaped value text of a definition or input in its unit (or the given unit)."""
    return escape(e.text(name, places, unit))


def q(e, name, unit=None):
    """Numeric value in the given unit (the definition's own unit when none); strings and booleans pass through."""
    v = e.value(name, unit)
    return v


def eq(e, name, places=3, unit=None):
    return f'{sym(name)} = {val(e, name, places, unit)}'


def meaning(spec, name):
    notes = spec.text.get('notes', {}).get(name)
    if notes:
        return notes[0] if isinstance(notes, list) else notes
    d = spec.definition(name)
    if d:
        return d.get('caption') or name
    return spec.inputs.get(name, {}).get('caption', name)


def _dash(dash):
    return f' stroke-dasharray="{dash}"' if dash else ''


# ----------------------------------------------------------------------------- canvas
class Svg:
    def __init__(self, label, width=W, height=H, title=''):
        self.w, self.h, self.label, self.items = width, height, label, []
        self.defs = []
        if title:
            self.text(12, 18, escape(title), 11, INK, 'start', 'bold')

    # -- primitives
    def rect(self, x, y, w, h, fill='none', stroke=INK, sw=1.0, dash=None, op=1.0, rx=0):
        if w < 0:
            x, w = x + w, -w
        if h < 0:
            y, h = y + h, -h
        self.items.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" fill-opacity="{op}" '
                          f'stroke="{stroke}" stroke-width="{sw}"{_dash(dash)}/>')

    def line(self, x1, y1, x2, y2, stroke=INK, sw=1.0, dash=None):
        self.items.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"{_dash(dash)}/>')

    def poly(self, points, fill='none', stroke=INK, sw=1.0, op=1.0, dash=None, closed=True):
        tag = 'polygon' if closed else 'polyline'
        pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
        self.items.append(f'<{tag} points="{pts}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="{sw}"{_dash(dash)}/>')

    def path(self, d, fill='none', stroke=INK, sw=1.0, dash=None, op=1.0):
        self.items.append(f'<path d="{d}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="{sw}"{_dash(dash)}/>')

    def circle(self, x, y, r, fill=INK, stroke='none', sw=1.0, dash=None):
        self.items.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{_dash(dash)}/>')

    def text(self, x, y, markup, size=10.5, color=INK, anchor='middle', weight='normal', rotate=None, italic=False):
        transform = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ''
        style = ' font-style="italic"' if italic else ''
        self.items.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}" '
                          f'font-weight="{weight}" font-family="Arial, sans-serif"{style}{transform}>{markup}</text>')

    def tag(self, x, y, markup, color=INK, anchor='middle', size=9.5, rotate=None):
        """Short label on a white halo so it stays legible over geometry."""
        transform = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ''
        self.items.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="bold" '
                          f'font-family="Arial, sans-serif" stroke="#ffffff" stroke-width="3" paint-order="stroke"{transform}>{markup}</text>')

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

    def dim(self, x1, y1, x2, y2, markup='', color=HL, side=1, offset=10, ext=0):
        """Dimension line with arrowheads both ends and a short label beside it; ext draws extension ticks."""
        length = math.hypot(x2 - x1, y2 - y1)
        if ext:
            vertical = abs(x2 - x1) < abs(y2 - y1)
            if vertical:
                self.line(x1 - ext * side, y1, x1 + 3 * side, y1, GREY, 0.7)
                self.line(x2 - ext * side, y2, x2 + 3 * side, y2, GREY, 0.7)
            else:
                self.line(x1, y1 + ext * side, x1, y1 - 3 * side, GREY, 0.7)
                self.line(x2, y2 + ext * side, x2, y2 - 3 * side, GREY, 0.7)
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

    def arc(self, cx, cy, r, a0, a1, color=HL, sw=1.8):
        """Circular arrow from angle a0 to a1 (degrees counterclockwise on screen)."""
        p0 = (cx + r * math.cos(math.radians(a0)), cy - r * math.sin(math.radians(a0)))
        p1 = (cx + r * math.cos(math.radians(a1)), cy - r * math.sin(math.radians(a1)))
        large = 1 if abs(a1 - a0) > 180 else 0
        sweep = 0 if a1 > a0 else 1
        self.items.append(f'<path d="M{p0[0]:.1f},{p0[1]:.1f} A{r:.1f},{r:.1f} 0 {large} {sweep} {p1[0]:.1f},{p1[1]:.1f}" '
                          f'fill="none" stroke="{color}" stroke-width="{sw}"/>')
        tangent = math.radians(a1 + (90 if a1 > a0 else -90))
        self.arrow(p1[0], p1[1], p1[0] + 7 * math.cos(tangent), p1[1] - 7 * math.sin(tangent), color, sw, 7)

    def moment(self, cx, cy, r, ccw=True, color=HL, markup='', sw=1.8):
        """Curved moment arrow around (cx, cy); label to the right."""
        if ccw:
            self.arc(cx, cy, r, -60, 200, color, sw)
        else:
            self.arc(cx, cy, r, 240, -20, color, sw)
        if markup:
            self.tag(cx + r + 6, cy + 4, markup, color, 'start')

    def angle(self, cx, cy, r, a0, a1, color=INK, sw=1.0):
        p0 = (cx + r * math.cos(math.radians(a0)), cy - r * math.sin(math.radians(a0)))
        p1 = (cx + r * math.cos(math.radians(a1)), cy - r * math.sin(math.radians(a1)))
        self.items.append(f'<path d="M{p0[0]:.1f},{p0[1]:.1f} A{r:.1f},{r:.1f} 0 0 0 {p1[0]:.1f},{p1[1]:.1f}" '
                          f'fill="none" stroke="{color}" stroke-width="{sw}"/>')

    def udl(self, x1, x2, y, length=22, direction=-1, color=BLUE, step=18, markup='', sw=1.4):
        """Uniform load on a horizontal line: arrows pointing down onto it (direction -1 = from above, +1 = from below)."""
        count = max(2, int(abs(x2 - x1) // step) + 1)
        for i in range(count):
            x = x1 + (x2 - x1) * i / (count - 1)
            self.arrow(x, y + direction * length, x, y, color, sw, 5)
        self.line(x1, y + direction * length, x2, y + direction * length, color, sw)
        if markup:
            self.tag((x1 + x2) / 2, y + direction * (length + 8) + (4 if direction > 0 else 0), markup, color)

    def wind(self, x, y1, y2, length=24, toward=1, color=BLUE, step=16, markup='', sw=1.4):
        """Row of horizontal arrows hitting a vertical face at x between y1 and y2 (toward +1 = arrows point +x)."""
        count = max(2, int(abs(y2 - y1) // step) + 1)
        for i in range(count):
            y = y1 + (y2 - y1) * i / (count - 1)
            self.arrow(x - toward * length, y, x, y, color, sw, 5)
        self.line(x - toward * length, y1, x - toward * length, y2, color, sw)
        if markup:
            self.tag(x - toward * (length + 6), (y1 + y2) / 2 + 4, markup, color, 'end' if toward > 0 else 'start')

    def force(self, x, y, dx, dy, markup='', color=HL, sw=2.2, anchor=None):
        """Point force arrow ending at (x, y) from (x - dx, y - dy)."""
        self.arrow(x - dx, y - dy, x, y, color, sw, 8)
        if markup:
            a = anchor or ('start' if dx >= 0 else 'end')
            self.tag(x - dx + (8 if a == 'start' else -8), y - dy + 4, markup, color, a)

    def hatch(self, x, y, w, h, color=GREY, step=7):
        """Diagonal hatch inside a rectangle (ground, cut concrete)."""
        x0, y0 = x, y
        d = 0
        while d < w + h:
            ax, ay = x0 + min(d, w), y0 + max(0, d - w)
            bx, by = x0 + max(0, d - h), y0 + min(d, h)
            self.line(ax, ay, bx, by, color, 0.6)
            d += step

    def status(self, x, y, text, anchor='start'):
        """Pass/fail badge."""
        text = str(text)
        bad = 'FAIL' in text or 'SHORTFALL' in text or 'INVALID' in text or 'REVISE' in text or 'LOSS' in text
        warn = 'REVIEW' in text or 'PROVISIONAL' in text or 'PENDING' in text or 'required' in text or 'MASS' in text
        color = HL if bad else AMBER if warn else TEAL
        w = min(max(60, 6.2 * len(text) + 14), 300)
        xx = x if anchor == 'start' else x - w
        self.rect(xx, y - 12, w, 18, fill='#fff', stroke=color, sw=1.4, rx=4)
        self.text(xx + w / 2, y + 1, escape(text[:48]), 9.5, color, 'middle', 'bold')

    # -- composites
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

    def table(self, y, columns, rows, step=16):
        for cells, color, bold in rows:
            for (x, anchor), cell in zip(columns, cells):
                self.text(x, y, cell, 10, color, anchor, 'bold' if bold else 'normal')
            y += step
        return y

    def num(self, x, y, k, color=INK):
        self.circle(x, y, 7, fill='#ffffff', stroke=color, sw=1.3)
        self.text(x, y + 3.4, str(k), 9, color, 'middle', 'bold')

    def gauge(self, x, y, w, ratio, markup='', color=None, limit_label='1.0'):
        """Demand/capacity bar: fill to the ratio, a mark at 1.0; red when over."""
        ratio = 0.0 if ratio is None or (isinstance(ratio, float) and math.isnan(ratio)) else float(ratio)
        color = color or (HL if ratio > 1 + 1e-9 else TEAL)
        span = max(1.25, ratio * 1.1)
        k = w / span
        self.rect(x, y, w, 16, fill='#f3f6f8', stroke=FAINT, sw=1)
        self.rect(x, y, max(min(ratio, span) * k, 1), 16, fill=color, stroke='none', op=0.85)
        self.line(x + k, y - 4, x + k, y + 20, INK, 1.3)
        self.tag(x + k, y + 31, escape(limit_label), INK)
        if markup:
            self.tag(x + max(min(ratio, span) * k, 1) + 6, y + 12, markup, color, 'start')

    def bars(self, x, y, items, width=200, highlight=None, places=3, unit=''):
        """Horizontal bar comparison: items are (label, value, color or None)."""
        top = max([abs(v) for _, v, *_ in items] + [1e-9])
        for i, item in enumerate(items):
            label, value = item[0], item[1]
            color = item[2] if len(item) > 2 and item[2] else (HL if i == highlight else '#9fb3c8')
            yy = y + 24 * i
            w = width * abs(value) / top
            self.text(x - 8, yy + 12, label, 10, INK, 'end')
            self.rect(x, yy + 1, max(w, 1.5), 16, fill=color, stroke='none')
            self.text(x + w + 6, yy + 13, f'{n(value, places)} {escape(unit)}'.strip(), 10,
                      color if i == highlight else INK, 'start', 'bold' if i == highlight else 'normal')
        return y + 24 * len(items)

    def plot(self, L, T, Wd, Hd, series, points=(), xlabel='', ylabel='', x_range=None, y_range=None, hlines=(), vlines=()):
        """Small xy plot; series are (xs, ys, color); points (x, y, label, color)."""
        xs_all = [x for xs, _, _ in series for x in xs] + [p[0] for p in points] + [v[0] for v in vlines]
        ys_all = [y for _, ys, _ in series for y in ys] + [p[1] for p in points] + [h[0] for h in hlines]
        x0, x1 = x_range or (min(xs_all), max(xs_all))
        y0, y1 = y_range or (min(0.0, min(ys_all)), max(ys_all) * 1.1 + 1e-9)
        if x1 - x0 < 1e-12:
            x1 = x0 + 1
        if y1 - y0 < 1e-12:
            y1 = y0 + 1
        X = lambda x: L + (x - x0) / (x1 - x0) * Wd
        Y = lambda y: T + Hd - (y - y0) / (y1 - y0) * Hd
        self.line(L, T + Hd, L + Wd, T + Hd, INK)
        self.line(L, T, L, T + Hd, INK)
        for i in range(5):
            xv, yv = x0 + (x1 - x0) * i / 4, y0 + (y1 - y0) * i / 4
            self.text(X(xv), T + Hd + 13, f'{xv:.3g}', 8.5, GREY)
            self.text(L - 5, Y(yv) + 3, f'{yv:.3g}', 8.5, GREY, 'end')
        if xlabel:
            self.text(L + Wd / 2, T + Hd + 28, escape(xlabel), 9.5, INK)
        if ylabel:
            self.text(L - 40, T + Hd / 2, escape(ylabel), 9.5, INK, rotate=-90)
        for xs, ys, color in series:
            self.poly([(X(x), Y(y)) for x, y in zip(xs, ys)], stroke=color, sw=2, closed=False)
        for y, lab in hlines:
            self.line(L, Y(y), L + Wd, Y(y), AMBER, 1.2, '5 3')
            self.tag(L + Wd - 4, Y(y) - 5, escape(lab), AMBER, 'end')
        for x, lab in vlines:
            self.line(X(x), T, X(x), T + Hd, GREY, 0.9, '3 3')
            self.tag(X(x) + 3, T + 10, escape(lab), GREY, 'start')
        for p in points:
            x, y, lab = p[0], p[1], p[2]
            color = p[3] if len(p) > 3 else HL
            self.circle(X(x), Y(y), 5, fill=color)
            self.tag(X(x) + 8, Y(y) - 8, lab, color, 'start')
        return X, Y

    def render(self):
        defs = f'<defs>{"".join(self.defs)}</defs>' if self.defs else ''
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'role="img" aria-label="{escape(self.label, quote=True)}" style="max-width:100%;height:auto;background:#fff">'
                f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>{defs}' + ''.join(self.items) + '</svg>')


class Frame:
    """Model coordinates (y up) to SVG pixels at equal scale, centered in a box."""

    def __init__(self, x0, x1, y0, y1, left, top, width, height):
        self.k = min(width / max(x1 - x0, 1e-9), height / max(y1 - y0, 1e-9))
        self.left = left + (width - (x1 - x0) * self.k) / 2
        self.top = top + (height - (y1 - y0) * self.k) / 2
        self.x0, self.y1 = x0, y1

    def X(self, x):
        return self.left + (x - self.x0) * self.k

    def Y(self, y):
        return self.top + (self.y1 - y) * self.k

    def L(self, d):
        return d * self.k


def make_drawer(static, patterns=()):
    """Build a package ``drawer(name)`` from a name map and (regex, function) pairs."""
    compiled = [(re.compile(p), fn) for p, fn in patterns]

    def drawer(name):
        if name in static:
            return static[name]
        for pattern, fn in compiled:
            if pattern.match(name):
                return fn
        return None
    return drawer


# ----------------------------------------------------------------------------- generic fallback
def _wrap(text, width=28):
    words, lines, cur = text.split(), [], ''
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        lines.append(cur)
    return lines[:2]


def term_diagram(spec, e, name):
    """(svg, label): inputs (amber), calculated terms (blue) and the result (red)."""
    d = spec.definition(name)
    if d is None:
        return '', ''
    if 'function' in d:
        terms = []
    else:
        terms = [t for t in sorted(names_in(parse(d['expr']))) if t in e.units or t in spec.inputs]
    count = max(len(terms), 1)
    cols = min(count, 6)
    rows = (count + cols - 1) // cols
    height = 70 + rows * 46 + 40
    box_w = min(118, (W - 220) // cols - 8)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" '
             f'font-family="Arial, sans-serif" font-size="11" role="img" aria-label="{escape(name)}">']
    parts.append(f'<rect x="0" y="0" width="{W}" height="{height}" fill="#f7fafc"/>')
    x0 = 16
    for i, t in enumerate(terms):
        r, c = divmod(i, cols)
        x, y = x0 + c * (box_w + 8), 24 + r * 46
        color = AMBER if t in spec.inputs else BLUE
        value = e.text(t, 3) if t in e.units else str(e.engine.get(t))
        parts.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="38" rx="4" fill="#fff" stroke="{color}" stroke-width="1.2"/>')
        parts.append(f'<text x="{x + 6}" y="{y + 15}" fill="{color}" font-weight="bold">{escape(t)}</text>')
        parts.append(f'<text x="{x + 6}" y="{y + 30}" fill="{INK}" font-size="10">{escape(value[:22])}</text>')
    if not terms:
        parts.append(f'<text x="{x0}" y="46" fill="{GREY}">Constant or function body: no evaluated terms.</text>')
    rx, ry = W - 190, 24
    parts.append(f'<line x1="{x0 + cols * (box_w + 8) - 8}" y1="{ry + 19}" x2="{rx - 10}" y2="{ry + 19}" stroke="{GREY}" stroke-width="1.4"/>')
    result = e.text(name, 3) if name in e.units else str(e.engine.get(name))
    parts.append(f'<rect x="{rx}" y="{ry}" width="170" height="38" rx="4" fill="#fff" stroke="{HL}" stroke-width="1.8"/>')
    parts.append(f'<text x="{rx + 8}" y="{ry + 15}" fill="{HL}" font-weight="bold">{escape(name)}</text>')
    parts.append(f'<text x="{rx + 8}" y="{ry + 30}" fill="{HL}" font-size="10">{escape(result[:30])}</text>')
    for j, line in enumerate(_wrap(d.get('caption') or meaning(spec, name), 110)):
        parts.append(f'<text x="{x0}" y="{height - 26 + j * 14}" fill="{INK}" font-size="10.5">{escape(line)}</text>')
    parts.append('</svg>')
    return ''.join(parts), d.get('caption') or meaning(spec, name)


_DRAWERS = {}


def package_drawer(spec):
    """The package's ``drawer(name)`` function, or None when the package has no drawing module."""
    if spec.package not in _DRAWERS:
        try:
            module = importlib.import_module(f'{spec.package}.schematics')
            _DRAWERS[spec.package] = getattr(module, 'drawer', None)
        except ImportError:
            _DRAWERS[spec.package] = None
    return _DRAWERS[spec.package]


def schematic(spec, e, name):
    """(svg markup, one-line description) for one definition."""
    d = spec.definition(name)
    if d is None or 'function' in d:
        return '', ''
    drawer = package_drawer(spec)
    fn = drawer(name) if drawer else None
    if fn is not None:
        svg = fn(e, name)
        return svg.render(), svg.label
    return term_diagram(spec, e, name)
