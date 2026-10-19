"""Plotly figures and result tables for the pile analysis and design calculation."""
import html
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pier_cap.visuals import theme, BLUE, TEAL, AMBER, RED, INK, GREY
from .model import DATA_TABLE_COLUMNS, INPUTS
from .loads import record_id

CONCRETE = '#e9eef2'; CONCRETE_LINE = '#5b6f80'; STEEL = '#b8c7d1'; SOIL = '#efe3c8'; SOIL_LINE = '#b59a62'
STRAND = '#213649'; SPIRAL = '#7a3e9d'; CORROSION = '#d9b44a'; PURPLE = '#7a3e9d'
COMBO_COLORS = [BLUE, TEAL, AMBER, PURPLE, '#4b8fc6', '#8a6d3b', RED, '#17633b']
GROUP_COLORS = {'Prestressed pile': BLUE, 'Steel pipe pile': BLUE, 'Geotechnical': TEAL, 'Reference': GREY}
NO_DATA = 'No FBMP results are loaded. Upload the pile XML in Cell 1.'


# ----------------------------------------------------------------------------- shared helpers
def combo_table(e):
    """[(key, state, label)] for the FBMP combinations in the case, in numeric order."""
    analysis = e.case.get('analysis') or {}
    factors = analysis.get('combination_factors') or {}
    seen = {}
    for r in e.records:
        seen.setdefault(str(r['combination']), r['state'])
    for key, state in (analysis.get('combinations') or {}).items():
        seen.setdefault(str(key), state)
    out = []
    for key in sorted(seen, key=lambda s: (len(s), s)):
        tags = [n for n, f in (factors.get(key) or {}).items() if n[:2] in ('WS', 'WL') and abs(f) > 0]
        out.append((key, seen[key], f'{key} {seen[key]}' + (f' ({", ".join(tags)})' if tags else '')))
    return out


def combo_colors(e):
    return {key: COMBO_COLORS[i % len(COMBO_COLORS)] for i, (key, _, _) in enumerate(combo_table(e))}


def governing_label(g):
    if not g:
        return ''
    return record_id(g)


UNIT_LABELS = {'kip/ft^3': 'kcf', 'kip/ft^2': 'ksf', 'kip*ft': 'kip-ft', 'in^2': 'in²', 'in^3': 'in³', 'in^4': 'in⁴'}


def unit_label(unit):
    return UNIT_LABELS.get(unit, unit or '')


def input_text(name, value):
    """Display text of an input value: option labels for categorical inputs, N/A for a blank optional input."""
    if value is None:
        return 'N/A (blank)'
    options = INPUTS[name].get('options')
    if options:
        for key, label in options.items():
            if abs(float(key) - float(value)) < 1e-9:
                return f'{value:g} · {label}'
    return f'{value:g}'


def check_ratio(e, key):
    """Ratio of the check with this key (the governing-record keys equal the check keys); 0 when absent."""
    for c in e.checks:
        if c.key == key and isinstance(c.ratio, (int, float)):
            return float(c.ratio)
    return 0.0


def structural_governing_check(e):
    """The structural check with the largest ratio (model.STRUCTURAL_CHECKS when available)."""
    from . import model
    keys = getattr(model, 'STRUCTURAL_CHECKS', None)
    pool = [c for c in e.checks if isinstance(c.ratio, (int, float)) and math.isfinite(c.ratio)
            and (c.key in keys if keys else c.group not in ('Prerequisites', 'Geotechnical', 'Reference'))]
    return max(pool, key=lambda c: c.ratio) if pool else None


def max_ratio_check(e):
    """The check with the largest ratio of any kind (prerequisites excluded)."""
    pool = [c for c in e.checks if isinstance(c.ratio, (int, float)) and math.isfinite(c.ratio) and c.group != 'Prerequisites']
    return max(pool, key=lambda c: c.ratio) if pool else None


GOVERNING_LABELS = {
    'psc_axial': 'Axial compression', 'psc_flex_bi': 'Axial + biaxial flexure (LRFD 5.6.4.5)', 'psc_flex_res': 'Axial + flexure, resultant axis',
    'psc_shear': 'Shear (general procedure)', 'psc_tension': 'Tension (maximum uplift)', 'psc_svc_comp': 'Service I compression',
    'psc_svc_tens': 'Service I tension', 'pipe_axial': 'Axial compression', 'pipe_comb': 'Combined axial load and flexure (6.9.2.2.1)',
    'pipe_shear': 'Shear', 'pipe_tension': 'Tension (maximum uplift)'}


def combination_envelope(e):
    """Per FBMP combination: the records with the largest and smallest P_u, largest M_res and V_res (all stations, all piles)."""
    out = []
    for key, state, label in combo_table(e):
        rows = [r for r in e.records if str(r['combination']) == key]
        if rows:
            out.append(dict(key=key, label=label, limit=rows[0]['limit'], max_P=max(rows, key=lambda r: r['P_u']), min_P=min(rows, key=lambda r: r['P_u']),
                            max_M=max(rows, key=lambda r: r['M_res']), max_V=max(rows, key=lambda r: r['V_res'])))
    return out


