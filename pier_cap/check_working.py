"""Per-check presentation of the current calculation, without changing its result."""
from html import escape
from .engine import UNITS
from .math_notation import expression, mathml, quantity, symbol


def record(check, equation, values):
    """Retain exact operands while they are available in the calculation."""
    check.working = (equation, tuple(values))
    return check


def clearance(check, actual, required):
    return record(check, 'ratio = required / max(actual, 0.000001 in); actual ≥ required; contact / overlap fails',
                  [('actual clear gap', actual, 'in'), ('required clear gap', required, 'in')])


def _value(value, unit=''):
    text = f'{value:.6g}' if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
    return escape(text + (' ' + unit if unit else ''))


def _values(values):
    return '<dl class="check-values">'+''.join(
        '<dt>'+escape(label)+'</dt><dd>'+_value(value, unit)+'</dd>' for label, value, unit in values)+'</dl>'


def _record_html(working):
    equation, values = working
    return '<p class="check-equation">'+escape(equation)+'</p>'+_values(values)


def _section_comparison(e, check):
    """Give single-component sectional checks explicit demand/result labels."""
    key = check.key
    z = key[-1]
    if key.startswith('Chk_flex_'):
        return [('required moment Mu', e.value('Mu_'+z, 'kip*ft'), 'kip-ft'),
                ('calculated resistance Mr', e.value('Mr_'+z, 'kip*ft'), 'kip-ft')]
    if key.startswith('Chk_strain_'):
        return [('required minimum tension strain', .005, ''), ('calculated tension strain', e.value('eps_t_'+z), '')]
    if key.startswith('Chk_long_') and not e.lrfd:
        return [('required tension F', e.value('F_long_'+z, 'kip'), 'kip'),
                ('provided yield resistance', (e.value('As_'+z)+e.value('As_skin_eff'))*e.case['inputs']['fy'], 'kip')]
    return []


def _names(ast, engine):
    """Current branch only: never present dormant placeholders as design actions."""
    kind = ast[0]
    if kind == 'name':
        if ast[1] not in UNITS and ast[1] not in ('true', 'false'):
            yield ast[1]
    elif kind == 'bin':
        yield from _names(ast[2], engine)
        yield from _names(ast[3], engine)
    elif kind == 'unary':
        yield from _names(ast[2], engine)
    elif kind == 'call':
        args = ast[2]
        if ast[1] == 'If':
            yield from _names(args[0], engine)
            yield from _names(args[1] if engine.eval(args[0], {}) else args[2], engine)
        else:
            for arg in args:
                yield from _names(arg, engine)


def _registered(e, check):
    from .model import DEFINITIONS, RATIOS
    definitions = {d['name']: d for d in DEFINITIONS}
    ast = RATIOS.get(check.key, e.engine.defs.get(check.key))
    if ast is None:
        return ''
    output = ['<div class="check-equation">'+mathml(expression(ast), True)+'</div>']
    if check.status == 'REFERENCE':
        return ''.join(output)+'<p>Reference equation only; no current demand or resistance is assigned by this row.</p>'
    if check.ratio == 'PENDING':
        ready = 'Ready_III' if check.key == 'Status_III' else 'Ready_fatigue'
        return ''.join(output)+_values([(ready, e.case['inputs'][ready], '')])+ '<p>Values and demand are unavailable until the required inputs are confirmed.</p>'
    output.append('<p><b>Current substitution</b></p><div class="check-equation">'+
                  mathml(expression(ast, e.engine, definitions, substitute=True), True)+'</div>')
    # Unwrap D/C aliases, then show the demand/resistance operands and their
    # governing relations. Every symbol on a displayed line gets a current value.
    queue = [(n, 0) for n in dict.fromkeys(_names(ast, e.engine))]
    seen = set()
    values = {}
    while queue:
        name, depth = queue.pop(0)
        if name in seen or name not in definitions:
            continue
        seen.add(name)
        d = definitions[name]
        values[name] = '<dt>'+mathml(symbol(name))+'</dt><dd>'+mathml(quantity(e.engine.get(name), e.engine, d['unit']))+'</dd>'
        if d['input'] or name in e.engine.overrides:
            continue
        formula = e.engine.defs.get(name)
        if formula is None or depth > 1:
            continue
        output.append('<div class="check-equation">'+mathml(symbol(name)+'<mo>=</mo>'+expression(formula)+
                      '<mo>=</mo>'+quantity(e.engine.get(name), e.engine, d['unit']), True)+'</div>')
        for child in dict.fromkeys(_names(formula, e.engine)):
            queue.append((child, depth if name.startswith('DC_') else depth+1))
    output.append('<p><b>Variable values</b></p><dl class="check-values">'+''.join(values.values())+'</dl>')
    overrides = seen.intersection(e.engine.overrides).difference(e.case['inputs'])
    if overrides:
        output.append('<p>Current drawn coordinates supply '+escape(', '.join(sorted(overrides)))+'.</p>')
    return ''.join(output)


