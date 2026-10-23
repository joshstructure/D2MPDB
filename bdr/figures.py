"""SVG figures for the Bridge Development Report, drawn from the registered geometry.

The longitudinal elevation along the PGL (the A-2 and B-2 geotechnical
sections: the model's finished components cut on the PGL, the existing-ground
survey and the Pond 14D grading). A schematic record drawing, not a contract drawing (the typical
section of the report is sheet S-1 of the substructure drawings, cut from the model).
"""
from __future__ import annotations

import math
from html import escape

ROLE_FILL = {
    "deck": "#9fb8d6", "cap": "#8a9bb0", "backwall": "#8a9bb0", "pier_wall": "#8a9bb0",
    "mse": "#d9c7a0", "coping": "#c9b78c", "footing": "#b8a884", "slab": "#cfd6de",
    "barrier": "#b0b8c2", "strap": "#c0392b", "pile": "#6f7f94",
}
ROLE_NAME = {
    "deck": "Deck, beams and haunch", "cap": "Caps", "backwall": "Backwall", "pier_wall": "Pier wall",
    "mse": "MSE wall panels", "coping": "Copings and barriers", "footing": "MSE leveling pads",
    "slab": "Walking slabs and closures", "barrier": "Ramp barriers", "strap": "Soil reinforcement (schematic)",
    "pile": "Piles (projected, cut at the figure limit)",
}