def combination_envelope_html(e, css='ebw-table'):
    where = lambda r: f'pile {r["pile"]} · {r["local_element"]}{r["side"]} · EL {r["elevation_ft"]:.1f}'
    body = ''.join(
        f'<tr><td>{html.escape(c["label"])}</td><td>{c["limit"]}</td><td class="num ebw-num">{c["max_P"]["P_u"]:.1f}</td><td>{html.escape(where(c["max_P"]))}</td>'
        f'<td class="num ebw-num">{c["min_P"]["P_u"]:.1f}</td><td class="num ebw-num">{c["max_M"]["M_res"]:.1f}</td><td>{html.escape(where(c["max_M"]))}</td>'
        f'<td class="num ebw-num">{c["max_V"]["V_res"]:.2f}</td><td>{html.escape(where(c["max_V"]))}</td></tr>' for c in combination_envelope(e))
    return (f'<table class="{css}"><tr><th>Combination</th><th>Limit</th><th>Max P<sub>u</sub> (kip)</th><th>Where</th><th>Min P<sub>u</sub> (kip)</th>'
            '<th>Max M<sub>res</sub> (kip-ft)</th><th>Where</th><th>Max V<sub>res</sub> (kip)</th><th>Where</th></tr>' + body + '</table>')


def records_table_html(records, css='ebw-table', limit=None):
    """FBMP records with the drag load applied: P_fbmp + gamma_DR DD = P_u (compression positive)."""
    rows = list(records)
    shown = rows if limit is None else rows[:limit]
    dc = lambda r: '' if r.get('model_dc') is None else '%.2f' % r['model_dc']
    body = ''.join(
        f'<tr><td>{html.escape(str(r["combination"]))} {html.escape(r["state"])}</td><td>{html.escape(str(r["pile"]))}</td><td>{r["local_element"]}{r["side"]}</td>'
        f'<td class="num ebw-num">{r["elevation_ft"]:.2f}</td><td class="num ebw-num">{r["P_fbmp"]:.2f}</td><td class="num ebw-num">{r["gamma_DR"]:g}</td>'
        f'<td class="num ebw-num">{r["P_u"]:.2f}</td><td class="num ebw-num">{r["M2"]:.2f}</td><td class="num ebw-num">{r["M3"]:.2f}</td>'
        f'<td class="num ebw-num">{r["M_res"]:.2f}</td><td class="num ebw-num">{r["V_res"]:.2f}</td>'
        f'<td class="num ebw-num">{dc(r)}</td></tr>' for r in shown)
    more = f'<p>Showing {len(shown)} of {len(rows)} records.</p>' if len(shown) < len(rows) else ''
    return (f'<table class="{css}"><tr><th>Combination</th><th>Pile</th><th>Element end</th><th>EL (ft)</th><th>P<sub>FBMP</sub> (kip)</th><th>γ<sub>DR</sub></th>'
            '<th>P<sub>u</sub> (kip)</th><th>M2 (kip-ft)</th><th>M3 (kip-ft)</th><th>M<sub>res</sub> (kip-ft)</th><th>V<sub>res</sub> (kip)</th><th>FBMP D/C</th></tr>'
            + body + '</table>' + more)


def governing_table_html(e, css='ebw-table'):
    rows = []
    for key, g in e.governing.items():
        if not g:
            continue
        ties = len(g.get('ties', ())) - 1
        rows.append(f'<tr><td>{html.escape(GOVERNING_LABELS.get(key, key))}</td><td>{html.escape(record_id(g))}{f" (+{ties} tied)" if ties > 0 else ""}</td>'
                    f'<td class="num ebw-num">{g["P_fbmp"]:.2f}</td><td class="num ebw-num">{g["P_u"]:.2f}</td><td class="num ebw-num">{g["M_res"]:.2f}</td>'
                    f'<td class="num ebw-num">{g["V_res"]:.2f}</td><td class="num ebw-num">{check_ratio(e, key):.3f}</td></tr>')
    return (f'<table class="{css}"><tr><th>Check</th><th>Governing record</th><th>P<sub>FBMP</sub> (kip)</th><th>P<sub>u</sub> (kip)</th>'
            '<th>M<sub>res</sub> (kip-ft)</th><th>V<sub>res</sub> (kip)</th><th>Check ratio</th></tr>' + ''.join(rows) + '</table>')


def _poly(fig, xs, ys, fill, line, hover, name=None, dash=None, legend=False, width=1.4):
    fig.add_trace(go.Scatter(x=list(xs) + [xs[0]], y=list(ys) + [ys[0]], mode='lines', fill='toself', fillcolor=fill,
                             line=dict(color=line, width=width, dash=dash), hoveron='fills+points', text=hover,
                             hoverinfo='text', name=name or hover, showlegend=legend))