def _actual(e, check):
    """Read the authoritative governing interval, segment, face or bar record."""
    d = e.lrfd
    if not d:
        return None
    key = check.key
    rows = d['intervals']
    field = None
    for prefix, f in [('Chk_actual_shear_', 'ratio'), ('Chk_actual_pitch_', 'spacing_ratio'),
                      ('Chk_actual_clear_', 'clear_ratio'), ('Chk_actual_min_', 'min_ratio')]:
        if key.startswith(prefix):
            rows = [r for r in rows if r['id'].replace(' → ', '_') == key[len(prefix):]]
            field = f
            break
    if field is None:
        for prefix, f in [('Chk_shear_', 'ratio'), ('Chk_spacing_', 'spacing_ratio'),
                          ('Chk_hoop_clear_', 'clear_ratio'), ('Chk_drawn_hoop_legs_', 'across_ratio'),
                          ('Chk_torsteel_', 'tor_ratio')]:
            if key.startswith(prefix):
                rows = [r for r in rows if key[-1] in r['zone'] and (f != 'tor_ratio' or r['torsion_required'])]
                field = f
                break
    if key == 'Status_actual_torsion':
        field = 'tor_ratio'
    if field and rows:
        r = max(rows, key=lambda row: row[field])
        values = [('Governing interval', r['id'], ''), ('Governing segment', r['governing_segment'], '')]
        if field == 'ratio':
            equation = 'Vc = 0.0316 λ β √fc b dv; Vs = ΣAv × min(fy, 100 ksi); Vr = φv min(Vc + Vs, Vn,limit); ratio = max(Vu / max(Vr, 10⁻⁹ kip), (Veff / φv) / Vn,limit)'
            values += [('demand Vu', r['vu'], 'kip'), ('effective demand Veff', r['veff'], 'kip'),
                       ('resistance Vr', r['vr_governing'], 'kip'), ('Vc', r['vc'], 'kip'), ('Vs', r['vs'], 'kip'),
                       ('Vn,limit = 0.25 fc b dv', r['nominal_limit'], 'kip'), ('φv', e.case['inputs']['phi_v'], ''),
                       ('λ', d['settings']['density_factor'], ''), ('β', r['beta'], ''), ('θ', r['theta'], 'deg'),
                       ('fc', e.case['inputs']['fc'], 'ksi'), ('fy', e.case['inputs']['fy'], 'ksi'),
                       ('b', e.case['inputs']['b'], 'in'), ('dv', e.value('dv'), 'in'),
                       ('ΣAv intersected', r['window']['area_in2'], 'in²')]
        elif field in ('spacing_ratio', 'across_ratio'):
            equation = ('ratio = across / across limit' if field == 'across_ratio' else
                        'ratio = max(pitch / pitch limit, across / across limit, minimum rate / adjacent rate)')
            values += [('actual pitch', r['pitch_in'], 'in'), ('pitch limit', r['pitch_limit'], 'in'),
                       ('across', r['across_in'], 'in'), ('across limit', r['across_limit'], 'in'),
                       ('minimum rate', r['minimum_rate'], 'in²/in'), ('adjacent rate = Av / pitch', r['rate_in2_in'], 'in²/in')]
        elif field == 'clear_ratio':
            equation = 'ratio = required clear gap / max(actual clear gap, 10⁻⁹ in)'
            values += [('actual clear gap', r['clear_in'], 'in'), ('required clear gap', r['clear_required_in'], 'in')]
        elif field == 'min_ratio':
            segment = r['minimum_segment']
            equation = 'ratio = required minimum rate / max(intersected rate, 10⁻⁹ in²/in); intersected rate = ΣAv / (dv cot θ)'
            values = [('Governing segment', segment['id'], ''), ('required minimum rate', segment['minimum_rate'], 'in²/in'),
                      ('intersected rate', segment['effective_rate'], 'in²/in'), ('ΣAv', segment['window']['area_in2'], 'in²'),
                      ('dv cot θ', segment['window']['length_in'], 'in')]
        else:
            segment = r['torsion_segment']
            equation = 'required rate = Av,req/s + 2At,req/s; provided rate = min(adjacent rate, intersected rate); ratio = required / max(provided, 10⁻⁹ in²/in). Required torsion with an open path uses failure flag 2; below threshold uses 0.'
            values = [('Governing segment', segment['id'], ''), ('torque demand', segment['tu'], 'kip-ft'),
                      ('investigation threshold', segment['threshold_kip_ft'], 'kip-ft'),
                      ('Av,req/s', segment['av_required_rate'], 'in²/in'), ('At,req/s', segment['at_required_rate'], 'in²/in'),
                      ('required combined rate', segment['combined_required_rate'], 'in²/in'),
                      ('provided rate', min(r['rate_in2_in'], segment['effective_rate']), 'in²/in'),
                      ('closed path', segment['closed'], '')]
        return equation, values
    if key.startswith('Chk_long_'):
        rows = [r for r in d['longitudinal'] if r['group'] == key[-1]]
        if rows:
            r = max(rows, key=lambda row: row['ratio'])
            return ('Ffull = |M|/(φm dv) + 0.5N/φn + cot θ √[max(0, V/φv − 0.5Vs,credited)² + Ft²]; Ft = 0.45 ph T/(2 Ao φv) for investigated torsion, otherwise 0. Eligible direct-loading regions cap F at their peak flexural demand. Capacity = As,eff fy; ratio = Fadopted / max(capacity, 10⁻⁹ kip). M and T are converted to kip-in.',
                    [('Governing segment', r['id'], ''), ('M', r['moment'], 'kip-ft'), ('V', r['vu'], 'kip'), ('N', r['nu'], 'kip'), ('T', r['tu'], 'kip-ft'),
                     ('φm', e.case['inputs']['phi_v' if r['torsion_required'] else 'phi_f'], ''),
                     ('φn', e.case['inputs']['phi_v'] if r['torsion_required'] else d['settings']['phi_axial'], ''),
                     ('φv', e.case['inputs']['phi_v'], ''), ('dv', e.value('dv'), 'in'), ('θ', r['long_theta'], 'deg'),
                     ('Vs,credited', r['vs_credited_kip'], 'kip'), ('ph', r['ph_in'], 'in'), ('Ao', r['ao_in2'], 'in²'),
                     ('Ffull', r['full_tension_kip'], 'kip'), ('required Fadopted', r['required_tension_kip'], 'kip'),
                     ('As,eff', r['steel_area_in2'], 'in²'), ('fy', e.case['inputs']['fy'], 'ksi'), ('capacity', r['capacity_kip'], 'kip'),
                     ('treatment', r['classification'], '')])
    if key in ('Chk_shrink_area', 'Chk_shrink_space', 'Chk_drawn_shrink_B'):
        field = 'area_ratio' if key == 'Chk_shrink_area' else 'spacing_ratio'
        rows = [r for r in d['faces'] if key != 'Chk_drawn_shrink_B' or r['face'] == 'Bottom' and r['direction'] == 'Longitudinal']
        if rows:
            r = max(rows, key=lambda row: row[field])
            return ('ratio = required area rate / max(provided area rate, 10⁻⁹ in²/ft)' if field == 'area_ratio' else 'ratio = actual spacing / adopted spacing limit',
                    [('Governing face', r['face']+' · '+r['direction'], ''), ('required area rate', r['required_in2_ft'], 'in²/ft'),
                     ('provided area rate', r['provided_in2_ft'], 'in²/ft'), ('actual spacing', r['spacing_in'], 'in'),
                     ('code spacing limit', r['code_spacing_in'], 'in'), ('adopted spacing limit', r['adopted_spacing_in'], 'in')])
    if key.startswith('Status_transverse_development_'):
        rows = [r for r in d['transverse_development'] if r['run'] == key[len('Status_transverse_development_'):]]
        if rows:
            r = rows[0]
            return ('ratio = max(required bend / actual bend, closure ratio, required embedment / max(available embedment, 10⁻⁹ in), engagement flag, unsupported-end flag, shape flag). Closure ratio = required closure length / max(available closure length, 10⁻⁹ in); unknown closure uses 0 with PENDING. Failed engagement, unsupported ends or shape issues use flag 2.',
                    [('actual bend', r['bend_in'], 'in'), ('required bend', r['bend_required_in'], 'in'),
                     ('actual hook extension', r['tail_in'], 'in'), ('required hook extension', r['tail_required_in'], 'in'),
                     ('closure type', r['closure_type'], ''), ('closure ratio', r['tail_ratio'], ''),
                     ('required closure length', r['closure_required_in'], 'in'), ('available closure length', r['closure_available_in'], 'in'),
                     ('available embedment', r['embed_available_in'], 'in'), ('required embedment', r['embed_required_in'], 'in'),
                     ('engagement flag', r['engagement_flag'], ''), ('unsupported-end flag', r['unsupported_flag'], ''), ('shape flag', r['shape_flag'], '')])
    if key == 'Status_hook_development':
        rows = [r for r in d['inventory'] if r['additional']]
        if rows:
            r = max(rows, key=lambda row: row['required_in']/max((row['right_in']-row['left_in'])/2, 1e-9))
            return ('ratio = required development / max(available half-length, 10⁻⁹ in); governing added bar',
                    [('required development', r['required_in'], 'in'), ('available half-length', (r['right_in']-r['left_in'])/2, 'in')])
        return 'No added bars: hook-development demand and ratio are zero.', []
    if key == 'Status_lrfd_strain':
        r = max(d['longitudinal'], key=lambda row: row['epsilon'], default=None)
        return ('Required: maximum uncapped strain ≤ 0.006. Larger strain retains PENDING; the numerical shear display caps strain at 0.006.',
                [('maximum uncapped strain', r['epsilon'] if r else 0., ''),
                 ('governing segment', r['id'] if r else 'No segments', ''), ('strain limit', .006, '')])
    if key == 'Status_lrfd_domain':
        p = e.case['inputs']
        return ('Required: fpc = 0, fc ≤ 15 ksi, fy ≤ 75 ksi for this readiness gate. Investigated torsion additionally requires fc ≤ 10 ksi in the local shear check. Higher-grade detailing retains review.',
                [('fpc', p['fpc'], 'ksi'), ('fc', p['fc'], 'ksi'), ('fy', p['fy'], 'ksi')])
    if key == 'Status_continuous_anchorage':
        return ('Required: splice state = none for this readiness gate. Straight-bar development is included in the local credited steel; unmodeled splices require review.',
                [('splice state', d['settings']['continuous_splices'], '')])
    return None


