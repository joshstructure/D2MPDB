"""'What it represents' drawings for the MSE wall exclusion calculation (C015).

Two scenes drawn from the current case: the typical pile in plan with the skewed strap passing its front corner (the
front and side clear limits, the rounded layout clear and the exclusion extents), and each end bent in plan with its
four piles, the three facing walls, the exclusion envelope, the cap, and the pile-face gap that the chosen equation
measures (shortfalls shaded).
"""
import math
import re
from html import escape
from calc_common.schematics import (Svg, Frame, sym, val, eq, n, make_drawer, schematic as _schematic, meaning as _meaning,
                                    INK, GREY, FAINT, HL, BLUE, TEAL, AMBER, PURPLE, CONC, SOIL, SLAB, PX)
from .model import SPEC

WALL_NAMES = {'1': 'front wall', '2': 'left side wall', '3': 'right side wall'}


def schematic(e, name):
    return _schematic(SPEC, e, name)


def meaning(name):
    return _meaning(SPEC, name)


def _txt(e, name):
    return str(e.engine.get(name))


# ----------------------------------------------------------------------------- typical pile and strap
def typical(e, name):
    v = e.value
    half, W, clr, a = v('Half', 'in'), v('Width', 'in'), v('Clear', 'in'), math.radians(v('α', 'deg'))
    minc, lay, fext, sext, top = v('MinClear', 'in'), v('LayoutClear', 'in'), v('FrontExtent', 'in'), v('SideExtent', 'in'), v('DrawTop', 'in')
    titles = {'Half': 'Half pile width', 'MinClear': 'Front clear needed for the skewed strap to pass the pile corner', 'LayoutClear': 'Adopted front clear, rounded up',
              'FrontExtent': 'Front exclusion extent from the pile centerline', 'SideExtent': 'Side exclusion extent from the pile centerline',
              'InputsValid': 'Geometry inputs within their valid ranges', 'InputStatus': 'Geometry input validity', 'SkewStatus': 'Front strap skew against the ordinary 15° limit',
              'DrawTop': 'Drawing extent above the pile row', 'TypicalScale': 'Drawing scale of the typical box', 'PlotScale': 'Drawing scale of the plan views'}
    s = Svg(f'{name}: typical pile', title=titles.get(name, name))
    span_y = lay + 2 * half + top
    f = Frame(-sext - 10, sext + 10, -6, span_y + 4, 12, 40, PX - 40, 300)
    # back of facing (front wall) at y = 0, pile face at y = lay
    s.rect(f.X(-sext - 10), f.Y(0), f.L(2 * sext + 20), f.L(5), fill=SOIL, stroke='none')
    s.line(f.X(-sext - 10), f.Y(0), f.X(sext + 10), f.Y(0), INK, 1.6)
    s.text(f.X(sext + 9), f.Y(0) + 12, 'front wall: back of MSE facing', 8.5, GREY, 'end')
    s.rect(f.X(-half), f.Y(lay + 2 * half), f.L(2 * half), f.L(2 * half), fill=CONC, stroke=INK)
    s.text(f.X(0), f.Y(lay + half) + 4, f'{n(2 * half, 0)} in pile', 9, INK)
    # exclusion extents
    hl_f = HL if name in ('FrontExtent', 'LayoutClear', 'MinClear') else INK
    hl_s = HL if name == 'SideExtent' else INK
    s.rect(f.X(-sext), f.Y(lay + 2 * half + top), f.L(2 * sext), f.L(top + 2 * half + lay), fill='none', stroke=GREY, sw=0.8, dash='4 2')
    s.dim(f.X(sext) + 10, f.Y(0), f.X(sext) + 10, f.Y(lay), f'{sym("LayoutClear")} = {n(lay, 2)} in', HL if name == 'LayoutClear' else INK, side=1, ext=6)
    s.dim(f.X(sext) + 10, f.Y(lay), f.X(sext) + 10, f.Y(lay + half), f'{sym("Half")}', HL if name == 'Half' else INK, side=1)
    s.dim(f.X(sext) + 66, f.Y(0), f.X(sext) + 66, f.Y(lay + half), f'{sym("FrontExtent")} = {n(fext, 2)} in', hl_f, side=1)
    s.dim(f.X(0), f.Y(lay + 2 * half + top) - 10, f.X(sext), f.Y(lay + 2 * half + top) - 10, f'{sym("SideExtent")} = {n(sext, 2)} in', hl_s, side=-1)
    s.dim(f.X(-sext) - 10, f.Y(lay + 2 * half), f.X(-sext) - 10, f.Y(lay + 2 * half + top), f'{sym("DrawTop")}', HL if name == 'DrawTop' else GREY, side=-1)
    # strap from the wall in front of the pile centerline, skewed α from the normal, passing the front corner
    L = (lay + 2 * half + top) / math.cos(a)
    dx, dy = math.sin(a), math.cos(a)
    nx, ny = math.cos(a), -math.sin(a)
    pts = [(f.X(-nx * W / 2), f.Y(-ny * W / 2)), (f.X(-nx * W / 2 + dx * L), f.Y(-ny * W / 2 + dy * L)),
           (f.X(nx * W / 2 + dx * L), f.Y(ny * W / 2 + dy * L)), (f.X(nx * W / 2), f.Y(ny * W / 2))]
    s.poly(pts, fill='#dcd3e8', stroke=PURPLE, sw=1, op=0.85)
    s.tag(f.X(dx * L * 0.9) + 8, f.Y(dy * L * 0.9), f'strap {n(W, 1)} in wide, skew α = {n(v("α", "deg"), 1)}°', PURPLE, 'start')
    s.angle(f.X(0), f.Y(0), f.L(lay * 0.55), 90 - math.degrees(a), 90, PURPLE)
    s.line(f.X(0), f.Y(0), f.X(0), f.Y(lay * 0.7), GREY, 0.8, '3 2')
    # the corner it must clear at MinClear
    s.circle(f.X(half), f.Y(lay), 4, fill='none', stroke=HL, sw=1.8)
    s.line(f.X(half), f.Y(0), f.X(half), f.Y(lay), HL if name == 'MinClear' else GREY, 0.8, '3 2')
    s.tag(f.X(half) + 6, f.Y(lay) + 14, f'corner: {sym("MinClear")} = {n(minc, 2)} in', HL if name == 'MinClear' else GREY, 'start')
    rows = {'Half': [f'{eq(e, "PileSize", 0)} / 2'],
            'MinClear': [f'({sym("Half")}·cos α + {sym("Width")}/2 + {sym("Clear")}) / sin α', f'= ({n(half, 1)}·cos {n(v("α", "deg"), 0)}° + {n(W / 2, 2)} + {n(clr, 2)}) / sin {n(v("α", "deg"), 0)}°',
                         ('strap anchored in front of the pile must get past its corner', GREY)],
            'LayoutClear': [f'{eq(e, "MinClear", 3)} rounded up to {eq(e, "RoundStep", 2)}'],
            'FrontExtent': [f'{eq(e, "Half", 1)} + {eq(e, "LayoutClear", 2)}'],
            'SideExtent': [f'{eq(e, "Half", 1)} + {eq(e, "SideClear", 1)}', ('SDG 3.13.2.N.2 side-wall clear', GREY)],
            'DrawTop': [f'{eq(e, "Half", 1)} + 12 in', ('drawing extent only', GREY)],
            'TypicalScale': ['2.25 / ((DrawTop + FrontExtent) in ft)', ('journal drawing scale only; no engineering effect', GREY)],
            'PlotScale': ['Min(6 / plan width, 2.5 / plan height) in ft', ('journal drawing scale only; no engineering effect', GREY)],
            'InputsValid': [f'pile {val(e, "PileSize", 0)} > 0, spacing {val(e, "PileSpacing", 0)} > pile', f'count = {n(v("PileCount"), 0)}, 0° &lt; α = {n(v("α", "deg"), 0)}° &lt; 90°',
                            f'width, clear, side clear, step ≥ 0'],
            'InputStatus': [f'InputsValid = {_txt(e, "InputsValid")}'],
            'SkewStatus': [f'0° &lt; α = {n(v("α", "deg"), 1)}° ≤ 15°']}
    if name in ('InputsValid', 'InputStatus', 'SkewStatus'):
        s.panel(f'{sym(name)}', [(escape(_txt(e, name)), HL if 'INVALID' in _txt(e, name) or 'Above' in _txt(e, name) else TEAL)] + rows.get(name, []))
        s.status(PX, 170, _txt(e, name))
    else:
        s.panel(eq(e, name, 3), rows.get(name, []))
    return s