def _rect(fig, x0, y0, x1, y1, fill, line, hover, **kw):
    _poly(fig, [x0, x1, x1, x0], [y0, y0, y1, y1], fill, line, hover, **kw)


def _circle(fig, cx, cy, r, fill, line, hover, n=48, **kw):
    xs = [cx + r * math.cos(2 * math.pi * i / n) for i in range(n)]
    ys = [cy + r * math.sin(2 * math.pi * i / n) for i in range(n)]
    _poly(fig, xs, ys, fill, line, hover, **kw)


def _dim_v(fig, x, y0, y1, text, color=INK, side='right'):
    fig.add_trace(go.Scatter(x=[x, x], y=[y0, y1], mode='lines+markers', line=dict(color=color, width=1),
                             marker=dict(symbol='line-ew', size=10, line=dict(width=1.5, color=color)),
                             hoverinfo='text', text=text, showlegend=False))
    fig.add_annotation(x=x, y=(y0 + y1) / 2, text=text, showarrow=False, font=dict(size=10, color=color),
                       xanchor='left' if side == 'right' else 'right', xshift=6 if side == 'right' else -6)


def _dim_h(fig, x0, x1, y, text, color=INK):
    fig.add_trace(go.Scatter(x=[x0, x1], y=[y, y], mode='lines+markers', line=dict(color=color, width=1),
                             marker=dict(symbol='line-ns', size=10, line=dict(width=1.5, color=color)),
                             hoverinfo='text', text=text, showlegend=False))
    fig.add_annotation(x=(x0 + x1) / 2, y=y, text=text, showarrow=False, yshift=-12, font=dict(size=10, color=color))


def _empty(title, message=NO_DATA, height=320):
    fig = go.Figure()
    fig.add_annotation(text=message, xref='paper', yref='paper', x=.5, y=.5, showarrow=False, font=dict(size=13, color=INK))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return theme(fig, title, height)


def _try_value(e, name, unit=None, default=None):
    try:
        return e.value(name, unit)
    except (KeyError, ValueError, AssertionError):
        return default


def quantity_rows(e, names):
    """[(name, caption, value text, unit label)] for inputs, calculated quantities and carried numerical results."""
    defs = {d['name']: d for d in e.definitions}
    rows = []
    for n in names:
        if n in defs:
            caption = defs[n]['caption']
        elif n in e.external_meta:
            caption = e.external_meta[n][1]
        elif n in INPUTS:
            caption = INPUTS[n]['caption']
        else:
            continue
        try:
            text = e.text(n, 4)
        except (KeyError, ValueError, AssertionError, TypeError):
            continue
        rows.append((n, caption, text))
    return rows


def quantity_table_html(e, names, css='ebw-table', symbols=False):
    """Two- or three-column HTML table of named quantities with their current values."""
    rows = quantity_rows(e, names)
    if symbols:
        from .notation import symbol, mathml
        body = ''.join(f'<tr><td>{mathml(symbol(n))}</td><td>{html.escape(c)}</td><td class="num ebw-num">{html.escape(t)}</td></tr>' for n, c, t in rows)
        head = '<tr><th>Symbol</th><th>Quantity</th><th>Value</th></tr>'
    else:
        body = ''.join(f'<tr><td>{html.escape(c)}</td><td class="num ebw-num">{html.escape(t)}</td></tr>' for n, c, t in rows)
        head = '<tr><th>Quantity</th><th>Value</th></tr>'
    return f'<table class="{css}">{head}{body}</table>'


def data_table_html(e, css='ebw-table', rows=None):
    """SDM 11.4 Pile Data Table: lettered columns A-Q, one row per support."""
    rows = rows or [e.data_table]
    fmt = lambda v: v if isinstance(v, str) else (f'{v:g}' if isinstance(v, float) else str(v))
    letters = ''.join(f'<th style="text-align:center;font-weight:normal;color:#485969">{letter}</th>' for letter, _ in DATA_TABLE_COLUMNS)
    headers = ''.join(f'<th>{html.escape(header)}</th>' for _, header in DATA_TABLE_COLUMNS)
    body = ''.join('<tr>' + ''.join(f'<td class="num ebw-num">{html.escape(fmt(row.get(header, "N/A")))}</td>' for _, header in DATA_TABLE_COLUMNS) + '</tr>'
                   for row in rows)
    return f'<div style="overflow-x:auto"><table class="{css}"><tr>{letters}</tr><tr>{headers}</tr>{body}</table></div>'


