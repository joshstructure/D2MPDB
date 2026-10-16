"""Per-equation QC schematics for the calculation report (inline SVG).

Every formula definition maps to a small drawing built from the current case:
the geometry it measures, the load or resistance it represents, or the
mathematical relation it evaluates. The drawing carries only short symbols;
the panel beside it states the result (red) and how it is composed from the
current values, so a reviewer can check the number against the picture.
"""
import math
import re
from html import escape
from .model import COMBINATIONS, STRENGTH, SERVICE, strap_table, _soil_factors

INK = '#213649'; GREY = '#8a99a6'; FAINT = '#c4cdd6'; CONC = '#e3e9ee'; SOIL = '#f1e6cc'; HL = '#c8322b'
BLUE = '#1f5b91'; STRAP = '#7a3e9d'; TEAL = '#167b75'; AMBER = '#c77d16'; PAD = '#30475e'; SLAB = '#d7e0e8'
GREEK = {'phi': 'φ', 'gamma': 'γ', 'beta': 'β', 'theta': 'θ', 'alpha': 'α', 'eps': 'ε', 'lambda': 'λ', 'delta': 'δ',
         'mu': 'μ', 'rho': 'ρ', 'Gamma': 'Γ', 'Delta': 'Δ'}
SPECIAL = {'fc': ('f′', 'c'), 'fy': ('f', 'y'), 'Es': ('E', 's'), 'dT': ('Δ', 'T'), 'K1': ('K', '1'), 'K2': ('K', '2')}
KEYS = '|'.join(c['key'] for c in COMBINATIONS)
LABELS = {c['key']: c['label'] for c in COMBINATIONS}
W, H, PX = 760, 360, 474          # canvas and the x of the info panel


def sym(name):
    """SVG text markup for a formula name: base letter plus subscript."""
    parts = name.split('_')
    base, subs = parts[0], parts[1:]
    if base in SPECIAL:
        glyph, first = SPECIAL[base]
        subs = [first] + subs
    else:
        glyph = GREEK.get(base, base)
    out = escape(glyph)
    if subs:
        out += f'<tspan baseline-shift="sub" font-size="75%">{escape(",".join(GREEK.get(s, s) for s in subs))}</tspan>'
    return out


