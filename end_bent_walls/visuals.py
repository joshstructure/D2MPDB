"""Plotly drawings and result plots for the end-bent wall calculation."""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pier_cap.visuals import theme, BLUE, TEAL, AMBER, RED, INK, GREY
from .model import COMBINATIONS, STRENGTH, SERVICE, wall_diagrams, strap_table

CONCRETE = '#e9eef2'; CONCRETE_LINE = '#5b6f80'; FILL = '#efe3c8'; SOIL_LINE = '#b59a62'
EH_COLOR = '#c98a2b'; ES_COLOR = '#8a6d3b'; LS_COLOR = '#d9b44a'; STRAP = '#7a3e9d'; PILE = '#b8c7d1'
CAPACITY = '#90bce4'; SLACK = '#2166ac'; ENGAGED = '#8250a0'


def _poly(fig, xs, ys, fill, line, hover, name=None, dash=None, legend=False, width=1.4):
    fig.add_trace(go.Scatter(x=list(xs) + [xs[0]], y=list(ys) + [ys[0]], mode='lines', fill='toself', fillcolor=fill,
                             line=dict(color=line, width=width, dash=dash), hoveron='fills+points', text=hover,
                             hoverinfo='text', name=name or hover, showlegend=legend))


def _rect(fig, x0, y0, x1, y1, fill, line, hover, **kw):
    _poly(fig, [x0, x1, x1, x0], [y0, y0, y1, y1], fill, line, hover, **kw)


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


def governing(e, prefix, combos=STRENGTH):
    return max(combos, key=lambda c: e.value(prefix + c['key']))


