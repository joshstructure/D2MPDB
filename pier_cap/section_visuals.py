"""Section maps and material-frontier views; data always carry their force mode."""
import html
import plotly.graph_objects as go
from .sections import ranked_cost_rows
from .visuals import theme, BLUE, TEAL, AMBER, GREY

METRICS = {'steel_lb': 'Minimum gross steel (lb)', 'concrete_yd3': 'Gross concrete (yd³)',
           'cost_premium_pct': 'Cost above cheapest (%)', 'estimated_cost': 'Estimated total cost',
           'strength_dc': 'Strength D/C of lightest cage'}
COST_METRICS = {'estimated_cost', 'cost_premium_pct'}
COST_PARTS = [('concrete_cost', 'Concrete', '#64748b'), ('steel_cost', 'Steel', BLUE), ('form_cost', 'Forms', AMBER)]


def study_label(study):
    return 'FIXED-FORCE SENSITIVITY' if study.grid['force_mode'] == 'fixed' else 'ANALYSIS-MATCHED CASES · pending checks retained'


def _breakdown(row):
    text = f'Concrete: {row["concrete_yd3"]:.3f} yd³<br>Steel: {row["steel_lb"]:,.0f} lb<br>Forms: {row["form_ft2"]:,.1f} ft²'
    if row['estimated_cost'] is not None:
        text += '<br><br>' + '<br>'.join(f'{label} cost: {row[key]:,.2f}' for key, label, _ in COST_PARTS)
        text += f'<br><b>Total: {row["estimated_cost"]:,.2f}</b>'
        premium = row['cost_premium_pct']
        gap = f' · +{premium:.1f}%' if premium is not None else ''
        text += '<br>Lowest explored cost' if row['lowest_cost'] else f'<br>Above cheapest: +{row["cost_difference"]:,.2f}{gap}'
    return text


