"""Equation images and engineering schematics for the workbook's Method tabs.

Everything is drawn with matplotlib from the live notebook model, so labels and
dimensions follow the current geometry. Vertical scales are exaggerated where
noted; the figures explain the method and are not drawings to scale.
"""
from __future__ import annotations

import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle
import numpy as np

INK = '#1f2a36'
BLUE = '#2b6cb0'
RED = '#c0392b'
GREEN = '#2f855a'
GREY = '#8a96a3'
CONCRETE = '#d9dde2'
STEEL = '#9aa5b1'
FONT = 'DejaVu Sans'
plt.rcParams.update({'font.family': FONT, 'font.size': 9, 'axes.linewidth': 0.6})


def _png(fig, dpi=170) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=dpi, bbox_inches='tight', facecolor='white', pad_inches=0.08)
    plt.close(fig)
    return buffer.getvalue()


def equation(latex: str, size: float = 13) -> bytes:
    """Render one display equation (matplotlib mathtext) to PNG bytes."""
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, f'${latex}$', fontsize=size, color=INK)
    return _png(fig, dpi=200)


def _dim(ax, x0, y0, x1, y1, text, offset=(0, 0), color=INK, fontsize=8, rotation=0):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle='<->', mutation_scale=7, lw=0.7, color=color))
    ax.text((x0 + x1) / 2 + offset[0], (y0 + y1) / 2 + offset[1], text, ha='center', va='center',
            fontsize=fontsize, color=color, rotation=rotation,
            bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.9))


def _frame(ax):
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


# ------------------------------------------------------------ schematics --
def data_flow() -> bytes:
    fig, ax = plt.subplots(figsize=(9.5, 3.0))
    _frame(ax); ax.set_xlim(0, 10); ax.set_ylim(0, 3.2)
    boxes = [
        (0.1, 1.9, 'Colab geometry notebook\nCONFIG + BridgeModel\n(geometry authority)', BLUE),
        (0.1, 0.3, 'Mathcad beam runs\nSpan 1 / Span 2\n(saved results)', GREEN),
        (3.0, 1.1, 'Inputs tab\n(generated, blue cells)', INK),
        (5.4, 1.9, 'Calculation tabs\nProfile, beams, haunch,\nFGE, seats, substructure', INK),
        (5.4, 0.3, 'Beam Data / Clearance\nshortening, 5K bars,\nvertical clearance', INK),
        (8.0, 1.1, 'CAD tables\nFGE, Build-Up, Beam Var.,\nBearing Plates, Pedestals', RED),
    ]
    for x, y, text, color in boxes:
        ax.add_patch(Rectangle((x, y), 1.95, 1.0, fc='white', ec=color, lw=1.3))
        ax.text(x + 0.975, y + 0.5, text, ha='center', va='center', fontsize=8, color=color)
    arrows = [((2.05, 2.4), (3.0, 1.75)), ((2.05, 0.8), (3.0, 1.45)), ((4.95, 1.75), (5.4, 2.3)),
              ((4.95, 1.45), (5.4, 0.8)), ((7.35, 2.3), (8.0, 1.75)), ((7.35, 0.8), (8.0, 1.45))]
    for a, b in arrows:
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=10, lw=1.0, color=GREY))
    ax.text(5.0, 3.12, 'scripts/build_geometry_cad_tables.py regenerates every tab; QC compares results with the notebook',
            ha='center', fontsize=8, color=GREY)
    return _png(fig)