def section_figure(e):
    v = e.value
    b, h = v('b_cap', 'ft'), v('h_cap', 'ft'); tb, H = v('t_bw', 'ft'), v('H_bw', 'ft')
    emb, ebrg, tol = v('embed_pile', 'ft'), v('e_brg', 'ft'), v('tol_pile', 'ft')
    hped, tpad, lpad = v('h_ped', 'ft'), v('t_pad', 'ft'), v('L_pad', 'ft')
    dp, zs, ts = v('D_pile', 'ft'), v('z_strap', 'ft'), v('t_slab', 'ft')
    rear, front = -b / 2, b / 2
    Hret = h + H
    reach = 5.0
    fig = go.Figure()
    _poly(fig, [rear, rear - reach, rear - reach, rear], [0, 0, Hret, Hret], FILL, FILL,
          'MSE backfill (φ = %.0f°, γ = %.0f pcf)' % (v('phi_soil', 'deg'), 1000 * v('gamma_s', 'kip/ft^3')))
    # Pressure diagram on the loaded rear face (service, unfactored components).
    ka, gs = v('k_a'), v('gamma_s', 'kip/ft^3')
    p_es, p_ls = v('p_ES', 'kip/ft^2'), v('p_LS', 'kip/ft^2')
    scale = 1.8 / (ka * gs * Hret + p_es + p_ls)
    ys = [Hret * i / 20 for i in range(21)]
    eh = [ka * gs * (Hret - y) * scale for y in ys]
    _poly(fig, [rear] * 21 + [rear - x for x in reversed(eh)], ys + list(reversed(ys)), 'rgba(201,138,43,.45)', EH_COLOR,
          f'EH: k_a·γ·z, {ka * gs * Hret * 1000:.0f} psf at the cap soffit', name='EH pressure', legend=True)
    _poly(fig, [rear - x for x in eh] + [rear - x - p_es * scale for x in reversed(eh)], ys + list(reversed(ys)),
          'rgba(138,109,59,.45)', ES_COLOR, f'ES: landing slab surcharge {p_es * 1000:.1f} psf', name='ES pressure', legend=True)
    _poly(fig, [rear - x - p_es * scale for x in eh] + [rear - x - (p_es + p_ls) * scale for x in reversed(eh)],
          ys + list(reversed(ys)), 'rgba(217,180,74,.45)', LS_COLOR, f'LS: pedestrian surcharge {p_ls * 1000:.1f} psf',
          name='LS pressure', legend=True)
    _rect(fig, -dp / 2, -2.6, dp / 2, emb, PILE, CONCRETE_LINE, f'{v("D_pile", "in"):g} in square pile, {v("embed_pile", "in"):g} in embedment')
    _rect(fig, -dp / 2 - tol, -2.6, dp / 2 - tol, emb, 'rgba(0,0,0,0)', RED,
          f'Pile shifted {v("tol_pile", "in"):g} in toward the fill (placement tolerance, SDG 3.13.2.N.3)', dash='dot')
    _rect(fig, rear, 0, front, h, CONCRETE, CONCRETE_LINE, f'Cap {v("b_cap", "in"):g} × {v("h_cap", "in"):g} in')
    _rect(fig, rear, h, rear + tb, h + H, CONCRETE, CONCRETE_LINE, f'Backwall {v("t_bw", "in"):g} in thick, {H:.3f} ft at the crown')
    _rect(fig, rear + tb, h, front, h + hped, '#dde5ec', CONCRETE_LINE, f'Pedestal {v("h_ped", "in"):g} in')
    _rect(fig, ebrg - lpad / 2, h + hped, ebrg + lpad / 2, h + hped + tpad, '#30475e', '#30475e',
          f'Type F pad {v("L_pad", "in"):g} × {v("W_pad", "in"):g} × {v("t_pad", "in"):g} in')
    deck_top = h + H + ts
    beam_top = deck_top - 0.5 - 1 / 12
    beam_end = ebrg - 0.75
    _rect(fig, beam_end, h + hped + tpad, front + 3.6, beam_top, '#f6f8fa', '#7d8b97', 'FIB-36 beam (schematic)')
    _rect(fig, rear + tb + 0.25, beam_top, front + 3.6, deck_top, '#f6f8fa', '#7d8b97', 'Deck, 3 in gap to the backwall (schematic)')
    _rect(fig, rear - reach, h + H, rear + tb, deck_top, '#d7e0e8', CONCRETE_LINE,
          f'Landing slab {v("t_slab", "in"):g} in, bears on the backwall (D-017)')
    ystrap = h + zs
    fig.add_trace(go.Scatter(x=[rear, rear - reach + 0.3], y=[ystrap, ystrap], mode='lines', line=dict(color=STRAP, width=4, dash='dash'),
                             name='Tie-back strap', hoverinfo='text',
                             text=f'Tie-back strap {zs:.2f} ft above the cap top: service {e.text("f_str_s")}, factored {e.text("f_str_u")}'))
    fig.add_annotation(x=rear - reach + 0.2, y=ystrap, ax=rear - reach + 1.4, ay=ystrap, xref='x', yref='y', axref='x', ayref='y',
                       showarrow=True, arrowhead=3, arrowsize=1.2, arrowcolor=STRAP, text='')
    fig.add_annotation(x=rear - 2.6, y=ystrap, text=f'<b>Tie-back</b> {e.text("f_str_u", 2)} factored', showarrow=False,
                       yshift=11, font=dict(color=STRAP, size=11))
    gov = governing(e, 'M_')
    ey = emb + v('e_' + gov['key'], 'ft')
    fig.add_trace(go.Scatter(x=[rear - 0.2, front + 3.6], y=[ey, ey], mode='lines', line=dict(color=RED, width=1.4, dash='dashdot'),
                             name=f'Resultant height ({gov["label"]})', hoverinfo='text',
                             text=f'{gov["label"]}: H = {e.text("H_" + gov["key"], 1)}, M = {e.text("M_" + gov["key"], 1)}, e = {e.text("e_" + gov["key"], 2)} above the pile top'))
    fig.add_annotation(x=front + 1.0, y=ey, ax=front + 2.9, ay=ey, xref='x', yref='y', axref='x', ayref='y', showarrow=True,
                       arrowhead=3, arrowcolor=RED, text='')
    fig.add_annotation(x=front + 2.0, y=ey, text=f'H at e = {v("e_" + gov["key"], "ft"):.2f} ft', showarrow=False, yshift=11,
                       font=dict(color=RED, size=11))
    fig.add_trace(go.Scatter(x=[rear - 0.4, front + 0.6], y=[emb, emb], mode='lines', line=dict(color=INK, width=1, dash='dot'),
                             hoverinfo='text', text='Pile top: moment reference', name='Pile top', showlegend=False))
    fig.add_annotation(x=front + 0.6, y=emb, text='pile top', showarrow=False, xanchor='left', font=dict(size=10))
    _dim_v(fig, rear + tb + 0.15, h, h + H, f'H<sub>bw</sub> = {H:.3f} ft')
    _dim_v(fig, front + 0.12, 0, h, f'{v("h_cap", "in"):g} in')
    _dim_v(fig, -dp / 2 - 0.15, 0, emb, f'{v("embed_pile", "in"):g} in', side='left')
    _dim_v(fig, rear - 0.12, h, ystrap, f'z = {zs:.2f} ft', color=STRAP, side='left')
    fig.add_annotation(x=ebrg, y=h + hped + tpad / 2, ax=36, ay=-30, text=f'bearing e<sub>brg</sub> = {v("e_brg", "in"):g} in',
                       showarrow=True, arrowhead=0, arrowcolor=INK, font=dict(size=10), xanchor='left')
    fig.add_annotation(x=rear - reach / 2, y=-0.35, text='FILL SIDE', showarrow=False, font=dict(color=SOIL_LINE, size=11))
    fig.add_annotation(x=front + 2.2, y=-0.35, text='SPAN SIDE', showarrow=False, font=dict(color=INK, size=11))
    fig.update_xaxes(range=[rear - reach - 0.4, front + 4.0], title='Along the bridge from the nominal pile line (ft)', zeroline=False,
                     constrain='domain')
    fig.update_yaxes(range=[-2.7, deck_top + 0.8], title='Height above the cap soffit (ft)', scaleanchor='x', scaleratio=1, zeroline=False,
                     constrain='domain')
    theme(fig, 'Figure B1 · End-bent section at the backwall crown (pressures to scale, service components)', 620)
    fig.update_layout(legend=dict(orientation='h', y=-.14), margin=dict(l=60, r=25, t=60, b=95))
    return fig


