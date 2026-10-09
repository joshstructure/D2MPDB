"""Labels shared by displacement plots, minimum-tip review and exports."""
import html
import plotly.graph_objects as go
from .pile_fixity import governor_label


def comparison_issues_html(result):
    issues = result.get('comparison_issues', [])
    if not issues: return ''
    return '<p><b>Why the comparison is incomplete</b></p><ul>'+''.join('<li>'+html.escape(s)+'</li>' for s in issues)+'</ul>'


def crossing_rows(fixity):
    """Read the same crossing records that supply the plotted markers."""
    rows = []
    cutoff = fixity['cutoff_elevation_ft']
    for p in fixity['profiles']:
        row = dict(p)
        if not p['included_in_fixity']:
            row['crossing_count'] = 'Not checked'
        for index, name in enumerate(('first', 'second')):
            if len(p['crossings']) > index:
                crossing = p['crossings'][index]
                row[name+'_vertical_ft'] = crossing['vertical_ft']
                row[name+'_elevation_ft'] = (cutoff-crossing['vertical_ft'] if cutoff is not None else 'Enter pile cutoff EL')
            else:
                reason = (p['scope_label'] if not p['included_in_fixity'] else 'No profile records' if p['status']=='No profile records' else
                          'Not applicable — within zero band' if not p['active'] else
                          'No first crossing found' if index==0 else 'No second crossing found')
                row[name+'_vertical_ft'] = row[name+'_elevation_ft'] = reason
        rows.append(row)
    return rows


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


def fixity_overview(fixity, result=None):
    governors = fixity['governors']
    if fixity['applicable'] is False:
        message = '<b>Second-zero crossing criterion: not applicable.</b> No imported combination contains a nonzero wind load factor.'
    elif not governors:
        message = '<b>Second zero crossing: unavailable.</b> No included wind profile has two resolved crossings.'
    else:
        p = governors[0]
        message = '<b>Raw second-zero crossing (before allowance): '
        message += (f'EL {p["second_elevation_ft"]:.3f} ft' if p['second_elevation_ft'] is not None else 'elevation needs pile cutoff')+'</b>'
        message += f'<br>Depth below pile cutoff: {p["second_vertical_ft"]:.3f} ft'
        if p['critical_embedment_ft'] is not None: message += f' · depth below ground / scour: {p["critical_embedment_ft"]:.3f} ft'
        message += '<br>'+html.escape('; '.join(governor_label(p) for p in governors))
        candidate = next((c for c in result['candidates'] if c['criterion']=='Second zero crossing'), None) if result else None
        if candidate and candidate['raw_tip_elevation_ft'] is not None:
            message += (f'<br>Crossing criterion tip EL = {p["second_elevation_ft"]:.3f} − '
                f'{candidate["extension_ft"]:.3f} allowance = <b>{candidate["raw_tip_elevation_ft"]:.3f} ft</b> (before rounding).')
            message += '<br>This is the second-zero row in the table. The adopted minimum tip is selected after comparing both criteria and applying any rounding.'
    if fixity.get('source_filename'):
        message += '<br>Loaded displacement XML: <b>'+html.escape(fixity['source_filename'])+'</b>.'
        message += ' Changing pasted trial rows does not replace these displacement profiles.'
    datum = lambda value: f'{value:.3f} ft' if value is not None else 'not entered'
    message += '<br>Current datums: pile cutoff EL <b>'+datum(fixity['cutoff_elevation_ft'])+'</b>; ground / scour EL <b>'+datum(fixity['ground_elevation_ft'])+'</b>.'
    included = [p for p in fixity['profiles'] if p['included_in_fixity']]
    found = sum(p['crossing_count'] >= 2 for p in included)
    inactive = sum(not p['active'] and p['status']!='No profile records' for p in included)
    wind_labels = [s['combination']+' ('+s['state']+'; '+s['wind_factor_label']+')' for s in fixity['combination_scope'] if s['included'] is True]
    message += '<br><b>Wind combinations included:</b> '+html.escape('; '.join(wind_labels) or 'None identified')+'.'
    if fixity['excluded_combinations']:
        message += '<br>Excluded from crossing checks — no wind: combinations '+html.escape(', '.join(fixity['excluded_combinations']))+'.'
    if fixity['unknown_combinations']:
        message += '<br><b>Reload the original XML to identify wind factors for combinations '+html.escape(', '.join(fixity['unknown_combinations']))+'.</b>'
    message += f'<br>Wind-profile coverage: <b>{found} with a second crossing</b>; {inactive} within the zero band; {fixity["unresolved_count"]} need review.'
    if fixity['unresolved_count']:
        message += '<br>The unresolved profiles are listed under <b>Table 7 — Profiles needing review</b> in Minimum tip. They do not erase the crossings shown for other profiles.'
    if fixity['cutoff_elevation_ft'] is None and fixity['applicable'] is not False:
        message += '<br><b>Enter Pile cutoff EL (ft) at the top of Minimum tip to convert crossing depths to project elevations.</b>'
    return ('<p>'+message+'</p><p><small>All piles in wind combinations, independent of plot selection. Circles = first crossing; orange diamonds = second. '
        +f'Zero band ±{fixity["zero_band_in"]:g} in; touches and zero tails are not counted as crossings.</small></p>')