def _fmt_sta(s):
    s = round(s, 2)
    h = int(s // 100)
    return f"{h}+{s - h * 100:05.2f}"


def _ftin(inches, denom=8):
    if inches is None:
        return "—"
    sign = "-" if inches < 0 else ""
    inches = abs(inches)
    ft, rem = divmod(inches, 12)
    frac = round(rem * denom) / denom
    if frac >= 12:
        ft, frac = ft + 1, 0
    whole = int(frac)
    num = int(round((frac - whole) * denom))
    s = f"{int(ft)}'-{whole}" if ft else f"{whole}"
    if num:
        from fractions import Fraction
        f = Fraction(num, denom)
        s += f" {f.numerator}/{f.denominator}"
    return s + '"' if sign == "" else sign + s + '"'


def elevation_svg(geo: dict, stations: dict, facts: dict) -> str:
    """Longitudinal elevation on the PGL from the A-2 and B-2 geotechnical sections."""
    secs = {s["id"]: s for s in geo["sections"]}
    A, B = secs["A-2"], secs["B-2"]
    x0, x1 = A["window"][0], B["window"][1]
    z0, z1 = 10.0, 60.0                     # elevation window of the figure (ft)
    W, H = 1100, 330
    ml, mr, mt, mb = 48, 20, 36, 40
    sx = (W - ml - mr) / (x1 - x0)
    sz = (H - mt - mb) / (z1 - z0)
    facts = dict(facts or {}, ve=f"{sz / sx:.1f}")
    X = lambda s: ml + (s - x0) * sx
    Y = lambda z: H - mb - (z - z0) * sz
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" class="fig" role="img" aria-label="Bridge elevation along the PGL">',
           '<style>.g{stroke:#e3e6ea;stroke-width:.8}.gt{font:10px system-ui,sans-serif;fill:#8a94a3}.t{font:11px system-ui,sans-serif;fill:#1d2430}'
           '.ti{font:italic 10.5px system-ui,sans-serif;fill:#4a5568}.eg{fill:none;stroke:#7a5c2e;stroke-width:1.8}.pond{fill:none;stroke:#2e86c1;stroke-width:1.6}'
           '.cl{stroke:#c0392b;stroke-width:1;stroke-dasharray:8 3 2 3}</style>',
           f'<clipPath id="clipE"><rect x="{ml}" y="{mt}" width="{W - ml - mr}" height="{H - mt - mb}"/></clipPath>']
    # grid
    for z in range(int(z0), int(z1) + 1, 10):
        out.append(f'<line class="g" x1="{ml}" y1="{Y(z):.1f}" x2="{W - mr}" y2="{Y(z):.1f}"/>'
                   f'<text class="gt" x="{ml - 4}" y="{Y(z) + 3.5:.1f}" text-anchor="end">{z}</text>')
    s = math.ceil(x0 / 100) * 100
    while s <= x1:
        out.append(f'<line class="g" x1="{X(s):.1f}" y1="{mt}" x2="{X(s):.1f}" y2="{H - mb}"/>'
                   f'<text class="gt" x="{X(s):.1f}" y="{H - mb + 12}" text-anchor="middle">{_fmt_sta(s)}</text>')
        s += 100
    out.append('<g clip-path="url(#clipE)">')
    for sec in (A, B):
        for p in sec["projected_piles"]:
            out.append(f'<rect x="{X(p["sta"][0]):.1f}" y="{Y(p["z"][1]):.1f}" width="{max((p["sta"][1] - p["sta"][0]) * sx, 1.2):.1f}" '
                       f'height="{(p["z"][1] - max(p["z"][0], z0 - 5)) * sz:.1f}" fill="none" stroke="{ROLE_FILL["pile"]}" stroke-width="1" stroke-dasharray="3 2"/>')
        for o in sec["objects"]:
            fill = ROLE_FILL.get(o["role"], "#ccc")
            for lp in o["loops"]:
                d = "M" + "L".join(f"{X(x):.1f},{Y(z):.1f}" for x, z in lp["pts"]) + ("Z" if lp["closed"] else "")
                stroke_w = 2 if o["role"] == "strap" else 0.7
                out.append(f'<path d="{d}" fill="{fill if lp["closed"] and o["role"] != "strap" else "none"}" fill-opacity=".8" stroke="{fill if o["role"] == "strap" else "#1d2430"}" stroke-width="{stroke_w}"/>')
        for piece in sec["terrain"].get("POND", []):
            out.append('<path class="pond" d="M' + "L".join(f"{X(x):.1f},{Y(z):.1f}" for x, z in piece) + '"/>')
        for piece in sec["terrain"]["EG"]:
            out.append('<path class="eg" d="M' + "L".join(f"{X(x):.1f},{Y(z):.1f}" for x, z in piece) + '"/>')
    out.append("</g>")
    # support labels
    labels = [("FFBW END BENT 1", stations["EB1"]), ("℄ PIER", stations["PIER"]), ("FFBW END BENT 2", stations["EB2"])]
    for name, sta in labels:
        out.append(f'<line class="cl" x1="{X(sta):.1f}" y1="{mt}" x2="{X(sta):.1f}" y2="{H - mb}"/>'
                   f'<text class="t" x="{X(sta):.1f}" y="{mt - 14}" text-anchor="middle">{name}</text>'
                   f'<text class="t" x="{X(sta):.1f}" y="{mt - 3}" text-anchor="middle">STA. {_fmt_sta(sta)}</text>')
    # survey limits
    for sec in (A, B):
        for lim in sec.get("limits", []):
            out.append(f'<text class="ti" x="{X(lim[0]):.1f}" y="{Y(lim[1]) - 6:.1f}" text-anchor="middle">survey limit</text>')
    out.append(f'<text class="t" x="{X(stations["PIER"]) + 6:.1f}" y="{H - mb - 6}" fill="#7a5c2e">existing ground (Ex_I-95_Middle survey)</text>')
    out.append(f'<text class="ti" x="{ml}" y="{H - 6}">Elevation on the PGL from the registered model and survey (geotechnical sections A-2 and B-2, {facts["ve"]}:1 vertical exaggeration); '
               f'ramps A and B continue beyond the end bents; piles cut at EL {z0:.0f} (trial lengths, tips pending). Elevations in feet.</text>')
    out.append("</svg>")
    return "\n".join(out)


def legend_html():
    items = ["deck", "cap", "backwall", "pier_wall", "mse", "coping", "footing", "slab", "barrier", "strap", "pile"]
    return '<p class="legend">' + " ".join(
        f'<span><span class="sw" style="background:{ROLE_FILL[k]}"></span>{escape(ROLE_NAME[k])}</span>' for k in items) + "</p>"