# ----------------------------------------------------------------------------- section
def section_figure(e):
    v, p = e.value, e.case['inputs']
    fig = go.Figure()
    if e.family == 'psc':
        sec, plan, option = e.details['section'], e.details['plan'], e.details['option']
        D = sec['D']; h = D / 2
        xs, ys, areas = list(sec['x']), list(sec['y']), list(sec['A'])
        _rect(fig, -h, -h, h, h, CONCRETE, CONCRETE_LINE, f'{D:g} in square pile (chamfers ignored)')
        if sec['d_void'] > 0:
            _circle(fig, 0, 0, sec['d_void'] / 2, '#ffffff', CONCRETE_LINE, f'{sec["d_void"]:g} in void (Index {plan["size_in"]:g} in pile)', dash='dash')
        inset = max(p['d_edge'] - 0.5, 0.5)
        _rect(fig, -h + inset, -h + inset, h - inset, h - inset, 'rgba(0,0,0,0)', SPIRAL,
              f'Spiral outline (schematic): {plan["spiral_wire"]} at {p["spiral_pitch"]:g} in pitch', dash='dash', legend=True, name='Spiral outline (schematic)', width=2)
        for x, y, a in zip(xs, ys, areas):
            _circle(fig, x, y, math.sqrt(a / math.pi), STRAND, STRAND, f'Strand {option["dia"]}" ({a:g} in²) at ({x:.2f}, {y:.2f}) in', n=20)
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(size=9, color=STRAND), name=f'{option["count"]} strands, {option["label"]}'))
        half = h - p['d_edge']
        per_side = int(round(option['count'] / 4)) + 1
        spacing = 2 * half / (per_side - 1)
        _dim_h(fig, -h, h, -h - 1.6, f'{D:g} in')
        _dim_v(fig, h + 1.0, -h, h, f'{D:g} in')
        _dim_v(fig, -h - 1.0, -h, -half, f'd_edge {p["d_edge"]:g} in', side='left')
        _dim_h(fig, -half, -half + spacing, h + 1.6, f's = {spacing:.2f} in')
        lim = h + 5.5
        notes = (f'A<sub>g</sub> = {v("A_g"):.1f} in² · I<sub>g</sub> = {v("I_g"):.0f} in⁴ · A<sub>ps</sub> = {v("A_ps"):.3f} in² · '
                 f'f<sub>pe</sub> = {v("f_pe"):.1f} ksi · f<sub>pc,eff</sub> = {v("f_pc_eff"):.3f} ksi')
        title = f'Figure P1 · Index {e.case["psc"]["index"]} section with {option["label"]} strands (chamfers ignored)'
    else:
        pipe = e.details['pipe']
        Do = pipe['D']; ro = Do / 2; t_des = pipe['t']; tw = p['t_wall']; t_corr = p['t_corr']
        _circle(fig, 0, 0, ro, CORROSION if t_corr > 0 else STEEL, CONCRETE_LINE, f'{Do:g} in pipe, {tw:g} in wall' + (f' (outer {t_corr:g} in lost to corrosion)' if t_corr > 0 else ''), n=96)
        if t_corr > 0:
            _circle(fig, 0, 0, ro - t_corr, STEEL, CONCRETE_LINE, f'Design wall {t_des:g} in', n=96)
        _circle(fig, 0, 0, pipe['Di'] / 2, '#ffffff', CONCRETE_LINE, f'Inside diameter {pipe["Di"]:.3f} in (unfilled; noncomposite)', n=96)
        _dim_h(fig, -ro, ro, -ro - 1.6, f'D = {Do:g} in')
        _dim_h(fig, -pipe['Di'] / 2, pipe['Di'] / 2, 0.0, f'D<sub>i</sub> = {pipe["Di"]:.3f} in')
        fig.add_annotation(x=0, y=ro - t_des / 2, ax=-ro * 0.3, ay=ro * 0.62, axref='x', ayref='y', xref='x', yref='y', showarrow=True, arrowhead=3,
                           arrowcolor=INK, text=f't = {t_des:g} in' + (f' (after {t_corr:g} in corrosion)' if t_corr > 0 else ''), font=dict(size=11, color=INK))
        lim = ro + 4.0
        notes = (f'A<sub>g</sub> = {v("A_g"):.2f} in² · I<sub>g</sub> = {v("I_g"):.1f} in⁴ · S = {v("S_g"):.1f} in³ · Z = {v("Z_p"):.1f} in³ · '
                 f'r = {v("r_g"):.2f} in · D/t = {v("D_t"):.2f}')
        title = f'Figure P1 · Steel pipe section, {Do:g} in × {t_des:g} in (noncomposite)'
    fig.update_xaxes(range=[-lim, lim], title='in', zeroline=False, constrain='domain')
    fig.update_yaxes(range=[-lim, lim], title='in', scaleanchor='x', scaleratio=1, zeroline=False, constrain='domain')
    theme(fig, title, 560)
    fig.add_annotation(text=notes, xref='paper', yref='paper', x=.5, y=-.2, showarrow=False, font=dict(size=11, color=INK))
    fig.update_layout(legend=dict(orientation='h', y=-.1), margin=dict(l=60, r=25, t=60, b=110))
    return fig