def minimum_tip_html(result, table, combo=None, piles=None):
    tip = result['tip_elevation_ft']
    title = 'Minimum tip elevation' if result['comparison_complete'] else 'Minimum tip from available criteria — comparison incomplete'
    text = '<h3>'+title+(': '+f'{tip:.3f} ft' if tip is not None else ': unavailable')+'</h3>'
    text += '<p><b>Controls'+(' among available criteria' if not result['comparison_complete'] else '')+': '
    text += html.escape(result['controlling_criterion'])+'</b></p>'+comparison_issues_html(result)
    text += table([dict(c, control_label='Yes' if c['controls'] else 'No') for c in result['candidates']], [('criterion','Criterion'), ('critical_embedment_ft','Critical depth below ground (ft)'),
        ('critical_elevation_ft','Critical EL before allowance (ft)'),
        ('extension_ft','Added (ft)'), ('required_embedment_ft','Required embedment (ft)'),
        ('raw_tip_elevation_ft','Tip EL before rounding (ft)'), ('control_label','Controls'), ('source','Governing source'), ('status','Status')], scroll=False, decimals=3, reference='minimum_tip')
    if result['required_embedment_ft'] is not None:
        text += f'<p>Required embedment: <b>{result["required_embedment_ft"]:.3f} ft</b> below design ground / scour.'
        if result['total_length_ft'] is not None: text += f' Total pile length: <b>{result["total_length_ft"]:.3f} ft</b>.'
        text += '</p>'
    text += '<p>'+html.escape(result['basis'])+'</p>'+fixity_overview(result['fixity'], result)
    text += table(result['fixity']['combination_scope'], [('combination','Combo'), ('state','Limit state'),
        ('wind_factor_label','Nonzero wind factors'), ('scope_label','Crossing check'), ('basis','Basis')], reference='wind_scope')
    rows = crossing_rows(result['fixity'])
    unresolved = [p for p in rows if p['review_reason']]
    if unresolved:
        text += '<h4>Profiles needing review</h4><p>These specific profiles prevent a complete comparison. '
        text += 'Check their signed displacement results and model depth; no second crossing is inferred from a first crossing or zero tail.</p>'
        text += table(unresolved, [('pile','Pile'), ('combination','Combo'), ('state','Limit state'), ('component','Direction'),
            ('crossing_count','Crossings found'), ('review_reason','Reason')], reference='profile_issues')
    selected = [p for p in rows if (combo is None or p['combination']==combo) and (piles is None or p['pile'] in piles)]
    other = [p for p in rows if p not in selected]
    text += '<h4>Crossing locations for Figure 2</h4>'
    if combo is not None:
        state = next((p['state'] for p in rows if p['combination']==combo), '')
        text += '<p><b>Current plot selection: combination '+html.escape(combo)+' · '+html.escape(state)
        text += ' · piles '+html.escape(', '.join(piles) if piles else 'none selected')+'</b>. Change this selection in Profiles and stresses.</p>'
    text += '<p>These are the same crossing records used for the plot markers. '
    text += 'First = circle; second = orange diamond. Depths are vertically below the pile cutoff; EL uses the project datum.</p>'
    columns = [('pile','Pile'), ('combination','Combo'), ('state','Limit state'), ('component','Direction'), ('crossing_count','Crossings found'),
        ('first_vertical_ft','First depth (ft)'), ('first_elevation_ft','First EL (ft)'),
        ('second_vertical_ft','Second depth (ft)'), ('second_elevation_ft','Second EL (ft)'), ('status','Profile status')]
    text += table(selected, columns, decimals=3, reference='crossings') if selected else '<p>No piles selected in Figure 2.</p>'
    if other:
        text += '<details><summary>Table 31 — Crossing locations outside the current plot selection ('+str(len(other))+' profiles)</summary>'
        text += table(other, columns, decimals=3, reference='other_crossings')+'</details>'
    text += '<p>The governing crossing criterion includes all piles in the wind combinations listed in Table 32, independent of this display selection. Non-wind profiles remain viewable without crossing checks.</p>'
    return text