def plan_figure(e):
    v = e.value
    L, b = v('L_load', 'ft'), v('b_cap', 'ft'); tb, Lb = v('t_bw', 'ft'), v('L_bw', 'ft'); tck = v('t_ck', 'ft')
    n, S, dp = int(v('N_pile')), v('S_pile', 'ft'), v('D_pile', 'ft')
    rear, front = -b / 2, b / 2
    fig = go.Figure()
    _rect(fig, 0, rear - 4.0, L, rear, FILL, FILL, 'Landing slab on MSE fill (shown 4 ft)')
    cap0 = (L - v('L_cap', 'ft'))/2
    _rect(fig, cap0, rear, L-cap0, front, CONCRETE, CONCRETE_LINE, f'Core cap {v("L_cap", "in"):g} in; overall {v("L_load", "in"):g} in')
    _rect(fig, (L - Lb) / 2, rear, (L + Lb) / 2, rear + tb, '#cfd9e2', CONCRETE_LINE, f'Backwall {Lb:.3f} ft between cheek walls')
    for x0 in (0, L - tck):
        _rect(fig, x0, rear, x0 + tck, front, '#cfd9e2', CONCRETE_LINE, f'Cheek wall {v("t_ck", "in"):g} in × {v("w_ck", "in"):g} in (wind only)')
    for i in range(n):
        x = L / 2 + (i - (n - 1) / 2) * S
        _rect(fig, x - dp / 2, -dp / 2, x + dp / 2, dp / 2, PILE, CONCRETE_LINE, f'Pile {i + 1} at {x:.2f} ft')
        _rect(fig, x - dp / 2, -dp / 2 - v('tol_pile', 'ft'), x + dp / 2, dp / 2 - v('tol_pile', 'ft'), 'rgba(0,0,0,0)', RED,
              'Pile shifted toward the fill by the placement tolerance', dash='dot')
    for x in e.cap['stations']:
        x_ft = x / 12
        _rect(fig, x_ft - v('W_pad', 'ft') / 2, v('e_brg', 'ft') - v('L_pad', 'ft') / 2, x_ft + v('W_pad', 'ft') / 2,
              v('e_brg', 'ft') + v('L_pad', 'ft') / 2, '#30475e', '#30475e', f'Bearing at {x_ft:.2f} ft')
        fig.add_trace(go.Scatter(x=[x_ft, x_ft], y=[v('e_brg', 'ft'), front + 3], mode='lines', line=dict(color='#7d8b97', width=6),
                                 hoverinfo='text', text='FIB-36 beam', showlegend=False))
    count = max(2, int(Lb // 2.5))
    for i in range(count):
        x = (L - Lb) / 2 + (i + 0.5) * Lb / count
        fig.add_trace(go.Scatter(x=[x, x], y=[rear, rear - 3.6], mode='lines', line=dict(color=STRAP, width=2, dash='dash'),
                                 hoverinfo='text', text='Tie-back strap (schematic; layout by the Specialty Engineer)',
                                 showlegend=i == 0, name='Tie-back straps (schematic)'))
    fig.add_annotation(x=L / 2, y=rear - 4.3, text='FILL / LANDING', showarrow=False, font=dict(color=SOIL_LINE))
    fig.add_annotation(x=L / 2, y=front + 3.3, text='SPAN', showarrow=False)
    fig.update_xaxes(title='Along the cap (ft)', range=[-1, L + 1], constrain='domain')
    fig.update_yaxes(title='Along the bridge (ft)', scaleanchor='x', range=[rear - 4.8, front + 3.7], constrain='domain')
    theme(fig, 'Figure B2 · End-bent plan: piles, bearings, walls and strap zone', 470)
    return fig


def waterfall_figure(e, combo_key=None):
    combo = next(c for c in COMBINATIONS if c['key'] == (combo_key or governing(e, 'M_')['key']))
    rows = [r for r in strap_table(e, combo['key']) if r['factor']]
    fig = make_subplots(rows=1, cols=2, column_widths=[.64, .36], horizontal_spacing=.1,
                        subplot_titles=('Factored overturning moment about the pile top (kip-ft)', 'Factored horizontal force toward the span (kip)'))
    fig.add_trace(go.Waterfall(x=[r['label'] for r in rows] + ['M total'],
                               y=[r['factored_moment'] for r in rows] + [0], measure=['relative'] * len(rows) + ['total'],
                               text=[f'{r["factored_moment"]:.1f}' for r in rows] + [f'{e.value("M_" + combo["key"]):.1f}'],
                               textposition='outside', increasing=dict(marker=dict(color=AMBER)), decreasing=dict(marker=dict(color=TEAL)),
                               totals=dict(marker=dict(color=BLUE)), connector=dict(line=dict(color='#9aa8b4', width=1)),
                               customdata=[[r['factor'], r['force_kip'], r['arm_ft'], r['basis']] for r in rows] + [[None, None, None, 'sum']],
                               hovertemplate='%{x}<br>γ = %{customdata[0]}<br>Force %{customdata[1]:.2f} kip × arm %{customdata[2]:.3f} ft'
                                             '<br>%{customdata[3]}<br>Factored %{y:.2f} kip-ft<extra></extra>', name='Moment'), row=1, col=1)
    horizontal = [r for r in rows if r['kind'] == 'H']
    fig.add_trace(go.Waterfall(x=[r['label'] for r in horizontal] + ['H total'], y=[r['factored_force'] for r in horizontal] + [0],
                               measure=['relative'] * len(horizontal) + ['total'],
                               text=[f'{r["factored_force"]:.1f}' for r in horizontal] + [f'{e.value("H_" + combo["key"]):.1f}'],
                               textposition='outside', increasing=dict(marker=dict(color=AMBER)), totals=dict(marker=dict(color=BLUE)),
                               connector=dict(line=dict(color='#9aa8b4', width=1)), name='Horizontal'), row=1, col=2)
    fig.update_xaxes(tickangle=-35)
    theme(fig, f'Figure B3 · {combo["label"]}: overturning contributions (amber overturns, teal stabilizes)', 520)
    fig.update_layout(showlegend=False, margin=dict(l=55, r=25, t=80, b=150))
    return fig


def strap_figure(e):
    labels = [c['label'] for c in COMBINATIONS]
    Lb = e.value('L_bw', 'ft')
    fig = make_subplots(rows=1, cols=2, column_widths=[.55, .45], horizontal_spacing=.12,
                        subplot_titles=('Tie-back load per foot of backwall (klf)', 'Resultant height vs strap elevation (ft above the pile top)'))
    for name, prefix, color in (('Horizontal force H / L<sub>bw</sub>', 'H_', '#9fb3c8'),
                                ('Moment equilibrium M / (y·L<sub>bw</sub>)', 'F_eq_', '#c4a4d8'),
                                ('Design strap load', 'F_str_', STRAP)):
        fig.add_trace(go.Bar(x=labels, y=[e.value(prefix + c['key'], 'kip') / Lb for c in COMBINATIONS], name=name, marker_color=color,
                             text=[f'{e.value(prefix + c["key"], "kip") / Lb:.2f}' for c in COMBINATIONS], textposition='outside'), row=1, col=1)
    fig.add_trace(go.Bar(x=labels, y=[e.value('e_' + c['key'], 'ft') for c in COMBINATIONS], name='Resultant height e', marker_color=RED,
                         opacity=.75, text=[f'{e.value("e_" + c["key"], "ft"):.2f}' for c in COMBINATIONS], textposition='outside'), row=1, col=2)
    for y, text, color, dash in ((e.value('y_strap', 'ft'), 'strap', STRAP, 'dash'), (e.value('y_top', 'ft'), 'cap top', INK, 'dot'),
                                 (e.value('y_top', 'ft') + e.value('H_bw_edge', 'ft'), 'backwall top (edge)', GREY, 'dot')):
        fig.add_hline(y=y, line_dash=dash, line_color=color, annotation_text=text, annotation_position='top left', row=1, col=2)
    fig.update_xaxes(tickangle=-25)
    theme(fig, 'Figure B4 · Tie-back strap loads; a strap at the resultant height makes the pile-head force zero', 470)
    fig.update_layout(barmode='group', legend=dict(orientation='h', y=-.32), margin=dict(l=55, r=25, t=80, b=120))
    return fig


def backwall_figure(e):
    slack = governing(e, 'M_sl_'); engaged = governing(e, 'M_en_')
    rs, re_ = wall_diagrams(e, slack['key']), wall_diagrams(e, engaged['key'])
    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=.05,
                        subplot_titles=('Factored pressure (ksf)', 'Shear per ft (kip)', 'Moment per ft (kip-ft) · + = span-face tension'))
    z = [r['z'] for r in rs]
    fig.add_trace(go.Scatter(x=[r['pressure'] for r in rs], y=z, mode='lines', fill='tozerox', line=dict(color=EH_COLOR),
                             name=f'Pressure, {slack["label"]}'), row=1, col=1)
    for rows, combo, color, state in ((rs, slack, SLACK, 'slack'), (re_, engaged, ENGAGED, 'eng')):
        label = ('Strap slack · ' if state == 'slack' else 'Strap engaged · ') + combo['label']
        fig.add_trace(go.Scatter(x=[r['V_' + state] for r in rows], y=z, mode='lines', line=dict(color=color, width=2.5), name=label,
                                 legendgroup=state, showlegend=False), row=1, col=2)
        fig.add_trace(go.Scatter(x=[r['M_' + state] for r in rows], y=z, mode='lines', line=dict(color=color, width=2.5), name=label,
                                 legendgroup=state), row=1, col=3)
    for x, text in ((-e.value('M_r_FF'), 'φMn fill face'), (e.value('M_r_SF'), 'φMn span face')):
        fig.add_trace(go.Scatter(x=[x, x], y=[0, z[-1]], mode='lines', line=dict(color=CAPACITY, width=3), name=text), row=1, col=3)
    fig.add_hline(y=e.value('z_strap', 'ft'), line_dash='dash', line_color=STRAP, annotation_text='strap', row=1, col=3)
    fig.update_yaxes(title='Height above the construction joint (ft)', row=1, col=1)
    theme(fig, 'Figure B5 · Backwall demands per 1-ft strip, both strap states', 470)
    fig.update_layout(legend=dict(orientation='h', y=-.18))
    return fig


def cheek_figure(e):
    H, p, mr = e.value('H_ck', 'ft'), e.value('P_Z_III', 'kip/ft^2'), e.value('M_r_CK')
    z = [H * i / 50 for i in range(51)]
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, subplot_titles=('Strength III wind pressure (ksf)', 'Moment per ft (kip-ft), either face'))
    fig.add_trace(go.Scatter(x=[p] * len(z), y=z, mode='lines', fill='tozerox', line=dict(color=TEAL), name='Wind pressure'), row=1, col=1)
    fig.add_trace(go.Scatter(x=[p * (H - zz) ** 2 / 2 for zz in z], y=z, mode='lines', line=dict(color=SLACK, width=2.5), name='Mu'), row=1, col=2)
    for x in (-mr, mr):
        fig.add_trace(go.Scatter(x=[x, x], y=[0, H], mode='lines', line=dict(color=CAPACITY, width=3), name='φMn', showlegend=x > 0), row=1, col=2)
    fig.update_yaxes(title='Height above the cap top (ft)', row=1, col=1)
    theme(fig, 'Figure B6 · Cheek wall wind demand (no retained fill, D-018)', 380)
    return fig