def profile_elevation(model) -> bytes:
    fig, ax = plt.subplots(figsize=(9.5, 3.2))
    s = np.linspace(model.start, model.end, 400)
    z = model.pgl(s)
    ax.plot(s, z, color=BLUE, lw=1.6, label='PGL (profile grade line)')
    for span in model.spans.itertuples():
        for x in (span.start_ft, span.end_ft):
            ax.axvline(x, color=GREY, lw=0.6, ls='--')
    labels = [(model.start, 'FFBW\nEnd Bent 1'), (model.peak, 'CL Pier\n(PI)'), (model.end, 'FFBW\nEnd Bent 2')]
    zmin, zmax = float(z.min()), float(z.max())
    for x, text in labels:
        ax.text(x, zmin - 0.16, f'{text}\n{_sta(x)}', ha='center', va='top', fontsize=7.5)
        ax.plot([x], [model.pgl(x)], 'o', color=INK, ms=3)
        ax.text(x, float(model.pgl(x)) + 0.03, f'EL {float(model.pgl(x)):.3f}', ha='center', va='bottom', fontsize=7.5)
    if model.profile_mode == 'brokeback':
        ax.text((model.start + model.peak) / 2, (model.z0 + model.peak_elev) / 2 + 0.06,
                f'$g_1$ = {model.g1*100:+.4f}%', ha='center', fontsize=8.5, color=BLUE)
        ax.text((model.peak + model.end) / 2, (model.z1 + model.peak_elev) / 2 + 0.06,
                f'$g_2$ = {model.g2*100:+.4f}%', ha='center', fontsize=8.5, color=BLUE)
    ax.set_ylim(zmin - 0.55, zmax + 0.2)
    ax.set_xlim(model.start - 6, model.end + 6)
    ax.set_xlabel('Station (ft)'); ax.set_ylabel('Elevation (ft)')
    ax.set_title(f'Profile: {model.profile_mode} (vertical scale exaggerated)', fontsize=9)
    ax.grid(alpha=0.25, lw=0.5)
    return _png(fig)


def _sta(value):
    hundredths = round(abs(float(value)) * 100)
    return f'{hundredths // 10000}+{(hundredths % 10000) / 100:05.2f}'


def _fib(ax, x0, y_bottom, depth=3.0, flange=4.0, color=CONCRETE):
    w = flange / 48
    pts = np.array([(-24, 36), (24, 36), (24, 32.5), (7, 31), (3.5, 27.5), (3.5, 10), (19, 7), (19, 0),
                    (-19, 0), (-19, 7), (-3.5, 10), (-3.5, 27.5), (-7, 31), (-24, 32.5)], dtype=float)
    pts[:, 0] = x0 + pts[:, 0] * w
    pts[:, 1] = y_bottom + pts[:, 1] * depth / 36
    ax.add_patch(Polygon(pts, closed=True, fc=color, ec=INK, lw=0.8))


