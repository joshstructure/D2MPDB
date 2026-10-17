"""Figures for the distilled Mathcad worksheets of the three cap designs.

Two schematics per cap (End Bent 1, End Bent 2, Pier Cap), drawn from the cap
tool's evaluated case and rendered to PNG with headless Microsoft Edge:

  elevation  where the governing check stations are (S shear, N / P / B
             longitudinal tension) and how the cage is arranged along the cap
  section    the section between piles: hoop, bar layers and the effective
             depths d_N and d_B

The drawings carry symbols and short words only; every value lives in the
worksheet.  The SVG helpers are the ones used for the backwall figures
(end_bent_walls/schematics.py).

    python scripts/cap_mathcad_figures.py
"""
import json
import re
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from end_bent_walls.schematics import Svg, Frame, sym, INK, GREY, FAINT, CONC, HL, BLUE, STRAP, PAD  # noqa: E402

FIGURES = ROOT / 'cap_mathcad' / 'figures'
EDGE = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')

CAPS = [
    dict(key='end_bent_1', label='End Bent 1', case='project_current/cap_design/end_bents/selected_case.json'),
    dict(key='end_bent_2', label='End Bent 2', case='project_current/cap_design/end_bent_2/selected_case.json'),
    dict(key='pier', label='Pier Cap', case='project_current/cap_design/pier/selected_case.json'),
]

TEAL = '#167b75'               # open pile U-bars
DARK = '#5d6f80'               # dimension lines of the geometry (b, h)
PILE = '#d3dbe2'
TAG_R = 9.5                    # radius of the circled station tags
TAG_STEP = 22                  # vertical stagger between tag levels
TAG_GAP = 26                   # minimum horizontal distance (px) between tags on one level


class Fig(Svg):
    """Svg whose short labels are 12.5 px with a white halo."""

    def tag(self, x, y, markup, color=INK, anchor='middle'):
        self.items.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="12.5" fill="{color}" text-anchor="{anchor}" font-weight="bold" '
                          f'font-family="Arial, sans-serif" stroke="#ffffff" stroke-width="3.5" paint-order="stroke">{markup}</text>')

    def path(self, points, color, sw, dash=None, closed=False, fill='none'):
        """Polyline with rounded joins and caps (bars read better with round ends)."""
        pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
        tag = 'polygon' if closed else 'polyline'
        dash = f' stroke-dasharray="{dash}"' if dash else ''
        self.items.append(f'<{tag} points="{pts}" fill="{fill}" stroke="{color}" stroke-width="{sw}"{dash} '
                          f'stroke-linecap="round" stroke-linejoin="round"/>')


# ----------------------------------------------------------------------------- data
def governing_stations(e):
    """Check stations that govern: shear (S) and longitudinal tension per group (N, P, B).

    Returns a list of dict(tag, x_in, face); x_in is measured from the left cap end.
    """
    out = []
    intervals = e.lrfd.get('intervals') or []
    if intervals:
        row = max(intervals, key=lambda r: r['ratio'])
        out.append(dict(tag='S', x_in=float(row['station_in']), face=row.get('face') or 'bottom'))
    for group in 'NPB':
        rows = [r for r in e.lrfd.get('longitudinal') or [] if r['group'] == group]
        if rows:
            row = max(rows, key=lambda r: r['ratio'])
            out.append(dict(tag=group, x_in=float(row['station_in']), face=row.get('face') or ('top' if group == 'N' else 'bottom')))
    return out


