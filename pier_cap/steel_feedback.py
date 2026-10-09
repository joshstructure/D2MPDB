"""Compact, family-specific readouts from the current evaluated check register."""
import html
import re
from .model import Check,bar_positions
from .detailing import spacing_records
from .transverse import enabled
from .added_steel import added_clearances
from .check_details import explain,service_components,service_note


def line(label,checks):
    checks=list(checks)
    numeric=[c for c in checks if isinstance(c.ratio,(int,float))]
    invalid=next((c for c in checks if 'FAIL' in c.status and c not in numeric),None)
    check=invalid or (max(numeric,key=lambda c:c.ratio) if numeric else (checks[0] if checks else None))
    if check is None:value='N/A';status='';basis='No applicable check for this configuration.'
    else:
        value=check.status if check.key.startswith(('Chk_alignment_','Chk_added_fit')) else f'{check.ratio:.3f}' if isinstance(check.ratio,(int,float)) else str(check.ratio)
        status=check.status;basis=check.basis
        if check.key in ('Chk_hook_cage','Chk_hook_pairs') and isinstance(check.ratio,(int,float)) and check.ratio>=1e6:
            value='Contact / overlap'
    color='#bb3e39' if 'FAIL' in status else '#9b6012' if status in ('PENDING','CONDITIONAL','REFERENCE') else '#167b75' if check and isinstance(check.ratio,(int,float)) else '#64748b'
    suffix=' · conditional' if status=='CONDITIONAL' else ' · FAIL' if 'FAIL' in status and value!=status else ''
    control=check.governing if check else ''
    if not control and check and check.key.startswith('Chk_drawn_'):control='Actual drawn bar spacing'
    if check and len(checks)>1:
        basis+='\nSelected check: '+check.label
        if len(checks)<=3:
            basis+='\nCompared readouts:\n'+'\n'.join(f'{c.label}: {c.ratio:.4f}' if isinstance(c.ratio,(int,float)) else f'{c.label}: {c.ratio}' for c in checks)
        else:basis+=f'\nLargest of {len(checks)} current checks.'
        # Retain sectional operands when the separate drawn-pitch screen wins.
        if check.key.startswith('Chk_drawn_'):
            basis+=''.join('\n'+c.basis for c in checks if c is not check and c.components)
    detail=f'<br><small>Controls: {html.escape(control)}</small>' if control else ''
    return f'<div title="{html.escape(basis,quote=True)}">{html.escape(label)}: <b style="color:{color}">{html.escape(value+suffix)}</b>{detail}</div>'


def block(rows,note=''):
    return '<div class="cap-steel-readout" style="border-top:1px solid #c4cdd6;margin-top:6px;padding-top:6px;font-size:12px;line-height:1.5">'+''.join(rows)+(f'<small>{html.escape(note)}</small>' if note else '')+'</div>'


def feedback(e):
    checks={c.key:c for c in e.checks}
    def pick(*keys):return [checks[k] for k in keys if k in checks]
    def row(label,*keys):return line(label,pick(*keys))
    def spacing(label,region,predicate):
        records=[r for r in spacing_records(e,region,bar_positions(e,region)) if predicate(r)]
        return line(label,[Check('',r['label'],r['status'],r['ratio'],f"Clear {r['actual']:.3f} in / required {r['required']:.3f} in; required ÷ actual.") for r in records])
    def service(z,label='Service I utilization'):return row(label,'Chk_I_'+z,'Chk_drawn_I_'+z)
    def optional(z):
        rows=[];p=e.case['inputs']
        if p['Ready_III']:
            parts=service_components(e,'III',z)
            ratio=max(c.ratio for c in parts) if all(c.ratio is not None for c in parts) else 'INVALID'
            check=Check('Chk_III_'+z,'Service III · '+z,e.value('Chk_III_'+z),ratio,'')
            explain(check,parts,note=service_note(e,'III',z))
            rows.append(line('Service III utilization',[check,*pick('Chk_drawn_III_'+z)]))
        if p['Ready_fatigue']:rows.append(line('Fatigue D/C',[Check('','',e.value('Chk_fat_'+z),e.value('DC_fat_'+z),'Factored stress range / fatigue threshold.')]))
        return rows
    top=[row('Negative flexure D/C','Chk_flex_N'),row('Minimum flexural steel','Chk_min_N'),service('N'),
         spacing('Bar clearance utilization','P',lambda r:r['a']['kind'].startswith('Top') and r['b']['kind'].startswith('Top')),*optional('N')]
    continuous=[row('Pile flexure D/C','Chk_flex_P'),row('Combined span flexure D/C','Chk_flex_B'),service('P'),
        spacing('Continuous row clearance','P',lambda r:r['a']['kind'].startswith('Bottom') and r['b']['kind'].startswith('Bottom')),*optional('P')]
    added=[row('Combined span flexure D/C','Chk_flex_B'),row('Minimum flexural steel','Chk_min_B'),service('B')]
    clearances={(r['row'],r['family']):r for r in added_clearances(e,bar_positions(e,'B'))}
    for k in (1,2):
        if e.case['inputs'][f'n_B{k}']:
            for family,label in [('added','added–added'),('continuous','added–continuous')]:
                r=clearances.get((k,family))
                if r:
                    color='#bb3e39' if r['status']=='FAIL' else '#167b75'
                    added.append(f'<div title="Actual surface gap / required minimum; inches">Row {k} {label}: <b style="color:{color}">{r["actual"]:.3f} / {r["required"]:.3f} in · {r["status"]}</b></div>')
    if 'Chk_added_fit' in checks:added.append(row('Cover / cage fit','Chk_added_fit'))
    added.extend([row('Hook clearance','Chk_hook_cage','Chk_hook_pairs'),*optional('B')])
    side=[row('Skin area utilization','Chk_skin_area'),row('Skin spacing utilization','Chk_skin_space'),
        spacing('Side-bar clearance','B',lambda r:r['a']['kind']=='Skin' or r['b']['kind']=='Skin')]
    layers=[spacing('Vertical clear utilization','B',lambda r:r['basis']=='Vertical layer clearance'),row('Layer alignment','Chk_alignment_P','Chk_alignment_B')]
    advanced=[service('N','Top Service I utilization'),service('P','Pile Service I utilization'),row('Side spacing utilization','Chk_skin_space')]
    hoops=([row('Shear D/C','Chk_shear_G','Chk_shear_L'),row('Shear + torsion steel','Chk_torsteel_G','Chk_torsteel_L'),row('Spacing utilization','Chk_spacing_G','Chk_spacing_L')]
        if not enabled(e.case) else ['<div>Actual runs active · see each run’s checks above.</div>'])
    note='≤ 1.000 satisfies the numerical check. Hover for basis.'
    return dict(top=block(top,note),continuous=block(continuous,note),added=block(added,'Span checks include continuous + added bars. Clear gaps: actual / required.'),
        side=block(side,note),layers=block(layers,note),advanced=block(advanced,note),hoops=block(hoops,'Anchorage and detail review remain separate.'))


def run_feedback(e,rid):
    pattern=re.compile(re.escape(rid)+r'-\d+(?:_|$)')
    def pick(prefix):return [c for c in e.checks if c.key.startswith(prefix) and pattern.search(c.key)]
    return block([line('Shear D/C',pick('Chk_actual_shear_')),line('Max spacing',pick('Chk_actual_pitch_')),
        line('Min clear spacing',pick('Chk_actual_clear_'))],'Adjacent intervals · shear requires developed legs.')