# ----------------------------------------------------------------------------- elevation
def elevation_figure(e):
    v, p = e.value, e.case['inputs']
    top, ground = p['EL_cutoff'], p['EL_ground']
    tips = [r['elevation_ft'] for r in e.records]
    tip_xml = min(tips) if tips else None
    min_tip = p.get('EL_min_tip')
    candidates = [x for x in (tip_xml, min_tip, ground - 8.0) if x is not None]
    scour = [(p.get('EL_scour_100'), '100-year scour'), (p.get('EL_scour_LT'), 'Long-term scour')]
    L_fix = _try_value(e, 'L_fix', 'ft') if e.family == 'pipe' else None
    if L_fix is not None:
        candidates.append(ground - L_fix - 2.0)
    candidates += [s for s, _ in scour if s is not None]
    bottom = min(candidates) - 2.0
    w = 0.45
    fig = go.Figure()
    _rect(fig, -4.5, bottom, 4.5, ground, SOIL, SOIL_LINE, 'Soil (layering not drawn; see the FBMP model)')
    _rect(fig, -2.4, top, 2.4, top + 3.0, CONCRETE, CONCRETE_LINE, 'Pile cap')
    _rect(fig, -w, tip_xml if tip_xml is not None else bottom + 1, w, top, STEEL if e.family == 'pipe' else '#cfd9e2', CONCRETE_LINE,
          f'Pile (width not to scale): cutoff EL {top:.2f} ft' + (f', FBMP model tip EL {tip_xml:.2f} ft' if tip_xml is not None else ''))
    fig.add_trace(go.Scatter(x=[-4.5, 4.5], y=[ground, ground], mode='lines', line=dict(color=SOIL_LINE, width=2.5), hoverinfo='text',
                             text=f'Ground EL {ground:.2f} ft (top of soil layer 1)', name='Ground', showlegend=False))
    fig.add_annotation(x=4.5, y=ground, text=f'Ground EL {ground:.2f} ft', showarrow=False, xanchor='left', font=dict(size=11, color='#8a6d3b'))
    fig.add_annotation(x=0, y=top + 1.5, text=f'Cap · pile cutoff EL {top:.2f} ft', showarrow=False, font=dict(size=11, color=INK))
    _dim_v(fig, 3.2, ground, top, f'L<sub>u</sub> = {top - ground:.2f} ft')
    if L_fix is not None:
        fix_el = ground - L_fix
        fig.add_trace(go.Scatter(x=[-3.6, 3.6], y=[fix_el, fix_el], mode='lines', line=dict(color=PURPLE, width=2, dash='dash'), hoverinfo='text',
                                 text=f'Equivalent fixity EL {fix_el:.2f} ft (LRFD 10.7.3.13.4, L_fix = {L_fix:.2f} ft)', name='Depth to fixity'))
        _dim_v(fig, -3.2, fix_el, ground, f'L<sub>fix</sub> = {L_fix:.2f} ft', color=PURPLE, side='left')
        KL = _try_value(e, 'KL', 'ft')
        if KL is not None:
            _dim_v(fig, -4.7, fix_el, top, f'KL = {KL:.2f} ft (K = {p["K_eff"]:g})', color=PURPLE, side='left')
    if tip_xml is not None:
        fig.add_trace(go.Scatter(x=[-1.6, 1.6], y=[tip_xml, tip_xml], mode='lines', line=dict(color=INK, width=1.5, dash='dot'), hoverinfo='text',
                                 text=f'Lowest FBMP result station EL {tip_xml:.2f} ft', name='FBMP model pile tip'))
    if min_tip is not None:
        fig.add_trace(go.Scatter(x=[-2.2, 2.2], y=[min_tip, min_tip], mode='lines', line=dict(color=RED, width=2, dash='dashdot'), hoverinfo='text',
                                 text=f'Minimum tip EL {min_tip:.2f} ft (geotechnical handoff)', name='Minimum tip'))
    for el, label in scour:
        if el is not None:
            fig.add_trace(go.Scatter(x=[-4.5, 4.5], y=[el, el], mode='lines', line=dict(color=BLUE, width=1.5, dash='dash'), hoverinfo='text',
                                     text=f'{label} EL {el:.2f} ft', name=label))
    dd = p['DD_tons']
    if dd > 0:
        y0 = ground - 0.6
        fig.add_annotation(x=w + 0.25, y=y0 - 4.0, ax=w + 0.25, ay=y0, axref='x', ayref='y', xref='x', yref='y', showarrow=True, arrowhead=3,
                           arrowwidth=3, arrowcolor=RED, text='')
        fig.add_annotation(x=w + 0.4, y=y0 - 2.0, text=f'DD {dd:g} tons<br>drag load', showarrow=False, xanchor='left', font=dict(size=11, color=RED))
    fig.update_xaxes(range=[-6.5, 8.0], visible=False)
    fig.update_yaxes(range=[bottom - 0.5, top + 3.5], title='Elevation (ft)', zeroline=False)
    theme(fig, 'Figure P2 · Pile elevation: cutoff, ground, unsupported length' + (', depth to fixity' if L_fix is not None else '') + ' and tip', 620)
    fig.update_layout(legend=dict(orientation='h', y=-.08), margin=dict(l=60, r=25, t=60, b=80))
    return fig


