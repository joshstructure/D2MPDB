"""Equation images and label-only schematics for the workbook's Method tabs.

These pictures carry symbols and letters only, never project values, so they
cannot drift from the workbook. Every figure that shows project geometry or
numbers is a live Excel chart (charts.py) drawn from the workbook cells.
"""
from __future__ import annotations

import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle
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


def support_details() -> bytes:
    """Beam-end, bearing and pier-joint dimensions as symbols (values are in the live table beside it)."""
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.1))
    e, sb, g = 0.45, 0.75, 0.6           # drawing proportions only (not to scale)
    ax = axes[0]; _frame(ax)
    ax.add_patch(Rectangle((-1.0, -0.6), 1.0, 2.6, fc=CONCRETE, ec=INK, lw=0.8))   # backwall
    ax.text(-0.5, 2.1, 'backwall', ha='center', fontsize=7)
    ax.axvline(0, color=INK, lw=1.0)
    ax.text(0, 2.45, 'FFBW (datum)', ha='center', fontsize=7.5)
    ax.add_patch(Rectangle((e, 0.25), 3.6, 0.9, fc='#eef1f4', ec=INK, lw=0.8))
    ax.text(e + 2.2, 0.7, 'beam (elevation)', fontsize=7.5)
    ax.add_patch(Rectangle((e + sb - 10 / 24, 0.0), 10 / 12, 0.25, fc=STEEL, ec=INK, lw=0.6))
    ax.axvline(e + sb, color=RED, ls='-.', lw=0.7)
    ax.text(e + sb, -0.15, 'CL brg', color=RED, ha='center', va='top', fontsize=7.5)
    _dim(ax, 0, 1.55, e, 1.55, '$e$')
    _dim(ax, e, 1.85, e + sb, 1.85, '$J$')
    _dim(ax, 0, -0.75, e + sb, -0.75, '$K_1 = e + J$')
    ax.set_xlim(-1.2, 4.6); ax.set_ylim(-1.0, 2.7); ax.set_title('End bent (span start)', fontsize=9)
    ax = axes[1]; _frame(ax)
    ax.axvline(0, color=BLUE, lw=0.8, ls='--')
    ax.text(0, 2.45, 'CL Pier', ha='center', color=BLUE, fontsize=7.5)
    for sign in (-1, 1):
        x0 = sign * g / 2
        ax.add_patch(Rectangle((min(x0, x0 + sign * 3.0), 0.25), 3.0, 0.9, fc='#eef1f4', ec=INK, lw=0.8))
        cb = x0 + sign * sb
        ax.add_patch(Rectangle((cb - 10 / 24, 0.0), 10 / 12, 0.25, fc=STEEL, ec=INK, lw=0.6))
        ax.axvline(cb, color=RED, ls='-.', lw=0.7)
    _dim(ax, -g / 2, 1.55, g / 2, 1.55, '$g$')
    _dim(ax, g / 2, 1.85, g / 2 + sb, 1.85, '$J$')
    _dim(ax, 0, -0.55, g / 2 + sb, -0.55, '$K = g/2 + J$')
    ax.set_xlim(-3.4, 3.4); ax.set_ylim(-1.0, 2.7); ax.set_title('Pier (simple spans, open joint)', fontsize=9)
    return _png(fig)


def pad_chord() -> bytes:
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