# ----------------------------------------------------------------------------- end bent plans
def _walls(e, bent):
    v = e.value
    walls = {}
    for w in ('1', '2', '3'):
        p = f'Bent{bent}W{w}'
        walls[w] = dict(x=v(p + 'x', 'ft'), y=v(p + 'y', 'ft'), tx=v(p + 'tx'), ty=v(p + 'ty'), nx=v(p + 'nx'), ny=v(p + 'ny'), len=v(p + 'len', 'ft'))
    return walls


def _piles(e, bent):
    v = e.value
    return [(v(f'Bent{bent}P{i}x', 'ft'), v(f'Bent{bent}P{i}y', 'ft')) for i in (1, 2, 3, 4)]


def _plan(s, e, bent, left, top, width, height, hl_wall=None, hl_pile=None, show_cap=False, show_env=False, gaps=False):
    v = e.value
    half = v('Half', 'ft')
    walls, piles = _walls(e, bent), _piles(e, bent)
    xs = [p[0] for p in piles]
    ymin = min(walls['1']['y'], min(p[1] for p in piles)) - 1.5
    ymax = max(p[1] for p in piles) + 6.5
    f = Frame(min(xs) - 5, max(xs) + 5, ymin, ymax, left, top, width, height)
    # walls (clipped to the frame), inward normal ticks
    for w, d in walls.items():
        x0, y0 = d['x'], d['y']
        x1, y1 = x0 + d['tx'] * d['len'], y0 + d['ty'] * d['len']
        xlo, xhi = min(xs) - 5, max(xs) + 5
        clip = lambda x, y: (min(max(x, xlo), xhi), min(max(y, ymin), ymax))
        (x0c, y0c), (x1c, y1c) = clip(x0, y0), clip(x1, y1)
        color = HL if w == hl_wall else INK
        s.line(f.X(x0c), f.Y(y0c), f.X(x1c), f.Y(y1c), color, 3.2 if w == hl_wall else 2.4)
        mx, my = (x0c + x1c) / 2, (y0c + y1c) / 2
        s.arrow(f.X(mx), f.Y(my), f.X(mx + d['nx'] * 0.8), f.Y(my + d['ny'] * 0.8), color, 1, 5)
        if (x0c, y0c) != (x0, y0) or (x1c, y1c) != (x1, y1):
            yc = y1c if (x1c, y1c) != (x1, y1) else y0c
            s.text(f.X(x1c) + (8 if d['nx'] > 0 else -8), f.Y(yc) + (12 if yc == ymax else -4), f'W{w} continues: {n(d["len"], 1)} ft long', 8, GREY, 'start' if d['nx'] > 0 else 'end')
        if w == '1':
            s.tag(f.X(mx), f.Y(my) - 8, f'W{w} {WALL_NAMES[w]}', color)
        else:
            s.tag(f.X(x0) + (-9 if w == '2' else 13), f.Y(my), f'W{w} {WALL_NAMES[w]}', color, 'middle', 9, rotate=-90)
    # cap and exclusion envelope
    if show_cap:
        cx, cy = v('CapX', 'ft'), v('CapY', 'ft')
        s.rect(f.X(-cx), f.Y(cy), f.L(2 * cx), f.L(2 * cy), fill=CONC, stroke=HL if show_cap == 'hl' else INK, sw=1.2, op=0.6)
        s.text(f.X(0), f.Y(cy) - 5, f'cap {n(2 * cx, 2)} × {n(2 * cy, 2)} ft', 8.5, GREY)
    if show_env:
        p = f'Bent{bent}'
        s.rect(f.X(v(p + 'Left', 'ft')), f.Y(v(p + 'Top', 'ft')), f.L(v(p + 'TotalX', 'ft')), f.L(v(p + 'Top', 'ft') - v(p + 'Bottom', 'ft')),
               fill='#f6d6d3', stroke=HL if show_env == 'hl' else AMBER, sw=1, op=0.35, dash='5 3')
        s.text(f.X(v(p + 'Left', 'ft')) + 4, f.Y(v(p + 'Top', 'ft')) + 11, 'exclusion envelope', 8.5, AMBER, 'start')
    # piles
    for i, (px, py) in enumerate(piles, 1):
        hit = i == hl_pile
        s.rect(f.X(px - half), f.Y(py + half), f.L(2 * half), f.L(2 * half), fill='#f6d6d3' if hit else CONC, stroke=HL if hit else INK, sw=1.6 if hit else 0.9)
        s.text(f.X(px), f.Y(py) + 3.5, f'P{i}', 8.5, HL if hit else INK, 'middle', 'bold' if hit else 'normal')
    # gaps from the highlighted pile (or every pile) to the highlighted wall
    if gaps and hl_wall:
        d = walls[hl_wall]
        for i, (px, py) in enumerate(piles, 1):
            if hl_pile and i != hl_pile:
                continue
            dist = (px - d['x']) * d['nx'] + (py - d['y']) * d['ny']
            gap = dist - half
            fx, fy = px - d['nx'] * half, py - d['ny'] * half          # pile face point
            wx, wy = px - d['nx'] * dist, py - d['ny'] * dist          # foot on the wall
            s.dim(f.X(fx), f.Y(fy), f.X(wx), f.Y(wy), f'{n(gap * 12, 2)} in' if hl_pile or i in (1, 4) else '', HL, side=1 if hl_wall != '3' else -1)
    return f


