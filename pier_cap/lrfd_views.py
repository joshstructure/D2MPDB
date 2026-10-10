"""Notebook controls and portable working for the actual-cage LRFD checks."""
from html import escape
from .lrfd_checks import settings,closure_extension


def _table(headers,rows):
    def cell(v):
        if isinstance(v,float):v=f'{v:.5g}'
        return '<td>'+escape(str(v))+'</td>'
    return '<div style="max-width:100%;overflow-x:auto"><table class="cap-table"><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(cell(v) for v in r)+'</tr>' for r in rows)+'</tbody></table></div>'


def working_html(e,*,full=False):
    d=e.lrfd
    if not d:return '<p>Enable the actual transverse layout to calculate the region and actual-cage checks.</p>'
    p=e.case['inputs'];s=d['settings']
    out=['<section class="lrfd-working"><h3>Actual-cage LRFD calculations · 10th edition</h3>',
         '<p>'+escape(d['source_notice'])+' Stations are inches from the left cap end. Unknown load paths retain the full interaction check. These classifications are for longitudinal reinforcement; they do not exempt shear, anchorage or D-region design.</p>']
    out.append(_table(['Input','Value / basis'],[
        ['Bearing loading',s['bearing_loading']],['Pile connection',s['pile_connection']],
        ['Load-path evidence',s['load_path_basis'] or 'Not recorded'],['Individual pile overrides',s['support_overrides']],
        ['Concrete density factor',s['density_factor']],['Coating',s['coating']+' (unknown uses adverse epoxy factors)'],
        ['Continuous-bar splices',s['continuous_splices']],['Hoop closure',s['hoop_closure']],
        ['Closed-stirrup hook extension','CRSI standard, automatic by bar size / angle' if s['closure_extension_mode']=='standard' else f'Custom: {s["closure_tail_in"]:g} in'],
        ['Code source','AASHTO LRFD BDS 10th ed. (2024), 5.7.3.5 pp. 5-78–80; 5.7.3.6.3 p. 5-81; 5.10.6 pp. 5-182–183; 5.10.8 pp. 5-188–198'],
        ['Owner criteria','FDOT Structures Design Guidelines, January 2026, 4.1.4A–C, p. 4-2'],
        ['Actual-cage calculation source SHA-256',d['engine_sha256']]]))
    out.append('<h4>Direct-loading applicability by combination and moment region</h4><p>Regions are bounded by zero-moment locations. Every local peak must have a confirmed direct load/support and adequate continuous-main-bar extension. A qualifying classification allows the flexural-maximum limit; it does not remove the numerical check. Axial tension, investigated torsion, uncertain splices or insufficient extension retain full interaction.</p>')
    length=e.value('L_cap')
    for combo in dict.fromkeys(r['combination'] for r in d['regions']):
        out.append('<div style="margin:8px 0">Combination '+escape(combo)+'<div style="height:24px;position:relative;background:#eee">')
        for r in d['regions']:
            if r['combination']!=combo:continue
            color='#277b63' if r['qualifies'] else '#b06c2b'
            title=f'{r["left_in"]:.3f}–{r["right_in"]:.3f} in: {r["classification"]}; {r["basis"]}'
            out.append(f'<span title="{escape(title,quote=True)}" style="position:absolute;left:{100*r["left_in"]/length:.5f}%;width:{100*(r["right_in"]-r["left_in"])/length:.5f}%;height:24px;background:{color};border-right:1px solid white"></span>')
        out.append('</div></div>')
    out.append('<p>Green: exception eligible. Brown: full interaction. Hover for the reason.</p>')
    out.append(_table(['Combination','From (in)','To (in)','Tension face','Peak |M| (kip-ft)','Classification','Evidence / reason'],
        [[r['combination'],r['left_in'],r['right_in'],r['face'],r['peak_moment_kip_ft'],r['classification'],r['basis']] for r in d['regions']]))
    out.append('<h4>Calculation equations and assumptions</h4>'
        '<p><b>Longitudinal tension, 5.7.3.5-1:</b> F = |M|/(φ<sub>f</sub>d<sub>v</sub>) + 0.5N/φ<sub>c</sub> + (|V|/φ<sub>v</sub> − 0.5V<sub>s</sub>)cot θ. '
        'V<sub>s</sub> credit is capped at |V|/φ<sub>v</sub> and set to zero if anchorage is unresolved. '
        'For investigated torsion, 5.7.3.6.3-1 replaces the shear term by cot θ √[(|V|/φ − 0.5V<sub>s</sub>)² + (0.45p<sub>h</sub>T/(2A<sub>o</sub>φ))²]. '
        'A<sub>s,eff</sub> is the actual steel in the tension half, reduced for available development at both ends. D/C = F/(A<sub>s,eff</sub>f<sub>y</sub>).</p>'
        '<p><b>Direct-loading limit:</b> only eligible regions can limit F to their maximum flexural demand, M<sub>max</sub>/(φ<sub>f</sub>d<sub>v</sub>). '
        'Continuous main bars alone must resist that demand and extend from each peak by at least max(ℓ<sub>d</sub>, d<sub>v</sub>cot 29°), conservatively covering the implemented angle range. '
        'Added hooked bars cannot establish this exemption. Each noneligible segment uses the full equation.</p>'
        '<p><b>Shear, 5.7.3.3:</b> V<sub>c</sub> = 0.0316λβ√f′<sub>c</sub>bd<sub>v</sub>; '
        'V<sub>s</sub> = ΣA<sub>v,intersected</sub>f<sub>y</sub>; V<sub>r</sub> = φ<sub>v</sub> min(V<sub>c</sub> + V<sub>s</sub>, 0.25f′<sub>c</sub>bd<sub>v</sub>). '
        'FDOT 2026 SDG 4.1.4A requires actual legs within 0.5d<sub>v</sub>cotθ on each side. Every bar-entry/exit event is examined for the minimum intersected area over the segment, including truncated end windows. '
        'The simplified β=2, θ=45° route is used only when 5.7.3.4.1 permits it. '
        'Otherwise ε<sub>s</sub>=[max(|M|/d<sub>v</sub>,V<sub>eff</sub>)+0.5N+V<sub>eff</sub>]/(E<sub>s</sub>A<sub>s,eff</sub>); '
        'For tensile N the strain is conservatively doubled (compression-face cracking branch). β=4.8/(1+750ε<sub>s</sub>), θ=29+3500ε<sub>s</sub>. Below minimum transverse steel, β also uses 51/(39+s<sub>xe</sub>), '
        'with s<sub>xe</sub>=clamp[1.38d<sub>v</sub>/(a<sub>g</sub>+0.63),12,80]. Strain beyond 0.006 remains pending. '
        'General-method longitudinal demand uses the lower θ bound of 29° to bound the whole segment; shear resistance uses its calculated θ. '
        'The simplified method uses 45° for both. Investigated torsion uses the single shear resistance factor in Eq. 5.7.3.6.3-1. '
        'The torsion threshold includes λ and the adverse tensile-axial adjustment to K; no prestress credit is assumed.</p>'
        '<p><b>Development, 10th edition:</b> ℓ<sub>db</sub>=0.17d<sub>b</sub>[(f<sub>y</sub>−F<sub>h</sub>/A<sub>b</sub>)/(1.97λf′<sub>c</sub><sup>0.25</sup>)]²; '
        'ℓ<sub>d</sub>=ℓ<sub>db</sub>λ<sub>rl</sub>λ<sub>cf</sub>λ<sub>rc</sub>. '
        'Straight bars: F<sub>h</sub>=0 and ℓ<sub>d</sub>≥12 in. Hooks: F<sub>h</sub>=d<sub>b</sub>Rνf′<sub>c</sub>, '
        'ℓ<sub>dh</sub>=max(ℓ<sub>d</sub>+R+d<sub>b</sub>/2,8d<sub>b</sub>,6 in). '
        'No excess-steel, transverse clamping or tie credit is used. With k<sub>tr</sub>=β<sub>t</sub>=0, λ<sub>rc</sub>=clamp(d<sub>b</sub>/c<sub>b</sub>,0.3,1). '
        'The location factor is 1.3 above 12 in of fresh concrete; the product with coating is capped at 1.7. '
        'Local available area uses min(1, available length / required length).</p>'
        '<p><b>Stirrup anchorage:</b> 5.10.8.2.6b requires #6–8 hooks around longitudinal bars and ℓ<sub>e</sub>≥0.44d<sub>b</sub>f<sub>y</sub>/(λ√f′<sub>c</sub>). '
        'Bend diameter, tail, embedment and enclosure are separate checks. A closed outline does not establish closure. A lap pair uses 1.3ℓ<sub>d</sub>.</p>'
        '<p><b>Face reinforcement:</b> 5.10.6 requires A<sub>s</sub>/ft = clamp[1.30bh/{2(b+h)f<sub>y</sub>},0.11,0.60] on each exposed face and direction. '
        'The spacing table separately identifies code and adopted project limits. Partial U tails are not counted as full-width bottom-face bars.</p>')
    out.append('<details open><summary>Actual transverse interval working</summary>'+_table(
        ['Interval','x1','x2','Av (in²)','s (in)','Vu (kip)','β','θ (deg)','Vc (kip)','Vs (kip)','Vr governing (kip)','Vr min for plot (kip)','Shear D/C','Av/s req','2At/s req','Torsion D/C','Status','Governing segment'],
        [[r['id'],r['left_in'],r['right_in'],r['av_in2'],r['pitch_in'],r['vu'],r['beta'],r['theta'],r['vc'],r['vs'],r['vr_governing'],r['vr'],r['ratio'],r['av_required_rate'],2*r['at_required_rate'],r['tor_ratio'],'FAIL' if r['ratio']>1 else 'PENDING' if r['pending'] else 'PASS',r['governing_segment']] for r in d['intervals']])+'</details>')
    out.append('<details><summary>Longitudinal tension working · every analyzed segment</summary>'+_table(
        ['Location / combination','Region','M (kip-ft)','V (kip)','N bound (kip)','T (kip-ft)','θ tension bound','Strain bound','Shear method','Vs credited (kip)','As developed (in²)','Full F (kip)','Adopted F (kip)','Capacity (kip)','D/C','Treatment'],
        [[r['id'],r['group'],r['moment'],r['vu'],r['nu'],r['tu'],r['long_theta'],r['epsilon'],r['method'],r['vs_credited_kip'],r['steel_area_in2'],r['full_tension_kip'],r['required_tension_kip'],r['capacity_kip'],r['ratio'],r['classification']] for r in d['longitudinal']])+'</details>')
    out.append('<details><summary>Bar development operands</summary>'+_table(
        ['Bar','Kind','#','cb (in)','Fh (kip)','Basic ld (in)','λrl','λcf','λrc','Required (in)','Left end','Right end'],
        [[r['id'],r['kind'],r['bar'],r['cb_in'],r['fh'],r['basic_in'],r['location_factor'],r['coating_factor'],r['confinement_factor'],r['required_in'],r['left_in'],r['right_in']] for r in d['inventory']])+'</details>')
    out.append('<details><summary>FDOT intersected stirrup legs and torsion operands · every segment</summary>'+_table(
        ['Segment','Window length (in)','Window center (in)','Intersected bar IDs','ΣAv (in²)','Developed ΣAv (in²)','Ao (in²)','ph (in)','Av/s req','At/s req','Combined req','Torsion D/C'],
        [[r['id'],r['window']['length_in'],r['window']['station_in'],', '.join(r['window']['bar_ids']),r['window']['area_in2'],r['developed_window_area_in2'],r['ao_in2'],r['ph_in'],r['av_required_rate'],r['at_required_rate'],r['combined_required_rate'],r['torsion_ratio']] for r in d['longitudinal']])+'</details>')
    out.append('<details><summary>Stirrup anchorage / closure working</summary>'+_table(
        ['Run','Type','#','Bend','Min bend','Hook extension (in)','LRFD min extension (in)','Available le','Required le','D/C','Notes'],
        [[r['run'],r['kind'],r['bar'],r['bend_in'],r['bend_required_in'],r['tail_in'],r['tail_required_in'],r['embed_available_in'],r['embed_required_in'],r['ratio'],r['notes']] for r in d['transverse_development']])+'</details>')
    out.append('<details><summary>Face reinforcement working</summary>'+_table(
        ['Face','Direction','Provided in²/ft','Required in²/ft','Area D/C','Spacing','Code max','Project max','Spacing D/C','Basis'],
        [[r['face'],r['direction'],r['provided_in2_ft'],r['required_in2_ft'],r['area_ratio'],r['spacing_in'],r['code_spacing_in'],r['adopted_spacing_in'],r['spacing_ratio'],r['notes']] for r in d['faces']])+'</details></section>')
    return ''.join(out)