def _data(e):
    """Plain numbers the two drawings need (inches, stations from the left cap end)."""
    from pier_cap.model import bar_positions, BAR_DIAMETER
    from pier_cap.transverse import scheduled_bars
    from pier_cap.detailing import hook_paths

    p = e.case['inputs']
    a = e.case['analysis']['xml_audit']
    origin = min(r['x_in'] for r in a['end_records'])
    runs = e.case['transverse_detail']['runs']
    hoop_runs = [r for r in runs if r['kind'] == 'hoop']
    hoop_bar = (hoop_runs[0] if hoop_runs else runs[0])['bar']
    section = [dict(b) for b in bar_positions(e, 'B')]
    hooks = {}
    for t in hook_paths(e, section):
        key = (round(t['left'], 3), round(t['right'], 3), round(t['bar']['y'], 3))
        hooks.setdefault(key, [(float(x), float(y)) for x, y in t['points']])
    return dict(
        b=float(p['b']), h=float(p['h']), C_t=float(p['C_t']), C_b=float(p['C_b']), C_s=float(p['C_s']),
        D_pile=float(p['D_pile']), embed=float(p['Pile_embed']), L=float(e.value('L_cap')),
        piles=[c - origin for c in a['pile_centers_in']],
        bearings=[c - origin for c in a['bearing_stations_in']],
        bars=[dict(b) for b in scheduled_bars(e.case)],
        runs=[dict(id=r['id'], kind=r['kind'], first=float(r['first_in']), end=float(r['end_in'])) for r in runs],
        longitudinal=[dict(kind=b['kind'], bar=b['bar'], d=BAR_DIAMETER[b['bar']], y=float(b['y']),
                           left=float(b['left_in']), right=float(b['right_in']), additional=bool(b['additional']))
                      for b in e.lrfd['inventory']],
        hooks=list(hooks.values()),
        section=[dict(x=float(b['x']), y=float(b['y']), d=float(b['diameter']), kind=b['kind'], additional=bool(b['additional']))
                 for b in section],
        hoop_d=BAR_DIAMETER[hoop_bar],
    )


# ----------------------------------------------------------------------------- elevation
def _stagger(xs):
    """Lowest level (0, 1, ...) for each tag so that tags on one level stay TAG_GAP apart."""
    last, levels = [], [0] * len(xs)
    for i in sorted(range(len(xs)), key=lambda i: xs[i]):
        for level, x in enumerate(last):
            if xs[i] - x >= TAG_GAP:
                last[level] = xs[i]
                levels[i] = level
                break
        else:
            last.append(xs[i])
            levels[i] = len(last) - 1
    return levels


def _legend(s, y, items, width):
    """One row of swatch + word pairs, centered on the canvas."""
    def span(text):
        return 6.6 * len(text)
    gap = 22
    swatch = {'hoop': 12, 'pile U': 12, 'longitudinal': 28, 'added bar': 26, 'bearing': 22, 'station': 14}
    total = sum(swatch[k] + 6 + span(t) for k, t in items) + gap * (len(items) - 1)
    x = (width - total) / 2
    for kind, text in items:
        w = swatch[kind]
        cx, cy = x + w / 2, y
        if kind == 'hoop':
            s.line(cx, cy - 8, cx, cy + 8, BLUE, 1.4)
        elif kind == 'pile U':
            s.line(cx, cy - 8, cx, cy + 8, TEAL, 1.6, '3 2')
        elif kind == 'longitudinal':
            s.line(x, cy, x + w, cy, INK, 2.2)
        elif kind == 'added bar':
            s.path([(x + 2, cy - 7), (x + 2, cy + 3), (x + w - 2, cy + 3), (x + w - 2, cy - 7)], HL, 3.2)
        elif kind == 'bearing':
            s.rect(cx - 10, cy - 2, 20, 5, fill=PAD, stroke=PAD)
            s.arrow(cx, cy - 12, cx, cy - 3, PAD, 1.6, 5)
        elif kind == 'station':
            s.line(cx, cy - 9, cx, cy + 9, STRAP, 1.4, '4 3')
            s.circle(cx, cy - 1, 5.5, fill='#ffffff', stroke=STRAP, sw=1.4)
        s.text(x + w + 6, cy + 4.3, escape(text), 12, INK, 'start')
        x += w + 6 + span(text) + gap