def typical_section(model) -> bytes:
    fig, ax = plt.subplots(figsize=(9.5, 3.6))
    _frame(ax)
    exag = 8.0  # cross-slope exaggeration for legibility (thicknesses drawn true)
    left, right = model.deck_left, model.deck_right
    ys = np.array([left, 0.0, right]) if left < 0 < right else np.array([left, right])
    def deck_top(y):
        return 4.6 + model.deck_delta(np.full(np.shape(y), model.peak), y) * exag
    top = deck_top(ys)
    ax.fill(np.r_[ys, ys[::-1]], np.r_[top, top[::-1] - model.deck_thickness], fc=CONCRETE, ec=INK, lw=0.8)
    for off in model.offsets:
        edges = np.array([off - model.flange / 2, off, off + model.flange / 2])
        beam_top = float(np.min(deck_top(edges))) - model.deck_thickness - 0.12
        _fib(ax, off, beam_top - model.depth, depth=model.depth, flange=model.flange)
        ax.fill_between(edges[[0, 2]], [beam_top, beam_top], deck_top(edges[[0, 2]]) - model.deck_thickness,
                        color='#f6e4b8', lw=0)
        ax.axvline(off, color=GREY, ls='-.', lw=0.6)
        ax.text(off, -0.45, f'CL Beam\n{off:+.4f} ft', ha='center', va='top', fontsize=7.5)
    ax.axvline(0, color=BLUE, ls='--', lw=0.8)
    ax.text(0, 4.65, 'PGL / crown\n(offset 0)', ha='center', va='bottom', fontsize=7.5, color=BLUE)
    for y in (left, right):
        ax.text(y, float(deck_top(np.array([y]))[0]) + 0.12, f'deck edge\n{y:+.4f} ft', ha='center', va='bottom', fontsize=7.5)
    if model.deck_mode == 'crowned':
        slope = model.cfg['deck']['crown_slope']
        for y in (left / 2, right / 2):
            ax.text(y, float(deck_top(np.array([y]))[0]) + 0.15, f'{slope*100:.1f}%', ha='center', color=RED, fontsize=9)
    b0 = model.offsets[0]
    edges0 = np.array([b0 - model.flange / 2, b0, b0 + model.flange / 2])
    top0 = float(np.min(deck_top(edges0))) - model.deck_thickness - 0.12
    for x, lab in zip(edges0, ('L', 'CL', 'R')):
        ax.plot([x], [top0 - 0.05], marker='^', color=RED, ms=5)
        ax.text(x, top0 - 0.22, lab, ha='center', va='top', fontsize=7, color=RED)
    _dim(ax, left, -1.55, right, -1.55, f'Deck width {model.deck_width*12:.0f} in ({model.deck_width:.4f} ft)')
    if len(model.offsets) > 1:
        _dim(ax, model.offsets[0], -1.05, model.offsets[1], -1.05, f'{(model.offsets[1]-model.offsets[0]):.4f} ft')
    ax.set_xlim(left - 0.8, right + 0.8); ax.set_ylim(-1.9, 5.6)
    ax.set_title(f'Typical section looking up-station (cross slope x{exag:.0f}; haunch shaded; red = haunch check points)', fontsize=9)
    return _png(fig)


def support_details(model) -> bytes:
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.1))
    phys = model.cfg['physical_geometry']
    # End bent 1
    ax = axes[0]; _frame(ax)
    ax.add_patch(Rectangle((-1.0, -0.6), 1.0, 2.6, fc=CONCRETE, ec=INK, lw=0.8))   # backwall
    ax.text(-0.5, 2.1, 'backwall', ha='center', fontsize=7)
    ax.axvline(0, color=INK, lw=1.0)
    ax.text(0, 2.45, 'FFBW (datum)', ha='center', fontsize=7.5)
    e = phys['beam_end_clear_in'] / 12; sb = phys['bearing_setback_in'] / 12
    ax.add_patch(Rectangle((e, 0.25), 3.6, 0.9, fc='#eef1f4', ec=INK, lw=0.8))
    ax.text(e + 2.2, 0.7, 'beam (elevation)', fontsize=7.5)
    ax.add_patch(Rectangle((e + sb - 10 / 24, 0.0), 10 / 12, 0.25, fc=STEEL, ec=INK, lw=0.6))
    ax.axvline(e + sb, color=RED, ls='-.', lw=0.7)
    ax.text(e + sb, -0.15, 'CL brg', color=RED, ha='center', va='top', fontsize=7.5)
    _dim(ax, 0, 1.55, e, 1.55, f'{phys["beam_end_clear_in"]:g}"')
    _dim(ax, e, 1.85, e + sb, 1.85, f'J = {phys["bearing_setback_in"]:g}"')
    _dim(ax, 0, -0.75, e + sb, -0.75, f'K1 = {phys["beam_end_clear_in"] + phys["bearing_setback_in"]:g}"')
    ax.set_xlim(-1.2, 4.6); ax.set_ylim(-1.0, 2.7); ax.set_title('End bent (span start)', fontsize=9)
    # Pier
    ax = axes[1]; _frame(ax)
    g = phys['pier_beam_gap_in'] / 12
    ax.axvline(0, color=BLUE, lw=0.8, ls='--')
    ax.text(0, 2.45, 'CL Pier', ha='center', color=BLUE, fontsize=7.5)
    for sign in (-1, 1):
        x0 = sign * g / 2
        ax.add_patch(Rectangle((min(x0, x0 + sign * 3.0), 0.25), 3.0, 0.9, fc='#eef1f4', ec=INK, lw=0.8))
        cb = x0 + sign * sb
        ax.add_patch(Rectangle((cb - 10 / 24, 0.0), 10 / 12, 0.25, fc=STEEL, ec=INK, lw=0.6))
        ax.axvline(cb, color=RED, ls='-.', lw=0.7)
    _dim(ax, -g / 2, 1.55, g / 2, 1.55, f'gap {phys["pier_beam_gap_in"]:g}"')
    _dim(ax, g / 2, 1.85, g / 2 + sb, 1.85, f'J = {phys["bearing_setback_in"]:g}"')
    _dim(ax, 0, -0.55, g / 2 + sb, -0.55, f'K = {phys["pier_beam_gap_in"]/2 + phys["bearing_setback_in"]:g}"')
    ax.set_xlim(-3.4, 3.4); ax.set_ylim(-1.0, 2.7); ax.set_title('Pier (simple spans, open joint)', fontsize=9)
    return _png(fig)