class LRFDPanel:
    def __init__(self,owner):
        import ipywidgets as W
        self.owner=owner;self.controls={};self.busy=False
        specs=[('bearing_loading','Bearing load path',[('Unconfirmed','unknown'),('Applied on top face','top'),('Indirect / framed connection','indirect')]),
            ('pile_connection','Pile-cap connection',[('Unconfirmed','unknown'),('Pinned direct support','pinned'),('Transfers moment','moment')]),
            ('coating','Bar coating',[('Unconfirmed (adverse factor)','unknown'),('Uncoated','uncoated'),('Epoxy coated','epoxy')]),
            ('continuous_splices','Continuous-bar splices',[('Unconfirmed','unknown'),('No splices','none'),('Splices present: separate review','present')]),
            ('hoop_closure','Hoop closure',[('Unconfirmed','unknown'),('Standard hooked ends','hooks'),('Overlapping U pair','lap_pair')]),
            ('closure_angle','Closure hook angle',[(90,90),(135,135)]),
            ('closure_extension_mode','Closed-stirrup hook extension',[('CRSI standard (automatic)','standard'),('Custom extension','custom')])]
        values=settings(owner.case);items=[]
        for key,label,options in specs:
            self.controls[key]=W.Dropdown(options=options,value=values[key],description=label,
                style={'description_width':'225px' if key=='closure_extension_mode' else '165px'},layout=W.Layout(width='470px' if key=='closure_extension_mode' else '390px'))
        for key,label in [('density_factor','Concrete density λ'),('phi_axial','Axial factor φc'),
            ('closure_tail_in','Custom hook extension (in)'),('closure_lap_in','Closure lap (in)'),
            ('shrinkage_project_spacing_in','Project face spacing (in; 0=code)')]:
            self.controls[key]=W.FloatText(value=values[key],description=label,style={'description_width':'225px'},layout=W.Layout(width='335px'))
        self.controls['closure_engages_bars']=W.Checkbox(value=values['closure_engages_bars'],description='Closure hooks engage longitudinal bars',indent=False,layout=W.Layout(width='390px'))
        self.controls['load_path_basis']=W.Textarea(value=values['load_path_basis'],description='Load-path basis',placeholder='Identify the bearing / connection drawing or design basis.',layout=W.Layout(width='98%',height='65px'))
        for control in self.controls.values():control.observe(self.changed,names='value')
        self.extension_summary=W.HTML()
        self.result=W.HTML();self.piles={};self.pile_box=W.HBox(layout=W.Layout(flex_flow='row wrap'))
        self.sync_piles()
        self.ui=W.VBox([W.HTML('<p><b>AASHTO LRFD 10th edition and FDOT SDG 2026.</b> Unknown connections use full longitudinal interaction. Enter the physical detail; a filename is not evidence of fixity. Closure dimensions describe the supplied detail and do not alter the cage drawing. Individual pile settings override the common connection setting.</p>'),
            W.HBox(list(self.controls.values())[:-1],layout=W.Layout(flex_flow='row wrap')),self.extension_summary,self.pile_box,self.controls['load_path_basis'],self.result],layout=W.Layout(width='100%'))
        self.sync_extensions()

    def sync_extensions(self):
        s=settings(self.owner.case);standard=s['closure_extension_mode']=='standard'
        self.controls['closure_tail_in'].disabled=standard or s['hoop_closure']!='hooks'
        self.controls['closure_tail_in'].layout.display='none' if standard else ''
        sizes=sorted({r['bar'] for r in self.owner.case.get('transverse_detail',{}).get('runs',[]) if r['kind']=='hoop'})
        if not sizes:sizes=[int(self.owner.case['inputs']['Bar_v'])]
        values=[f'#{bar}: {value:g} in' if (value:=closure_extension(s,bar)) is not None else f'#{bar}: outside CRSI stirrup table' for bar in sizes]
        self.extension_summary.value=('<p><b>Closed-stirrup hook extension:</b> '+escape('; '.join(values))+
            (' · CRSI standard; updates with bar size and hook angle.' if standard else ' · custom detail.')+
            ' Measured from the end of the bend to the bar tip.</p>') if s['hoop_closure']=='hooks' else ''

    def sync_piles(self):
        import ipywidgets as W
        count=int(self.owner.case['inputs']['N_pile'])
        if len(self.piles)!=count:
            for w in self.piles.values():w.close()
            self.piles={str(i):W.Dropdown(description=f'Pile {i}',options=[('Use common setting','inherit'),('Unconfirmed','unknown'),('Pinned','pinned'),('Transfers moment','moment')],layout=W.Layout(width='270px')) for i in range(1,count+1)}
            for w in self.piles.values():w.observe(self.changed,names='value')
            self.pile_box.children=tuple(self.piles.values())
        prior=self.busy;self.busy=True
        try:
            values=settings(self.owner.case)['support_overrides']
            for k,w in self.piles.items():w.value=values.get(k,'inherit')
        finally:self.busy=prior

    def changed(self,_):
        if self.busy or self.owner.busy:return
        if _['owner'] is self.controls['closure_extension_mode'] and _['new']=='custom':
            # Start a custom edit from the resolved standard, never a hidden zero.
            sizes=[r['bar'] for r in self.owner.case.get('transverse_detail',{}).get('runs',[]) if r['kind']=='hoop']
            values=[closure_extension(settings(self.owner.case),bar) for bar in sizes or [int(self.owner.case['inputs']['Bar_v'])]]
            self.busy=True
            try:self.controls['closure_tail_in'].value=max((v for v in values if v is not None),default=0.)
            finally:self.busy=False
        self.owner.case['lrfd_checks']={**settings(self.owner.case),**{k:w.value for k,w in self.controls.items()}}
        self.owner.case['lrfd_checks']['support_overrides']={k:w.value for k,w in self.piles.items() if w.value!='inherit'}
        self.owner.refresh();self.owner._notify_case_change()

    def load(self):
        self.busy=True
        try:
            for k,w in self.controls.items():w.value=settings(self.owner.case)[k]
            self.sync_piles()
            self.sync_extensions()
        finally:self.busy=False

    def refresh(self,e):
        self.sync_piles()
        self.sync_extensions()
        self.result.value=working_html(e)

    def close(self):
        for w in self.controls.values():w.close()
        for w in self.piles.values():w.close()
        self.pile_box.close()
        self.extension_summary.close()
        self.result.close();self.ui.close()