def section_heatmap(study, rows, metric='steel_lb', labels='quantities'):
    if metric not in METRICS:
        raise ValueError('Unknown map metric.')
    if labels not in ('quantities', 'costs', 'none'):
        raise ValueError('Unknown cell label choice.')
    if (metric in COST_METRICS or labels == 'costs') and any(r['matches'] and r['estimated_cost'] is None for r in rows):
        raise ValueError('Enable comparison costs and enter rates to show costs.')
    by_size = {(r['width_in'], r['depth_in']): r for r in rows}
    z = [[by_size[w, h][metric] if by_size[w, h]['matches'] else None
          for w in study.grid['widths']] for h in study.grid['depths']]
    units = {'steel_lb': 'lb', 'concrete_yd3': 'yd³', 'estimated_cost': 'Cost', 'cost_premium_pct': '% above<br>cheapest', 'strength_dc': 'D/C'}
    visible_labels = labels != 'none' and len(rows) <= 36 and len(study.grid['widths']) <= 4 and len(study.grid['depths']) <= 12
    def cell_text(row):
        if not row['matches']:
            return 'No match' if row['state'] in ('EVALUATED', 'PARTIAL') else row['state'].title()
        if labels == 'costs':
            return f'C {row["concrete_cost"]:,.0f} · S {row["steel_cost"]:,.0f}<br>F {row["form_cost"]:,.0f}<br><b>Total {row["estimated_cost"]:,.0f}</b>'
        text = f'C {row["concrete_yd3"]:.2f} yd³<br>S {row["steel_lb"]:,.0f} lb'
        if row['estimated_cost'] is not None:
            premium = row['cost_premium_pct']
            text += '<br><b>Lowest cost</b>' if row['lowest_cost'] else (f'<br>Cost +{premium:.1f}%' if premium is not None else '')
        return text
    cell_labels = [[cell_text(by_size[w, h]) for w in study.grid['widths']] for h in study.grid['depths']]
    fig = go.Figure(go.Heatmap(x=study.grid['widths'], y=study.grid['depths'], z=z,
                             colorscale=[[0, '#d1eee5'], [0.5, '#f8edc4'], [1, '#e5b596']], colorbar=dict(title=units[metric]),
                             text=cell_labels, texttemplate='%{text}' if visible_labels else None, textfont=dict(size=11, color='#213649'),
                             xgap=2, ygap=2, hoverinfo='skip', showscale=any(r['matches'] for r in rows)))
    hover = []
    priced = ranked_cost_rows(rows)
    baseline = priced[0] if priced else None
    for r in rows:
        if r['matches']:
            value = r[metric]
            metric_value = f'{value:,.3f}' if value is not None else 'Undefined at zero baseline'
            detail = f'{METRICS[metric]}: {metric_value}<br><br>{_breakdown(r)}<br><br>{r["matches"]} target-matching cages<br>Strength D/C {r["strength_dc"]:.3f}'
            if baseline is not None and r['point_id'] != baseline['point_id']:
                detail += f'<br><br>Versus cheapest {baseline["width_in"]:g} × {baseline["depth_in"]:g} in:'
                detail += f'<br>Concrete {r["concrete_yd3"] - baseline["concrete_yd3"]:+.3f} yd³ · steel {r["steel_lb"] - baseline["steel_lb"]:+,.0f} lb'
                detail += '<br>' + ' · '.join(f'{label} cost {r[key] - baseline[key]:+,.2f}' for key, label, _ in COST_PARTS)
        else:
            detail = r['reason'] if r['state'] not in ('EVALUATED', 'PARTIAL') else 'No explored cage meets the strength target and all available checks.'
        hover.append(f'{r["width_in"]:g} × {r["depth_in"]:g} in<br>{detail}<br>{r["state"]}<br>{study_label(study)}')
    # Both the cell and its marker expose the same material/cost breakdown.
    fig.data[0].customdata = [[hover[by_size[w, h]['point_id']] for w in study.grid['widths']] for h in study.grid['depths']]
    fig.data[0].hoverinfo = None
    fig.data[0].hovertemplate = '%{customdata}<extra></extra>'
    fig.add_trace(go.Scatter(x=[r['width_in'] for r in rows], y=[r['depth_in'] for r in rows],
                            customdata=[r['point_id'] for r in rows], text=hover, mode='markers',
                            marker=dict(size=14, color=[GREY if not r['matches'] else 'rgba(0,0,0,0)' if visible_labels else 'white' for r in rows],
                                        symbol=['circle-open' if r['matches'] else 'x' for r in rows], line=dict(width=2)),
                            hovertemplate='%{text}<extra></extra>', showlegend=False))
    fig.add_trace(go.Scatter(x=[], y=[], mode='markers', marker=dict(size=23, color=AMBER, symbol='circle-open', line=dict(width=3)),
                            hoverinfo='skip', showlegend=False))
    fig.update_xaxes(title='Cap width (in)', tickmode='array', tickvals=study.grid['widths'])
    fig.update_yaxes(title='Cap depth (in)', tickmode='array', tickvals=study.grid['depths'])
    title = METRICS[metric] + (' · lower is cheaper' if metric in COST_METRICS else '')
    height = max(450, 175 + 62 * len(study.grid['depths'])) if visible_labels else 450
    theme(fig, title + '<br><sup>' + study_label(study) + '</sup>', height)
    note = 'C = concrete · S = steel · F = forms. Click a cell; hover for the full breakdown.'
    if not visible_labels and labels != 'none':
        note = 'Dense grid: hover for concrete, steel, forms and cost breakdown.'
    fig.add_annotation(x=0, y=-.18, xref='paper', yref='paper', xanchor='left', text=note, showarrow=False, font=dict(size=10))
    fig.update_layout(width=600, margin=dict(l=65, r=80, t=85, b=100))
    return fig