# ----------------------------------------------------------------------------- demand profile
def _group_records(e, limit=None):
    groups = {}
    for r in e.records:
        if limit and r['limit'] != limit:
            continue
        groups.setdefault((str(r['combination']), str(r['pile'])), []).append(r)
    for rows in groups.values():
        rows.sort(key=lambda r: (r['local_element'], 0 if r['side'] == 'I' else 1))     # walk down the pile: I-end then J-end of each element
    return groups


def governing_keys(e):
    if e.family == 'psc':
        return [('psc_axial', 'Governing axial', 'triangle-up', (1,)), ('psc_flex_res', 'Governing combined', 'star', (1, 2, 3)),
                ('psc_shear', 'Governing shear', 'diamond', (3,))]
    return [('pipe_axial', 'Governing axial', 'triangle-up', (1,)), ('pipe_comb', 'Governing combined', 'star', (1, 2, 3)),
            ('pipe_shear', 'Governing shear', 'diamond', (3,))]


def demand_profile_figure(e):
    if not e.records:
        return _empty('Figure P3 · Demand profiles along the pile')
    colors = combo_colors(e)
    labels = {k: lab for k, _, lab in combo_table(e)}
    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=.04,
                        subplot_titles=('P<sub>u</sub> = FBMP + γ<sub>DR</sub>·DD (kip, compression +)', 'M<sub>res</sub> (kip-ft)', 'V<sub>res</sub> (kip)'))
    legend_done = set()
    for (combo, pile), rows in sorted(_group_records(e).items()):
        elev = [r['elevation_ft'] for r in rows]
        hover = [f'Combination {labels.get(combo, combo)}<br>Pile {pile} · element {r["local_element"]}{r["side"]} · EL {r["elevation_ft"]:.2f} ft<br>'
                 f'P_fbmp {r["P_fbmp"]:.2f} + {r["gamma_DR"]:g}·DD → P_u {r["P_u"]:.2f} kip<br>M_res {r["M_res"]:.2f} kip-ft · V_res {r["V_res"]:.2f} kip' for r in rows]
        first = combo not in legend_done
        legend_done.add(combo)
        for col, key in enumerate(('P_u', 'M_res', 'V_res'), 1):
            fig.add_trace(go.Scatter(x=[r[key] for r in rows], y=elev, mode='lines', line=dict(color=colors[combo], width=1.4), opacity=.75,
                                     name=labels.get(combo, combo), legendgroup=combo, showlegend=first and col == 1, text=hover, hoverinfo='text'),
                          row=1, col=col)
    p = e.case['inputs']
    for col in (1, 2, 3):
        note = (lambda text, pos: dict(annotation_text=text, annotation_position=pos)) if col == 1 else (lambda text, pos: {})
        fig.add_hline(y=p['EL_ground'], line_dash='dot', line_color=SOIL_LINE, row=1, col=col, **note('ground', 'top left'))
        fig.add_hline(y=p['EL_cutoff'], line_dash='dot', line_color=GREY, row=1, col=col, **note('cutoff', 'bottom left'))
    fig.add_vline(x=0, line_color=GREY, line_width=1, row=1, col=1)
    keys = {'P_u': 1, 'M_res': 2, 'V_res': 3}
    for gkey, label, symbol, panels in governing_keys(e):
        g = e.governing.get(gkey)
        if not g:
            continue
        for panel in panels:
            name = [n for n, c in keys.items() if c == panel][0]
            fig.add_trace(go.Scatter(x=[g[name]], y=[g['elevation_ft']], mode='markers', marker=dict(symbol=symbol, size=14, color=RED, line=dict(width=1.5, color=INK)),
                                     name=label, legendgroup=label, showlegend=panel == panels[0], hoverinfo='text',
                                     text=f'{label}: {record_id(g)}<br>P_u {g["P_u"]:.2f} kip · M_res {g["M_res"]:.2f} kip-ft · V_res {g["V_res"]:.2f} kip'
                                          f'<br>check ratio {check_ratio(e, gkey):.3f}'),
                          row=1, col=panel)
    fig.update_yaxes(title='Elevation (ft)', row=1, col=1)
    theme(fig, 'Figure P3 · FBMP demand profiles by combination (one line per pile; red marks = governing records)', 620)
    fig.update_layout(legend=dict(orientation='h', y=-.12), margin=dict(l=60, r=25, t=85, b=95))
    return fig


# ----------------------------------------------------------------------------- interaction
def _demand_points(fig, e, colors, labels):
    by_combo = {}
    for r in e.records:
        if r['limit'] == 'strength':
            by_combo.setdefault(str(r['combination']), []).append(r)
    for combo, rows in by_combo.items():
        fig.add_trace(go.Scatter(x=[r['M_res'] for r in rows], y=[r['P_u'] for r in rows], mode='markers', marker=dict(size=5, color=colors[combo], opacity=.55),
                                 name=f'Demands, {labels.get(combo, combo)}',
                                 text=[f'Pile {r["pile"]} · element {r["local_element"]}{r["side"]} · EL {r["elevation_ft"]:.2f} ft<br>P_u {r["P_u"]:.2f} kip · M_res {r["M_res"]:.2f} kip-ft'
                                       for r in rows], hoverinfo='text'))


