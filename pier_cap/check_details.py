"""Explain the components of existing ratios without changing acceptance rules."""
from dataclasses import dataclass
import html
import math
import textwrap


@dataclass(frozen=True)
class Component:
    label: str
    actual: float
    limit: float
    unit: str

    @property
    def ratio(self):
        return self.actual/self.limit if self.limit>0 else None

    def text(self):
        ratio=f'{self.ratio:.4f}' if self.ratio is not None else 'INVALID (nonpositive limit)'
        return f'{self.label}: {self.actual:.4g} / {self.limit:.4g} {self.unit} = {ratio}'


def explain(check,components,rule='max',note=''):
    """Attach current operands and controlling component(s), preserving ratio/status."""
    if check.status in ('REFERENCE','PENDING') or check.ratio in ('N/A','PENDING'):return check
    check.components=tuple(components);check.component_rule=rule
    if not check.components:return check
    invalid=[c.label for c in check.components if c.ratio is None]
    if invalid:
        check.governing='Invalid limit: '+', '.join(invalid)
    else:
        target=(min if rule=='min' else max)(c.ratio for c in check.components)
        winners=[c.label for c in check.components if math.isclose(c.ratio,target,rel_tol=1e-9,abs_tol=1e-12)]
        check.governing=' + '.join(winners)+(' (tie)' if len(winners)>1 else '')
    operation='Smaller component' if rule=='min' else 'Largest component'
    selection='No valid combined ratio.' if invalid else f'{operation} sets this ratio.'
    check.basis='\n'.join([f'Controls: {check.governing}. {selection}',
        *(c.text() for c in check.components),*([note] if note else []),check.basis])
    return check


def service_components(e,state,z):
    stress=e.value(('fs_I_' if state=='I' else 'fo_III_')+z)
    limit=e.value('fs_I_limit') if state=='I' else 24.
    return [Component('Steel stress' if state=='I' else 'Outer-bar stress',stress,limit,'ksi'),
            Component('Bar spacing',e.value('SP_'+z),e.value('S'+state+'_'+z),'in')]


def service_note(e,state,z):
    drawn=e.longitudinal_layout or z=='B' and e.spacing_values
    pitch=('maximum drawn row pitch' if drawn else 'entered sectional pitch' if e.case['inputs']['Manual_spacing']
           else 'nominal combined-row pitch' if z=='B' else 'sectional row pitch')
    note=f'Spacing uses the {pitch}. The allowable crack-control spacing also depends on calculated steel stress.'
    if state=='I' and e.case['inputs']['fy']>=75:
        note+=' Applicability gate FAIL: this Service I check requires fy < 75 ksi, regardless of the numerical ratio.'
    return note


