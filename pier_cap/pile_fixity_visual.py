"""Labels shared by displacement plots, minimum-tip review and exports."""
import html
import plotly.graph_objects as go
from .pile_fixity import governor_label


def mark_fixity(fig, fixity, combo, piles, result=None):
    cutoff = fixity['cutoff_elevation_ft']
    for profile in fixity['profiles']:
        if profile['combination'] != combo or profile['pile'] not in piles: continue
        for crossing in profile['crossings'][:2]:
            second = crossing['number']==2
            y = crossing['distance_ft'] if cutoff is None else cutoff-crossing['vertical_ft']
            label = governor_label(profile)
            fig.add_trace(go.Scatter(x=[0], y=[y], mode='markers', showlegend=False,
                name=('Second' if second else 'First')+' zero crossing', legendgroup=profile['pile'],
                meta=dict(part='fixity'), marker=dict(size=12 if second else 8, symbol='diamond' if second else 'circle-open',
                    color='#b34e00' if second else '#384858', line=dict(width=1, color='white')),
                hovertemplate=html.escape(label)+f'<br>Zero crossing {crossing["number"]}<br>'
                    +f'{crossing["distance_ft"]:.3f} ft along pile; {crossing["vertical_ft"]:.3f} ft vertically below cutoff'
                    +(f'<br>Elevation {y:.3f} ft' if cutoff is not None else '')
                    +'<br>'+html.escape(crossing['method'])+' · nodes '+html.escape(crossing['upper_node'])+'–'+html.escape(crossing['lower_node'])+'<extra></extra>'), row=1, col=1)
    fig.update_xaxes(zeroline=True, zerolinecolor='#233e50', zerolinewidth=2, row=1, col=1)
    if result and result['tip_elevation_ft'] is not None and cutoff is not None:
        tip = result['tip_elevation_ft']
        fig.add_hline(y=tip, row=1, col=1, line_color='#b34e00', line_width=2,
            annotation_text=f'Tip {tip:.2f} ft'+(' *' if not result['comparison_complete'] else ''),
            annotation_position='bottom right', exclude_empty_subplots=False)


def fixity_overview(fixity):
    governors = fixity['governors']
    if not governors:
        message = '<b>Second zero crossing: unavailable.</b> No imported signed profile has two resolved crossings.'
    else:
        p = governors[0]
        message = f'<b>Deepest second zero crossing: {p["second_vertical_ft"]:.3f} ft vertically below cutoff</b>'
        if p['second_elevation_ft'] is not None: message += f' · EL {p["second_elevation_ft"]:.3f} ft'
        message += '<br>'+html.escape('; '.join(governor_label(p) for p in governors))
    if fixity['unresolved_count']:
        message += f'<br><b>{fixity["unresolved_count"]} active/missing profiles lack a resolved second crossing.</b> The deepest available crossing does not complete that comparison.'
    return ('<p>'+message+'</p><p><small>All imported piles and combinations, independent of plot selection. Circles = first crossing; orange diamonds = second. '
        +f'Zero band ±{fixity["zero_band_in"]:g} in; touches and zero tails are not counted as crossings.</small></p>')


def minimum_tip_html(result, table):
    tip = result['tip_elevation_ft']
    title = 'Minimum tip elevation' if result['comparison_complete'] else 'Minimum tip from available criteria — comparison incomplete'
    text = '<h3>'+title+(': '+f'{tip:.3f} ft' if tip is not None else ': unavailable')+'</h3>'
    text += '<p><b>Controls'+(' among available criteria' if not result['comparison_complete'] else '')+': '
    text += html.escape(result['controlling_criterion'])+'</b></p>'
    text += table([dict(c, control_label='Yes' if c['controls'] else 'No') for c in result['candidates']], [('criterion','Criterion'), ('critical_embedment_ft','Critical depth below ground (ft)'),
        ('extension_ft','Added (ft)'), ('required_embedment_ft','Required embedment (ft)'),
        ('raw_tip_elevation_ft','Tip EL before rounding (ft)'), ('control_label','Controls'), ('source','Governing source'), ('status','Status')], scroll=False)
    if result['required_embedment_ft'] is not None:
        text += f'<p>Required embedment: <b>{result["required_embedment_ft"]:.3f} ft</b> below design ground / scour.'
        if result['total_length_ft'] is not None: text += f' Total pile length: <b>{result["total_length_ft"]:.3f} ft</b>.'
        text += '</p>'
    text += '<p>'+html.escape(result['basis'])+'</p>'+fixity_overview(result['fixity'])
    rows = []
    for p in result['fixity']['profiles']:
        rows.append(dict(p, first_vertical_ft=p['crossings'][0]['vertical_ft'] if p['crossings'] else None))
    text += table(rows, [('pile','Pile'), ('combination','Combo'), ('state','Limit state'), ('component','Direction'),
        ('first_vertical_ft','First crossing below cutoff (ft)'), ('second_vertical_ft','Second crossing below cutoff (ft)'),
        ('second_elevation_ft','Second crossing EL (ft)'), ('status','Profile status')])
    return text