def _parse(name):
    m = re.match(r'^Bent([12])(?:Wall(\d)Pile(\d)(Face|Extra)|W(\d)(Gap|Extra|Status|xend|yend)|(CapGap|CapStatus|Left|Right|Bottom|Top|TotalX)|P(\d)([xy]))$', name)
    if m:
        bent = m.group(1)
        if m.group(2):
            return bent, m.group(2), int(m.group(3)), m.group(4)
        if m.group(5):
            return bent, m.group(5), None, m.group(6)
        if m.group(7):
            return bent, None, None, m.group(7)
        return bent, None, int(m.group(8)), 'P' + m.group(9)
    m = re.match(r'^DC_B([12])_(front|left|right|cap)$', name)
    if m:
        return m.group(1), {'front': '1', 'left': '2', 'right': '3', 'cap': None}[m.group(2)], None, 'DC_' + m.group(2)
    return None


def bent(e, name):
    v = e.value
    bent_no, wall, pile, kind = _parse(name)
    wn = WALL_NAMES.get(wall, '')
    titles = {'Face': f'End Bent {bent_no}: pile P{pile} face to the {wn}', 'Extra': (f'End Bent {bent_no}: shortfall of pile P{pile} at the {wn}' if pile else f'End Bent {bent_no}: extra setback the {wn} needs'),
              'Gap': f'End Bent {bent_no}: smallest pile-face gap to the {wn}', 'Status': f'End Bent {bent_no}: {wn} result', 'xend': f'End Bent {bent_no}: end of the {wn}',
              'yend': f'End Bent {bent_no}: end of the {wn}', 'CapGap': f'End Bent {bent_no}: front cap face to the back of facing', 'CapStatus': f'End Bent {bent_no}: front cap setback (24 in minimum)',
              'Left': f'End Bent {bent_no}: exclusion envelope, left edge', 'Right': f'End Bent {bent_no}: exclusion envelope, right edge', 'Bottom': f'End Bent {bent_no}: exclusion envelope, front edge',
              'Top': f'End Bent {bent_no}: exclusion envelope, back edge', 'TotalX': f'End Bent {bent_no}: exclusion envelope width', 'Px': f'End Bent {bent_no}: pile P{pile} x coordinate',
              'Py': f'End Bent {bent_no}: pile P{pile} y coordinate', 'DC_front': f'End Bent {bent_no}: front clear required / provided', 'DC_left': f'End Bent {bent_no}: left side clear required / provided',
              'DC_right': f'End Bent {bent_no}: right side clear required / provided', 'DC_cap': f'End Bent {bent_no}: cap setback 24 in / provided'}
    s = Svg(f'{name}: End Bent {bent_no}', title=titles.get(kind, name))
    req_name = 'LayoutClear' if wall == '1' else 'SideClear'
    gap_pile = pile
    if kind in ('Gap', 'Extra', 'Status') and not pile or kind in ('DC_front', 'DC_left', 'DC_right'):
        faces = [(i, v(f'Bent{bent_no}Wall{wall}Pile{i}Face', 'in')) for i in (1, 2, 3, 4)]
        gap_pile = min(faces, key=lambda t: t[1])[0]
    f = _plan(s, e, bent_no, 12, 40, PX - 40, 290, hl_wall=wall, hl_pile=gap_pile if kind not in ('Px', 'Py') else pile,
              show_cap='hl' if kind in ('CapGap', 'CapStatus', 'DC_cap') else bool(kind in ('Left', 'Right', 'Bottom', 'Top', 'TotalX')),
              show_env='hl' if kind in ('Left', 'Right', 'Bottom', 'Top', 'TotalX') else False, gaps=kind in ('Face', 'Extra', 'Gap', 'Status', 'DC_front', 'DC_left', 'DC_right'))
    if kind in ('CapGap', 'CapStatus', 'DC_cap'):
        d = _walls(e, bent_no)['1']
        cy = v('CapY', 'ft')
        s.dim(f.X(0) + 30, f.Y(-cy), f.X(0) + 30, f.Y(d['y']), f'{sym("Bent" + bent_no + "CapGap")} = {val(e, "Bent" + bent_no + "CapGap", 2)}', HL, side=1)
    p = f'Bent{bent_no}'
    rows = []
    if kind == 'Face':
        rows = [f'(P − wall start) · inward normal − {sym("Half")}', f'required {eq(e, req_name, 2)}', ('perpendicular distance from the pile face to the back of facing', GREY)]
    elif kind == 'Extra' and pile:
        rows = [f'Max(0, {eq(e, req_name, 2)} − {eq(e, f"{p}Wall{wall}Pile{pile}Face", 2)})']
    elif kind == 'Extra':
        rows = [f'Max(0, {eq(e, req_name, 2)} − {eq(e, f"{p}W{wall}Gap", 2)})', ('setback the wall must move to clear every pile', GREY)]
    elif kind == 'Gap':
        rows = [f'Min of the four pile-face gaps', f'governing pile P{gap_pile}: {val(e, f"{p}Wall{wall}Pile{gap_pile}Face", 2)}', f'required {eq(e, req_name, 2)}']
    elif kind == 'Status':
        rows = [f'{eq(e, f"{p}W{wall}Extra", 2)} ≤ 0 → MEETS CLEAR', f'inputs {_txt(e, "InputStatus")}']
    elif kind in ('xend', 'yend'):
        rows = [f'start + tangent × {eq(e, f"{p}W{wall}len", 2)}', ('end of the wall segment taken from the CAD model', GREY)]
    elif kind == 'CapGap':
        rows = [f'wall offset − {eq(e, "CapX", 2, "ft")}·|n_x| − {eq(e, "CapY", 2, "ft")}·|n_y|', ('front cap face to the back of facing', GREY)]
    elif kind == 'CapStatus':
        rows = [f'{eq(e, p + "CapGap", 2)} ≥ 24 in']
    elif kind in ('Left', 'Right'):
        rows = [f'outer pile x {"−" if kind == "Left" else "+"} {eq(e, "SideExtent", 2)}']
    elif kind == 'Bottom':
        rows = [f'front pile y − {eq(e, "FrontExtent", 2)}']
    elif kind == 'Top':
        rows = [f'back pile y + {eq(e, "DrawTop", 2)}', ('drawing extent, not a requirement', GREY)]
    elif kind == 'TotalX':
        rows = [f'{eq(e, p + "Right", 2)} − {eq(e, p + "Left", 2)}']
    elif kind in ('Px', 'Py'):
        rows = [f'±(0.5 or 1.5) × {eq(e, "PileSpacing", 0)} along the rotated bent frame', f'FrameAngle = {val(e, "FrameAngle", 4, "deg")}']
    elif kind.startswith('DC_'):
        w = {'DC_front': '1', 'DC_left': '2', 'DC_right': '3'}.get(kind)
        rows = ([f'{eq(e, req_name, 2)} / {eq(e, f"{p}W{w}Gap", 2)}', ('1.0 is the knife edge: the facing sits exactly at the required clear', GREY)] if w
                else [f'24 in / {eq(e, p + "CapGap", 2)}'])
    text_result = kind in ('Status', 'CapStatus')
    if text_result:
        s.panel(f'{sym(name)} = {escape(_txt(e, name))}', rows)
        s.status(PX, 150, _txt(e, name))
    else:
        s.panel(eq(e, name, 3), rows)
        if kind.startswith('DC_'):
            s.gauge(PX, 150, 220, v(name), n(v(name), 3))
    return s


