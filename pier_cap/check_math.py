"""Explicit MathML for check records outside the scalar expression engine.

These are presentation relations, paired with the authoritative recorded values.
No calculation or acceptance rule is evaluated here.
"""
from html import escape
from .engine import parse
from .math_notation import expression, mathml, number, tag


def equation_html(source):
    return '<div class="check-equation">'+mathml(expression(parse(source)), True)+'</div>'


def working_html(check, equation):
    key = check.key; notes = ''; lines = []
    if equation.startswith('FDOT bar'):
        lines = ['d_b >= d_min', 'd_b <= d_max']
    elif equation.startswith('FDOT minimum'):
        lines = ['c >= c_req', 'ratio == c_req / c']
        if check.status == 'PENDING':
            notes = 'Required: confirm the environmental classification and face condition before assigning the cover demand.'
    elif equation.startswith('Vc ='):
        lines = ['Vc == 0.0316 * lambda * beta * Sqrt(fc) * b * dv',
                 'Vs == Sigma_Av * Min(fy, 100 * ksi)', 'Vn_limit == 0.25 * fc * b * dv',
                 'Vr == phi_v * Min(Vc + Vs, Vn_limit)',
                 'ratio == Max(Vu / Max(Vr, 10^(-9) * kip), (V_eff / phi_v) / Vn_limit)']
        notes = 'The stirrup area is the sum intersecting the governing shear window. Use inches, kips and ksi in these relations.'
    elif equation.startswith('ratio = across'):
        lines = ['ratio == "across" / "across limit"']
    elif equation.startswith('ratio = max(pitch'):
        lines = ['ratio == Max("actual pitch" / "pitch limit", "across" / "across limit", "minimum rate" / "adjacent rate")']
    elif equation.startswith('ratio = required / max(actual'):
        lines = ['ratio == "required clear gap" / Max("actual clear gap", 0.000001 * in)',
                 '"actual clear gap" >= "required clear gap"']
        notes = 'Required: positive clearance; contact / overlap fails. The denominator floor is 0.000001 in.'
    elif equation.startswith('ratio = required clear gap'):
        lines = ['ratio == "required clear gap" / Max("actual clear gap", 10^(-9) * in)']
    elif equation.startswith('ratio = required minimum rate'):
        lines = ['"intersected rate" == Sigma_Av / (dv * Cot(theta))',
                 'ratio == "required minimum rate" / Max("intersected rate", 10^(-9) * in^2 / in)']
    elif equation.startswith('required rate = Av'):
        lines = ['"required combined rate" == Av_req / s + 2 * At_req / s',
                 '"provided rate" == Min("adjacent rate", "intersected rate")',
                 'ratio == "required combined rate" / Max("provided rate", 10^(-9) * in^2 / in)']
        notes = 'Investigated torsion requires a closed path; an open path uses failure flag 2. Below the investigation threshold the torsion ratio is zero.'
    elif equation.startswith('Ffull ='):
        lines = ['F_full == Abs(M) / (phi_m * dv) + 0.5 * N / phi_n + Cot(theta) * Sqrt(Max(0, V / phi_v - 0.5 * Vs_credited)^2 + F_t^2)',
                 'F_t == 0.45 * p_h * T / (2 * A_o * phi_v)',
                 '"capacity" == As_eff * fy', 'ratio == F_adopted / Max("capacity", 10^(-9) * kip)']
        notes = 'The torsion term applies only to investigated torsion; otherwise it is zero. Eligible direct-loading regions cap adopted tension at their peak flexural demand. Convert the listed moments and torques from kip-ft to kip-in before substitution.'
    elif equation.startswith('ratio = required area rate'):
        lines = ['ratio == "required area rate" / Max("provided area rate", 10^(-9) * in^2 / ft)']
    elif equation.startswith('ratio = actual spacing'):
        lines = ['ratio == "actual spacing" / "adopted spacing limit"']
    elif equation.startswith('ratio = max(required bend'):
        lines = ['"closure ratio" == "required closure length" / Max("available closure length", 10^(-9) * in)',
                 'ratio == Max("required bend" / "actual bend", "closure ratio", "required embedment" / Max("available embedment", 10^(-9) * in), "engagement flag", "unsupported-end flag", "shape flag")']
        notes = 'Unknown closure uses zero with PENDING. Failed engagement, unsupported ends or shape issues use flag 2.'
    elif equation.startswith('ratio = required development'):
        lines = ['ratio == "required development" / Max("available half-length", 10^(-9) * in)']
    elif equation.startswith('ratio = maximum drawn'):
        limit = 'Max("service spacing limit", 0.000001 * in)' if 'service' in equation else '"shrinkage spacing limit"'
        lines = ['ratio == "maximum drawn center spacing" / '+limit]
    elif equation.startswith('ratio = drawn outer-leg'):
        lines = ['ratio == "drawn outer-leg center spacing" / "spacing limit"']
    elif key == 'Status_lrfd_strain':
        lines = ['eps_max <= 0.006']
        notes = 'Calculated strain is compared with the applicability limit. Larger strain has no adopted resistance; no clipping. Simplified epsilon is not required.'
    elif key == 'Status_lrfd_domain':
        lines = ['fpc == 0 * ksi', 'fc <= 15 * ksi', 'fy <= 75 * ksi']
        notes = 'This is the implementation readiness gate. Investigated torsion additionally requires concrete strength at most 10 ksi in the local shear check. Higher-grade detailing retains review.'
    elif 'Flag = 0' in equation:
        lines = ['"flag" == If("criterion satisfied", 0, 2)']
        notes = equation.split('Flag =')[0]+'This is a detailing flag, not a physical demand-to-capacity ratio.'
    else:
        # Nonnumerical review gates have a written requirement, not an equation.
        notes = equation
    return ''.join(equation_html(line) for line in lines)+('<p>'+escape(notes)+'</p>' if notes else '')


def components_html(check):
    rule = 'Min' if check.component_rule == 'min' else 'Max'
    body = '<p><b>Demand / required value and resistance / limit</b></p>'
    body += equation_html('ratio == '+rule+'("component ratios")')
    for c in check.components:
        result = number(c.ratio) if c.ratio is not None else tag('mtext', 'INVALID (nonpositive limit)')
        body += '<p>'+escape(c.label)+': '+mathml('<mfrac>'+number(c.actual)+number(c.limit)+'</mfrac><mo>=</mo>'+result)+'</p>'
        body += '<p>Demand / actual: '+escape(f'{c.actual:.6g} {c.unit}')+'; capacity / limit: '+escape(f'{c.limit:.6g} {c.unit}')+'.</p>'
    return body