def sub(base, low):
    return f'{escape(base)}<tspan baseline-shift="sub" font-size="75%">{escape(low)}</tspan>'


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

    def circle(self, x, y, r, fill=INK, stroke='none', sw=1.0):
        self.items.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

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

    def arc(self, cx, cy, r, a0, a1, color=HL, sw=1.8):
        """Circular arrow from angle a0 to a1 (degrees measured counterclockwise on screen)."""
        p0 = (cx + r * math.cos(math.radians(a0)), cy - r * math.sin(math.radians(a0)))
        p1 = (cx + r * math.cos(math.radians(a1)), cy - r * math.sin(math.radians(a1)))
        large = 1 if abs(a1 - a0) > 180 else 0
        sweep = 0 if a1 > a0 else 1
        self.items.append(f'<path d="M{p0[0]:.1f},{p0[1]:.1f} A{r:.1f},{r:.1f} 0 {large} {sweep} {p1[0]:.1f},{p1[1]:.1f}" '
                          f'fill="none" stroke="{color}" stroke-width="{sw}"/>')
        tangent = math.radians(a1 + (90 if a1 > a0 else -90))
        self.arrow(p1[0], p1[1], p1[0] + 7 * math.cos(tangent), p1[1] - 7 * math.sin(tangent), color, sw, 7)

    def angle(self, cx, cy, r, a0, a1, color=INK, sw=1.0):
        """Plain angle mark (no arrowhead) between screen angles a0 < a1, degrees counterclockwise."""
        p0 = (cx + r * math.cos(math.radians(a0)), cy - r * math.sin(math.radians(a0)))
        p1 = (cx + r * math.cos(math.radians(a1)), cy - r * math.sin(math.radians(a1)))
        self.items.append(f'<path d="M{p0[0]:.1f},{p0[1]:.1f} A{r:.1f},{r:.1f} 0 0 0 {p1[0]:.1f},{p1[1]:.1f}" '
                          f'fill="none" stroke="{color}" stroke-width="{sw}"/>')

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
        """Small aligned table: columns are (x, anchor); rows are (cells, color, bold)."""
        for cells, color, bold in rows:
            for (x, anchor), cell in zip(columns, cells):
                self.text(x, y, cell, 10, color, anchor, 'bold' if bold else 'normal')
            y += step
        return y

    def num(self, x, y, n, color=INK):
        """Numbered callout keyed to a table row."""
        self.circle(x, y, 7, fill='#ffffff', stroke=color, sw=1.3)
        self.text(x, y + 3.4, str(n), 9, color, 'middle', 'bold')

    def render(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'role="img" aria-label="{escape(self.label, quote=True)}" style="max-width:100%;height:auto;background:#fff">'
                f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>' + ''.join(self.items) + '</svg>')


def _dash(dash):
    return f' stroke-dasharray="{dash}"' if dash else ''


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


def _val(e, name, places=3):
    return escape(e.text(name, places))


def _eq(e, name, places=3):
    return f'{sym(name)} = {_val(e, name, places)}'


def _n(x, places=3):
    return f'{x:.{places}f}'.rstrip('0').rstrip('.') if places else f'{x:.0f}'


# ----------------------------------------------------------------------------- end-bent section
def _geometry(e):
    v = e.value
    g = dict(b=v('b_cap', 'ft'), h=v('h_cap', 'ft'), tb=v('t_bw', 'ft'), H=v('H_bw', 'ft'), emb=v('embed_pile', 'ft'),
             ebrg=v('e_brg', 'ft'), tol=v('tol_pile', 'ft'), hped=v('h_ped', 'ft'), tpad=v('t_pad', 'ft'), lpad=v('L_pad', 'ft'),
             dp=v('D_pile', 'ft'), zs=v('z_strap', 'ft'), ts=v('t_slab', 'ft'), Hck=v('H_ck', 'ft'), wck=v('w_ck', 'ft'))
    g['rear'], g['front'] = -g['b'] / 2, g['b'] / 2
    g['pad_top'] = g['h'] + g['hped'] + g['tpad']
    return g


SECTION_H = 400
DIM_LEVEL = -1.0          # model elevation (ft, cap soffit = 0) of the horizontal arm dimensions


def _section_frame(g, fill_left=1.9, span=1.5):
    top = g['h'] + max(g['H'] + g['ts'], g['Hck']) + 0.25
    return Frame(g['rear'] - fill_left, g['front'] + span, -1.75, top, 12, 30, PX - 40, SECTION_H - 44)


def _section_base(s, f, g, fill_left=1.9, span=1.5):
    rear, front = g['rear'], g['front']
    s.rect(f.X(rear - fill_left), f.Y(g['h'] + g['H']), f.L(fill_left), f.L(g['h'] + g['H']), fill=SOIL, stroke='none')
    s.rect(f.X(-g['dp'] / 2), f.Y(g['emb']), f.L(g['dp']), f.L(g['emb'] + 1.6), fill='#d3dbe2', stroke=GREY)
    s.rect(f.X(-g['dp'] / 2 - g['tol']), f.Y(g['emb']), f.L(g['dp']), f.L(g['emb'] + 1.6), stroke=GREY, dash='3 2')
    s.rect(f.X(rear), f.Y(g['h']), f.L(g['b']), f.L(g['h']), fill=CONC, stroke=INK)
    s.rect(f.X(rear), f.Y(g['h'] + g['H']), f.L(g['tb']), f.L(g['H']), fill=CONC, stroke=INK)
    s.rect(f.X(rear + g['tb']), f.Y(g['h'] + g['hped']), f.L(g['b'] - g['tb']), f.L(g['hped']), fill='#eef2f5', stroke=INK, sw=0.8)
    s.rect(f.X(g['ebrg'] - g['lpad'] / 2), f.Y(g['pad_top']), f.L(g['lpad']), f.L(g['tpad']), fill=PAD, stroke=PAD)
    deck = g['h'] + g['H'] + g['ts']
    s.rect(f.X(g['ebrg'] - 0.75), f.Y(deck - 0.55), f.L(front + span - g['ebrg'] + 0.75), f.L(deck - 0.55 - g['pad_top']),
           fill='#f7f9fb', stroke=FAINT)
    s.rect(f.X(rear - fill_left), f.Y(deck), f.L(fill_left + g['tb']), f.L(g['ts']), fill=SLAB, stroke=GREY, sw=0.8)
    s.line(f.X(rear - 0.2), f.Y(g['emb']), f.X(front + 0.3), f.Y(g['emb']), GREY, 0.9, '2 3')
    s.tag(f.X(front + 0.33), f.Y(g['emb']) + 3, 'pile top', GREY, 'start')
    s.line(f.X(0), f.Y(-1.7), f.X(0), f.Y(-0.1), GREY, 0.8, '1 3')
    s.tag(f.X(0) + 4, f.Y(-1.62), 'nominal pile', GREY, 'start')
    s.line(f.X(-g['tol']), f.Y(-1.7), f.X(-g['tol']), f.Y(g['h'] + 0.1), BLUE, 0.9, '5 3')
    s.tag(f.X(-g['tol']) - 4, f.Y(-1.62), 'shifted pile line', BLUE, 'end')
    s.tag(f.X(rear - fill_left / 2), f.Y(0.2), 'FILL', '#9b8456')
    s.tag(f.X(front + span / 2 + 0.2), f.Y(0.2), 'SPAN', GREY)


SECTION_TEXT = {
    'y_top': 'Cap top above the pile top: cap depth less pile embedment.',
    'H_ret': 'Retained height loaded by earth pressure: cap soffit to backwall crown.',
    'y_brg': 'Height of the bearing-level forces (top of pad) above the pile top.',
    'y_strap': 'Height of the tie-back strap above the pile top, the strap lever arm.',
    'x_brg': 'Arm of the bearing reactions toward the span, measured from the pile line shifted toward the fill by the placement tolerance.',
    'x_cap': 'Arm of the cap self-weight: the cap is centered on the nominal pile line, so the arm equals the tolerance shift.',
    'x_ped': 'Arm of the pedestal weight from the shifted pile line.',
    'x_ck': 'Arm of the total cheek-wall weight, including its rear and bottom lugs.',
    'x_bw': 'Arm of the backwall weight; negative values lie behind the pile line and stabilize the end bent.',
    'W_cap': 'Cap self-weight acting at the cap centerline.',
    'W_ped': 'Pedestal weight acting at the pedestal centroid.',
    'W_bw': 'Backwall weight acting at the backwall centerline (average height).',
    'W_ck': 'Weight of both cheek walls (outline behind the section).',
    'w_sl_DC': 'Share of the landing slab dead load carried by the backwall top (gravity design only).',
    'w_sl_PL': 'Share of the pedestrian load on the landing slab carried by the backwall top (gravity design only).',
    'W_DCb': 'Superstructure dead load delivered at the bearings.',
    'W_PLb': 'Pedestrian live load delivered at the bearings.',
    'H_WS1': 'Longitudinal wind at the bearings, Strength III direction 1.',
    'H_WS2': 'Longitudinal wind at the bearings, Strength III direction 2.',
    'H_WS3': 'Longitudinal wind at the bearings, Service I.',
}


def _section_rows(e, name):
    v = e.value
    inch = lambda n: f'{v(n, "in"):g} in'
    rows = {
        'y_top': [f'= {sym("h_cap")} − {sym("embed_pile")}', f'= {inch("h_cap")} − {inch("embed_pile")}'],
        'H_ret': [f'= {sym("H_bw")} + {sym("h_cap")}', f'= {v("H_bw", "ft"):.3f} + {v("h_cap", "ft"):.3f} ft', 'backwall crown height (D-019)'],
        'y_brg': [f'= {sym("y_top")} + {sym("h_ped")} + {sym("t_pad")}', f'= {v("y_top", "in"):g} + {v("h_ped", "in"):g} + {v("t_pad", "in"):g} in'],
        'y_strap': [f'= {sym("y_top")} + {sym("z_strap")}', f'= {v("y_top", "ft"):.3f} + {v("z_strap", "ft"):.3f} ft', 'strap lever arm about the pile top'],
        'x_brg': [f'= {sym("e_brg")} + {sym("tol_pile")}', f'= {inch("e_brg")} + {inch("tol_pile")}',
                  'pile shifted toward the fill (SDG 3.13.2.N.3)', ('positive arm overturns toward the span', GREY)],
        'x_cap': [f'= {sym("tol_pile")} = {inch("tol_pile")}', 'cap centered on the nominal pile line'],
        'x_ped': [f'= {sym("t_bw")} + {sym("L_ped")}/2 − {sym("b_cap")}/2 + tol',
                  f'= {v("t_bw", "in"):g} + {v("L_ped", "in") / 2:g} − {v("b_cap", "in") / 2:g} + {v("tol_pile", "in"):g} in'],
        'x_ck': [f'= {sym("w_ck")}/2 − {sym("b_cap")}/2 + tol', f'= {v("w_ck", "in") / 2:g} − {v("b_cap", "in") / 2:g} + {v("tol_pile", "in"):g} in'],
        'x_bw': [f'= {sym("t_bw")}/2 − {sym("b_cap")}/2 + tol', f'= {v("t_bw", "in") / 2:g} − {v("b_cap", "in") / 2:g} + {v("tol_pile", "in"):g} in',
                 ('negative: behind the pile line, stabilizing', GREY)],
        'W_cap': [f'= b · h · L · w<tspan baseline-shift="sub" font-size="75%">c</tspan>',
                  f'= {v("b_cap", "in"):g} × {v("h_cap", "in"):g} × {v("L_cap", "in"):g} in', f'× {v("w_c", "kip/ft^3"):g} kcf'],
        'W_ped': [f'= N · L · B · h<tspan baseline-shift="sub" font-size="75%">ped</tspan> · w<tspan baseline-shift="sub" font-size="75%">c</tspan>',
                  f'= {v("N_brg"):g} × {v("L_ped", "in"):g} × {v("B_ped", "in"):g} × {v("h_ped", "in"):g} in', f'× {v("w_c", "kip/ft^3"):g} kcf'],
        'W_bw': [f'= t · H<tspan baseline-shift="sub" font-size="75%">avg</tspan> · L<tspan baseline-shift="sub" font-size="75%">bw</tspan> · w<tspan baseline-shift="sub" font-size="75%">c</tspan>',
                 f'= {v("t_bw", "in"):g} in × {v("H_bw_avg", "ft"):.3f} ft × {v("L_bw", "ft"):.3f} ft', f'× {v("w_c", "kip/ft^3"):g} kcf'],
        'W_ck': [f'= 2 · t · w · H<tspan baseline-shift="sub" font-size="75%">ck</tspan> · w<tspan baseline-shift="sub" font-size="75%">c</tspan>',
                 f'= 2 × {v("t_ck", "in"):g} in × {v("w_ck", "in"):g} in × {v("H_ck", "ft"):.3f} ft', f'× {v("w_c", "kip/ft^3"):g} kcf'],
        'w_sl_DC': ['= share · L<tspan baseline-shift="sub" font-size="75%">slab</tspan> · t<tspan baseline-shift="sub" font-size="75%">slab</tspan> · w<tspan baseline-shift="sub" font-size="75%">c</tspan>',
                    f'= {v("share_slab"):g} × {v("L_slab", "ft"):g} ft × {v("t_slab", "in"):g} in × {v("w_c", "kip/ft^3"):g} kcf',
                    ('gravity design only; no stabilizing credit (D-017)', GREY)],
        'w_sl_PL': ['= share · L<tspan baseline-shift="sub" font-size="75%">slab</tspan> · q<tspan baseline-shift="sub" font-size="75%">PL</tspan>',
                    f'= {v("share_slab"):g} × {v("L_slab", "ft"):g} ft × {v("q_PL", "kip/ft^2") * 1000:g} psf',
                    ('gravity design only; no stabilizing credit (D-017)', GREY)],
        'W_DCb': [f'= {sym("N_brg")} × {sym("P_DC")} = {v("N_brg"):g} × {v("P_DC", "kip"):g} kip', 'FBMP load case 1 at the bearing nodes'],
        'W_PLb': [f'= {sym("N_brg")} × {sym("P_PL")} = {v("N_brg"):g} × {v("P_PL", "kip"):g} kip', 'FBMP load case 5 (pedestrian load)'],
    }
    for k, case in (('H_WS1', 'WS1'), ('H_WS2', 'WS2'), ('H_WS3', 'WS3')):
        rows[k] = [f'= {sym("N_brg")} × |F<tspan baseline-shift="sub" font-size="75%">Y</tspan>| = {v("N_brg"):g} × {v("FY_" + case, "kip"):g} kip',
                   f'FBMP {case}, either direction, at the top of the pads']
    rows['x_ck'] = ['= native centroid offset + pile tolerance', f'= {v("dx_ck", "in"):.4f} + {v("tol_pile", "in"):g} in']
    for force, volume in (('W_cap', 'V_cap'), ('W_ck', 'V_ck')):
        if v(volume, 'ft^3') > 0:
            rows[force] = ['= native net concrete volume × unit weight', f'= {v(volume, "ft^3"):.4f} ft³ × {v("w_c", "kip/ft^3"):g} kcf']
    return rows[name]


def section(e, name):
    g = _geometry(e)
    s = Svg(SECTION_TEXT[name], height=SECTION_H, title='End-bent section at the backwall crown')
    f = _section_frame(g)
    _section_base(s, f, g)
    rear, front, tol = g['rear'], g['front'], g['tol']
    if name == 'y_top':
        s.dim(f.X(front + 0.2), f.Y(g['emb']), f.X(front + 0.2), f.Y(g['h']), sym(name))
    elif name == 'H_ret':
        s.line(f.X(rear), f.Y(0), f.X(rear), f.Y(g['h'] + g['H']), HL, 3.5)
        s.dim(f.X(rear - 1.6), f.Y(0), f.X(rear - 1.6), f.Y(g['h'] + g['H']), sym(name))
    elif name == 'y_brg':
        s.line(f.X(g['ebrg'] - 0.35), f.Y(g['pad_top']), f.X(front + 0.25), f.Y(g['pad_top']), HL, 1.4, '3 2')
        s.dim(f.X(front + 0.2), f.Y(g['emb']), f.X(front + 0.2), f.Y(g['pad_top']), sym(name))
    elif name == 'y_strap':
        ys = g['h'] + g['zs']
        s.arrow(f.X(rear), f.Y(ys), f.X(rear - 1.4), f.Y(ys), STRAP, 2.6)
        s.dim(f.X(rear - 0.3), f.Y(g['emb']), f.X(rear - 0.3), f.Y(ys), sym(name), side=-1)
    elif name in ('x_brg', 'x_cap', 'x_ped', 'x_ck', 'x_bw'):
        target = {'x_brg': g['ebrg'], 'x_cap': 0.0, 'x_ped': rear + g['tb'] + (g['b'] - g['tb']) / 2,
                  'x_ck': e.value('dx_ck', 'ft'), 'x_bw': rear + g['tb'] / 2}[name]
        level = DIM_LEVEL
        if name == 'x_ck':
            s.rect(f.X(rear), f.Y(g['h'] + g['Hck']), f.L(g['wck']), f.L(g['Hck']), stroke=HL, dash='4 3')
        if name == 'x_bw':
            s.rect(f.X(rear), f.Y(g['h'] + g['H']), f.L(g['tb']), f.L(g['H']), fill=HL, op=0.15, stroke=HL)
        if name == 'x_ped':
            s.rect(f.X(rear + g['tb']), f.Y(g['h'] + g['hped']), f.L(g['b'] - g['tb']), f.L(g['hped']), fill=HL, op=0.2, stroke=HL)
        s.line(f.X(target), f.Y(level - 0.15), f.X(target), f.Y(g['h'] + g['H'] + 0.1), HL, 1.1, '4 3')
        s.dim(f.X(-tol), f.Y(level), f.X(target), f.Y(level), sym(name), side=-1, offset=9)
        s.circle(f.X(target), f.Y(level), 2.2, fill=HL)
    elif name in ('W_cap', 'W_ped', 'W_bw', 'W_ck'):
        x0, y0, w, h = {'W_cap': (rear, 0, g['b'], g['h']), 'W_ped': (rear + g['tb'], g['h'], g['b'] - g['tb'], g['hped']),
                        'W_bw': (rear, g['h'], g['tb'], g['H']), 'W_ck': (rear, g['h'], g['wck'], g['Hck'])}[name]
        s.rect(f.X(x0), f.Y(y0 + h), f.L(w), f.L(h), fill=HL, op=0.18, stroke=HL, sw=1.4, dash='4 3' if name == 'W_ck' else None)
        cx, cy = x0 + w / 2, y0 + h / 2
        s.circle(f.X(cx), f.Y(cy), 2.6, fill=HL)
        s.arrow(f.X(cx), f.Y(cy), f.X(cx), f.Y(cy) + 28, HL, 2.4)
        s.tag(f.X(cx) + 7, f.Y(cy) + 20, sym(name), HL, 'start')
    elif name in ('w_sl_DC', 'w_sl_PL'):
        top = g['h'] + g['H'] + g['ts']
        s.rect(f.X(rear - 1.9), f.Y(top), f.L(1.9 + g['tb']), f.L(g['ts']), fill=HL, op=0.2, stroke=HL)
        for x in (rear + g['tb'] * 0.25, rear + g['tb'] * 0.75):
            s.arrow(f.X(x), f.Y(top) - 24, f.X(x), f.Y(top), HL, 1.8)
        s.tag(f.X(rear + g['tb'] / 2), f.Y(top) - 28, sym(name), HL)
    elif name in ('W_DCb', 'W_PLb'):
        s.arrow(f.X(g['ebrg']), f.Y(g['pad_top']) - 46, f.X(g['ebrg']), f.Y(g['pad_top']), HL, 2.8)
        s.tag(f.X(g['ebrg']) + 6, f.Y(g['pad_top']) - 40, sym(name), HL, 'start')
    elif name.startswith('H_WS'):
        y = g['pad_top']
        s.arrow(f.X(g['ebrg']) - 44, f.Y(y), f.X(g['ebrg']) - 2, f.Y(y), HL, 2.8)
        s.tag(f.X(g['ebrg']) - 48, f.Y(y) - 6, sym(name), HL, 'end')
    s.panel(_eq(e, name, 3), _section_rows(e, name))
    return s


# ----------------------------------------------------------------------------- earth pressure
def coulomb(e, name):
    v = e.value
    s = Svg('Coulomb active wedge: back face angle θ, backfill slope β, wall friction δ and soil friction angle φ.',
            title='Coulomb active wedge behind the retained face')
    wx, y0, y1 = 330, 330, 60
    s.poly([(wx, y1), (wx, y0), (40, y0), (40, y1)], fill=SOIL, stroke='none')
    s.rect(wx, y1, 50, y0 - y1, fill=CONC, stroke=INK)
    phi = v('phi_soil', 'deg')
    rho = 45 + phi / 2
    x_top = wx - (y0 - y1) / math.tan(math.radians(rho))
    s.poly([(wx, y0), (x_top, y1), (wx, y1)], fill=HL, op=0.12, stroke=HL, sw=1.3)
    s.tag((x_top + wx) / 2 + 10, y1 + 18, 'active wedge', HL)
    s.angle(wx, y0, 40, 180 - rho, 180, INK, 1.2)
    s.tag(wx - 56, y0 - 10, f'{rho:.0f}°', INK, 'end')
    mid = y0 - (y0 - y1) / 3
    delta = v('delta_w', 'deg')
    dx, dy = 80 * math.cos(math.radians(delta)), 80 * math.sin(math.radians(delta))
    s.arrow(wx - dx, mid + dy, wx, mid, HL, 2.6)
    s.tag(wx - dx - 4, mid + dy - 6, sub('P', 'a'), HL, 'end')
    rows = [f'θ = {v("theta_w", "deg"):g}° back face from horizontal', f'β = {v("beta_f", "deg"):g}° backfill slope',
            f'δ = {delta:g}° wall friction (neglected)', f'φ = {phi:g}° backfill friction (D-016)',
            f'failure plane ≈ 45° + φ/2 = {rho:.1f}°']
    if name == 'k_a':
        rows += [f'Γ = {v("Gamma_c"):.4f}', 'p(z) = k<tspan baseline-shift="sub" font-size="75%">a</tspan>·γ·z']
    s.panel(_eq(e, name, 4), rows)
    return s


def pressure(e, name):
    v = e.value
    kind = name.split('_')[1]
    Hr, emb = v('H_ret', 'ft'), v('embed_pile', 'ft')
    s = Svg(f'{kind} pressure on the retained face over the cap length.', title=f'{kind} pressure on the retained face (cap soffit to backwall crown)')
    f = Frame(-3.4, 2.4, -0.4, Hr + 1.0, 12, 30, PX - 40, H - 44)
    s.rect(f.X(0), f.Y(Hr), f.L(0.85), f.L(Hr), fill=CONC, stroke=INK)
    s.rect(f.X(-3.4), f.Y(Hr), f.L(3.4), f.L(Hr), fill=SOIL, stroke='none', op=0.6)
    s.line(f.X(-3.4), f.Y(emb), f.X(2.0), f.Y(emb), GREY, 0.9, '2 3')
    s.tag(f.X(-3.3), f.Y(emb) - 4, 'pile top', GREY, 'start')
    width = 2.4
    if kind == 'EH':
        pts = [(f.X(0), f.Y(Hr)), (f.X(0), f.Y(0)), (f.X(-width), f.Y(0))]
        ybar, frac = Hr / 3, 'H/3'
    else:
        w = width * 0.5
        pts = [(f.X(0), f.Y(Hr)), (f.X(0), f.Y(0)), (f.X(-w), f.Y(0)), (f.X(-w), f.Y(Hr))]
        ybar, frac = Hr / 2, 'H/2'
    s.poly(pts, fill=AMBER, op=0.35, stroke=AMBER, sw=1.2)
    s.tag(pts[2][0], f.Y(0) + 13, sym('p_' + kind), HL if name.startswith('p_') else INK)
    if kind in ('ES', 'LS'):
        s.rect(f.X(-3.4), f.Y(Hr + 0.33), f.L(3.4), f.L(0.33), fill=SLAB, stroke=GREY) if kind == 'ES' else None
        for x in (-3.0, -2.1, -1.2, -0.3):
            s.arrow(f.X(x), f.Y(Hr + 0.95), f.X(x), f.Y(Hr + (0.35 if kind == 'ES' else 0.05)), HL if name == 'q_ES' else GREY, 1.3)
        s.tag(f.X(-1.7), f.Y(Hr + 0.98) - 2, sym('q_ES') if kind == 'ES' else sub('q', 'PL'), HL if name == 'q_ES' else INK)
    force = 'F_' + kind
    color = HL if name.startswith('F_') else BLUE
    s.arrow(f.X(-1.3), f.Y(ybar), f.X(0) - 1, f.Y(ybar), color, 2.8)
    s.tag(f.X(-1.33), f.Y(ybar) - 5, sym(force), color, 'end')
    s.dim(f.X(1.0), f.Y(0), f.X(1.0), f.Y(ybar), frac, GREY)
    s.dim(f.X(1.8), f.Y(emb), f.X(1.8), f.Y(ybar), sym('y_' + kind), HL if name.startswith('y_') else GREY)
    s.dim(f.X(-3.2), f.Y(0), f.X(-3.2), f.Y(Hr), sym('H_ret'), GREY)
    ka = v('k_a')
    load = {'EH': f'γ = {v("gamma_s", "kip/ft^3") * 1000:g} pcf', 'LS': f'q = {v("q_PL", "kip/ft^2") * 1000:g} psf (pedestrian)',
            'ES': f'q = t·w<tspan baseline-shift="sub" font-size="75%">c</tspan> = {v("q_ES", "kip/ft^2") * 1000:.0f} psf (slab)'}[kind]
    formula = {'p_EH': 'p = k<tspan baseline-shift="sub" font-size="75%">a</tspan>·γ·H<tspan baseline-shift="sub" font-size="75%">ret</tspan>',
               'F_EH': 'F = ½·k<tspan baseline-shift="sub" font-size="75%">a</tspan>·γ·H²·L<tspan baseline-shift="sub" font-size="75%">load</tspan>',
               'y_EH': 'y = H<tspan baseline-shift="sub" font-size="75%">ret</tspan>/3 − embedment',
               'p_LS': 'p = k<tspan baseline-shift="sub" font-size="75%">a</tspan>·q', 'F_LS': 'F = p·H<tspan baseline-shift="sub" font-size="75%">ret</tspan>·L<tspan baseline-shift="sub" font-size="75%">load</tspan>',
               'y_LS': 'y = H<tspan baseline-shift="sub" font-size="75%">ret</tspan>/2 − embedment', 'q_ES': 'q = t<tspan baseline-shift="sub" font-size="75%">slab</tspan>·w<tspan baseline-shift="sub" font-size="75%">c</tspan>',
               'p_ES': 'p = k<tspan baseline-shift="sub" font-size="75%">a</tspan>·q', 'F_ES': 'F = p·H<tspan baseline-shift="sub" font-size="75%">ret</tspan>·L<tspan baseline-shift="sub" font-size="75%">load</tspan>',
               'y_ES': 'y = H<tspan baseline-shift="sub" font-size="75%">ret</tspan>/2 − embedment'}[name]
    rows = [formula, f'k<tspan baseline-shift="sub" font-size="75%">a</tspan> = {ka:.4f}', load,
            f'H<tspan baseline-shift="sub" font-size="75%">ret</tspan> = {Hr:.3f} ft · L<tspan baseline-shift="sub" font-size="75%">load</tspan> = {v("L_load", "ft"):.3f} ft',
            f'embedment = {v("embed_pile", "in"):g} in (pile top)']
    s.panel(_eq(e, name, 3 if not name.startswith('p_') else 4), rows)
    return s


# ----------------------------------------------------------------------------- bearing pad and movements
def pad(e, name):
    v = e.value
    s = Svg('Laminated Type F elastomeric bearing: plan area, elastomer layers and shear deformation.',
            title='Type F laminated elastomeric bearing pad (one of N bearings)')
    L, Wp = v('L_pad', 'in'), v('W_pad', 'in')
    n, ti, tc = int(round(v('n_int'))), v('t_int', 'in'), v('t_cov', 'in')
    layers = [tc] + [ti] * n + [tc]
    total = sum(layers)
    k = min(250 / L, 110 / total)
    x0, y_base = 50, 285
    shear = name in ('K_pad', 'F_TU', 'F_SH')
    delta = v('Delta_TU', 'in') if name == 'F_TU' else v('Delta_SH', 'in') if name == 'F_SH' else 0.0
    drawn = max(delta * k, 22) if shear else 0.0
    s.rect(x0 - 30, y_base, L * k + 90, 16, fill=CONC, stroke=GREY, sw=0.8)
    s.tag(x0 - 26, y_base + 12, 'cap / pedestal', GREY, 'start')
    y = y_base
    for i, t in enumerate(layers):
        h = t * k
        s0, s1 = drawn * (y_base - y) / (total * k), drawn * (y_base - y + h) / (total * k)
        s.poly([(x0 + s0, y), (x0 + L * k + s0, y), (x0 + L * k + s1, y - h), (x0 + s1, y - h)],
               fill='#f0b9b5' if name == 'h_rt' else '#b9c3cc', stroke=GREY, sw=0.8)
        y -= h
        if i < len(layers) - 1:
            sh = drawn * (y_base - y) / (total * k)
            s.line(x0 + sh, y, x0 + L * k + sh, y, PAD, 3)
    top = y
    s.rect(x0 - 30 + drawn, top - 18, L * k + 90, 18, fill='#f7f9fb', stroke=GREY, sw=0.8)
    s.tag(x0 - 26 + drawn, top - 5, 'beam', GREY, 'start')
    s.tag(x0 + L * k / 2, y_base + 32, f'section along the beam: L = {L:g} in · dark lines = steel shims', INK)
    if name == 'h_rt' or shear:
        s.dim(x0 + L * k + drawn + 16, y_base, x0 + L * k + drawn + 16, top, sym('h_rt'), HL if name == 'h_rt' else GREY)
    if shear:
        s.line(x0, y_base, x0, top - 22, GREY, 0.8, '3 2')
        s.dim(x0, top - 30, x0 + drawn, top - 30, 'Δ' if name == 'K_pad' else sym(name.replace('F_', 'Delta_')), HL if name != 'K_pad' else GREY, side=-1)
        s.arrow(x0 + L * k + 40, y_base + 8, x0 + L * k + 92, y_base + 8, HL, 2.6)
        s.tag(x0 + L * k + 96, y_base + 12, 'H on cap', HL, 'start')
        if drawn > delta * k + 0.5:
            s.text(x0 + L * k / 2, top - 52, 'shear deformation exaggerated', 9, GREY)
        s.text(x0 + L * k / 2, top - 66, 'beam end moves toward the span', 9, GREY)
    px, py = 345, 52
    sk = min(110 / Wp, 70 / L)
    s.rect(px, py, L * sk, Wp * sk, fill=HL if name in ('A_pad', 'K_pad') else '#b9c3cc', op=0.3 if name in ('A_pad', 'K_pad') else 1, stroke=INK)
    s.tag(px + L * sk / 2, py - 6, 'plan', INK)
    s.tag(px + L * sk + 5, py + Wp * sk / 2 + 3, f'W = {Wp:g} in', INK, 'start')
    s.tag(px + L * sk / 2, py + Wp * sk + 13, f'L = {L:g} in', INK)
    rows = {
        'A_pad': [f'= L × W = {L:g} × {Wp:g} in'],
        'h_rt': [f'= n·t<tspan baseline-shift="sub" font-size="75%">int</tspan> + 2·t<tspan baseline-shift="sub" font-size="75%">cov</tspan>',
                 f'= {n} × {ti:g} + 2 × {tc:g} in', ('steel shims do not shear', GREY)],
        'K_pad': ['= G<tspan baseline-shift="sub" font-size="75%">fac</tspan>·G·A / h<tspan baseline-shift="sub" font-size="75%">rt</tspan>',
                  f'= {v("G_fac"):g} × {v("G_pad", "ksi") * 1000:g} psi × {v("A_pad", "in^2"):g} in² / {v("h_rt", "in"):g} in',
                  ('H = K·Δ per pad; upper-bound G gives the larger force', GREY)],
        'F_TU': ['= N · K · Δ<tspan baseline-shift="sub" font-size="75%">TU</tspan>',
                 f'= {v("N_brg"):g} × {v("K_pad", "kip/in"):.2f} kip/in × {v("Delta_TU", "in"):.4f} in', ('temperature fall: pads pull the cap toward the span', GREY)],
        'F_SH': ['= N · K · Δ<tspan baseline-shift="sub" font-size="75%">SH</tspan>',
                 f'= {v("N_brg"):g} × {v("K_pad", "kip/in"):.2f} kip/in × {v("Delta_SH", "in"):.4f} in', ('beam shrinkage: pads pull the cap toward the span', GREY)],
    }[name]
    s.panel(_eq(e, name, 3), rows)
    return s


def movement(e, name):
    v = e.value
    thermal = name == 'Delta_TU'
    s = Svg('Shortening of the span between the movement center at the pier and the end bent.', height=230,
            title='Span shortening toward the movement center')
    x0, x1, y = 420, 70, 120
    s.rect(x1, y - 14, x0 - x1, 14, fill=CONC, stroke=INK)
    s.poly([(x0, y + 2), (x0 - 10, y + 20), (x0 + 10, y + 20)], fill=INK)
    s.tag(x0, y + 36, 'pier (movement center)', INK)
    s.rect(x1 - 8, y, 16, 26, fill=PAD)
    s.tag(x1, y + 42, 'end bent pad', INK)
    s.dim(x1, y - 36, x0, y - 36, sym('L_exp'), GREY, side=-1)
    s.arrow(x1 - 2, y - 7, x1 + 48, y - 7, HL, 2.8)
    s.tag(x1 + 52, y - 3, 'Δ', HL, 'start')
    rows = ([f'= α·ΔT·L<tspan baseline-shift="sub" font-size="75%">exp</tspan>', f'= {v("alpha_t"):.1e} × {v("dT"):g} °F × {v("L_exp", "in"):.1f} in',
             ('concrete only, 70 °F mean, 35 °F low (SDG 2.7.1)', GREY)] if thermal else
            [f'= ε<tspan baseline-shift="sub" font-size="75%">sh</tspan>·L<tspan baseline-shift="sub" font-size="75%">exp</tspan>',
             f'= {v("eps_sh"):.1e} × {v("L_exp", "in"):.1f} in', ('template strain placeholder (pending)', GREY)])
    s.panel(_eq(e, name, 4), rows)
    return s


# ----------------------------------------------------------------------------- overturning free body
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


def free_body(e, name):
    m = re.match(rf'^(H|M|e|F_eq|F_str|f_str|V_pile)_({KEYS})$', name)
    part, key = m.group(1), m.group(2)
    v = e.value
    g = _geometry(e)
    rear, front, tol = g['rear'], g['front'], g['tol']
    s = Svg(f'{LABELS[key]} free body about the pile top O: factored loads, strap force and pile reaction.', height=430,
            title=f'{LABELS[key]} · free body about the pile top O (callouts key to the table)')
    top = g['h'] + max(g['H'], g['Hck'])
    f = Frame(rear - 2.5, front + 1.9, -1.0, top + 0.55, 12, 34, PX - 40, 384)
    # structure, faint: the drawing is about the forces
    s.rect(f.X(rear), f.Y(g['h'] + g['Hck']), f.L(g['wck']), f.L(g['Hck']), stroke=FAINT, dash='3 3')
    s.tag(f.X(rear + g['wck']) + 4, f.Y(g['h'] + g['Hck']) + 10, 'cheek wall (behind)', GREY, 'start')
    s.rect(f.X(-g['dp'] / 2 - tol), f.Y(g['emb']), f.L(g['dp']), f.L(g['emb'] + 0.95), fill='#e4e9ee', stroke=FAINT)
    s.rect(f.X(rear), f.Y(g['h']), f.L(g['b']), f.L(g['h']), fill=CONC, stroke=GREY, sw=0.8)
    s.rect(f.X(rear), f.Y(g['h'] + g['H']), f.L(g['tb']), f.L(g['H']), fill=CONC, stroke=GREY, sw=0.8)
    s.rect(f.X(rear + g['tb']), f.Y(g['h'] + g['hped']), f.L(g['b'] - g['tb']), f.L(g['hped']), fill='#eef2f5', stroke=GREY, sw=0.6)
    s.rect(f.X(g['ebrg'] - g['lpad'] / 2), f.Y(g['pad_top']), f.L(g['lpad']), f.L(g['tpad']), fill=PAD, stroke=PAD)
    px, py = -tol, g['emb']
    s.line(f.X(px), f.Y(-0.95), f.X(px), f.Y(top + 0.1), BLUE, 0.8, '5 3')
    s.circle(f.X(px), f.Y(py), 4.5, fill='#ffffff', stroke=BLUE, sw=2)
    s.tag(f.X(px) + 8, f.Y(py) + 15, 'O', BLUE, 'start')
    s.tag(f.X(rear - 2.4), f.Y(-0.75), 'FILL', '#9b8456', 'start')
    s.tag(f.X(front + 1.8), f.Y(-0.75), 'SPAN →', GREY, 'end')

    rows = [dict(r, n=i + 1) for i, r in enumerate(r for r in strap_table(e, key) if r['factor'])]
    family = {'H': 'H', 'M': 'both', 'e': 'H'}.get(part, 'none')
    h_color = HL if family in ('H', 'both') else '#6b7f92'
    v_color = HL if family == 'both' else '#6b7f92'
    soil = [r for r in rows if r['kind'] == 'H' and r['item'] in ('EH', 'ES', 'LS')]
    brg = [r for r in rows if r['kind'] == 'H' and r not in soil]
    vert = [r for r in rows if r['kind'] != 'H']
    peak_h = max([abs(r['factor'] * r['force_kip']) for r in soil + brg] + [1e-9])
    peak_v = max([abs(r['factor'] * r['force_kip']) for r in vert] + [1e-9])

    # soil forces on the retained face; callouts in a column on the fill side
    ys = []
    for r in soil:
        ys.append(f.Y(py + r['arm_ft']))
    ys = _spread(ys, 9) if ys else ys
    tags = _spread(list(ys), 17) if ys else ys
    for r, y, ty in zip(soil, ys, tags):
        length = 18 + 46 * abs(r['factor'] * r['force_kip']) / peak_h
        s.arrow(f.X(rear) - length, y, f.X(rear) - 1, y, h_color, 1.8)
        tx = f.X(rear - 2.2)
        s.line(tx + 7, ty, f.X(rear) - length - 2, y, FAINT, 0.8)
        s.num(tx, ty, r['n'], h_color)
    # bearing forces at the top of the pads, pulling toward the span
    x0 = f.X(g['ebrg'] + g['lpad'] / 2) + 2
    tags = _spread([f.Y(g['pad_top']) - 10 * i for i in range(len(brg))], 17)
    for i, (r, ty) in enumerate(zip(brg, tags)):
        y = f.Y(g['pad_top']) - 7 * i
        length = 18 + 46 * abs(r['factor'] * r['force_kip']) / peak_h
        s.arrow(x0, y, x0 + length, y, h_color, 1.8)
        s.line(x0 + length + 3, y, x0 + 66 + 9, ty, FAINT, 0.8)
        s.num(x0 + 66 + 16, ty, r['n'], h_color)
    # gravity loads at their points of application; callouts in a row along the top
    points = []
    for r in vert:
        x = px + r['arm_ft']
        y = {'DCb': g['pad_top'], 'PLb': g['pad_top'], 'cap': g['h'] / 2, 'ped': g['h'] + g['hped'] / 2,
             'ck': g['h'] + g['Hck'] / 2, 'bw': g['h'] + g['H'] / 2}.get(r['item'], g['h'])
        nudge = {'DCb': -4, 'PLb': 4}.get(r['item'], 0)
        points.append((f.X(x) + nudge, f.Y(y)))
    lane = f.Y(top + 0.38)
    tags = _spread([p[0] for p in points], 18) if points else []
    for r, (x, y), tx in zip(vert, points, tags):
        length = 16 + 40 * abs(r['factor'] * r['force_kip']) / peak_v
        s.circle(x, y, 2.2, fill=v_color)
        s.arrow(x, y - length, x, y, v_color, 1.6)
        s.line(tx, lane + 7, x, y - length - 2, FAINT, 0.8)
        s.num(tx, lane, r['n'], v_color)

    # strap, resultant, pile reaction
    y_strap = py + v('y_strap', 'ft')
    strap_color = HL if part in ('F_eq', 'F_str', 'f_str') else STRAP
    s.arrow(f.X(rear), f.Y(y_strap), f.X(rear) - 64, f.Y(y_strap), strap_color, 3)
    s.tag(f.X(rear) - 34, f.Y(y_strap) - 8, 'strap', strap_color)
    Hk, Mk = v('H_' + key), v('M_' + key)
    F_eq, F_str = v('F_eq_' + key), v('F_str_' + key)
    if part == 'M':
        s.arc(f.X(px), f.Y(py), 24, 155, 25, HL, 2)
        s.tag(f.X(px) - 30, f.Y(py) - 16, 'M', HL, 'end')
    if part == 'e':
        ey = py + v(name, 'ft')
        s.line(f.X(rear - 0.3), f.Y(ey), f.X(front + 1.6), f.Y(ey), HL, 1.4, '6 3')
        s.tag(f.X(front + 1.6), f.Y(ey) - 5, 'resultant H', HL, 'end')
        s.dim(f.X(front + 1.35), f.Y(py), f.X(front + 1.35), f.Y(ey), sym(name), side=1)
    if part in ('F_eq', 'F_str', 'f_str', 'V_pile', 'e'):
        s.dim(f.X(rear) + 10, f.Y(py), f.X(rear) + 10, f.Y(y_strap), sym('y_strap'), STRAP)
    if part == 'V_pile':
        vp = v(name)
        if abs(vp) > 1e-6:
            sign = 1 if vp > 0 else -1
            s.arrow(f.X(px) - 46 * sign, f.Y(py) + 1, f.X(px) - 7 * sign, f.Y(py) + 1, HL, 2.6)
            s.tag(f.X(px) - 50 * sign, f.Y(py) - 6, sym('V_pile'), HL, 'end' if sign > 0 else 'start')

    detail = {'H': ['= Σ γ·F of the horizontal loads (toward the span)'],
              'M': ['= Σ γ·F·arm about O (+ overturns toward the span)'],
              'e': [f'= M / H = {Mk:.1f} / {Hk:.2f}', ('a strap at this height needs no pile force', GREY)],
              'F_eq': [f'= M / y<tspan baseline-shift="sub" font-size="75%">strap</tspan> = {Mk:.1f} / {v("y_strap", "ft"):.3f}'],
              'F_str': [f'= max(H, M/y<tspan baseline-shift="sub" font-size="75%">strap</tspan>) = max({Hk:.2f}, {F_eq:.2f})'],
              'f_str': [f'= F<tspan baseline-shift="sub" font-size="75%">str</tspan> / L<tspan baseline-shift="sub" font-size="75%">bw</tspan> = {F_str:.2f} / {v("L_bw", "ft"):.3f} ft',
                        ('per foot of backwall, for the plans (SDM 12.3.F)', GREY)],
              'V_pile': [f'= M/y<tspan baseline-shift="sub" font-size="75%">strap</tspan> − H = {F_eq:.2f} − {Hk:.2f}', ('+ : piles push the cap toward the span', GREY)]}[part]
    places = {'M': 1, 'e': 3, 'f_str': 3}.get(part, 2)
    y = s.panel(_eq(e, name, places), detail, heading=LABELS[key])
    cols = [(PX, 'start'), (PX + 16, 'start'), (PX + 92, 'end'), (PX + 140, 'end'), (PX + 200, 'end'), (PX + 268, 'end')]
    table = [(['#', 'load', 'γ', 'arm ft', 'γ·F kip', 'γ·M k-ft'], GREY, True)]
    for r in rows:
        color = h_color if r['kind'] == 'H' else v_color
        table.append(([str(r['n']), escape(r['item']), f'{r["factor"]:g}', f'{r["arm_ft"]:.2f}',
                       f'{r["factor"] * r["force_kip"]:.1f}', f'{r["factored_moment"]:.1f}'],
                      color if color == HL else INK, False))
    table.append((['', 'Σ', '', '', f'{Hk:.1f} (H)', f'{Mk:.1f}'], HL if part in ('H', 'M') else INK, True))
    s.table(y + 4, cols, table, step=15)
    s.text(PX, s.h - 12, 'H arms: height above O · V arms: + toward the span from O', 9, GREY, 'start')
    return s


def envelope(e, name):
    spec = {
        'f_str_u': ('f_str_', STRENGTH, 'kip/ft', 'Largest factored strap load per foot over the strength combinations.'),
        'f_str_s': ('f_str_', [SERVICE], 'kip/ft', 'Service I strap load per foot.'),
        'F_str_u': ('f_str_', STRENGTH, 'kip/ft', 'Factored strap total = governing load per foot × backwall length.'),
        'F_str_s': ('f_str_', [SERVICE], 'kip/ft', 'Service strap total = service load per foot × backwall length.'),
        'M_u_FF': ('M_sl_', STRENGTH, 'kip*ft', 'Largest strap-slack joint moment (fill-face tension) over the strength combinations.'),
        'M_s_FF': ('M_sl_', [SERVICE], 'kip*ft', 'Service I strap-slack joint moment.'),
        'M_u_SF': ('M_en_', STRENGTH, 'kip*ft', 'Largest strap-engaged joint moment (span-face tension), not less than zero.'),
        'M_s_SF': ('M_en_', [SERVICE], 'kip*ft', 'Service I strap-engaged joint moment, not less than zero.'),
        'V_u_bw': ('V_sl_', STRENGTH, 'kip', 'Largest joint shear over both strap states and the strength combinations.'),
    }[name]
    prefix, combos, unit, text = spec
    items = [(c['label'], e.value(prefix + c['key'], unit)) for c in combos]
    if name == 'V_u_bw':
        items += [(c['label'] + ' (engaged)', abs(e.value('V_en_' + c['key'], unit))) for c in combos]
    extra = []
    if name.startswith('F_str'):
        extra = [f'= f × L<tspan baseline-shift="sub" font-size="75%">bw</tspan> = {e.value(name.replace("F_", "f_")):.3f} × {e.value("L_bw", "ft"):.3f} ft']
    return _bars(e, name, items, unit.replace('kip*ft', 'kip-ft'), text, highlight=max(range(len(items)), key=lambda i: items[i][1]), extra=extra)


# ----------------------------------------------------------------------------- backwall strip
def wall_strip(e, name):
    component = re.match(r'^(V|M)_(EH|LS|ES)_bw$', name)
    if component:
        key, state, kind = STRENGTH[0]['key'], 'component', component.group(2)
    else:
        m = re.match(rf'^(M|V)_(sl|en)_({KEYS})$', name)
        key, state, kind = m.group(3), 'slack' if m.group(2) == 'sl' else 'engaged', None
    v = e.value
    Hb, t, zs = v('H_bw', 'ft'), v('t_bw', 'ft'), v('z_strap', 'ft')
    title = (f'1-ft backwall strip · {kind} component (unfactored)' if kind else
             f'1-ft backwall strip · {LABELS[key]} · strap {"slack" if state == "slack" else "engaged"}')
    s = Svg(title, title=title)
    f = Frame(-2.6, 2.2, -0.7, Hb + 0.5, 12, 30, PX - 40, H - 44)
    s.rect(f.X(0), f.Y(Hb), f.L(t), f.L(Hb), fill=CONC, stroke=INK)
    s.rect(f.X(-0.5), f.Y(0), f.L(t + 1.4), f.L(0.6), fill='#eef2f5', stroke=FAINT)
    s.tag(f.X(t + 0.55), f.Y(-0.35), 'cap', GREY)
    s.line(f.X(-0.5), f.Y(0), f.X(t + 0.9), f.Y(0), GREY, 1, '4 2')
    s.tag(f.X(t + 0.95), f.Y(0) + 3, 'joint', GREY, 'start')
    combo = next(c for c in COMBINATIONS if c['key'] == key)
    eh, es, ls = _soil_factors(combo)
    if kind:
        eh, es, ls = (1.0 if kind == 'EH' else 0.0), (1.0 if kind == 'ES' else 0.0), (1.0 if kind == 'LS' else 0.0)
    ka, gs = v('k_a'), v('gamma_s', 'kip/ft^3')
    unif = es * v('p_ES', 'kip/ft^2') + ls * v('p_LS', 'kip/ft^2')
    pmax = eh * ka * gs * Hb + unif
    scale = 2.0 / max(pmax, 1e-9)
    s.poly([(f.X(0), f.Y(Hb)), (f.X(0), f.Y(0)), (f.X(-pmax * scale), f.Y(0)), (f.X(-unif * scale), f.Y(Hb))], fill=AMBER, op=0.35, stroke=AMBER)
    s.tag(f.X(-pmax * scale), f.Y(0) + 13, f'{pmax * 1000:.0f} psf', INK)
    s.dim(f.X(-2.4), f.Y(0), f.X(-2.4), f.Y(Hb), sym('H_bw'), GREY)
    if kind:
        y = Hb / 3 if kind == 'EH' else Hb / 2
        s.arrow(f.X(-1.2), f.Y(y), f.X(0) - 1, f.Y(y), HL if name.startswith('V') else BLUE, 2.8)
        s.tag(f.X(-1.23), f.Y(y) - 5, sym(f'V_{kind}_bw'), HL if name.startswith('V') else BLUE, 'end')
        s.dim(f.X(t + 0.3), f.Y(0), f.X(t + 0.3), f.Y(y), f'H/{3 if kind == "EH" else 2}', GREY)
        if name.startswith('M'):
            s.arc(f.X(t / 2), f.Y(0), 24, 150, 30, HL)
        formula = {('V', 'EH'): '= ½·k<tspan baseline-shift="sub" font-size="75%">a</tspan>·γ·H²·1 ft', ('M', 'EH'): '= V · H/3',
                   ('V', 'LS'): '= p<tspan baseline-shift="sub" font-size="75%">LS</tspan>·H·1 ft', ('M', 'LS'): '= V · H/2',
                   ('V', 'ES'): '= p<tspan baseline-shift="sub" font-size="75%">ES</tspan>·H·1 ft', ('M', 'ES'): '= V · H/2'}[(name[0], kind)]
        rows = [formula, f'H<tspan baseline-shift="sub" font-size="75%">bw</tspan> = {Hb:.3f} ft (crown)', f'base pressure {pmax * 1000:.1f} psf']
        if name.startswith('M'):
            rows.insert(1, f'= {v(f"V_{kind}_bw"):.4f} kip × {Hb / (3 if kind == "EH" else 2):.3f} ft')
    else:
        tension_x = 0 if state == 'slack' else t
        s.line(f.X(tension_x), f.Y(0), f.X(tension_x), f.Y(min(Hb, 1.5)), HL, 4)
        s.tag(f.X(tension_x) + (-5 if state == 'slack' else 5), f.Y(1.6), 'tension face', HL, 'end' if state == 'slack' else 'start')
        if state == 'engaged':
            s.arrow(f.X(0), f.Y(zs), f.X(0) - 66, f.Y(zs), STRAP, 2.8)
            s.tag(f.X(0) - 68, f.Y(zs) - 6, 'strap', STRAP, 'end')
            s.dim(f.X(t + 0.3), f.Y(0), f.X(t + 0.3), f.Y(zs), sym('z_strap'), STRAP)
        if name.startswith('M'):
            s.arc(f.X(t / 2), f.Y(0), 24, *((150, 30) if state == 'slack' else (30, 150)), HL)
        else:
            s.arrow(f.X(t / 2) + 38, f.Y(0) + 8, f.X(t / 2) - 28, f.Y(0) + 8, HL, 2.4)
        soil = f'{eh:g}·EH + {es:g}·ES + {ls:g}·LS'
        if state == 'slack':
            rows = [f'= {soil} ({"moments" if name[0] == "M" else "shears"} at the joint)',
                    f'= {eh:g}×{v("M_EH_bw" if name[0] == "M" else "V_EH_bw"):.3f} + {es:g}×{v("M_ES_bw" if name[0] == "M" else "V_ES_bw"):.3f} + {ls:g}×{v("M_LS_bw" if name[0] == "M" else "V_LS_bw"):.3f}',
                    ('soil pushes the wall toward the span', GREY)]
        else:
            fs = v('f_str_' + key, 'kip/ft')
            other = v('M_sl_' + key) if name[0] == 'M' else v('V_sl_' + key)
            rows = ([f'= f<tspan baseline-shift="sub" font-size="75%">str</tspan>·1 ft·z − M<tspan baseline-shift="sub" font-size="75%">slack</tspan>',
                     f'= {fs:.3f} × {zs:.3f} − {other:.3f}'] if name[0] == 'M' else
                    [f'= f<tspan baseline-shift="sub" font-size="75%">str</tspan>·1 ft − V<tspan baseline-shift="sub" font-size="75%">slack</tspan>', f'= {fs:.3f} − {other:.3f}'])
            rows.append(('strap pull exceeds the soil load: span face in tension', GREY))
        rows.append(f'factors: EH {eh:g}, ES {es:g}, LS {ls:g}')
    s.panel(_eq(e, name, 3), rows, heading=('Unfactored component' if kind else LABELS[key]))
    return s


# ----------------------------------------------------------------------------- 1-ft strip section
SECTION_PARTS = ('d', 'A_s', 'a', 'c', 'eps_t', 'phi', 'M_n', 'M_r', 'A_req', 'S_c', 'M_cr', 'M_min', 'rho', 'k', 'j',
                 'f_ss', 'd_c', 'beta_s', 's_cr', 'd_v', 'V_c', 'V_n', 'V_r')
MEMBER = {'FF': ('t_bw', 'backwall · fill-face steel (strap slack)'), 'SF': ('t_bw', 'backwall · span-face steel (strap engaged)'),
          'CK': ('t_ck', 'cheek wall · either face')}
PART_ROWS = {
    'd': lambda v, X, t: [f'= h − cover − d<tspan baseline-shift="sub" font-size="75%">b</tspan>/2', f'= {t:g} − {v("cv_ck" if X == "CK" else "cv_bw", "in"):g} − {v("d_b_" + X, "in"):g}/2 in'],
    'A_s': lambda v, X, t: [f'= A<tspan baseline-shift="sub" font-size="75%">bar</tspan> × 12 in / s', f'= {v("A_b_" + X, "in^2"):g} × 12 / {v("s_" + X, "in"):g}'],
    'a': lambda v, X, t: ['= A<tspan baseline-shift="sub" font-size="75%">s</tspan>·f<tspan baseline-shift="sub" font-size="75%">y</tspan> / (0.85·f′c·b)',
                          f'= {v("A_s_" + X, "in^2"):.3f} × {v("fy", "ksi"):g} / (0.85 × {v("fc", "ksi"):g} × 12)'],
    'c': lambda v, X, t: [f'= a / β<tspan baseline-shift="sub" font-size="75%">1</tspan> = {v("a_" + X, "in"):.4f} / {v("beta_1"):.3f}'],
    'eps_t': lambda v, X, t: ['= 0.003·(d − c)/c', f'= 0.003 × ({v("d_" + X, "in"):.4f} − {v("c_" + X, "in"):.4f}) / {v("c_" + X, "in"):.4f}',
                              ('≥ 0.005: tension controlled', GREY)],
    'M_n': lambda v, X, t: ['= A<tspan baseline-shift="sub" font-size="75%">s</tspan>·f<tspan baseline-shift="sub" font-size="75%">y</tspan>·(d − a/2)',
                            f'= {v("A_s_" + X, "in^2"):.3f} × {v("fy", "ksi"):g} × ({v("d_" + X, "in"):.4f} − {v("a_" + X, "in"):.4f}/2)'],
    'M_r': lambda v, X, t: [f'= φ·M<tspan baseline-shift="sub" font-size="75%">n</tspan> = {v("phi_" + X):.2f} × {v("M_n_" + X):.3f} kip-ft',
                            f'demand M<tspan baseline-shift="sub" font-size="75%">u</tspan> = {v("M_u_" + X):.3f} kip-ft'],
    'S_c': lambda v, X, t: [f'= b·h²/6 = 12 × {t:g}² / 6 in³'],
    'M_cr': lambda v, X, t: ['= γ<tspan baseline-shift="sub" font-size="75%">3</tspan>·γ<tspan baseline-shift="sub" font-size="75%">1</tspan>·f<tspan baseline-shift="sub" font-size="75%">r</tspan>·S<tspan baseline-shift="sub" font-size="75%">c</tspan>',
                             f'= {v("gamma_3"):g} × {v("gamma_1"):g} × {v("f_r", "ksi"):.3f} ksi × {v("S_c_" + X, "in^3"):g} in³'],
    'rho': lambda v, X, t: [f'= A<tspan baseline-shift="sub" font-size="75%">s</tspan>/(b·d) = {v("A_s_" + X, "in^2"):.3f} / (12 × {v("d_" + X, "in"):.4f})'],
    'k': lambda v, X, t: ['= √(2ρn + (ρn)²) − ρn', f'ρ = {v("rho_" + X):.5f}, n = {v("n_m"):.3f}'],
    'j': lambda v, X, t: [f'= 1 − k/3 = 1 − {v("k_" + X):.4f}/3'],
    'f_ss': lambda v, X, t: ['= M<tspan baseline-shift="sub" font-size="75%">s</tspan> / (A<tspan baseline-shift="sub" font-size="75%">s</tspan>·j·d)',
                             f'= {v("M_s_" + X):.3f} kip-ft × 12 / ({v("A_s_" + X, "in^2"):.3f} × {v("j_" + X):.4f} × {v("d_" + X, "in"):.4f})',
                             f'limit 0.80 f<tspan baseline-shift="sub" font-size="75%">y</tspan> = {v("f_ss_lim", "ksi"):g} ksi'],
    'd_c': lambda v, X, t: [f'= h − d = {t:g} − {v("d_" + X, "in"):.4f} in'],
    'beta_s': lambda v, X, t: ['= 1 + d<tspan baseline-shift="sub" font-size="75%">c</tspan>/(0.7·(h − d<tspan baseline-shift="sub" font-size="75%">c</tspan>))',
                               f'= 1 + {v("d_c_" + X, "in"):.4f} / (0.7 × ({t:g} − {v("d_c_" + X, "in"):.4f}))'],
    'd_v': lambda v, X, t: [f'd − a/2 = {v("d_" + X, "in") - v("a_" + X, "in") / 2:.3f} in', f'0.9·d = {0.9 * v("d_" + X, "in"):.3f} in', f'0.72·h = {0.72 * t:.3f} in', ('largest governs', GREY)],
    'V_c': lambda v, X, t: ['= 0.0316·β·λ·√f′c·b<tspan baseline-shift="sub" font-size="75%">v</tspan>·d<tspan baseline-shift="sub" font-size="75%">v</tspan>',
                            f'= 0.0316 × {v("beta_v"):g} × {v("lambda_c"):g} × √{v("fc", "ksi"):g} × 12 × {v("d_v_" + X, "in"):.3f}'],
    'V_n': lambda v, X, t: [f'= min(V<tspan baseline-shift="sub" font-size="75%">c</tspan>, 0.25·f′c·b<tspan baseline-shift="sub" font-size="75%">v</tspan>·d<tspan baseline-shift="sub" font-size="75%">v</tspan>)',
                            f'= min({v("V_c_" + X):.3f}, {0.25 * v("fc", "ksi") * 12 * v("d_v_" + X, "in"):.2f}) kip'],
    'V_r': lambda v, X, t: [f'= φ<tspan baseline-shift="sub" font-size="75%">v</tspan>·V<tspan baseline-shift="sub" font-size="75%">n</tspan> = {v("phi_v"):g} × {v("V_n_" + X):.3f} kip'],
}


def strip_section(e, name):
    m = re.match(r'^(' + '|'.join(SECTION_PARTS) + r')_(FF|SF|CK)$', name)
    part, X = m.group(1), m.group(2)
    v = e.value
    if part == 'phi':
        return _phi_plot(e, name, X)
    if part == 'A_req':
        return _areq_plot(e, name, X)
    if part == 'M_min':
        low = 0 if v('M_cr_' + X) <= 1.33 * v('M_u_' + X) else 1
        return _bars(e, name, [('M_cr cracking', v('M_cr_' + X)), ('1.33 M_u', 1.33 * v('M_u_' + X)), ('φM_n provided', v('M_r_' + X))],
                     'kip-ft', 'Minimum reinforcement: φMn must reach the smaller of Mcr and 1.33·Mu.', highlight=low)
    if part == 's_cr':
        return _spacing(e, name, 's_' + X, 's_cr_' + X, 'Bar spacing vs the crack-control limit (LRFD 5.6.7)',
                        ['= 700·γ<tspan baseline-shift="sub" font-size="75%">e</tspan>/(β<tspan baseline-shift="sub" font-size="75%">s</tspan>·f<tspan baseline-shift="sub" font-size="75%">ss</tspan>) − 2·d<tspan baseline-shift="sub" font-size="75%">c</tspan>',
                         f'γe = {v("gamma_e"):g}, βs = {v("beta_s_" + X):.4f}', f'fss = {v("f_ss_" + X, "ksi"):.3f} ksi, dc = {v("d_c_" + X, "in"):.4f} in'])
    t_name, label = MEMBER[X]
    t, d, db = v(t_name, 'in'), v('d_' + X, 'in'), v('d_b_' + X, 'in')
    a, c = v('a_' + X, 'in'), v('c_' + X, 'in')
    s = Svg(f'1-ft strip section, {label}.', title=f'1-ft strip · {label} · compression face on top')
    k = 230 / max(t, 8)
    ox, oy, bw = 54, 60, 118
    th = t * k
    s.rect(ox, oy, bw, th, fill=CONC, stroke=INK)
    s.tag(ox + bw / 2, oy - 8, 'b = 12 in (not to scale)', GREY)
    if part in ('d_v', 'V_c', 'V_n', 'V_r'):
        dv = v('d_v_' + X, 'in')
        s.rect(ox, oy, bw, dv * k, fill=HL, op=0.15, stroke=HL, dash='3 2')
        s.tag(ox + bw / 2, oy + dv * k / 2, sub('b', 'v') + '·' + sub('d', 'v'), HL)
    count = max(1, int(round(12 / v('s_' + X, 'in'))))
    for i in range(count):
        s.circle(ox + bw * (i + 0.5) / count, oy + d * k, db * k / 2 + 1.5, fill=HL if part in ('A_s', 'rho') else INK)
    s.dim(ox - 12, oy, ox - 12, oy + d * k, sym('d'), HL if part == 'd' else GREY, side=-1)
    s.dim(ox + bw + 10, oy, ox + bw + 10, oy + th, 'h', GREY)
    if part in ('d_c', 'beta_s'):
        dc = v('d_c_' + X, 'in')
        s.dim(ox + bw + 30, oy + th - dc * k, ox + bw + 30, oy + th, sym('d_c'), HL)
    sx = ox + bw + 92
    if part in ('S_c', 'M_cr'):
        s.line(sx, oy, sx, oy + th, INK)
        s.poly([(sx, oy), (sx - 46, oy), (sx + 46, oy + th), (sx, oy + th)], fill=AMBER, op=0.3, stroke=AMBER)
        s.tag(sx + 48, oy + th - 4, sub('f', 'r'), HL, 'start')
        s.tag(sx, oy + th + 14, 'elastic stress at cracking', GREY)
    elif part in ('rho', 'k', 'j', 'f_ss'):
        kd = v('k_' + X) * d
        s.line(sx, oy, sx, oy + th, INK)
        s.poly([(sx, oy), (sx - 44, oy), (sx, oy + kd * k)], fill=BLUE, op=0.3, stroke=BLUE)
        s.line(ox, oy + kd * k, sx + 40, oy + kd * k, BLUE, 1, '4 2')
        s.dim(sx - 58, oy, sx - 58, oy + kd * k, 'kd', HL if part == 'k' else GREY, side=-1)
        s.dim(sx + 16, oy + kd * k / 3, sx + 16, oy + d * k, 'jd', HL if part == 'j' else GREY)
        s.arrow(sx, oy + d * k, sx + 70, oy + d * k, HL if part == 'f_ss' else INK, 2.2)
        s.tag(sx + 74, oy + d * k + 4, sub('f', 'ss'), HL if part == 'f_ss' else INK, 'start')
        s.tag(sx, oy + th + 14, 'cracked elastic (service)', GREY)
    else:
        s.line(sx, oy, sx, oy + th, INK)
        lc = 60 * c / max(d - c, 1e-9)
        s.line(sx - lc, oy, sx + 60, oy + d * k, BLUE, 1.6)
        s.line(ox, oy + c * k, sx + 70, oy + c * k, BLUE, 0.9, '4 2')
        s.tag(sx - lc - 4, oy + 4, sub('ε', 'cu') + ' = 0.003', INK, 'end')
        s.tag(sx + 64, oy + d * k + 4, sub('ε', 't'), HL if part == 'eps_t' else INK, 'start')
        s.dim(sx - 76, oy, sx - 76, oy + c * k, 'c', HL if part == 'c' else GREY, side=-1)
        s.tag(sx, oy + th + 14, 'strain', GREY)
        fx = sx + 130
        s.rect(fx, oy, 42, a * k, fill=AMBER, op=0.45, stroke=AMBER)
        s.dim(fx + 50, oy, fx + 50, oy + a * k, 'a', HL if part == 'a' else GREY)
        force_color = HL if part in ('M_n', 'M_r') else INK
        s.arrow(fx + 4, oy + a * k / 2, fx - 30, oy + a * k / 2, force_color, 2)
        s.tag(fx - 33, oy + a * k / 2 + 4, 'C', force_color, 'end')
        s.arrow(fx - 30, oy + d * k, fx + 22, oy + d * k, force_color, 2)
        s.tag(fx + 26, oy + d * k + 4, 'T', force_color, 'start')
        s.dim(fx - 46, oy + a * k / 2, fx - 46, oy + d * k, 'd − a/2', force_color if part in ('M_n', 'M_r') else GREY, side=-1)
        s.tag(fx + 20, oy + th + 14, 'stress block', GREY)
    detail_rows = PART_ROWS[part](v, X, t)
    if X == 'CK' and part == 'd' and v('single_ck') == 1:
        detail_rows = ['= half web thickness − half horizontal bar diameter', f'= {t:g}/2 − {v("d_b_CKH", "in"):g}/2 in', 'Weaker direction for tangent bars in one centered mat']
    s.panel(_eq(e, name, 4 if part in ('eps_t', 'rho', 'k', 'j', 'beta_s', 'c', 'a', 'd') else 3), detail_rows,
            heading=label)
    return s


def _phi_plot(e, name, X):
    eps = e.value('eps_t_' + X)
    xs = [0.0, 0.002, 0.005, 0.008, max(0.01, eps * 1.1)]
    ys = [0.75, 0.75, 0.9, 0.9, 0.9]
    return _plot(e, name, [(xs, ys, BLUE)], 'net tensile strain εt', 'φ', [(eps, e.value(name), f'εt = {eps:.4f}')],
                 'Resistance factor vs net tensile strain (LRFD 5.5.4.2)',
                 x_range=(0, max(xs)), y_range=(0.7, 0.95), vlines=[(0.002, 'εcl'), (0.005, 'εtl')],
                 rows=['0.75 when εt ≤ 0.002 (compression controlled)', '0.90 when εt ≥ 0.005 (tension controlled)', 'linear between'])


def _areq_plot(e, name, X):
    v = e.value
    fc, fy, d, b = v('fc', 'ksi'), v('fy', 'ksi'), v('d_' + X, 'in'), 12.0
    mu, prov, req = v('M_u_' + X), v('A_s_' + X, 'in^2'), v(name, 'in^2')
    top = max(prov, req) * 1.6 + 0.05
    xs = [top * i / 40 for i in range(41)]
    ys = [0.9 * a * fy * (d - a * fy / (1.7 * fc * b)) / 12 for a in xs]
    return _plot(e, name, [(xs, ys, BLUE)], 'As per ft (in²)', 'φMn (kip-ft)',
                 [(req, mu, 'required'), (prov, v('M_r_' + X), 'provided')],
                 'Steel that makes φMn equal the factored moment', hlines=[(mu, 'Mu')],
                 rows=['solves φ·As·fy·(d − As·fy/(1.7·f′c·b)) = Mu', f'Mu = {mu:.3f} kip-ft, d = {d:.4f} in',
                       f'provided As = {prov:.3f} in²/ft'])


def _plot(e, name, series, xlabel, ylabel, points, title, x_range=None, y_range=None, hlines=(), vlines=(), rows=()):
    s = Svg(title, title=title)
    L, T, Wd, Hd = 70, 44, PX - 120, 240
    xs_all = [x for xs, _, _ in series for x in xs] + [p[0] for p in points]
    ys_all = [y for _, ys, _ in series for y in ys] + [p[1] for p in points] + [h[0] for h in hlines]
    x0, x1 = x_range or (min(xs_all), max(xs_all))
    y0, y1 = y_range or (min(0.0, min(ys_all)), max(ys_all) * 1.1 + 1e-9)
    X = lambda x: L + (x - x0) / (x1 - x0) * Wd
    Y = lambda y: T + Hd - (y - y0) / (y1 - y0) * Hd
    s.line(L, T + Hd, L + Wd, T + Hd, INK)
    s.line(L, T, L, T + Hd, INK)
    for i in range(5):
        xv, yv = x0 + (x1 - x0) * i / 4, y0 + (y1 - y0) * i / 4
        s.text(X(xv), T + Hd + 14, f'{xv:.3g}', 9, GREY)
        s.text(L - 6, Y(yv) + 3, f'{yv:.3g}', 9, GREY, 'end')
    s.text(L + Wd / 2, T + Hd + 32, escape(xlabel), 10, INK)
    s.text(20, T + Hd / 2, escape(ylabel), 10, INK, rotate=-90)
    for xs, ys, color in series:
        s.poly([(X(x), Y(y)) for x, y in zip(xs, ys)], stroke=color, sw=2, closed=False)
    for y, lab in hlines:
        s.line(L, Y(y), L + Wd, Y(y), AMBER, 1.2, '5 3')
        s.tag(L + Wd - 4, Y(y) - 5, escape(lab), AMBER, 'end')
    for x, lab in vlines:
        s.line(X(x), T, X(x), T + Hd, GREY, 0.9, '3 3')
        s.tag(X(x) + 3, T + 10, escape(lab), GREY, 'start')
    for i, (x, y, lab) in enumerate(points):
        color = HL if i == 0 else INK
        s.circle(X(x), Y(y), 5, fill=color)
        s.tag(X(x) + 8, Y(y) - 8, escape(lab), color, 'start')
    s.panel(_eq(e, name, 4), list(rows))
    return s


def _bars(e, name, items, unit, title, highlight=None, extra=()):
    s = Svg(title, height=max(200, 70 + 28 * len(items)), title=title)
    top = max([abs(x) for _, x in items] + [1e-9])
    for i, (label, x) in enumerate(items):
        y = 40 + 28 * i
        w = 170 * abs(x) / top
        color = HL if i == highlight else '#9fb3c8'
        s.text(160, y + 14, escape(label), 10, INK, 'end')
        s.rect(168, y + 3, max(w, 1), 17, fill=color, stroke='none')
        s.text(174 + w, y + 16, f'{x:.3f}', 10, color if i == highlight else INK, 'start', 'bold' if i == highlight else 'normal')
    rows = list(extra) + [(f'bars in {escape(unit)}; red = value used', GREY)]
    s.panel(_eq(e, name, 3), rows)
    return s


def _spacing(e, name, actual, limit, title, rows=()):
    v = e.value
    sa, sl = v(actual, 'in'), v(limit, 'in')
    s = Svg(title, height=220, title=title)
    span = PX - 90
    k = span / max(3 * sa, sl * 1.15, 1)
    x0, y = 40, 110
    s.line(x0, y, x0 + span, y, FAINT, 7)
    n = 0
    while n * sa * k <= span:
        s.circle(x0 + n * sa * k, y, 6, fill=INK)
        n += 1
    s.dim(x0, y - 26, x0 + sa * k, y - 26, f's = {sa:g} in', INK, side=-1)
    s.dim(x0, y + 30, x0 + min(sl * k, span), y + 30, sym(limit), HL, side=1)
    s.panel(_eq(e, name, 3), list(rows) + [f'provided s = {sa:g} in ({escape(actual)})'])
    return s


# ----------------------------------------------------------------------------- materials (relations)
def materials(e, name):
    v = e.value
    fc = v('fc', 'ksi')
    curve = [3 + i * 0.1 for i in range(71)]
    if name == 'beta_1':
        return _plot(e, name, [(curve, [min(0.85, max(0.65, 0.85 - 0.05 * (x - 4))) for x in curve], BLUE)], 'f′c (ksi)', 'β1',
                     [(fc, v(name), f'f′c = {fc:g} ksi')], 'Stress block factor β1 vs f′c (LRFD 5.6.2.2)', y_range=(0.6, 0.9),
                     rows=['= 0.85 − 0.05·(f′c − 4), between 0.65 and 0.85'])
    if name == 'E_c':
        w = v('w_cE', 'kip/ft^3')
        return _plot(e, name, [(curve, [120000 * v('K_1') * w ** 2 * x ** 0.33 for x in curve], BLUE)], 'f′c (ksi)', 'Ec (ksi)',
                     [(fc, v(name), f'f′c = {fc:g} ksi')], 'Concrete modulus vs f′c (LRFD 5.4.2.4)',
                     rows=['= 120,000·K<tspan baseline-shift="sub" font-size="75%">1</tspan>·w<tspan baseline-shift="sub" font-size="75%">c</tspan>²·f′c^0.33',
                           f'w<tspan baseline-shift="sub" font-size="75%">c</tspan> = {w:.4f} kcf, K<tspan baseline-shift="sub" font-size="75%">1</tspan> = {v("K_1"):g}'])
    if name == 'f_r':
        return _plot(e, name, [(curve, [0.24 * v('lambda_c') * math.sqrt(x) for x in curve], BLUE)], 'f′c (ksi)', 'fr (ksi)',
                     [(fc, v(name), f'f′c = {fc:g} ksi')], 'Modulus of rupture vs f′c (LRFD 5.4.2.6)', rows=['= 0.24·λ·√f′c', f'λ = {v("lambda_c"):g}'])
    if name == 'n_m':
        return _bars(e, name, [('Es steel', v('Es', 'ksi')), ('Ec concrete', v('E_c', 'ksi'))], 'ksi',
                     'Modular ratio n = Es / Ec', extra=[f'= {v("Es", "ksi"):g} / {v("E_c", "ksi"):.1f}'])
    return _bars(e, name, [('fy', v('fy', 'ksi')), ('0.80 fy limit', v(name, 'ksi'))], 'ksi', 'Service stress limit (SDG 3.10.F)',
                 highlight=1, extra=[f'= {v("fss_ratio"):g} × {v("fy", "ksi"):g} ksi'])


# ----------------------------------------------------------------------------- distribution steel, joint, cheek, cap
def distribution(e, name):
    v = e.value
    cheek = name.endswith('_ck') or name in ('A_pr_CK', 'A_pr_CKH')
    if name in ('s_max_bw', 's_ts_bw', 's_max_ck', 's_ts_ck'):
        actual = {'s_max_bw': 's_FF', 's_ts_bw': 's_HZ', 's_max_ck': 's_CK', 's_ts_ck': 's_CKH'}[name]
        t = v('t_ck' if cheek else 't_bw', 'in')
        rule = (f'= min(1.5·h, 18 in) = min({1.5 * t:g}, 18) in' if 'max' in name else f'= min(3·h, 18 in) = min({3 * t:g}, 18) in')
        title = 'Maximum primary bar spacing (LRFD 5.10.3.2)' if 'max' in name else 'Maximum shrinkage and temperature spacing (LRFD 5.10.6)'
        return _spacing(e, name, actual, name, title, [rule])
    if name in ('A_pr_FF', 'A_pr_SF', 'A_pr_HZ', 'A_pr_CK', 'A_pr_CKH'):
        tag = name[5:]
        size, sp = int(e.case['inputs']['bar_' + tag]), v('s_' + tag, 'in')
        return _bars(e, name, [(f'#{size} @ {sp:g} in provided', v(name, 'in^2/ft')), ('required S&T', v('A_ts_ck' if cheek else 'A_ts_bw', 'in^2/ft'))],
                     'in²/ft', 'Steel provided per foot of wall', highlight=0,
                     extra=[f'= A<tspan baseline-shift="sub" font-size="75%">bar</tspan> × 12 / s = {v("A_b_" + tag, "in^2"):g} × 12 / {sp:g}'])
    Hh = v('H_ck' if cheek else 'H_bw', 'ft')
    Lw = v('w_ck' if cheek else 'L_bw', 'ft')
    t = v('t_ck' if cheek else 't_bw', 'in')
    s = Svg('Shrinkage and temperature steel on the wall elevation (LRFD 5.10.6).', title=('Cheek wall' if cheek else 'Backwall') + ' elevation · distribution steel')
    f = Frame(-0.6, Lw + 0.6, -0.5, Hh + 0.4, 12, 34, PX - 40, H - 80)
    s.rect(f.X(0), f.Y(Hh), f.L(Lw), f.L(Hh), fill=CONC, stroke=INK)
    sv, sh = v('s_CK' if cheek else 's_FF', 'ft'), v('s_CKH' if cheek else 's_HZ', 'ft')
    x = sv / 2
    while x < Lw:
        s.line(f.X(x), f.Y(0), f.X(x), f.Y(Hh), BLUE, 1.1)
        x += sv
    y = sh / 2
    while y < Hh:
        s.line(f.X(0), f.Y(y), f.X(Lw), f.Y(y), TEAL, 1.1)
        y += sh
    least = 'height' if Hh <= Lw else 'length'
    s.dim(f.X(Lw) + 10, f.Y(0), f.X(Lw) + 10, f.Y(Hh), f'{Hh:.3f} ft', HL if least == 'height' else GREY)
    s.dim(f.X(0), f.Y(0) + 14, f.X(Lw), f.Y(0) + 14, f'{Lw:.3f} ft', HL if least == 'length' else GREY, side=1)
    b_in = min(Hh, Lw) * 12
    raw = 1.3 * b_in * t / (2 * (b_in + t) * v('fy', 'ksi'))
    rows = ([f'b = least width = {least} = {b_in:.1f} in'] if name.startswith('b_ts') else
            ['= 1.30·b·h / (2·(b + h)·f<tspan baseline-shift="sub" font-size="75%">y</tspan>)', f'= 1.30 × {b_in:.1f} × {t:g} / (2 × ({b_in:.1f} + {t:g}) × {v("fy", "ksi"):g})',
             f'= {raw:.4f} in²/ft → limited to 0.11–0.60'])
    if cheek and name == 'A_ts_ck' and v('single_ck') == 1:
        rows += ['Single mat: combine both face requirements.',
                 f'= 2 × {min(max(raw, .11), .60):.3f} = {v(name, "in^2/ft"):.3f} in²/ft']
    s.panel(_eq(e, name, 3), rows)
    return s


def joint(e, name):
    v = e.value
    cheek = name.endswith('_ck')
    tag = 'ck' if cheek else 'bw'
    if name in ('V_ni_bw', 'V_ni_ck', 'V_ri_bw', 'V_ri_ck'):
        acv, avf = v('A_cv_' + tag, 'in^2'), v('A_s_CK' if cheek else 'A_vf_bw', 'in^2')
        items = [('c·Acv + μ·Avf·fy', v('c_if', 'ksi') * acv + v('mu_if') * avf * v('fy', 'ksi')),
                 ('K1·f′c·Acv', v('K1_if') * v('fc', 'ksi') * acv), ('K2·Acv', v('K2_if', 'ksi') * acv)]
        low = min(range(3), key=lambda i: items[i][1])
        extra = [f'Acv = {acv:.2f} in², Avf = {avf:.3f} in²', f'c = {v("c_if", "ksi"):g} ksi, μ = {v("mu_if"):g}, Pc = 0']
        if name.startswith('V_ri'):
            extra.append(f'× φ = {v("phi_v"):g}')
        return _bars(e, name, items, 'kip', 'Interface shear: least of the three LRFD 5.7.4.3 limits', highlight=low, extra=extra)
    if name == 'V_r_bw':
        return _bars(e, name, [('φVn fill-face strip', v('V_r_FF')), ('φVn span-face strip', v('V_r_SF'))], 'kip',
                     'Backwall shear resistance: weaker strip governs', highlight=0 if v('V_r_FF') <= v('V_r_SF') else 1)
    t = v('t_ck' if cheek else 't_bw', 'in')
    dv = v('d_v_CK' if cheek else 'd_v_FF', 'in')
    cover = v('cv_ck' if cheek else 'cv_bw', 'in')
    s = Svg('Construction joint at the cap top: interface area and reinforcement crossing it (LRFD 5.7.4).',
            title=('Cheek wall' if cheek else 'Backwall') + ' construction joint at the cap top')
    k = 16.0
    ox, oy = 120, 60
    s.rect(ox, oy, t * k, 190, fill=CONC, stroke=INK)
    s.rect(ox - 50, oy + 190, t * k + 100, 60, fill='#eef2f5', stroke=FAINT)
    s.line(ox - 50, oy + 190, ox + t * k + 50, oy + 190, GREY, 1, '4 2')
    s.tag(ox + t * k + 54, oy + 194, 'joint', GREY, 'start')
    for x in (ox + cover * k, ox + t * k - cover * k):
        s.line(x, oy + 20, x, oy + 240, HL if name.startswith('A_vf') else BLUE, 2.6)
    if name.startswith('A_cv'):
        s.rect(ox, oy + 185, dv * k, 10, fill=HL, op=0.5, stroke=HL)
        s.dim(ox, oy + 170, ox + dv * k, oy + 170, sub('d', 'v'), HL, side=-1)
    s.arrow(ox + t * k + 44, oy + 180, ox + t * k + 2, oy + 180, AMBER, 2.4)
    s.tag(ox + t * k + 48, oy + 176, sub('V', 'u'), AMBER, 'start')
    rows = {'A_cv': [f'= d<tspan baseline-shift="sub" font-size="75%">v</tspan> × 12 in = {dv:.3f} × 12', ('template basis: dv strip (conservative)', GREY)],
            'A_vf': [f'= min(A<tspan baseline-shift="sub" font-size="75%">s,fill</tspan>, A<tspan baseline-shift="sub" font-size="75%">s,span</tspan>) per ft', ('one face counted', GREY)],
            'A_vfmin': ['= 0.05·A<tspan baseline-shift="sub" font-size="75%">cv</tspan> / f<tspan baseline-shift="sub" font-size="75%">y</tspan>',
                        f'= 0.05 × {v("A_cv_" + tag, "in^2"):.2f} / {v("fy", "ksi"):g}']}[name.split('_' + tag)[0]]
    rows += [('clean joint, not intentionally roughened (SDG 1.15)', GREY)]
    s.panel(_eq(e, name, 3), rows)
    return s


def cheek(e, name):
    v = e.value
    if name in ('P_Z_III', 'P_Z_SER'):
        xs = [40 + i * 2.5 for i in range(57)]
        K = v('K_Z_III' if name == 'P_Z_III' else 'K_Z_SER')
        V = v('V_III' if name == 'P_Z_III' else 'V_SER')
        return _plot(e, name, [(xs, [2.56e-6 * x ** 2 * K * v('G_w') * v('C_D') * 1000 for x in xs], BLUE)], 'wind speed V (mph)', 'P (psf)',
                     [(V, v(name, 'kip/ft^2') * 1000, f'V = {V:g} mph')], 'Wind pressure vs speed (LRFD 3.8.1.2.1)',
                     rows=['= 2.56×10⁻⁶·V²·K<tspan baseline-shift="sub" font-size="75%">z</tspan>·G·C<tspan baseline-shift="sub" font-size="75%">D</tspan>',
                           f'Kz = {K:g}, G = {v("G_w"):g}, CD = {v("C_D"):g}'])
    Hc, w = v('H_ck', 'ft'), v('w_ck', 'ft')
    s = Svg('Cheek wall loaded by transverse wind; 1-ft vertical strip cantilevered from the cap.', title='Cheek wall · transverse wind on a 1-ft strip')
    f = Frame(-0.9, w + 2.6, -0.6, Hc + 0.4, 12, 34, PX - 40, H - 50)
    s.rect(f.X(0), f.Y(Hc), f.L(w), f.L(Hc), fill=CONC, stroke=INK)
    s.rect(f.X(-0.5), f.Y(0), f.L(w + 1.0), f.L(0.5), fill='#eef2f5', stroke=FAINT)
    s.rect(f.X(w / 2 - 0.5), f.Y(Hc), f.L(1.0), f.L(Hc), fill=HL, op=0.12, stroke=HL, dash='3 2')
    s.tag(f.X(w / 2), f.Y(Hc) - 5, '1-ft strip', HL)
    for i in range(6):
        y = Hc * (i + 0.5) / 6
        s.arrow(f.X(w + 2.0), f.Y(y), f.X(w) + 2, f.Y(y), TEAL, 1.4)
    s.tag(f.X(w + 2.0), f.Y(Hc) + 2, 'wind P', TEAL, 'end')
    s.dim(f.X(-0.5), f.Y(0), f.X(-0.5), f.Y(Hc), sym('H_ck'), GREY, side=-1)
    if name == 'V_u_CK':
        s.arrow(f.X(w + 2.4), f.Y(Hc / 2), f.X(w) + 2, f.Y(Hc / 2), HL, 3)
    else:
        s.arc(f.X(w / 2), f.Y(0), 22, 150, 30, HL)
    p = v('P_Z_SER' if name == 'M_s_CK' else 'P_Z_III', 'kip/ft^2')
    rows = {'V_u_CK': ['= P·H·1 ft', f'= {p * 1000:.1f} psf × {Hc:.3f} ft'],
            'M_u_CK': ['= P·H²/2·1 ft', f'= {p * 1000:.1f} psf × {Hc:.3f}² / 2'],
            'M_s_CK': ['= P<tspan baseline-shift="sub" font-size="75%">SER</tspan>·H²/2·1 ft', f'= {p * 1000:.1f} psf × {Hc:.3f}² / 2']}[name]
    rows.append(('no retained fill (D-018)', GREY))
    s.panel(_eq(e, name, 3), rows)
    return s


def cap_section(e, name):
    v = e.value
    b, h, tb = v('b_cap', 'in'), v('h_cap', 'in'), v('t_bw', 'in')
    s = Svg('Cap cross-section: area, perimeter and backwall loads that create torsion.', title='Cap cross-section (along the bridge)')
    k = 5.6
    ox, oy = 90, 112
    s.rect(ox, oy, b * k, h * k, fill=HL if name == 'A_cp' else CONC, op=0.2 if name == 'A_cp' else 1,
           stroke=HL if name == 'p_cp' else INK, sw=3.5 if name == 'p_cp' else 1)
    s.rect(ox, oy - 44, tb * k, 44, fill=CONC, stroke=INK)
    s.tag(ox + tb * k + 5, oy - 30, 'backwall', INK, 'start')
    s.line(ox + b * k / 2, oy - 14, ox + b * k / 2, oy + h * k + 12, BLUE, 0.9, '5 3')
    s.tag(ox + b * k / 2, oy + h * k + 24, 'cap centerline', BLUE)
    s.tag(ox + 8, oy + h * k - 10, f'b × h = {b:g} × {h:g} in', INK, 'start')
    if name in ('T_cr', 'T_lim'):
        for x1, y1, x2, y2 in ((ox + 24, oy + 10, ox + b * k - 24, oy + 10), (ox + b * k - 10, oy + 24, ox + b * k - 10, oy + h * k - 24),
                               (ox + b * k - 24, oy + h * k - 10, ox + 24, oy + h * k - 10), (ox + 10, oy + h * k - 24, ox + 10, oy + 24)):
            s.arrow(x1, y1, x2, y2, HL, 1.8)
    if name in ('w_bw', 't_bw_DC', 't_bw_PL'):
        x = ox + tb * k / 2
        s.arrow(x, oy - 84, x, oy - 46, HL, 2.8)
        s.tag(x + 7, oy - 70, 'w', HL, 'start')
        if name != 'w_bw':
            s.dim(x, oy + 16, ox + b * k / 2, oy + 16, 'e', HL, side=1)
            s.arc(ox + b * k / 2, oy + h * k / 2, 44, 60, 150, HL)
    rows = {'A_cp': [f'= b × h = {b:g} × {h:g} in'], 'p_cp': [f'= 2·(b + h) = 2 × ({b:g} + {h:g}) in'],
            'T_cr': ['= 0.126·√f′c·A<tspan baseline-shift="sub" font-size="75%">cp</tspan>²/p<tspan baseline-shift="sub" font-size="75%">cp</tspan> (K = 1)',
                     f'= 0.126 × √{v("fc", "ksi"):g} × {v("A_cp", "in^2"):g}² / {v("p_cp", "in"):g}'],
            'T_lim': [f'= 0.25·φ·T<tspan baseline-shift="sub" font-size="75%">cr</tspan> = 0.25 × {v("phi_v"):g} × {v("T_cr"):.1f}', ('below this, torsion may be neglected', GREY)],
            'w_bw': [f'= t·H<tspan baseline-shift="sub" font-size="75%">avg</tspan>·w<tspan baseline-shift="sub" font-size="75%">c</tspan> = {tb:g} in × {v("H_bw_avg", "ft"):.3f} ft × {v("w_c", "kip/ft^3"):g} kcf', ('not in the FBMP model', GREY)],
            't_bw_DC': [f'= (w<tspan baseline-shift="sub" font-size="75%">bw</tspan> + w<tspan baseline-shift="sub" font-size="75%">sl,DC</tspan>)·e', f'= ({v("w_bw"):.3f} + {v("w_sl_DC"):.3f}) klf × −{b / 2 - tb / 2:g} in'],
            't_bw_PL': [f'= w<tspan baseline-shift="sub" font-size="75%">sl,PL</tspan>·e = {v("w_sl_PL"):.3f} klf × −{b / 2 - tb / 2:g} in']}[name]
    s.panel(_eq(e, name, 3), rows)
    return s


def strip_plan(e, name):
    s = Svg('Design strip: per-foot loads and steel are taken over one foot of wall length.', height=200, title='Plan of a wall: one-foot design strip')
    s.rect(30, 90, 400, 36, fill=CONC, stroke=INK)
    s.rect(200, 90, 70, 36, fill=HL, op=0.25, stroke=HL)
    s.dim(200, 140, 270, 140, sym(name), HL, side=1)
    s.panel(_eq(e, name, 0), ['loads, moments and steel are per foot of wall'])
    return s


def wall_elevation(e, name):
    v = e.value
    Hc, He, L = v('H_bw', 'ft'), v('H_bw_edge', 'ft'), v('L_bw', 'ft')
    s = Svg('Backwall conservative crown/edge envelope; local landing underside governs the actual surface.', height=300, title='Backwall front elevation between the cheek walls')
    f = Frame(-1.0, L + 1.0, -0.6, max(Hc, v('H_ck', 'ft')) + 0.4, 12, 34, PX - 40, 250)
    s.poly([(f.X(0), f.Y(0)), (f.X(L), f.Y(0)), (f.X(L), f.Y(He)), (f.X(L / 2), f.Y(Hc)), (f.X(0), f.Y(He))], fill=CONC, stroke=INK)
    for x in (-0.67, L):
        s.rect(f.X(x), f.Y(v('H_ck', 'ft')), f.L(0.67), f.L(v('H_ck', 'ft')), fill='#d3dbe2', stroke=GREY)
    avg = v('H_bw_avg', 'ft')
    s.line(f.X(0), f.Y(avg), f.X(L), f.Y(avg), HL, 1.8, '6 3')
    s.tag(f.X(L * 0.25), f.Y(avg) - 6, sym('H_bw_avg'), HL)
    s.dim(f.X(L / 2) + 8, f.Y(0), f.X(L / 2) + 8, f.Y(Hc), 'crown', GREY)
    s.dim(f.X(L) - 8, f.Y(0), f.X(L) - 8, f.Y(He), 'edge', GREY, side=-1)
    s.panel(_eq(e, name, 4), [f'= native volume / (thickness × length) = {v("V_bw", "ft^3"):.4f} / ({v("t_bw", "ft"):g} × {L:.3f}) ft' if v('V_bw', 'ft^3') > 0 else f'= (crown + edge)/2 = ({Hc:.4f} + {He:.4f})/2 ft', f'L<tspan baseline-shift="sub" font-size="75%">bw</tspan> = {L:.3f} ft between cheek walls'])
    return s


# ----------------------------------------------------------------------------- plain-language meaning
PART_MEANING = {
    'd': 'Effective depth: compression face to the centroid of the tension bars in a 1-ft strip.',
    'A_s': 'Tension steel in one foot of wall: bar area × 12 in / spacing.',
    'a': 'Depth of the equivalent rectangular stress block, from the force balance 0.85·f′c·a·b = As·fy.',
    'c': 'Neutral axis depth at nominal strength: stress block depth divided by β1.',
    'eps_t': 'Net tensile strain in the tension steel at nominal strength (strain compatibility with 0.003 at the compression face).',
    'phi': 'Flexural resistance factor set by the net tensile strain (0.90 when tension controlled).',
    'M_n': 'Nominal moment strength: steel force As·fy times the lever arm d − a/2.',
    'M_r': 'Factored flexural resistance φ·Mn, compared with the factored moment.',
    'A_req': 'Steel area per foot that makes φ·Mn exactly equal to the factored moment.',
    'S_c': 'Elastic section modulus of the uncracked 1-ft strip.',
    'M_cr': 'Moment that cracks the strip (minimum-reinforcement benchmark).',
    'M_min': 'Minimum flexural resistance the steel must provide: the smaller of Mcr and 1.33·Mu.',
    'rho': 'Reinforcement ratio As / (b·d) used for the cracked elastic section.',
    'k': 'Cracked elastic neutral axis as a fraction of d (transformed section, modular ratio n).',
    'j': 'Lever arm of the cracked elastic section as a fraction of d.',
    'f_ss': 'Service I tensile stress in the reinforcement: Ms / (As·j·d).',
    'd_c': 'Concrete cover measured to the center of the tension bar (crack-control dc).',
    'beta_s': 'Ratio of the strain at the tension face to the strain at the steel (crack control).',
    's_cr': 'Largest bar spacing permitted by crack control at the service stress.',
    'd_v': 'Effective shear depth: the largest of d − a/2, 0.9·d and 0.72·h.',
    'V_c': 'Concrete shear resistance of the 1-ft strip with β = 2.0 (no shear reinforcement).',
    'V_n': 'Nominal shear resistance, capped at 0.25·f′c·bv·dv.',
    'V_r': 'Factored shear resistance φ·Vn, compared with the factored shear.',
    'H': 'Sum of the factored horizontal forces pushing the end bent toward the span.',
    'M': 'Factored overturning moment about the pile top (pinned single pile row), including the pile-tolerance arms.',
    'e': 'Height of the horizontal resultant above the pile top, e = M / H; a strap at this height needs no pile help.',
    'F_eq': 'Strap force that balances the overturning moment with pinned piles: M / y_strap.',
    'F_str': 'Design tie-back force for the whole end bent: the larger of H and M / y_strap.',
    'f_str': 'Design tie-back force per foot of backwall, the value reported on the plans (SDM 12.3.F).',
    'V_pile': 'Horizontal force the piles must supply at the pile top so the free body balances (positive toward the span).',
    'M_sl': 'Backwall joint moment with the strap slack: soil pressure bends the wall toward the span (fill-face tension).',
    'V_sl': 'Backwall joint shear with the strap slack: the factored soil force on a 1-ft strip.',
    'M_en': 'Backwall joint moment with the strap engaged: the strap pull exceeds the soil moment (span-face tension).',
    'V_en': 'Backwall joint shear with the strap engaged: strap pull less the soil force on a 1-ft strip.',
}
NAME_MEANING = {
    'b_s': 'Width of the design strip: one foot of wall.',
    'H_bw_avg': 'Average backwall height between the crown and the cheek walls, used for the backwall weight.',
    'Gamma_c': 'Coulomb geometry term Γ that combines the soil friction, wall friction, back-face and backfill angles.',
    'k_a': 'Active earth pressure coefficient: lateral soil pressure = k_a × vertical stress.',
    'p_EH': 'Active earth pressure at the cap soffit, the bottom of the retained height.',
    'F_EH': 'Earth pressure resultant over the full retained height and the cap length.',
    'y_EH': 'Height of the earth pressure resultant above the pile top (one third of the retained height above the soffit).',
    'p_LS': 'Lateral pressure from the 90 psf pedestrian surcharge, constant over the height.',
    'F_LS': 'Pedestrian surcharge resultant over the retained height and cap length.',
    'y_LS': 'Height of the surcharge resultant above the pile top (mid-height of the retained face).',
    'q_ES': 'Landing slab self-weight resting on the fill, treated as a uniform earth surcharge.',
    'p_ES': 'Lateral pressure from the landing slab surcharge, constant over the height.',
    'F_ES': 'Landing slab surcharge resultant over the retained height and cap length.',
    'y_ES': 'Height of the slab surcharge resultant above the pile top.',
    'A_pad': 'Plan area of one Type F bearing pad.',
    'h_rt': 'Total elastomer thickness that shears (steel shims excluded).',
    'K_pad': 'Horizontal shear stiffness of one pad, using the upper-bound shear modulus.',
    'Delta_TU': 'Shortening at the end bent from the temperature fall over the expansion length.',
    'F_TU': 'Pad shear force from the temperature fall, all bearings, pulling the cap toward the span.',
    'Delta_SH': 'Shortening at the end bent from beam shrinkage over the expansion length.',
    'F_SH': 'Pad shear force from beam shrinkage, all bearings, pulling the cap toward the span.',
    'f_str_u': 'Factored tie-back load per foot of backwall for the plans: the largest strength combination.',
    'f_str_s': 'Service tie-back load per foot of backwall for the plans (Service I).',
    'F_str_u': 'Factored tie-back force for the whole backwall.',
    'F_str_s': 'Service tie-back force for the whole backwall.',
    'V_EH_bw': 'Earth pressure resultant on a 1-ft backwall strip above the construction joint.',
    'M_EH_bw': 'Earth pressure moment at the backwall construction joint, 1-ft strip.',
    'V_LS_bw': 'Pedestrian surcharge resultant on a 1-ft backwall strip.',
    'M_LS_bw': 'Pedestrian surcharge moment at the backwall construction joint, 1-ft strip.',
    'V_ES_bw': 'Landing slab surcharge resultant on a 1-ft backwall strip.',
    'M_ES_bw': 'Landing slab surcharge moment at the backwall construction joint, 1-ft strip.',
    'M_u_FF': 'Design moment for the fill-face steel: the largest strap-slack joint moment.',
    'M_s_FF': 'Service I moment for fill-face crack control.',
    'M_u_SF': 'Design moment for the span-face steel: the largest strap-engaged joint moment.',
    'M_s_SF': 'Service I moment for span-face crack control.',
    'V_u_bw': 'Design shear at the backwall joint: the largest of both strap states.',
    'beta_1': 'Ratio of stress block depth to neutral axis depth for this concrete strength.',
    'E_c': 'Concrete modulus of elasticity from unit weight and strength.',
    'n_m': 'Modular ratio that converts steel area to equivalent concrete area.',
    'f_r': 'Concrete tensile stress at cracking (modulus of rupture).',
    'f_ss_lim': 'Upper limit on the service steel stress (SDG 3.10.F).',
    'V_r_bw': 'Backwall shear resistance: the weaker of the two strip sections.',
    's_max_bw': 'Largest spacing allowed for the backwall primary bars.',
    'b_ts_bw': 'Least width of the backwall used in the shrinkage and temperature formula.',
    'A_ts_bw': 'Shrinkage and temperature steel required on each backwall face.',
    's_ts_bw': 'Largest spacing allowed for backwall shrinkage and temperature bars.',
    'A_pr_FF': 'Vertical steel provided per foot on the fill face.',
    'A_pr_SF': 'Vertical steel provided per foot on the span face.',
    'A_pr_HZ': 'Horizontal steel provided per foot on each backwall face.',
    'A_cv_bw': 'Concrete area engaged in shear transfer across the backwall construction joint (1-ft strip).',
    'A_vf_bw': 'Reinforcement crossing the backwall joint counted for shear friction (one face).',
    'V_ni_bw': 'Nominal shear-friction resistance of the backwall joint: least of the three LRFD limits.',
    'V_ri_bw': 'Factored shear-friction resistance of the backwall joint.',
    'A_vfmin_bw': 'Minimum reinforcement that must cross the backwall joint.',
    'P_Z_III': 'Strength III design wind pressure on the cheek walls.',
    'P_Z_SER': 'Service I wind pressure on the cheek walls.',
    'V_u_CK': 'Factored wind shear at the base of a 1-ft cheek-wall strip.',
    'M_u_CK': 'Factored wind moment at the base of a 1-ft cheek-wall strip.',
    'M_s_CK': 'Service I wind moment at the base of a 1-ft cheek-wall strip.',
    's_max_ck': 'Largest spacing allowed for the cheek-wall primary bars.',
    'b_ts_ck': 'Least width of the cheek wall used in the shrinkage and temperature formula.',
    'A_ts_ck': 'Shrinkage and temperature steel required in each direction; both face requirements are combined for the single mat.',
    's_ts_ck': 'Largest spacing allowed for cheek-wall shrinkage and temperature bars.',
    'A_pr_CK': 'Vertical steel provided per foot in the cheek mat.',
    'A_pr_CKH': 'Horizontal steel provided per foot in the cheek mat.',
    'A_cv_ck': 'Concrete area engaged in shear transfer across the cheek-wall joint (1-ft strip).',
    'V_ni_ck': 'Nominal shear-friction resistance of the cheek-wall joint.',
    'V_ri_ck': 'Factored shear-friction resistance of the cheek-wall joint.',
    'A_vfmin_ck': 'Minimum reinforcement that must cross the cheek-wall joint.',
    'A_cp': 'Gross area enclosed by the cap cross-section (torsion).',
    'p_cp': 'Outside perimeter of the cap cross-section (torsion).',
    'T_cr': 'Torque that cracks the cap section.',
    'T_lim': 'Torsion threshold: below this factored torque, torsion may be neglected.',
    'w_bw': 'Backwall self-weight per foot of cap, a load not in the FBMP model.',
    't_bw_DC': 'Dead-load torque per foot on the cap from the backwall and landing slab acting behind the cap centerline.',
    't_bw_PL': 'Pedestrian-load torque per foot on the cap from the landing slab reaction on the backwall.',
}
NAME_MEANING.update(SECTION_TEXT)
NAME_MEANING['cover_ck_actual'] = 'Minimum physical cover to the combined envelope of tangent vertical and horizontal bars in the centered cheek mat.'


def meaning(name):
    """One plain-language sentence saying what the equation represents."""
    if name in NAME_MEANING:
        return NAME_MEANING[name]
    for pattern, _ in PATTERNS:
        m = pattern.match(name)
        if m:
            part, tag = m.group(1), m.group(2)
            text = PART_MEANING[part]
            if tag in LABELS:
                return f'{text} ({LABELS[tag]})'
            return f'{text} ({MEMBER[tag][1]})'
    return None


# ----------------------------------------------------------------------------- registry
STATIC = {
    'b_s': strip_plan, 'H_bw_avg': wall_elevation, 'Gamma_c': coulomb, 'k_a': coulomb,
    'A_pad': pad, 'h_rt': pad, 'K_pad': pad, 'F_TU': pad, 'F_SH': pad, 'Delta_TU': movement, 'Delta_SH': movement,
    'beta_1': materials, 'E_c': materials, 'n_m': materials, 'f_r': materials, 'f_ss_lim': materials,
    'A_cp': cap_section, 'p_cp': cap_section, 'T_cr': cap_section, 'T_lim': cap_section, 'w_bw': cap_section,
    't_bw_DC': cap_section, 't_bw_PL': cap_section,
    'P_Z_III': cheek, 'P_Z_SER': cheek, 'V_u_CK': cheek, 'M_u_CK': cheek, 'M_s_CK': cheek,
}
STATIC.update({name: section for name in SECTION_TEXT})
STATIC.update({name: pressure for name in ('p_EH', 'F_EH', 'y_EH', 'p_LS', 'F_LS', 'y_LS', 'q_ES', 'p_ES', 'F_ES', 'y_ES')})
STATIC.update({name: envelope for name in ('f_str_u', 'f_str_s', 'F_str_u', 'F_str_s', 'M_u_FF', 'M_s_FF', 'M_u_SF', 'M_s_SF', 'V_u_bw')})
STATIC.update({name: wall_strip for name in ('V_EH_bw', 'M_EH_bw', 'V_LS_bw', 'M_LS_bw', 'V_ES_bw', 'M_ES_bw')})
STATIC.update({name: distribution for name in ('s_max_bw', 'b_ts_bw', 'A_ts_bw', 's_ts_bw', 'A_pr_FF', 'A_pr_SF', 'A_pr_HZ',
                                                's_max_ck', 'b_ts_ck', 'A_ts_ck', 's_ts_ck', 'A_pr_CK', 'A_pr_CKH')})
STATIC.update({name: joint for name in ('V_r_bw', 'A_cv_bw', 'A_vf_bw', 'V_ni_bw', 'V_ri_bw', 'A_vfmin_bw',
                                        'A_cv_ck', 'V_ni_ck', 'V_ri_ck', 'A_vfmin_ck')})
PATTERNS = [
    (re.compile(rf'^(H|M|e|F_eq|F_str|f_str|V_pile)_({KEYS})$'), free_body),
    (re.compile(rf'^(M_sl|V_sl|M_en|V_en)_({KEYS})$'), wall_strip),
    (re.compile(r'^(' + '|'.join(SECTION_PARTS) + r')_(FF|SF|CK)$'), strip_section),
]


def drawer(name):
    if name in STATIC:
        return STATIC[name]
    for pattern, fn in PATTERNS:
        if pattern.match(name):
            return fn
    return None


def schematic(e, name):
    """(svg markup, one-line description) for a formula definition, or (None, None)."""
    if name == 'cover_ck_actual':
        svg = _bars(e, name, [('required cover', e.value('cv_ck', 'in')), ('physical cover', e.value(name, 'in'))],
                    'in', 'Centered mat concrete cover', extra=['Combined vertical/horizontal bar envelope is centered in the web.'])
        return svg.render(), svg.label
    fn = drawer(name)
    if fn is None:
        return None, None
    svg = fn(e, name)
    return svg.render(), svg.label