def highlight_section(fig, study, rows, point_id):
    """Outline cells without covering the concrete/steel labels."""
    def edges(values, value):
        index = values.index(value)
        before = (value - values[index - 1]) / 2 if index else ((values[1] - value) / 2 if len(values) > 1 else .5)
        after = (values[index + 1] - value) / 2 if index + 1 < len(values) else before
        return value - before, value + after
    shapes = []
    marked = [(r, TEAL, 'solid') for r in rows if r['lowest_cost']]
    if point_id is not None:
        marked.append((rows[point_id], AMBER, 'dash'))
    for row, color, dash in marked:
        left, right = edges(study.grid['widths'], row['width_in'])
        bottom, top = edges(study.grid['depths'], row['depth_in'])
        dx, dy = (right - left) * .025, (top - bottom) * .04
        shapes.append(dict(type='rect', x0=left + dx, x1=right - dx, y0=bottom + dy, y1=top - dy,
                           line=dict(color=color, width=3, dash=dash), fillcolor='rgba(0,0,0,0)'))
    fig.update_layout(shapes=shapes)


def section_cost_chart(study, rows, selected=None, limit=10):
    ranked = ranked_cost_rows(rows)
    shown = ranked[:limit]
    extra = next((r for r in ranked[limit:] if r['point_id'] == selected), None)
    if extra:
        shown = [*shown, extra]
    names = [f'#{r["cost_rank"]} · {r["width_in"]:g}×{r["depth_in"]:g}' + (' ◀' if r['point_id'] == selected else '') for r in shown]
    fig = go.Figure()
    for key, label, color in COST_PARTS:
        fig.add_trace(go.Bar(x=[r[key] for r in shown], y=names, orientation='h', name=label,
                            customdata=[r['point_id'] for r in shown], marker=dict(color=color),
                            text=[_breakdown(r) for r in shown], textposition='none',
                            hovertemplate='%{y} in<br>%{text}<extra>%{fullData.name}</extra>'))
    labels = []
    for r in shown:
        suffix = 'lowest' if r['lowest_cost'] else f'+{r["cost_premium_pct"]:.1f}%' if r['cost_premium_pct'] is not None else 'above zero baseline'
        labels.append(f'{r["estimated_cost"]:,.0f} · {suffix}')
    fig.add_trace(go.Scatter(x=[r['estimated_cost'] for r in shown], y=names, mode='text',
                            text=labels, textposition='middle right', customdata=[r['point_id'] for r in shown],
                            textfont=dict(size=11), cliponaxis=False, hoverinfo='skip', showlegend=False))
    fig.update_xaxes(title='Estimated cost per cap · your currency', rangemode='tozero')
    fig.update_yaxes(autorange='reversed', categoryorder='array', categoryarray=names, title='Width × depth (in)')
    theme(fig, 'Cost ranking · shortest total is cheapest<br><sup>' + study_label(study) + '</sup>', max(450, 180 + len(shown) * 31))
    fig.update_layout(width=600, barmode='stack', margin=dict(l=120, r=125, t=85, b=115),
                      legend=dict(orientation='h', y=-.22, traceorder='normal', itemclick=False, itemdoubleclick=False))
    fig.add_annotation(x=0, y=-.36, xref='paper', yref='paper', xanchor='left', showarrow=False, font=dict(size=10),
                       text=f'Showing {len(shown)} of {len(ranked)} priced sections. All appear in the table. Click a bar to select.')
    return fig