def camber_haunch(model, span_index=1) -> bytes:
    fig, ax = plt.subplots(figsize=(9.6, 3.6))
    a, b = model.bearing_limits[span_index]
    lo, hi = model.beam_limits[span_index]
    s = np.linspace(lo, hi, 300)
    exag = 40.0
    e = model.evaluate(s, span_index)
    chord = model.pgl(a) + (model.pgl(b) - model.pgl(a)) * (s - a) / (b - a)
    ref = chord
    deck_bot = (e['deck'][:, 0, 1] - model.deck_thickness - ref) * exag
    top = (e['top'][:, 0] - ref) * exag
    bottom_chord = (chord - model.support_drop + model.depth - ref) * exag
    ax.plot(s, deck_bot, color=BLUE, lw=1.4, label='deck soffit over CL beam')
    ax.plot(s, top, color=INK, lw=1.4, label='beam top (cambered)')
    ax.plot(s, bottom_chord, color=GREY, lw=1.0, ls='--', label='beam top with zero camber (chord)')
    ax.fill_between(s, top, deck_bot, color='#f6e4b8', alpha=0.8, label='haunch / build-up')
    mid = (a + b) / 2
    for x, lab in ((a, 'Dim B\n(begin brg)'), (mid, 'Dim C\n(midspan)'), (b, 'Dim D\n(end brg)')):
        i = int(np.argmin(abs(s - x)))
        ax.annotate('', xy=(x, top[i]), xytext=(x, deck_bot[i]),
                    arrowprops=dict(arrowstyle='<->', color=RED, lw=0.9))
        ax.text(x, deck_bot[i] + 0.25, lab, ha='center', va='bottom', fontsize=7.5, color=RED)
    ax.axhline(0, color='white', lw=0)
    ax.set_xlabel('Station (ft)')
    ax.set_yticks([])
    ax.set_title(f'Span {span_index+1}: haunch = deck soffit - beam top (vertical scale x{exag:.0f} about the bearing chord)', fontsize=9)
    ax.legend(loc='lower center', fontsize=7.5, ncol=2, frameon=False)
    ax.set_ylim(min(top.min(), bottom_chord.min()) - 2.2, deck_bot.max() + 1.6)
    return _png(fig)