def annotate_checks(e):
    """Numerical max/min bundles in the formula register; geometry gates stay separate."""
    v=e.value
    for check in e.checks:
        k=check.key;parts=[];rule='max';note=''
        if k.startswith('Chk_I_'):
            z=k[-1];parts=service_components(e,'I',z);note=service_note(e,'I',z)
            check.basis='Larger of steel stress / limit and current sectional bar-spacing value / allowable spacing.'
        elif k=='Status_III' and e.case['inputs']['Ready_III']:
            parts=[Component(f'{c.label} · {z}',c.actual,c.limit,c.unit) for z in 'NPB' for c in service_components(e,'III',z)]
            note='N = top; P = at piles; B = between piles. Allowable spacing also depends on calculated stress.'
        elif k=='Status_fatigue' and e.case['inputs']['Ready_fatigue']:
            parts=[Component('Fatigue stress range · '+z,v('Df_'+z),
                max(v('FTH_'+z),1e-6) if v('FTH_'+z)>0 else v('FTH_'+z),'ksi') for z in 'NPB']
            if any(0<v('FTH_'+z)<1e-6 for z in 'NPB'):
                note='The existing fatigue ratio uses a 0.000001 ksi denominator floor; nonpositive thresholds still invalidate the check.'
        elif k.startswith('Chk_min_'):
            z=k[-1];rule='min'
            parts=[Component('Cracking-moment criterion',v('Mmin_cr')/12,v('Mr_'+z)/12,'kip-ft'),
                   Component('1.33 × factored moment',1.33*v('Mu_'+z)/12,v('Mr_'+z)/12,'kip-ft')]
        elif k.startswith('Chk_shear_'):
            z=k[-1]
            parts=[Component('Shear resistance',v('Vu_'+z),v('Vr_'+z),'kip'),
                   Component('Section upper bound',v('Vn_req_'+z),v('Vn_limit'),'kip')]
        elif k.startswith('Chk_spacing_'):
            z=k[-1]
            parts=[Component('Along-cap spacing · '+label,v('s_'+z),v(name),'in') for label,name in
                   [('strength','s_strength_'+z),('minimum steel','s_minsteel'),('code limit','s_code_'+z)]]
            parts.append(Component('Across-cap leg spacing',v('S_leg'),v('Sw_'+z),'in'))
        elif k.startswith('Chk_torsteel_'):
            from .model import BAR_AREA
            z=k[-1]
            parts=[Component('Torsion steel per leg',v('At_'+z),BAR_AREA[e.case['inputs']['Bar_v']],'in²'),
                   Component('Combined shear + torsion steel',v('Acomb_'+z),v('Av'),'in²')]
        elif k=='Chk_skin_area' and v('Skin_required'):
            parts=[Component('Negative-bending half-side area',v('As_skin_N'),v('As_skin_half'),'in²'),
                   Component('Positive-bending half-side area',v('As_skin_P'),v('As_skin_half'),'in²')]
        elif k=='Chk_skin_space' and v('Skin_required'):
            parts=[Component('Effective depth / 6 · '+z,v('SP_skin'),v('d_'+z)/6,'in') for z in 'NPB']
            parts.append(Component('12 in absolute spacing limit',v('SP_skin'),12.,'in'))
        elif k=='Chk_shrink_area':
            from .model import BAR_AREA
            p=e.case['inputs'];need=v('Ash_req')*12
            parts=[Component(label,need,rate*12,'in²/ft') for label,rate in [
                ('Top steel',v('Ash_top')),('Bottom steel · at piles',v('As_P')/p['b']),
                ('Bottom steel · between piles',v('As_B')/p['b']),('Side steel',v('Ash_side')),
                ('Hoops · G',BAR_AREA[p['Bar_v']]/p['s_G']),('Hoops · L',BAR_AREA[p['Bar_v']]/p['s_L'])]]
        elif k=='Chk_shrink_space':
            parts=[Component(label,v(name),v('s_shrink_limit'),'in') for label,name in
                   [('Top spacing','SP_N'),('Bottom span spacing','SP_B'),('Side spacing','SP_skin'),('Hoop spacing · G','s_G'),('Hoop spacing · L','s_L')]]
        if parts:explain(check,parts,rule,note)
    return e


def controlling_label(check):
    return check.label+(' — '+check.governing if check.governing else '')


def hover_basis(check):
    """Escaped, wrapped lines keep detailed Plotly pop-ups readable."""
    return '<br>'.join(html.escape(line) for paragraph in check.basis.splitlines()
                      for line in textwrap.wrap(paragraph,width=92))


def service_hover(e,z,state='I'):
    """Response plots include both sectional components and the drawn-row screen."""
    from .model import Check
    parts=service_components(e,state,z)
    ratio=max(c.ratio for c in parts) if all(c.ratio is not None for c in parts) else 'INVALID'
    check=Check('',f'Service {state} · {z}',e.value('Chk_'+state+'_'+z),ratio,'')
    explain(check,parts,note=service_note(e,state,z))
    drawn=next((c for c in e.checks if c.key==f'Chk_drawn_{state}_{z}'),None)
    # The plotted stress is still the sectional stress; identify the stricter
    # separate spacing screen when it controls the steel card's readout.
    if drawn:
        if isinstance(ratio,(int,float)) and isinstance(drawn.ratio,(int,float)) and drawn.ratio>ratio:
            check.basis='Card readout controls: actual drawn bar spacing.\n'+check.basis
        check.basis+='\nSeparate drawn-spacing check: '+f'{drawn.ratio:.4f}. '+drawn.basis
    return hover_basis(check)