def _elevation(d, stations):
    W, MARGIN = 680, 16
    k = (W - 2 * MARGIN) / d['L']
    top_stations = [t for t in stations if t['face'] == 'top']
    bottom_stations = [t for t in stations if t['face'] != 'top']
    xs_top = [MARGIN + t['x_in'] * k for t in top_stations]
    xs_bot = [MARGIN + t['x_in'] * k for t in bottom_stations]
    lv_top, lv_bot = _stagger(xs_top), _stagger(xs_bot)
    n_top, n_bot = (max(lv_top) + 1 if lv_top else 0), (max(lv_bot) + 1 if lv_bot else 0)

    RUN_Y, BRACKET_Y, STUB = 21, 33, 46
    cap_top = 92 + TAG_STEP * max(n_top - 1, 0)
    cap_bot = cap_top + d['h'] * k
    lowest = max(cap_bot + STUB, cap_bot + 16 + TAG_STEP * max(n_bot - 1, 0) + TAG_R)
    legend_y = lowest + 30
    s = Fig('Cap elevation: governing check stations, transverse bars, longitudinal steel and added span bars.', W, round(legend_y + 20))
    f = Frame(0, d['L'], 0, d['h'], MARGIN, cap_top, W - 2 * MARGIN, d['h'] * k)
    X, Y = f.X, f.Y

    # piles: stub below the cap with a break line, embedded length dashed inside the cap
    half = d['D_pile'] / 2
    for c in d['piles']:
        x0, x1 = X(c - half), X(c + half)
        w = x1 - x0
        s.path([(x0, cap_bot), (x0, cap_bot + STUB), (x0 + w * .25, cap_bot + STUB + 4), (x0 + w * .5, cap_bot + STUB - 3),
                (x0 + w * .75, cap_bot + STUB + 4), (x1, cap_bot + STUB), (x1, cap_bot)], GREY, 1.1, closed=True, fill=PILE)
    s.rect(X(0), cap_top, X(d['L']) - X(0), cap_bot - cap_top, fill=CONC, stroke=INK, sw=1.5)
    for c in d['piles']:
        s.rect(X(c - half), Y(d['embed']), f.L(d['D_pile']), f.L(d['embed']), stroke=GREY, sw=1.1, dash='4 3')

    # transverse bars, one thin vertical line per bar at its station
    y0, y1 = Y(d['C_b'] + d['hoop_d'] / 2), Y(d['h'] - d['C_t'] - d['hoop_d'] / 2)
    for bar in d['bars']:
        if bar['kind'] == 'hoop':
            s.line(X(bar['station_in']), y0, X(bar['station_in']), y1, BLUE, 1.2)
    for bar in d['bars']:
        if bar['kind'] != 'hoop':
            s.line(X(bar['station_in']), y0, X(bar['station_in']), y1, TEAL, 1.5, '3 2')

    # continuous longitudinal steel (top and bottom rows); added span bars with upturned hooks
    seen = set()
    for bar in d['longitudinal']:
        key = (bar['kind'], round(bar['y'], 3), round(bar['left'], 3), round(bar['right'], 3))
        if bar['additional'] or bar['kind'] == 'Skin' or key in seen:
            continue
        seen.add(key)
        s.line(X(bar['left']), Y(bar['y']), X(bar['right']), Y(bar['y']), INK, 2.0)
    for pts in d['hooks']:
        s.path([(X(x), Y(y)) for x, y in pts], HL, 3.2)

    # bearings: small pad on the cap top, load arrow pointing down onto it
    for c in d['bearings']:
        x = X(c)
        s.rect(x - 11, cap_top - 5, 22, 5, fill=PAD, stroke=PAD)
        s.arrow(x, cap_top - 26, x, cap_top - 6, PAD, 2.0, 7)

    # transverse runs: bracket over the run's bars, label at its centre
    for r in d['runs']:
        color = BLUE if r['kind'] == 'hoop' else TEAL
        a, b = X(r['first']), X(r['end'])
        s.path([(a, BRACKET_Y + 5), (a, BRACKET_Y), (b, BRACKET_Y), (b, BRACKET_Y + 5)], color, 1.3)
        s.text((a + b) / 2, RUN_Y, escape(r['id']), 12.5, color, 'middle', 'bold')

    # governing stations: dashed line through the cap, circled tag at the face they are checked on
    def tag_at(x, cy, letter):
        s.circle(x, cy, TAG_R, fill='#ffffff', stroke=STRAP, sw=1.7)
        s.text(x, cy + 4.4, letter, 12.5, STRAP, 'middle', 'bold')

    for t, lv in zip(top_stations, lv_top):
        x = MARGIN + t['x_in'] * k
        cy = cap_top - 39 - TAG_STEP * lv
        s.line(x, cy, x, cap_bot + 6, STRAP, 1.5, '5 3')
        tag_at(x, cy, t['tag'])
    for t, lv in zip(bottom_stations, lv_bot):
        x = MARGIN + t['x_in'] * k
        cy = cap_bot + 16 + TAG_STEP * lv
        s.line(x, cap_top - 6, x, cy, STRAP, 1.5, '5 3')
        tag_at(x, cy, t['tag'])

    _legend(s, legend_y, [('hoop', 'hoop'), ('pile U', 'pile U'), ('longitudinal', 'longitudinal'), ('added bar', 'added bar'),
                          ('bearing', 'bearing'), ('station', 'governing station')], W)
    return s.render()