def cost_summary_html(study, rows, rates):
    ranked = ranked_cost_rows(rows)
    if not ranked:
        return '<p>No explored cage meets the current target; no cost winner can be identified.</p>'
    best = ranked[0]
    tied = sum(r['lowest_cost'] for r in ranked)
    heading = 'Lowest estimated cost among explored matches' + (f' · {tied} tied sections' if tied > 1 else '')
    text = f'<div style="border:2px solid {TEAL};border-radius:8px;padding:14px;margin:8px 0"><b>{heading}</b>'
    text += f'<div style="font-size:23px;margin:5px 0">{best["width_in"]:g} × {best["depth_in"]:g} in · {best["estimated_cost"]:,.2f} per cap</div>'
    parts = []
    for key, label, color in COST_PARTS:
        share = f' ({100 * best[key] / best["estimated_cost"]:.1f}%)' if best['estimated_cost'] else ''
        parts.append(f'<span style="color:{color}">{label}: <b>{best[key]:,.2f}</b>{share}</span>')
    text += ' &nbsp; | &nbsp; '.join(parts)
    runner = next((r for r in ranked if not r['lowest_cost']), None)
    if runner:
        text += f'<p>Next higher cost: {runner["width_in"]:g} × {runner["depth_in"]:g} in adds <b>{runner["cost_difference"]:,.2f}</b>'
        if runner['cost_premium_pct'] is not None:
            text += f' ({runner["cost_premium_pct"]:.1f}%)'
        text += ' per cap.</p>'
    excluded = [name for name, value in [('concrete', rates.concrete_per_yd3), ('steel', rates.steel_per_lb), ('forms', rates.form_per_ft2)] if value == 0]
    text += f'<small>Entered rates: concrete {rates.concrete_per_yd3:g}/yd³ · steel {rates.steel_per_lb:g}/lb · forms {rates.form_per_ft2:g}/ft². All costs use your currency.'
    if excluded:
        text += '<br><b>Zero-rate items excluded: ' + ', '.join(excluded) + '.</b>'
    text += '<br>Cheapest within explored choices and the current strength target; pending checks remain.'
    if not study.exhaustive:
        text += ' <b>Search coverage is incomplete.</b>'
    return text + '</small></div>'


def cost_table_html(rows):
    ranked = ranked_cost_rows(rows)
    if not ranked:
        return '<p>No priced target-matching sections.</p>'
    headers = ['Rank', 'Width × depth (in)', 'Concrete yd³', 'Steel lb', 'Concrete cost', 'Steel cost', 'Forms cost', 'Total / cap', 'Extra / cap', 'Extra %', 'Strength D/C', 'Search']
    text = '<div style="overflow:auto;max-height:360px"><table style="border-collapse:collapse;width:100%;font-size:12px"><thead><tr>'
    text += ''.join(f'<th style="padding:7px;text-align:right;position:sticky;top:0;background:#edf3f6">{name}</th>' for name in headers) + '</tr></thead><tbody>'
    for r in ranked:
        values = [str(r['cost_rank']), f'{r["width_in"]:g} × {r["depth_in"]:g}', f'{r["concrete_yd3"]:.3f}', f'{r["steel_lb"]:,.0f}',
                  *(f'{r[k]:,.2f}' for k in ('concrete_cost', 'steel_cost', 'form_cost', 'estimated_cost', 'cost_difference')),
                  f'{r["cost_premium_pct"]:.1f}%' if r['cost_premium_pct'] is not None else '—', f'{r["strength_dc"]:.3f}', r['state']]
        text += '<tr style="background:' + ('#e4f3ed' if r['lowest_cost'] else 'white') + '">' + ''.join(f'<td style="padding:7px;text-align:right;border-bottom:1px solid #dde5ea">{html.escape(v)}</td>' for v in values) + '</tr>'
    return text + '</tbody></table></div>'