def _ray(fig, x, y, name, color=RED, dash='dash', width=1.6):
    fig.add_trace(go.Scatter(x=[0, x], y=[0, y], mode='lines', line=dict(color=color, width=width, dash=dash), name=name, hoverinfo='name'))


def interaction_figure(e):
    if not e.records:
        return _empty('Figure P4 · Interaction diagram')
    colors = combo_colors(e)
    labels = {k: lab for k, _, lab in combo_table(e)}
    v = lambda n: e.value(n)
    fig = go.Figure()
    if e.family == 'psc':
        c = e.curve
        fig.add_trace(go.Scatter(x=list(c['Mn']), y=list(c['Pn']), mode='lines', line=dict(color=GREY, width=2, dash='dash'), name='Nominal curve (Mn, Pn), bending parallel to a face',
                                 hoverinfo='x+y'))
        fig.add_trace(go.Scatter(x=list(c['Mr']), y=list(c['Pr']), mode='lines', line=dict(color=BLUE, width=3), name='φ-curve (Mr, Pr), bending parallel to a face',
                                 text=[f'c = {ci:.2f} in · φ = {ph:.3f}' if math.isfinite(ci) else f'pure compression · φ = {ph:.3f}' for ci, ph in zip(c['c'], c['phi'])],
                                 hoverinfo='text+x+y'))
        res = c.get('resultant')
        if res:
            fig.add_trace(go.Scatter(x=list(res['Mr']), y=list(res['Pr']), mode='lines', line=dict(color=TEAL, width=2, dash='dot'),
                                     name=f'φ-curve, axis at {c.get("resultant_angle_deg", 0):.1f}° (governing resultant)', hoverinfo='x+y'))
        _demand_points(fig, e, colors, labels)
        fig.add_hline(y=c['Pr_max'], line_dash='dot', line_color=BLUE, annotation_text='φPn,max', annotation_position='top right')
        fig.add_hline(y=e.details['P_limit'], line_dash='dot', line_color=GREY, annotation_text="0.10 φ f′c Ag (Eq. 5.6.4.5-1 / -3 boundary)", annotation_position='bottom right')
        g = e.governing.get('psc_flex_res')
        if g:
            Pc, Mc = v('P_r_rs'), v('M_r_rs')
            _ray(fig, Mc, Pc, 'Resultant-axis ray to the φ-curve')
            fig.add_trace(go.Scatter(x=[g['M_res']], y=[g['P_u']], mode='markers', name='Governing resultant-axis demand',
                                     marker=dict(symbol='star', size=16, color=RED, line=dict(width=1.5, color=INK)), hoverinfo='name+x+y'))
            fig.add_trace(go.Scatter(x=[Mc], y=[Pc], mode='markers', name='Capacity on the ray', marker=dict(symbol='circle-open', size=12, color=RED, line=dict(width=2)),
                                     hoverinfo='name+x+y'))
            fig.add_annotation(x=g['M_res'], y=g['P_u'], text=f'<b>Governing</b>: {record_id(g)}<br>P<sub>u</sub> {g["P_u"]:.1f} kip · M<sub>u</sub> {g["M_res"]:.1f} kip-ft · D/C {v("DC_rs"):.3f}',
                               ax=70, ay=-70, showarrow=True, arrowhead=2, arrowcolor=RED, font=dict(size=11, color=RED), align='left', bgcolor='rgba(255,255,255,.85)')
        bi = e.details['biaxial']
        gb = e.governing.get('psc_flex_bi')
        if gb:
            Pu = v('P_u_bi')
            fig.add_trace(go.Scatter(x=[v('M_ux_bi'), v('M_uy_bi')], y=[Pu, Pu], mode='markers', name='5.6.4.5 demand (Mux, Muy at Pu)',
                                     marker=dict(symbol='diamond', size=11, color=PURPLE, line=dict(width=1, color=INK)), hoverinfo='name+x+y'))
            if bi['method'] == '5.6.4.5-1':
                for tag, Pr_, ecc in (('x', bi['Prx'], bi['ey']), ('y', bi['Pry'], bi['ex'])):
                    _ray(fig, Pr_ * ecc / 12.0, Pr_, f'5.6.4.5-1 ray, e{tag} = {ecc:.2f} in → Pr{tag} = {Pr_:.1f} kip', color=PURPLE, dash='dashdot', width=1.3)
            else:
                fig.add_trace(go.Scatter(x=[0, v('M_rx')], y=[Pu, Pu], mode='lines+markers', line=dict(color=PURPLE, width=1.5, dash='dashdot'),
                                         marker=dict(symbol='line-ns', size=10), name=f'5.6.4.5-3: Mrx = Mry = {v("M_rx"):.1f} kip-ft at Pu', hoverinfo='name'))
        xmax = max(float(max(c['Mn'])), float(max(c['Mr']))) * 1.12
        fig.update_xaxes(range=[0, xmax], title='Moment M (kip-ft)')
        fig.update_yaxes(title='Axial load P (kip, compression +)', zeroline=True)
        theme(fig, f'Figure P4 · Prestressed pile P–M interaction (LRFD 5.6.4.5, strain compatibility; bi-axial demand shown as M<sub>res</sub> on the face axis)', 640)
    else:
        Prc, Prt, Mr = v('P_r_comb'), v('P_r_t'), v('M_r')
        env_x = [0, 0.9 * Mr, Mr, 0.9 * Mr, 0]
        env_y = [Prc, 0.2 * Prc, 0, -0.2 * Prt, -Prt]
        fig.add_trace(go.Scatter(x=env_x, y=env_y, mode='lines+markers', line=dict(color=BLUE, width=3), name='Eq. 6.9.2.2.1-1/-2 envelope (Pu/Pr + 8/9 Mu/Mr = 1)',
                                 hoverinfo='x+y'))
        fig.add_trace(go.Scatter(x=[0], y=[v('P_r_axial')], mode='markers', marker=dict(symbol='line-ew', size=16, color=TEAL, line=dict(width=3)),
                                 name=f'φc Pn, axial only = {v("P_r_axial"):.0f} kip (φc = {e.case["inputs"]["phi_c_axial"]:g})'))
        _demand_points(fig, e, colors, labels)
        g = e.governing.get('pipe_comb')
        if g:
            dc = v('DC_comb')
            cap_x, cap_y = (g['M_res'] / dc, g['P_u'] / dc) if dc > 0 else (0.0, 0.0)
            _ray(fig, cap_x, cap_y, 'Ray from the origin through the governing demand')
            fig.add_trace(go.Scatter(x=[g['M_res']], y=[g['P_u']], mode='markers', name='Governing demand',
                                     marker=dict(symbol='star', size=16, color=RED, line=dict(width=1.5, color=INK)), hoverinfo='name+x+y'))
            fig.add_trace(go.Scatter(x=[cap_x], y=[cap_y], mode='markers', name='Capacity on the ray', marker=dict(symbol='circle-open', size=12, color=RED, line=dict(width=2)),
                                     hoverinfo='name+x+y'))
            fig.add_annotation(x=g['M_res'], y=g['P_u'], text=f'<b>Governing</b>: {record_id(g)}<br>P<sub>u</sub> {g["P_u"]:.1f} kip · M<sub>u</sub> {g["M_res"]:.1f} kip-ft · D/C {dc:.3f}',
                               ax=80, ay=-60, showarrow=True, arrowhead=2, arrowcolor=RED, font=dict(size=11, color=RED), align='left', bgcolor='rgba(255,255,255,.85)')
        fig.update_xaxes(range=[0, Mr * 1.15], title='Resultant moment M (kip-ft)')
        fig.update_yaxes(title='Axial load P (kip, compression +)', zeroline=True)
        theme(fig, 'Figure P4 · Steel pipe pile: LRFD 6.9.2.2.1 interaction envelope (φc = %g combined, φf = %g)' % (e.case['inputs']['phi_c_comb'], e.case['inputs']['phi_f']), 640)
    fig.update_layout(legend=dict(orientation='h', y=-.2), margin=dict(l=60, r=25, t=65, b=140))
    return fig