def cap_extent(e, name):
    v = e.value
    s = Svg(f'{name}: cap extent', title='Cap half-extent across the frame ' + ('x axis' if name == 'CapX' else 'y axis'))
    f = _plan(s, e, '1', 12, 40, PX - 40, 290, show_cap='hl')
    cx, cy = v('CapX', 'ft'), v('CapY', 'ft')
    if name == 'CapX':
        s.dim(f.X(0), f.Y(cy) - 22, f.X(cx), f.Y(cy) - 22, f'{sym("CapX")} = {n(cx * 12, 2)} in', HL, side=-1)
    else:
        s.dim(f.X(cx) + 16, f.Y(0), f.X(cx) + 16, f.Y(cy), f'{sym("CapY")} = {n(cy * 12, 2)} in', HL, side=1)
    rows = [f'({eq(e, "CapLength", 0)}·|sin θ| + {eq(e, "CapWidth", 0)}·|cos θ|) / 2' if name == 'CapX' else f'({eq(e, "CapWidth", 0)}·|sin θ| + {eq(e, "CapLength", 0)}·|cos θ|) / 2',
            f'θ = FrameAngle = {val(e, "FrameAngle", 4, "deg")}', ('the bent frame is rotated almost 90° in the CAD model', GREY)]
    s.panel(eq(e, name, 2), rows)
    return s


drawer = make_drawer({'Half': typical, 'MinClear': typical, 'LayoutClear': typical, 'FrontExtent': typical, 'SideExtent': typical, 'InputsValid': typical,
                      'InputStatus': typical, 'SkewStatus': typical, 'DrawTop': typical, 'TypicalScale': typical, 'PlotScale': typical,
                      'CapX': cap_extent, 'CapY': cap_extent},
                     [(r'^Bent[12]', bent), (r'^DC_B[12]_', bent)])