def section_pareto(study, rows):
    feasible = [r for r in rows if r['matches']]
    front = sorted((r for r in feasible if r['pareto']), key=lambda r: r['concrete_yd3'])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[r['concrete_yd3'] for r in feasible], y=[r['steel_lb'] for r in feasible],
                            mode='markers', name='Best cage at each explored section',
                            marker=dict(size=11, color=BLUE), customdata=[r['point_id'] for r in feasible],
                            text=[f'{r["width_in"]:g} × {r["depth_in"]:g} in · strength D/C {r["strength_dc"]:.3f}' for r in feasible],
                            hovertemplate='%{text}<br>%{x:.2f} yd³ concrete<br>%{y:,.0f} lb gross steel<extra></extra>'))
    fig.add_trace(go.Scatter(x=[r['concrete_yd3'] for r in front], y=[r['steel_lb'] for r in front],
                            mode='markers+lines', name='Observed material frontier',
                            line=dict(color=TEAL, dash='dash'), marker=dict(size=12, symbol='diamond'),
                            customdata=[r['point_id'] for r in front],
                            text=[f'{r["width_in"]:g} × {r["depth_in"]:g} in' for r in front],
                            hovertemplate='%{text}<br>%{x:.2f} yd³ concrete<br>%{y:,.0f} lb gross steel<extra></extra>'))
    fig.update_xaxes(title='Gross concrete (yd³)')
    fig.update_yaxes(title='Minimum gross steel meeting target (lb)')
    theme(fig, 'Concrete / steel tradeoffs<br><sup>' + study_label(study) + '</sup>', 450)
    fig.update_layout(width=600, margin=dict(l=70, r=25, t=85, b=100), legend=dict(orientation='h', y=-.25, font=dict(size=10)))
    return fig


def section_snapshot(study, rows):
    """Static GitHub preview; the workbench uses clickable Plotly figures."""
    import numpy as np
    import matplotlib.pyplot as plt
    by_size = {(r['width_in'], r['depth_in']): r for r in rows}
    values = np.array([[by_size[w, h]['steel_lb'] if by_size[w, h]['matches'] else np.nan
                        for w in study.grid['widths']] for h in study.grid['depths']])
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.3), layout='constrained')
    ax = axes[0]
    image = ax.imshow(np.ma.masked_invalid(values), origin='lower', aspect='auto', cmap='viridis')
    ax.set(xticks=range(len(study.grid['widths'])), xticklabels=study.grid['widths'],
           yticks=range(len(study.grid['depths'])), yticklabels=study.grid['depths'],
           xlabel='Cap width (in)', ylabel='Cap depth (in)', title='Concrete + steel required at each section')
    for j, h in enumerate(study.grid['depths']):
        for i, w in enumerate(study.grid['widths']):
            row = by_size[w, h]
            text = f'{row["concrete_yd3"]:.2f} yd³\n{row["steel_lb"]:,.0f} lb' if row['matches'] else ('Needs\nanalysis' if row['state'] == 'NEEDS ANALYSIS' else 'No match')
            ax.text(i, j, text, ha='center', va='center', color='white' if row['matches'] else '#34495e', fontsize=10,
                    bbox=dict(facecolor='#25364b', alpha=.65, edgecolor='none', pad=2) if row['matches'] else None)
    if np.isfinite(values).any():
        fig.colorbar(image, ax=ax, label='Gross steel (lb)', shrink=.8)
    ax = axes[1]
    valid = [r for r in rows if r['matches']]
    front = sorted((r for r in valid if r['pareto']), key=lambda r: r['concrete_yd3'])
    ax.scatter([r['concrete_yd3'] for r in valid], [r['steel_lb'] for r in valid], color=BLUE, label='Explored sections')
    ax.plot([r['concrete_yd3'] for r in front], [r['steel_lb'] for r in front], 'D--', color=TEAL, label='Observed frontier')
    for r in valid:
        ax.annotate(f'{r["width_in"]:g}×{r["depth_in"]:g}', (r['concrete_yd3'], r['steel_lb']), xytext=(4, 5), textcoords='offset points', fontsize=8)
    ax.set(xlabel='Gross concrete (yd³)', ylabel='Gross steel (lb)', title='Concrete / steel tradeoff')
    ax.legend(fontsize=8)
    fig.suptitle(study_label(study) + '\nAvailable checks only · single outer hoop · no new force analysis', fontsize=12)
    return fig
