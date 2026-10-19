"""Plain numbers the distilled cap figures are drawn from (Mathcad PNGs and Blockpad canvases).

Everything here reads an evaluated cap case only, so the portable notebook can draw the distilled Blockpad figures
without the SVG renderer of scripts/cap_mathcad_figures.py, which imports these helpers back.
"""


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


def _centroid_y(bars):
    area = [b['d'] ** 2 for b in bars]          # same-material bars: area scales with d squared
    return sum(a * b['y'] for a, b in zip(area, bars)) / sum(area)