def cap_figure(e):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.12,
                        subplot_titles=('Cap torsion from walls, eccentric bearings and uniform strap restraint (kip-ft)',
                                        'Cap weak-axis (horizontal) moment (kip-ft)'))
    colors = [BLUE, '#4b8fc6', TEAL, AMBER]
    for color, c in zip(colors, STRENGTH):
        r = e.cap['by_combo'][c['key']]
        x = [xi / 12 for xi in r['x_in']]
        fig.add_trace(go.Scatter(x=x, y=r['torsion'], mode='lines', line=dict(color=color, width=2), name=c['label'], legendgroup=c['key']), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=r['weak_moment'], mode='lines', line=dict(color=color, width=2), name=c['label'],
                                 legendgroup=c['key'], showlegend=False), row=2, col=1)
    lim = e.value('T_lim')
    for y in (lim, -lim):
        fig.add_hline(y=y, line_dash='dash', line_color=RED, annotation_text='0.25 φ Tcr' if y > 0 else '', row=1, col=1)
    for x in e.cap['stations']:
        fig.add_vline(x=x / 12, line_dash='dot', line_color=GREY)
    fig.update_xaxes(title='Along the cap (ft)', row=2, col=1)
    theme(fig, 'Figure B7 · Cap supplement: actions not in the FBMP model (dotted lines = bearings)', 560)
    return fig