def fge_grid(model, span_index=0, increments=10) -> bytes:
    fig, ax = plt.subplots(figsize=(9.6, 3.2))
    _frame(ax)
    a, b = model.bearing_limits[span_index]
    sp = model.spans.iloc[span_index]
    stations = [sp.start_ft, a] + [a + k * (b - a) / increments for k in range(1, increments)] + [b, sp.end_ft]
    lines = [(model.deck_left, 'deck edge (coping)')] + [(o, f'CL Beam {span_index+1}-{i+1}') for i, o in enumerate(model.offsets)]
    lines += [(0.0, 'PGL'), (model.deck_right, 'deck edge (coping)')]
    lines.sort(key=lambda t: t[0])
    for y, label in lines:
        ax.plot([stations[0], stations[-1]], [y, y], color=BLUE if label == 'PGL' else INK,
                lw=1.1 if label != 'PGL' else 0.9, ls='--' if label == 'PGL' else '-')
        ax.text(stations[0] - 2.0, y, label, ha='right', va='center', fontsize=7.5)
    for k, x in enumerate(stations):
        ax.plot([x, x], [lines[0][0], lines[-1][0]], color=GREY, lw=0.5)
        name = ('Datum' if k in (0, len(stations) - 1) else 'CL brg' if k in (1, len(stations) - 2) else str(k - 1))
        ax.text(x, lines[-1][0] + 0.55, name, ha='center', va='bottom', fontsize=7, rotation=90)
        for y, _ in lines:
            ax.plot([x], [y], 'o', color=RED, ms=2.2)
    ax.set_xlim(stations[0] - 26, stations[-1] + 3)
    ax.set_ylim(lines[0][0] - 1.0, lines[-1][0] + 3.2)
    ax.set_title(f'FGE grid, Span {span_index+1} (plan): every red point is one finished-grade elevation', fontsize=9)
    return _png(fig)


def pad_chord(model) -> bytes:
    fig, ax = plt.subplots(figsize=(8.8, 3.0))
    s = np.linspace(-1.2, 1.2, 200)
    curv = 0.18
    soffit = 0.25 * s - curv * s ** 2
    ax.plot(s, soffit, color=INK, lw=1.5, label='cambered beam soffit (exaggerated)')
    L = 0.6
    z_lo, z_hi = 0.25 * -L - curv * L ** 2, 0.25 * L - curv * L ** 2
    ax.plot([-L, L], [z_lo, z_hi], color=RED, lw=1.4, label='pad-top plane (chord over pad length)')
    ax.add_patch(Rectangle((-L, z_lo - 0.36), 2 * L, 0.22, fc=STEEL, ec=INK, lw=0.6, angle=0))
    ax.plot([0, 0], [0, (z_lo + z_hi) / 2], color=BLUE, lw=0.9)
    ax.annotate('chord gap', xy=(0, (z_lo + z_hi) / 2), xytext=(0.45, 0.3), fontsize=7.5, color=BLUE,
                arrowprops=dict(arrowstyle='->', color=BLUE, lw=0.7))
    for x, lab in ((-L, '$s_{lo}$'), (0, '$s_{brg}$'), (L, '$s_{hi}$')):
        ax.axvline(x, color=GREY, lw=0.5, ls='--'); ax.text(x, -0.95, lab, ha='center', fontsize=9)
    ax.text(0, z_lo - 0.42, 'bearing pad', ha='center', va='top', fontsize=7.5)
    ax.set_ylim(-1.05, 0.55); ax.set_xticks([]); ax.set_yticks([])
    ax.legend(loc='upper left', fontsize=7.5, frameon=False)
    ax.set_title('Seat plane: the pad top chords the soffit between pad ends', fontsize=9)
    return _png(fig)