# ----------------------------------------------------------------------------- section
def _centroid_y(bars):
    area = [b['d'] ** 2 for b in bars]          # same-material bars: area scales with d squared
    return sum(a * b['y'] for a, b in zip(area, bars)) / sum(area)


def _hoop_radius(d, xa, xb, ya, yb):
    """Centerline corner radius of the drawn hoop: as generous as possible while every
    corner bar still sits inside the bend (inches)."""
    dv = d['hoop_d']

    def fits(r):
        centers = [(xa + r, ya + r), (xb - r, ya + r), (xa + r, yb - r), (xb - r, yb - r)]
        for q in d['section']:
            for cx, cy in centers:
                inside_zone = (q['x'] < xa + r if cx < (xa + xb) / 2 else q['x'] > xb - r) and \
                              (q['y'] < ya + r if cy < (ya + yb) / 2 else q['y'] > yb - r)
                if inside_zone and ((q['x'] - cx) ** 2 + (q['y'] - cy) ** 2) ** .5 + q['d'] / 2 > r - dv / 2 + 1e-6:
                    return False
        return True

    r = 2.6 * dv
    while r > 0.7 * dv and not fits(r):
        r -= 0.05 * dv
    return r


def _section(d):
    W, X0, SEC_W = 520, 112, 316
    b, h = d['b'], d['h']
    k = SEC_W / b
    TOP = 34
    bottom = TOP + h * k
    right = X0 + SEC_W
    H = round(bottom + 62)
    s = Fig('Cap cross-section between piles: hoop, bar layers and the effective depths.', W, H)
    PX = lambda x: X0 + x * k
    PY = lambda y: bottom - y * k

    top_bars = [q for q in d['section'] if q['kind'].startswith('Top')]
    bot_bars = [q for q in d['section'] if q['kind'].startswith('Bottom')]
    add_bars = [q for q in d['section'] if q['additional']]
    skin_bars = [q for q in d['section'] if q['kind'] == 'Skin']
    d_N = _centroid_y(top_bars)                           # from the bottom face to the top steel
    y_bot = _centroid_y(bot_bars + add_bars)              # from the bottom face to the bottom steel
    # (the section is between piles, where the added span bars are part of the bottom steel)

    s.text(X0, 17, 'section between piles', 12.5, GREY, 'start', 'bold')

    # concrete outline and hoop
    s.rect(X0, TOP, SEC_W, h * k, fill=CONC, stroke=INK, sw=1.6)
    dv = d['hoop_d']
    xa, xb = d['C_s'] + dv / 2, b - d['C_s'] - dv / 2          # hoop centerline, inches
    ya, yb_ = d['C_b'] + dv / 2, h - d['C_t'] - dv / 2
    hx0, hx1 = PX(xa), PX(xb)
    hy0, hy1 = PY(yb_), PY(ya)
    rr = _hoop_radius(d, xa, xb, ya, yb_) * k
    s.items.append(f'<rect x="{hx0:.1f}" y="{hy0:.1f}" width="{hx1 - hx0:.1f}" height="{hy1 - hy0:.1f}" rx="{rr:.1f}" ry="{rr:.1f}" '
                   f'fill="none" stroke="{BLUE}" stroke-width="{max(dv * k, 1.5):.1f}"/>')

    # effective-depth reference lines through the steel centroids
    for yc in (d_N, y_bot):
        s.line(PX(0) - 30, PY(yc), right + 30, PY(yc), STRAP, 0.9, '5 3')

    # bars at their diameter
    for q in d['section']:
        color = HL if q['additional'] else GREY if q['kind'] == 'Skin' else INK
        s.circle(PX(q['x']), PY(q['y']), q['d'] / 2 * k, fill=color)

    # dimensions: b below, h and d_N on the left, d_B on the right
    yb = bottom + 28
    s.line(X0, bottom + 3, X0, yb + 5, DARK, 0.8)
    s.line(right, bottom + 3, right, yb + 5, DARK, 0.8)
    s.dim(X0, yb, right, yb, sym('b'), DARK, side=1, offset=12)
    xh = 26
    s.line(X0 - 4, TOP, xh - 4, TOP, DARK, 0.8)
    s.line(X0 - 4, bottom, xh - 4, bottom, DARK, 0.8)
    s.dim(xh, TOP, xh, bottom, sym('h'), DARK, side=1)
    xn = 82
    s.dim(xn, bottom, xn, PY(d_N), sym('d_N'), STRAP, side=-1)
    xd = right + 30
    s.line(right + 4, TOP, xd + 4, TOP, DARK, 0.8)
    s.dim(xd, TOP, xd, PY(y_bot), sym('d_B'), STRAP, side=1)

    # labels with leaders into the section
    def leader(x0, y0, x1, y1, color):
        s.line(x0, y0, x1, y1, color, 1.0)
        s.circle(x0, y0, 1.8, fill=color)

    nearest_top = min(top_bars, key=lambda q: (-q['y'], abs(q['x'] - b / 2)))
    tx, ty = PX(nearest_top['x']), PY(nearest_top['y'])
    leader(tx, ty + nearest_top['d'] / 2 * k + 2, tx, ty + 24, INK)
    s.tag(tx, ty + 38, 'top steel (' + 'N' + ')', INK)

    cont = [q for q in bot_bars if not q['additional']]
    left_half = [q for q in cont if q['x'] < b / 2] or cont
    pbar = max(left_half, key=lambda q: q['x'])
    px_, py_ = PX(pbar['x']), PY(pbar['y'])
    leader(px_, py_ - pbar['d'] / 2 * k - 2, px_, py_ - 26, INK)
    s.tag(px_ - 4, py_ - 33, 'bottom steel (P)', INK, 'start')

    if add_bars:
        abar = max(add_bars, key=lambda q: q['x'])
        ax, ay = PX(abar['x']), PY(abar['y'])
        leader(ax, ay - abar['d'] / 2 * k - 2, ax, ay - 52, HL)
        s.tag(ax + 4, ay - 59, 'added span bars (B)', HL, 'end')

    if skin_bars:
        sbar = sorted([q for q in skin_bars if q['x'] < b / 2], key=lambda q: q['y'])
        sbar = sbar[len(sbar) // 2] if sbar else skin_bars[0]
        sx, sy = PX(sbar['x']), PY(sbar['y'])
        leader(sx + sbar['d'] / 2 * k + 2, sy, sx + 30, sy, GREY)
        s.tag(sx + 34, sy + 4.5, 'skin', GREY, 'start')

    hoop_y = (hy0 + hy1) / 2 + 10
    leader(hx1, hoop_y, hx1 - 34, hoop_y, BLUE)
    s.tag(hx1 - 38, hoop_y + 4.5, 'hoop', BLUE, 'end')
    return s.render()


def figures(e, stations):
    """SVG markup for the two worksheet figures of one evaluated cap."""
    d = _data(e)
    return dict(elevation=_elevation(d, stations), section=_section(d))


# ----------------------------------------------------------------------------- render
def render(svg, png_path, scale=2.5):
    """Screenshot an SVG to PNG with headless Edge (same recipe as the backwall figures)."""
    if not EDGE.exists():
        raise SystemExit('Microsoft Edge is needed to redraw the figures.')
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    w = int(re.search(r'width="(\d+)"', svg).group(1))
    h = int(re.search(r'height="(\d+)"', svg).group(1))
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / 'figure.html'
        page.write_text(f'<html><head><meta charset="utf-8"><style>body{{margin:0;background:#fff}}</style></head><body>{svg}</body></html>',
                        encoding='utf-8')
        subprocess.run([str(EDGE), '--headless=new', '--disable-gpu', '--hide-scrollbars', f'--force-device-scale-factor={scale}',
                        f'--screenshot={png_path}', f'--window-size={w},{h}', page.as_uri()],
                       capture_output=True, timeout=90, check=False)
    if not png_path.exists():
        raise RuntimeError(f'Edge did not write {png_path}')


def main():
    from pier_cap.model import evaluate
    FIGURES.mkdir(parents=True, exist_ok=True)
    for cap in CAPS:
        e = evaluate(json.loads((ROOT / cap['case']).read_text(encoding='utf-8')))
        stations = governing_stations(e)
        for name, svg in figures(e, stations).items():
            target = FIGURES / f'{cap["key"]}_{name}.png'
            render(svg, target)
            print('drew', target)


if __name__ == '__main__':
    main()