# ----------------------------------------------------------------------------- ratios
def ratios_figure(e):
    checks = [c for c in e.checks if isinstance(c.ratio, (int, float)) and math.isfinite(c.ratio)]
    fig = go.Figure(go.Bar(x=[c.ratio for c in checks], y=[f'{c.group} · {c.label}' for c in checks], orientation='h',
                           marker_color=[RED if 'FAIL' in c.status else GROUP_COLORS.get(c.group, GREY) for c in checks],
                           text=[f'{c.ratio:.3f}' for c in checks], textposition='outside',
                           customdata=[[c.basis, c.status] for c in checks],
                           hovertemplate='%{y}<br>Ratio %{x:.4f}<br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>'))
    fig.add_vline(x=1, line_dash='dash', line_color=AMBER, annotation_text='limit 1.0')
    fig.update_yaxes(autorange='reversed')
    fig.update_xaxes(range=[0, max(1.2, max((c.ratio for c in checks), default=1) * 1.15)], title='Check ratio')
    theme(fig, 'Figure P5 · All numerical check ratios', max(420, 26 * len(checks) + 80))
    fig.update_layout(margin=dict(l=380, r=40, t=60, b=50))
    return fig


FIGURES = [('section', section_figure), ('elevation', elevation_figure), ('profile', demand_profile_figure),
           ('interaction', interaction_figure), ('ratios', ratios_figure)]