def pedestal_plan() -> bytes:
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.3))
    ax = axes[0]; _frame(ax)
    ax.add_patch(Rectangle((0, 0), 2.5, 3.5, fc=CONCRETE, ec=INK, lw=1.0))
    ax.add_patch(Rectangle((0.583, 0.5), 0.833, 2.5, fc=STEEL, ec=INK, lw=0.6))
    ax.axvline(1.0, color=RED, ls='-.', lw=0.7)
    ax.text(1.0, 3.75, 'CL brg', color=RED, ha='center', fontsize=7.5)
    ax.plot([0, 0], [-0.3, 3.8], color=INK, lw=1.6)
    ax.text(-0.12, 1.75, 'FFBW (back edge)', ha='right', va='center', rotation=90, fontsize=7.5)
    for (x, y, lab) in ((0, 0, 'A'), (2.5, 0, 'B'), (0, 3.5, 'C'), (2.5, 3.5, 'D')):
        ax.text(x + (-0.18 if x == 0 else 0.18), y + (-0.18 if y == 0 else 0.18), lab, fontsize=11, color=BLUE,
                ha='center', va='center', weight='bold')
    ax.annotate('', xy=(3.3, 1.75), xytext=(2.7, 1.75), arrowprops=dict(arrowstyle='->', lw=1))
    ax.text(3.35, 1.75, 'into span', va='center', fontsize=7.5)
    ax.text(1.25, -0.55, 'left side (beam offset -)', ha='center', fontsize=7)
    ax.text(1.25, 4.35, 'right side (beam offset +)', ha='center', fontsize=7)
    ax.set_xlim(-0.8, 4.3); ax.set_ylim(-0.9, 4.6); ax.set_aspect('equal')
    ax.set_title('End-bent pedestal plan: corners A-D', fontsize=9)
    ax = axes[1]; _frame(ax)
    ax.add_patch(Rectangle((-2, 0), 4, 3.5, fc=CONCRETE, ec=INK, lw=1.0))
    for c in (-1.25, 1.25):
        ax.add_patch(Rectangle((c - 0.417, 0.5), 0.833, 2.5, fc=STEEL, ec=INK, lw=0.6))
    ax.axvline(0, color=BLUE, ls='--', lw=0.8); ax.text(0, 3.75, 'CL Pier', color=BLUE, ha='center', fontsize=7.5)
    for (x, y, lab) in ((-2, 0, 'A'), (2, 0, 'B'), (-2, 3.5, 'C'), (2, 3.5, 'D')):
        ax.text(x + (-0.2 if x < 0 else 0.2), y + (-0.18 if y == 0 else 0.18), lab, fontsize=11, color=BLUE,
                ha='center', va='center', weight='bold')
    for x, lab in ((-0.83, 'E'), (0.83, 'F')):
        ax.plot([x, x], [0, 3.5], color=RED, lw=0.8, ls=':'); ax.text(x, -0.3, lab, color=RED, ha='center', fontsize=10, weight='bold')
    ax.text(-1.25, 3.95, 'Span 1 seat', ha='center', fontsize=7.5); ax.text(1.25, 3.95, 'Span 2 seat', ha='center', fontsize=7.5)
    ax.set_xlim(-2.8, 2.8); ax.set_ylim(-0.9, 4.6); ax.set_aspect('equal')
    ax.set_title('Pier pedestal plan: A/C, B/D outer faces; E/F pad-end break lines', fontsize=9)
    return _png(fig)


def pier_pedestal_profile(model) -> bytes:
    pier = model.pier
    ped = pier['solid_geometry']['pedestals'][0]
    fig, ax = plt.subplots(figsize=(8.8, 2.9))
    xs = np.asarray(ped['stations']); zs = np.asarray(ped['tops'])
    lo, hi = zs.min() - 0.006, zs.max() + 0.006
    ax.fill(np.r_[xs, xs[::-1]], np.r_[zs, np.full(len(xs), lo)], fc=CONCRETE, ec=INK, lw=0.8)
    ax.plot(xs, zs, 'o-', color=RED, ms=3, lw=1.2)
    for x, z, lab in zip(xs, zs, ['A/C', 'E', 'F', 'B/D']):
        ax.text(x, z - 0.0012, f'{lab}\n{z:.4f}', ha='center', va='top', fontsize=7.5)
    ax.axvline(pier['station'], color=BLUE, ls='--', lw=0.8)
    ax.text(pier['station'], hi - 0.0008, 'CL pier', color=BLUE, ha='center', va='top', fontsize=7.5)
    ax.set_ylim(lo, hi)
    ax.set_xlabel('Station (ft)'); ax.set_ylabel('Elevation (ft)')
    ax.ticklabel_format(useOffset=False)
    ax.set_title(f'Pier pedestal top along a beam line (cap top {pier["top"]:.4f} ft is below this window): '
                 'seat plane, transition E-F, seat plane', fontsize=9, pad=8)
    return _png(fig)


