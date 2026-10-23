"""SVG figures for the Bridge Development Report, drawn from the registered geometry.

Two figures: the bridge typical section (journal Bridge Geometry - 2 Beam values)
and the longitudinal elevation along the PGL (the A-2 and B-2 geotechnical
sections: the model's finished components cut on the PGL, the existing-ground
survey and the Pond 14D grading). Both are schematic record drawings, not
contract drawings.
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


def typical_section_svg(g: dict) -> str:
    """g: inches unless noted. Keys: deck_w, slab_t, parapet_w, parapet_h, edge_offset, beam_spacing,
    beam_depth, top_flange_w, clear_w, fence_straight, fence_radius, crossfall, haunch_min,
    pedestal_h, pad_t, cap_w, cap_h, pile_d, pile_type, handrail_h."""
    W, H = 900, 650
    scale = 2.3                       # px per inch
    cx = W / 2
    deck_w = g["deck_w"]
    # vertical datum: deck top at centreline
    y_top = 400
    X = lambda x_in: cx + x_in * scale          # x_in measured from the bridge centreline
    Y = lambda z_in: y_top - z_in * scale       # z_in above the deck top at the crown
    cf = g["crossfall"]
    half = deck_w / 2
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" class="fig" role="img" '
           f'aria-label="Bridge typical section">',
           '<style>.c{fill:#dfe5ec;stroke:#1d2430;stroke-width:1.4}.cl{stroke:#1d2430;stroke-width:1.1;stroke-dasharray:10 3 2 3}'
           '.dim{stroke:#34495e;stroke-width:.9}.t{font:12px system-ui,sans-serif;fill:#1d2430}.ts{font:11px system-ui,sans-serif;fill:#4a5568}'
           '.ti{font:italic 11px system-ui,sans-serif;fill:#4a5568}.fe{fill:none;stroke:#555;stroke-width:1.2}</style>']
    # deck slab with crown
    t = g["slab_t"]
    pts = [(-half, -half * cf), (0, 0), (half, -half * cf), (half, -half * cf - t), (0, -t), (-half, -half * cf - t)]
    out.append('<polygon class="c" points="' + " ".join(f"{X(x):.1f},{Y(z):.1f}" for x, z in pts) + '"/>')
    # parapets
    pw, ph, eo = g["parapet_w"], g["parapet_h"], g["edge_offset"]
    for s in (-1, 1):
        xo = s * (half - eo)                  # outer face
        xi = s * (half - eo - pw)             # inner face
        zt = -abs(xo) * cf
        out.append(f'<rect class="c" x="{min(X(xo), X(xi)):.1f}" y="{Y(zt + ph):.1f}" width="{pw * scale:.1f}" height="{ph * scale:.1f}"/>')
        # handrail
        hr = g["handrail_h"]
        out.append(f'<line class="fe" x1="{X(xi - s * 3.5):.1f}" y1="{Y(zt + ph):.1f}" x2="{X(xi - s * 3.5):.1f}" y2="{Y(zt + hr):.1f}"/>'
                   f'<circle cx="{X(xi - s * 3.5):.1f}" cy="{Y(zt + hr):.1f}" r="2.5" fill="#555"/>')
    # fence enclosure: straight above each parapet, semicircular top
    fs, fr = g["fence_straight"], g["fence_radius"]
    base_z = -abs(half - eo) * cf + ph
    xl, xr = -(half - eo - pw / 2), (half - eo - pw / 2)
    r_px = fr * scale
    out.append(f'<path class="fe" d="M{X(xl):.1f},{Y(base_z):.1f} V{Y(base_z + fs):.1f} '
               f'A{r_px:.1f},{r_px:.1f} 0 0 1 {X(xr):.1f},{Y(base_z + fs):.1f} V{Y(base_z):.1f}" stroke-dasharray="4 3"/>')
    out.append(f'<text class="ti" x="{cx:.1f}" y="{Y(base_z + fs + fr) - 8:.1f}" text-anchor="middle">Metal-fabric fence enclosure (LRFD 13.8.2 basis), crown about {_ftin(base_z + fs + fr, 1)} above the deck</text>')
    # beams (FIB-36 schematic: top flange 48 in, web 7 in, bottom flange 38 in)
    bs, bd, tf = g["beam_spacing"], g["beam_depth"], g["top_flange_w"]
    hm = g["haunch_min"]
    for s in (-1, 1):
        bx = s * bs / 2
        ztop = -abs(bx) * cf - t - hm - (bx and 0)    # beam top under the haunch
        # haunch
        out.append(f'<rect class="c" x="{X(bx - tf / 2):.1f}" y="{Y(-abs(bx) * cf - t):.1f}" width="{tf * scale:.1f}" height="{hm * scale + 1.5:.1f}" fill="#eef1f4"/>')
        zb = ztop - bd
        shape = [(bx - tf / 2, ztop), (bx + tf / 2, ztop), (bx + tf / 2, ztop - 3.5), (bx + 3.5, ztop - 7.5),
                 (bx + 3.5, zb + 10), (bx + 19, zb + 4), (bx + 19, zb), (bx - 19, zb), (bx - 19, zb + 4),
                 (bx - 3.5, zb + 10), (bx - 3.5, ztop - 7.5), (bx - tf / 2, ztop - 3.5)]
        out.append('<polygon class="c" points="' + " ".join(f"{X(x):.1f},{Y(z):.1f}" for x, z in shape) + '"/>')
        out.append(f'<text class="ts" x="{X(bx):.1f}" y="{Y(zb - 14):.1f}" text-anchor="middle">{escape(g["beam_name"])}</text>')
        # bearing pad and pedestal under the beam (at a support)
        pad_t, ped_h, ped_w = g["pad_t"], g["pedestal_h"], g["pedestal_w"]
        out.append(f'<rect class="c" x="{X(bx - 16):.1f}" y="{Y(zb):.1f}" width="{32 * scale:.1f}" height="{pad_t * scale:.1f}" fill="#444"/>')
        out.append(f'<rect class="c" x="{X(bx - ped_w / 2):.1f}" y="{Y(zb - pad_t):.1f}" width="{ped_w * scale:.1f}" height="{ped_h * scale:.1f}"/>')
    # cap outline (support shown dashed below the pedestals)
    cap_top = -half * cf - t - hm - bd - g["pad_t"] - g["pedestal_h"]
    cap_l = g["cap_len"]
    out.append(f'<rect class="c" x="{X(-cap_l / 2):.1f}" y="{Y(cap_top):.1f}" width="{cap_l * scale:.1f}" height="{g["cap_h"] * scale:.1f}" stroke-dasharray="6 3" fill="#f4f6f8"/>')
    out.append(f'<text class="ts" x="{cx:.1f}" y="{Y(cap_top - g["cap_h"] / 2) + 4:.1f}" text-anchor="middle">{escape(g["cap_label"])}</text>')
    # centreline
    out.append(f'<line class="cl" x1="{cx:.1f}" y1="{Y(base_z + fs + fr) - 30:.1f}" x2="{cx:.1f}" y2="{Y(cap_top - g["cap_h"]) + 20:.1f}"/>')
    out.append(f'<text class="ts" x="{cx + 4:.1f}" y="{Y(base_z + fs + fr) - 20:.1f}">℄ bridge / PGL</text>')

    def dim(x1, x2, y, label, above=True):
        out.append(f'<line class="dim" x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}"/>')
        for x in (x1, x2):
            out.append(f'<line class="dim" x1="{x:.1f}" y1="{y - 5:.1f}" x2="{x:.1f}" y2="{y + 5:.1f}"/>')
        out.append(f'<text class="t" x="{(x1 + x2) / 2:.1f}" y="{y - 4 if above else y + 13:.1f}" text-anchor="middle">{escape(label)}</text>')

    def vdim(x, z1, z2, label):
        y1, y2 = Y(z1), Y(z2)
        out.append(f'<line class="dim" x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}"/>')
        for y in (y1, y2):
            out.append(f'<line class="dim" x1="{x - 5:.1f}" y1="{y:.1f}" x2="{x + 5:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text class="t" x="{x + 6:.1f}" y="{(y1 + y2) / 2 + 4:.1f}">{escape(label)}</text>')

    yd = Y(base_z + ph + 2) - 4
    dim(X(-(half - eo - pw)), X(half - eo - pw), Y(ph + 4), f'{_ftin(g["clear_w"])} clear between parapets')
    dim(X(-half), X(half), Y(-t - bd - 40), f'{_ftin(deck_w)} out-to-out of deck', above=False)
    dim(X(-bs / 2), X(bs / 2), Y(-t - bd - 22), f'{_ftin(bs)} beam spacing', above=False)
    dim(X(bs / 2), X(half), Y(-t - bd - 22), f'{_ftin(half - bs / 2)}', above=False)
    vdim(X(half) + 14, -half * cf, -half * cf - t, f'{_ftin(t)} slab')
    vdim(X(half) + 14, -half * cf - t - hm, -half * cf - t - hm - bd, f'{_ftin(bd)} {escape(g["beam_name"])}')
    vdim(X(-(half - eo)) - 16, -abs(half - eo) * cf, -abs(half - eo) * cf + ph, f'{_ftin(ph)} parapet')
    vdim(X(-(half - eo)) - 16, base_z, base_z + fs, f'{_ftin(fs, 16)} fence, straight')
    out.append(f'<text class="ts" x="{X(0):.1f}" y="{Y(-1) + 11:.1f}" text-anchor="middle">{cf * 100:.0f}% crossfall each way from the crown</text>')
    out.append(f'<text class="ti" x="12" y="{H - 10}">Schematic typical section from the registered journal geometry (Bridge Geometry - 2 Beam); FIB-36 shape simplified; not a contract drawing.</text>')
    out.append("</svg>")
    return "\n".join(out)


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
