"""Section maps and material-frontier views; data always carry their force mode."""
import plotly.graph_objects as go
from .visuals import theme, BLUE, TEAL, AMBER, GREY

METRICS = {'steel_lb': 'Minimum gross steel (lb)', 'concrete_yd3': 'Gross concrete (yd³)',
           'estimated_cost': 'Estimated comparison cost', 'strength_dc': 'Strength D/C of lightest cage'}


def study_label(study):
    return 'FIXED-FORCE SENSITIVITY' if study.grid['force_mode'] == 'fixed' else 'ANALYSIS-MATCHED CASES · pending checks retained'


def section_heatmap(study, rows, metric='steel_lb'):
    if metric not in METRICS:
        raise ValueError('Unknown map metric.')
    by_size = {(r['width_in'], r['depth_in']): r for r in rows}
    z = [[by_size[w, h][metric] if by_size[w, h]['matches'] else None
          for w in study.grid['widths']] for h in study.grid['depths']]
    units = {'steel_lb': 'lb', 'concrete_yd3': 'yd³', 'estimated_cost': 'Cost', 'strength_dc': 'D/C'}
    fig = go.Figure(go.Heatmap(x=study.grid['widths'], y=study.grid['depths'], z=z,
                             colorscale='Viridis', colorbar=dict(title=units[metric]),
                             hoverinfo='skip', showscale=any(r['matches'] for r in rows)))
    hover = []
    for r in rows:
        if r['matches']:
            value = r[metric]
            detail = f'{METRICS[metric]}: {value:,.3f}<br>{r["matches"]} target-matching cages'
        else:
            detail = r['reason'] if r['state'] not in ('EVALUATED', 'PARTIAL') else 'No explored cage meets the strength target and all available checks.'
        hover.append(f'{r["width_in"]:g} × {r["depth_in"]:g} in<br>{detail}<br>{r["state"]}<br>{study_label(study)}')
    fig.add_trace(go.Scatter(x=[r['width_in'] for r in rows], y=[r['depth_in'] for r in rows],
                            customdata=[r['point_id'] for r in rows], text=hover, mode='markers',
                            marker=dict(size=14, color=['white' if r['matches'] else GREY for r in rows],
                                        symbol=['circle-open' if r['matches'] else 'x' for r in rows], line=dict(width=2)),
                            hovertemplate='%{text}<extra></extra>', showlegend=False))
    fig.add_trace(go.Scatter(x=[], y=[], mode='markers', marker=dict(size=23, color=AMBER, symbol='circle-open', line=dict(width=3)),
                            hoverinfo='skip', showlegend=False))
    fig.update_xaxes(title='Cap width (in)', tickmode='array', tickvals=study.grid['widths'])
    fig.update_yaxes(title='Cap depth (in)', tickmode='array', tickvals=study.grid['depths'])
    theme(fig, 'Click a section marker<br><sup>' + study_label(study) + '</sup>', 450)
    fig.update_layout(margin=dict(l=65, r=65, t=85, b=60))
    return fig


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
    fig.update_layout(margin=dict(l=70, r=25, t=85, b=100), legend=dict(orientation='h', y=-.25, font=dict(size=10)))
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
           xlabel='Cap width (in)', ylabel='Cap depth (in)', title='Lightest target-matching cage at each section')
    for j, h in enumerate(study.grid['depths']):
        for i, w in enumerate(study.grid['widths']):
            row = by_size[w, h]
            text = f'{row["steel_lb"]:,.0f} lb' if row['matches'] else ('Needs\nanalysis' if row['state'] == 'NEEDS ANALYSIS' else 'No match')
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