def details_html(e, check):
    """Native details is keyboard accessible and closed unless explicitly opened."""
    from .lrfd_checks import REPLACED_KEYS, REPLACED_PREFIXES
    key = check.key
    working = check.working or _actual(e, check)
    actual_key = e.lrfd and (key in REPLACED_KEYS or key.startswith(REPLACED_PREFIXES))
    if working:
        body = _record_html(working)
    elif key in ('Status_layout', 'Status_section'):
        names = ('b', 'h') if key == 'Status_section' else ('N_pile', 'S_pile', 'D_pile', 'E_clear', 'E_detail')
        body = '<p>Required: current geometry must match the imported force model.</p>'+_values([
            (name+' · '+source, values[name], e.case['units'][name])
            for name in names for source, values in [('current', e.case['inputs']), ('imported', e.case['analysis']['geometry'])]])
    elif key == 'Status_overall' or actual_key:
        body = '<p>Required: all applicable numerical checks and prerequisites must be satisfied. '+('No applicable calculation locations.' if check.status == 'NOT REQUIRED' else 'See the current conditions below.')+'</p>'
    elif key in e.engine.defs:
        body = _values(_section_comparison(e, check))+_registered(e, check)
    elif check.components:
        body = '<p>Governing equation: ratio = '+('min' if check.component_rule == 'min' else 'max')+'(component demand / component limit).</p>'
    else:
        body = '<p>Governing criterion: '+escape(check.basis)+'</p><p>Required: satisfy this detailing / readiness condition. No physical demand-to-capacity equation is assigned to this review gate.</p>'
    if check.components:
        rule = 'min' if check.component_rule == 'min' else 'max'
        body += '<p><b>Demand / required value and resistance / limit</b><br>ratio = '+rule+'(component ratios). Spacing checks compare actual spacing with its allowed limit.</p>'
        body += ''.join('<p>'+escape(c.text())+'</p>' for c in check.components)
    ratio = _value(check.ratio)
    physical = isinstance(check.ratio, (int, float)) and not key.startswith(('Chk_alignment_', 'Chk_added_fit', 'Chk_actual_longitudinal_fit'))
    body += '<p><b>Result:</b> '+escape(check.status)+' · '+('Check ratio: ' if physical else 'Recorded ratio / flag: ')+ratio+'</p>'
    if physical:
        body += '<p><b>Required:</b> ratio ≤ 1, together with the stated applicability and detailing conditions.</p>'
    body += '<p class="check-basis">'+escape(check.basis).replace('\n', '<br>')+'</p>'
    return '<details class="check-working" data-check="'+escape(key, quote=True)+'"><summary>Equation &amp; values</summary><div class="check-working-body">'+body+'</div></details>'


STYLE = '''.check-working{margin-top:5px}.check-working>summary{cursor:pointer;color:#245c85;font-size:12px;width:max-content;max-width:100%}
.check-working>summary:focus-visible{outline:2px solid #245c85;outline-offset:3px}
.check-working-body{margin:8px 0;padding:12px;background:#f5f8fb;border-left:3px solid #a4bdce;max-width:100%;overflow-wrap:anywhere}
.check-working-body p{margin:7px 0}.check-equation{overflow-x:auto;padding:6px 0;white-space:normal}
.check-equation math{font-size:14px;min-width:max-content}.check-values{display:grid;grid-template-columns:minmax(100px,max-content) minmax(100px,1fr);gap:5px 18px;margin:10px 0}
.check-values dt{font-weight:600}.check-values dd{margin:0}.check-basis{color:#485969;font-size:12px}'''