def cap_section(model, support) -> bytes:
    fig, ax = plt.subplots(figsize=(9.4, 3.4))
    _frame(ax)
    length = support['length']; depth = support['depth']; top = support['top']
    c = support['center']
    ax.add_patch(Rectangle((c - length / 2, top - depth), length, depth, fc=CONCRETE, ec=INK, lw=1.0))
    piles = support['pile_elevations']
    width = float(piles['Diameter (in)'].iloc[0]) / 12
    for _, row in piles.iterrows():
        x = float(row['Offset (ft)'])
        ax.add_patch(Rectangle((x - width / 2, top - depth - 2.2), width, 2.2 + support['pile_embedment_ft'],
                               fc=STEEL, ec=INK, lw=0.7, alpha=0.9))
    for _, seat in support['seats'].drop_duplicates('Beam').iterrows():
        x = seat['Offset (ft)']; w = seat['Width (in)'] / 12
        ped_top = seat['Pedestal top (ft)']
        ax.add_patch(Rectangle((x - w / 2, top), w, ped_top - top, fc='#c7ccd2', ec=INK, lw=0.7))
        ax.add_patch(Rectangle((x - 16 / 12, ped_top), 32 / 12, seat['Pad (in)'] / 12, fc=STEEL, ec=INK, lw=0.6))
        ax.text(x, ped_top + 0.35, f'pad top\n{seat["Pad top (ft)"]:.3f}', ha='center', va='bottom', fontsize=7)
    ax.text(c, top + 0.05, f'cap top {top:.4f}', ha='center', va='bottom', fontsize=7.5, color=BLUE)
    ax.text(c, top - depth - 0.1, f'cap underside {top-depth:.4f}', ha='center', va='top', fontsize=7.5)
    x0 = float(piles.iloc[0]['Offset (ft)'])
    ax.text(x0, top - depth + support['pile_embedment_ft'] + 0.12,
            f'pile cutoff {float(piles.iloc[0]["Pile cutoff (ft)"]):.4f}', ha='center', fontsize=7, color=RED)
    _dim(ax, c - length / 2, top - depth - 2.6, c + length / 2, top - depth - 2.6, f'cap length {length*12:.1f} in')
    ax.set_xlim(c - length / 2 - 1, c + length / 2 + 1); ax.set_ylim(top - depth - 3.0, top + 1.6)
    ax.set_title(f'{support["name"]}: transverse section through the cap (looking up-station)', fontsize=9)
    return _png(fig)