def reinforcement_figure(e):
    v = e.value
    fig = make_subplots(rows=1, cols=2, column_widths=[.55, .45], subplot_titles=('Backwall section', 'Cheek wall section'))
    for col, t, H, cv, vert, horiz, s_h, label in ((1, v('t_bw', 'in'), v('H_bw', 'in'), v('cv_bw', 'in'), ('FF', 'SF'), 'HZ', v('s_HZ', 'in'), 'Backwall'),
                                                   (2, v('t_ck', 'in'), v('H_ck', 'in'), v('cv_ck', 'in'), ('CK', 'CK'), 'CKH', v('s_CKH', 'in'), 'Cheek wall')):
        xs = [0, t, t, 0, 0]
        fig.add_trace(go.Scatter(x=xs, y=[0, 0, H, H, 0], fill='toself', fillcolor=CONCRETE, line=dict(color=CONCRETE_LINE), hoverinfo='text',
                                 text=f'{label} {t:g} in thick', showlegend=False), row=1, col=col)
        fig.add_trace(go.Scatter(x=[-6, t + 6, t + 6, -6, -6], y=[-18, -18, 0, 0, -18], fill='toself', fillcolor='#f2f5f7',
                                 line=dict(color=CONCRETE_LINE, dash='dot'), hoverinfo='text', text='Cap (top)', showlegend=False), row=1, col=col)
        single = label == 'Cheek wall' and bool(v('single_ck'))
        layers = [(0, 'CK')] if single else list(zip((0, 1), vert))
        for side, tag in layers:
            db = v('d_b_' + tag, 'in')
            x = cv + db / 2 if side == 0 else t - cv - db / 2
            bar = int(e.case['inputs']['bar_' + tag])
            spacing = e.case['inputs']['s_' + tag]
            if single:
                x = t/2 - v('d_b_CKH', 'in')/2
            face = ('fill face' if side == 0 else 'span face') if label == 'Backwall' else 'single centered mat' if single else 'each face'
            fig.add_trace(go.Scatter(x=[x, x], y=[cv if single else -16, H - cv], mode='lines', line=dict(color=BLUE, width=3), hoverinfo='text',
                                     text=f'#{bar} @ {spacing:g} in vertical, {face}', showlegend=False), row=1, col=col)
        dh = v('d_b_' + horiz, 'in')
        count = int((H - 2 * cv) // s_h) + 1
        for side, tag in layers:
            db = v('d_b_' + tag, 'in')
            x = cv + db + dh / 2 if side == 0 else t - cv - db - dh / 2
            if single:
                x = t/2 + db/2
            ys = [cv + 2 + i * s_h for i in range(count) if cv + 2 + i * s_h < H - cv]
            fig.add_trace(go.Scatter(x=[x] * len(ys), y=ys, mode='markers', marker=dict(size=7, color=TEAL), hoverinfo='text',
                                     text=f'#{int(e.case["inputs"]["bar_" + horiz])} @ {s_h:g} in horizontal', showlegend=False), row=1, col=col)
        shown_cover = v('cover_ck_actual', 'in') if single else cv
        fig.add_annotation(x=t / 2, y=H + 3, text=f'{t:g} in · physical cover {shown_cover:g} in', showarrow=False, row=1, col=col)
        left, right = ('FILL FACE', 'SPAN FACE') if label == 'Backwall' else ('WIND EITHER FACE', '')
        fig.add_annotation(x=0, y=H / 2, text=left, textangle=-90, showarrow=False, xshift=-16, font=dict(size=10, color=SOIL_LINE), row=1, col=col)
        if right:
            fig.add_annotation(x=t, y=H / 2, text=right, textangle=-90, showarrow=False, xshift=16, font=dict(size=10, color=INK), row=1, col=col)
        fig.update_xaxes(range=[-8, max(t, 12) + 8], title='in', row=1, col=col)
        fig.update_yaxes(range=[-20, max(v('H_bw', 'in'), v('H_ck', 'in')) + 8], row=1, col=col)
    fig.update_yaxes(title='Height above the cap top (in)', scaleanchor='x', row=1, col=1)
    fig.update_yaxes(scaleanchor='x2', row=1, col=2)
    layout_label = 'single centered mat' if v('single_ck') == 1 else 'legacy two faces'
    theme(fig, f'Figure B8 · Backwall two faces; cheek {layout_label} (anchorage pending)', 560)
    return fig


def ratios_figure(e):
    checks = [c for c in e.checks if isinstance(c.ratio, (int, float))]
    group_color = {'Backwall': BLUE, 'Cheek walls': TEAL, 'Tie-back straps': STRAP, 'Cap supplement': AMBER}
    fig = go.Figure(go.Bar(x=[c.ratio for c in checks], y=[f'{c.group} · {c.label}' for c in checks], orientation='h',
                           marker_color=[RED if 'FAIL' in c.status else group_color.get(c.group, GREY) for c in checks],
                           text=[f'{c.ratio:.3f}' for c in checks], textposition='outside',
                           customdata=[[c.basis, c.status] for c in checks],
                           hovertemplate='%{y}<br>Ratio %{x:.4f}<br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>'))
    fig.add_vline(x=1, line_dash='dash', line_color=AMBER, annotation_text='limit 1.0')
    fig.update_yaxes(autorange='reversed')
    fig.update_xaxes(range=[0, max(1.2, max((c.ratio for c in checks), default=1) * 1.15)], title='Check ratio')
    theme(fig, 'Figure B9 · All numerical check ratios', max(420, 26 * len(checks) + 80))
    fig.update_layout(margin=dict(l=330, r=40, t=60, b=50))
    return fig


FIGURES = [('section', section_figure), ('plan', plan_figure), ('waterfall', waterfall_figure), ('strap', strap_figure),
           ('backwall', backwall_figure), ('cheek', cheek_figure), ('cap', cap_figure), ('reinforcement', reinforcement_figure),
           ('ratios', ratios_figure)]
