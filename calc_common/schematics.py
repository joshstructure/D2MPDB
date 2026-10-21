"""'What it represents' blocks: a term diagram of every equation drawn from the current case, with the result in red.

The journal calculations are algebraic (loads, pressures, reactions, screens) rather than geometric, so the QC drawing
is the same for every equation: the terms the formula reads, each with its current value and where it comes from,
flowing into the defined quantity. The meaning text is the equation note the journal author wrote (``text.json``).
"""
from html import escape
from pier_cap.engine import parse
from .model import names_in

W, H = 760, 170
INK, GREY, HL, BLUE, AMBER, OUT = '#213649', '#8a99a6', '#c8322b', '#1f5b91', '#c77d16', '#167b75'


def meaning(spec, name):
    notes = spec.text.get('notes', {}).get(name)
    if notes:
        return notes[0] if isinstance(notes, list) else notes
    d = spec.definition(name)
    if d:
        return d.get('caption') or name
    return spec.inputs.get(name, {}).get('caption', name)


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


def schematic(spec, e, name):
    """(svg, label) for one definition: inputs (amber), calculated terms (blue) and the result (red)."""
    d = spec.definition(name)
    if d is None:
        return '', ''
    if 'function' in d:
        terms = []
    else:
        terms = [n for n in sorted(names_in(parse(d['expr']))) if n in e.units or n in spec.inputs]
    n = max(len(terms), 1)
    cols = min(n, 6)
    rows = (n + cols - 1) // cols
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
    parts.append(f'<line x1="{x0 + cols * (box_w + 8) - 8}" y1="{ry + 19}" x2="{rx - 10}" y2="{ry + 19}" stroke="{GREY}" stroke-width="1.4" marker-end="url(#arrow-{escape(name)})"/>')
    parts.append(f'<defs><marker id="arrow-{escape(name)}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
                 f'<path d="M0,0 L8,4 L0,8 z" fill="{GREY}"/></marker></defs>')
    result = e.text(name, 3) if name in e.units else str(e.engine.get(name))
    parts.append(f'<rect x="{rx}" y="{ry}" width="170" height="38" rx="4" fill="#fff" stroke="{HL}" stroke-width="1.8"/>')
    parts.append(f'<text x="{rx + 8}" y="{ry + 15}" fill="{HL}" font-weight="bold">{escape(name)}</text>')
    parts.append(f'<text x="{rx + 8}" y="{ry + 30}" fill="{HL}" font-size="10">{escape(result[:30])}</text>')
    for j, line in enumerate(_wrap(d.get('caption') or meaning(spec, name), 110)):
        parts.append(f'<text x="{x0}" y="{height - 26 + j * 14}" fill="{INK}" font-size="10.5">{escape(line)}</text>')
    parts.append('</svg>')
    label = d.get('caption') or meaning(spec, name)
    return ''.join(parts), label