def stirrup_zones(zones, half_length_in, s4) -> bytes:
    fig, ax = plt.subplots(figsize=(9.6, 2.2))
    _frame(ax)
    x = zones['end_space']
    colors = ['#c0392b', '#e67e22', '#2b6cb0', '#2f855a', '#6b46c1', '#b7791f']
    segments = [('S*', zones['S*'], zones['V*']), ('Sj', zones['Sj'], zones['Vj']), ('S1', zones['S1'], zones['V1']),
                ('S2', zones['S2'], zones['V2']), ('S3', zones['S3'], zones['V3']), ('S4', s4, zones['V4'])]
    ax.plot([0, half_length_in], [0, 0], color=INK, lw=2)
    ax.plot([0, 0], [-0.3, 0.6], color=INK, lw=1.4); ax.text(0, 0.75, 'beam end', ha='center', fontsize=7)
    ax.plot([half_length_in] * 2, [-0.3, 0.6], color=BLUE, lw=1.0, ls='--'); ax.text(half_length_in, 0.75, 'midspan', ha='center', fontsize=7, color=BLUE)
    for (name, n, v), color in zip(segments, colors):
        if not n:
            continue
        ax.add_patch(Rectangle((x, -0.18), n * v, 0.36, fc=color, alpha=0.25, ec=color))
        ax.text(x + n * v / 2, 0.32, f'{name}: {n} @ {v:g}"', ha='center', fontsize=7.2, color=color)
        x += n * v
    ax.set_xlim(-10, half_length_in + 10); ax.set_ylim(-0.6, 1.0)
    ax.set_title('Bars 5K spacing zones along one half of the beam (symmetric about midspan)', fontsize=9)
    return _png(fig)


def clearance_profile(model) -> bytes:
    fig, ax = plt.subplots(figsize=(9.6, 3.0))
    s = np.linspace(model.start, model.end, 800)
    road = model.roadway(s)
    ax.plot(s, road, color=GREEN, lw=1.2, label='roadway / ground profile (Geometry Report.xml)')
    for i, (lo, hi) in enumerate(model.beam_limits):
        ss = np.linspace(lo, hi, 200)
        ax.plot(ss, model.evaluate(ss, i)['bottom'][:, 0], color=INK, lw=1.3, label='beam bottom' if i == 0 else None)
    ax.plot(s, road + model.clearance_required, color=RED, lw=0.9, ls='--', label=f'roadway + {model.clearance_required:g} ft')
    if np.isfinite(model.clearance_min):
        x = model.clearance_station
        ax.annotate(f'min {model.clearance_min:.3f} ft @ {_sta(x)}', xy=(x, float(model.roadway([x])[0]) + model.clearance_min),
                    xytext=(x - 60, float(model.roadway([x])[0]) + model.clearance_min + 3), fontsize=7.5,
                    arrowprops=dict(arrowstyle='->', lw=0.7))
    ax.set_xlabel('Station (ft)'); ax.set_ylabel('Elevation (ft)')
    ax.legend(loc='lower left', fontsize=7, frameon=False, ncol=3)
    ax.grid(alpha=0.25, lw=0.5)
    ax.set_title('Vertical clearance = beam bottom - roadway, evaluated only where a beam exists', fontsize=9)
    return _png(fig)


def beam_end_dims() -> bytes:
    fig, ax = plt.subplots(figsize=(9.0, 2.8))
    _frame(ax)
    ax.add_patch(Rectangle((0, 0.4), 6.0, 0.9, fc='#eef1f4', ec=INK, lw=0.9))
    ax.plot([-0.25, -0.25], [-0.2, 1.9], color=INK, lw=1.6); ax.text(-0.25, 2.05, 'FFBW / CL Pier', ha='center', fontsize=7.5)
    ax.axvline(0.75, color=RED, ls='-.', lw=0.7); ax.text(0.75, -0.25, 'CL brg', color=RED, ha='center', fontsize=7.5)
    _dim(ax, 0, 1.55, 0.75, 1.55, 'Dim J')
    _dim(ax, -0.25, -0.55, 0.75, -0.55, 'Dim K1 (K2 at End 2)')
    _dim(ax, 0, 0.15, 6.0, 0.15, 'Dim L (template: sloped length + R)', fontsize=7.5)
    ax.text(3.2, 0.85, 'beam along grade', ha='center', fontsize=7.5)
    ax.text(6.25, 0.85, 'End 2 ...', fontsize=7.5)
    ax.set_xlim(-1.2, 7.2); ax.set_ylim(-0.9, 2.3)
    ax.set_title('Table of Beam Variables: end-of-beam dimensions (zero skew, Angle phi = 90 deg)', fontsize=9)
    return _png(fig)
