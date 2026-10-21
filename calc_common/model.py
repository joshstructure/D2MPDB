"""Case handling, evaluation and the check register of a journal calculation.

Every definition is a unit-aware formula evaluated by the shared engine (`pier_cap.engine`: inch, kip, radian), so
the report, the notebook, the Blockpad edition and the tests all walk the same list. Inputs come from
``inputs.json`` (number, text, option or true/false); each carries its caption, unit, source and status, and the
journal owner it is read from when the journal edition makes it a live reference.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import math
import re

from pier_cap.engine import Engine, Q, parse, UNITS
from .spec import PASS, FAIL, ALL_PASS, FAILURES, SCHEMA_VERSION

_UNIT_ENGINE = Engine([])
UNIT_LABELS = {'kip*ft': 'kip-ft', 'kip/ft^2': 'ksf', 'kip/ft^3': 'kcf', 'kip/ft': 'klf', 'in^2/ft': 'in²/ft', 'in^2': 'in²',
               'in^3': 'in³', 'ft^2': 'ft²', 'ft^3': 'ft³', 'kip*ft/ft': 'kip-ft/ft', 'kip*in': 'kip-in', 'kip*in^2': 'kip-in²',
               'rad^2': 'rad²', 'ksf*ft': 'kip/ft'}


def unit_quantity(unit):
    return Q(1.0) if not unit else _UNIT_ENGINE.eval(parse('1 ' + unit), {})


def default_case(spec):
    return {
        'format': spec.format, 'schema_version': SCHEMA_VERSION, 'name': spec.text.get('case_name', spec.full_title),
        'inputs': {d['name']: d['value'] for d in spec.input_spec},
        'units': {d['name']: d.get('unit') for d in spec.input_spec},
        'sources': {d['name']: {'source': d['source'], 'status': d['status']} for d in spec.input_spec},
        'confirmations': {k: bool(v.get('confirmed', False)) for k, v in spec.text.get('confirmations', {}).items()},
        'receipts': {}, 'reviews': {},
    }


def upgrade_case(spec, case):
    case = deepcopy(case)
    if case.get('format') != spec.format:
        raise ValueError(f'This is not a {spec.title} case. Load a file saved by this notebook.')
    if int(case.get('schema_version', 0)) > SCHEMA_VERSION:
        raise ValueError(f'This case uses schema {case["schema_version"]}; this notebook supports {SCHEMA_VERSION}. Use the newer notebook.')
    base = default_case(spec)
    for key in ('inputs', 'units', 'sources', 'confirmations'):
        merged = deepcopy(base[key])
        merged.update(case.get(key, {}))
        case[key] = merged
    case['units'] = base['units']
    case.setdefault('receipts', {})
    case.setdefault('reviews', {})
    case['schema_version'] = SCHEMA_VERSION
    return case


def input_kind(spec, name):
    return spec.inputs[name].get('kind', 'number')


def validate_case(spec, case):
    problems = []
    for d in spec.input_spec:
        name, kind = d['name'], d.get('kind', 'number')
        value = case['inputs'].get(name)
        if kind == 'number':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                problems.append(f'{name}: enter a number')
            elif d.get('positive') and value <= 0:
                problems.append(f'{name}: must be greater than zero')
            elif d.get('nonnegative') and value < 0:
                problems.append(f'{name}: cannot be negative')
        elif kind == 'option':
            if value not in d.get('options', []):
                problems.append(f'{name}: choose one of {", ".join(d.get("options", []))}')
        elif kind == 'text':
            if not isinstance(value, str):
                problems.append(f'{name}: enter text')
        elif kind == 'bool':
            if not isinstance(value, bool):
                problems.append(f'{name}: true or false')
    if problems:
        raise ValueError('Check inputs: ' + '; '.join(problems))
    return True


def input_externals(spec, case):
    out = {}
    for d in spec.input_spec:
        name, kind = d['name'], d.get('kind', 'number')
        value = case['inputs'][name]
        if kind == 'number':
            out[name] = Q(float(value)) * unit_quantity(d.get('unit'))
        else:
            out[name] = value
    return out


def definitions_of(spec):
    """The engine definition list: the package definitions plus the ratio definitions the checks declare."""
    out = []
    for d in spec.definition_spec:
        if 'function' in d:
            out.append({'section': d['section'], 'name': d['function'].split('(')[0], 'function': d['function'],
                        'formula': f'{d["function"]} = {d["expr"]}', 'expr': d['expr'], 'unit': d.get('unit'),
                        'caption': d.get('caption', ''), 'refs': list(d.get('refs', [])), 'hidden': d.get('hidden', False)})
        else:
            out.append({'section': d['section'], 'name': d['name'], 'formula': f'{d["name"]} = {d["expr"]}', 'expr': d['expr'],
                        'unit': d.get('unit'), 'caption': d.get('caption', ''), 'refs': list(d.get('refs', [])),
                        'hidden': d.get('hidden', False), 'anchor': d.get('anchor'), 'native_section': d.get('native_section')})
    return out


@dataclass
class Check:
    key: str
    group: str
    label: str
    ratio: object
    status: str
    demand: str
    capacity: str
    basis: str
    refs: list
    names: list
    note: str = ''
    review: dict = None
    flag: str = None


@dataclass
class Evaluation:
    spec: object
    case: dict
    engine: Engine
    definitions: list
    units: dict
    checks: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    def value(self, name, unit=None):
        q = self.engine.get(name)
        if not isinstance(q, Q):
            return q
        return q.v / unit_quantity(unit or self.units.get(name)).v

    def text(self, name, places=3, unit=None):
        value = self.engine.get(name)
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if not isinstance(value, Q):
            return str(value)
        unit = unit or self.units.get(name)
        number = value.v / unit_quantity(unit).v
        label = UNIT_LABELS.get(unit, unit or '')
        return f'{number:.{places}f} {label}'.strip()

    @property
    def strength_dc(self):
        ratios = [c.ratio for c in self.checks if isinstance(c.ratio, (int, float)) and c.group != 'Prerequisites']
        return max(ratios) if ratios else 0.0

    @property
    def status(self):
        failed = [c for c in self.checks if 'FAIL' in c.status]
        pending = [c for c in self.checks if 'PENDING' in c.status]
        if failed:
            return f'{len(failed)} check(s) FAIL · {len(pending)} pending'
        return f'All numerical checks pass · {len(pending)} pending item(s) remain' if pending else 'All checks pass'

    @property
    def blockpad_status(self):
        return FAILURES if any('FAIL' in c.status for c in self.checks) else ALL_PASS


def _status(ratio, pending=False):
    if ratio is None:
        return 'PENDING' if pending else 'INFO'
    if ratio > 1 + 1e-9:
        return 'FAIL'
    return 'PASS · PENDING INPUT' if pending else 'PASS'


def _ratio(a, b):
    return a / b if b else float('inf')


DEFAULT_FAIL = (FAIL, 'FAIL')
DEFAULT_PASS = (PASS, 'PASS')


def flag_status(text, check=None):
    """PASS / FAIL / PENDING of a journal status string: the check lists its own pass and fail values ('MEETS CLEAR', 'SHORTFALL');
    the defaults are the '✓ PASS' / '⊗ FAIL' pair."""
    t = str(text)
    fail = tuple((check or {}).get('fail_values', DEFAULT_FAIL))
    ok = tuple((check or {}).get('pass_values', DEFAULT_PASS))
    if t in fail:
        return 'FAIL'
    if t in ok:
        return 'PASS'
    return 'PENDING'


def _number_or_name(e, token):
    if isinstance(token, (int, float)):
        return float(token)
    try:
        return float(token)
    except (TypeError, ValueError):
        return e.value(token)


def build_checks(spec, e):
    checks = []
    for c in spec.checks:
        kind = c.get('kind', 'ratio')
        pending = bool(c.get('pending'))
        if pending and c.get('confirmation'):
            pending = not e.case['confirmations'].get(c['confirmation'], False)
        ratio, status = None, None
        demand = c.get('demand', '')
        capacity = c.get('capacity', '')
        demand = e.text(demand) if isinstance(demand, str) and demand in e.units else str(demand)
        capacity = e.text(capacity) if isinstance(capacity, str) and capacity in e.units else str(capacity)
        if kind == 'ratio':
            if c.get('ratio_name'):
                ratio = float(e.value(c['ratio_name']))
            else:
                ratio = _ratio(_number_or_name(e, c['num']), _number_or_name(e, c['den']))
            status = _status(ratio, pending)
            if c.get('flag') and status in ('PASS', 'FAIL'):
                flagged = flag_status(e.engine.get(c['flag']), c)
                if flagged != status and flagged != 'PENDING':
                    # the journal flag can bundle more conditions than the ratio (e.g. a skew range); the flag governs
                    status = flagged
        elif kind == 'flag':
            status = flag_status(e.engine.get(c['flag']), c)
            if status == 'PASS' and pending:
                status = 'PASS · PENDING INPUT'
        else:
            status = 'PENDING' if pending else 'INFO'
        checks.append(Check(c['key'], c.get('group', 'Checks'), c['label'], ratio, status, demand, capacity, c.get('basis', ''),
                            list(c.get('refs', [])), list(c.get('names', [])), c.get('note', ''), None, c.get('flag')))
    return checks


def evaluate(spec, case=None):
    case = upgrade_case(spec, case or default_case(spec))
    validate_case(spec, case)
    externals = input_externals(spec, case)
    definitions = definitions_of(spec)
    shadowed = sorted({d['name'] for d in definitions} & set(externals))
    if shadowed:
        raise ValueError('Formula names duplicate input names: ' + ', '.join(shadowed))
    engine = Engine(definitions, externals=dict(externals))
    try:
        engine.all()
    except (ValueError, AssertionError, ZeroDivisionError, TypeError, KeyError) as exc:
        raise ValueError(f'Calculation stopped: {exc}') from exc
    units = {d['name']: d.get('unit') for d in spec.input_spec}
    units.update({d['name']: d['unit'] for d in definitions if 'function' not in d})
    e = Evaluation(spec=spec, case=case, engine=engine, definitions=definitions, units=units)
    e.checks = build_checks(spec, e)
    from .reviews import apply_reviews
    apply_reviews(e)
    return e


def names_in(ast, out=None):
    out = set() if out is None else out
    if ast[0] == 'name':
        if ast[1] not in UNITS:
            out.add(ast[1])
    elif ast[0] == 'bin':
        names_in(ast[2], out)
        names_in(ast[3], out)
    elif ast[0] == 'unary':
        names_in(ast[2], out)
    elif ast[0] == 'call':
        for a in ast[2]:
            names_in(a, out)
    return out


def formula_trace(e):
    from .notation import Notation
    n = Notation(e.spec)
    out = []
    for d in e.definitions:
        if 'function' in d:
            params = d['function'].split('(', 1)[1].rstrip(')').split(',')
            out.append(dict(name=d['name'], section=d['section'], caption=d['caption'], unit=d['unit'], refs=d['refs'],
                            formula=d['formula'], hidden=d['hidden'],
                            mathml=n.function_mathml(d['name'], [p.strip() for p in params], parse(d['expr']))))
        else:
            out.append(dict(name=d['name'], section=d['section'], caption=d['caption'], unit=d['unit'], refs=d['refs'],
                            formula=d['formula'], hidden=d['hidden'],
                            mathml=n.definition_mathml(d['name'], parse(d['expr']), e.engine, e.units, d['unit'])))
    return out


def evaluate_expression(e, expr, unit=None):
    """A bare expression over the evaluated names (table cells such as 'γ_DC*R_1'): (value, text)."""
    expr = re.sub(r'\s+to\s+[A-Za-z0-9^*/ ]+$', '', expr)
    value = e.engine.eval(parse(expr), {})
    if isinstance(value, bool):
        return value, ('true' if value else 'false')
    if not isinstance(value, Q):
        return value, str(value)
    if unit is None and value.d == (0., 0., 0.):
        return value.v, f'{value.v:.3f}'
    number = value.v / unit_quantity(unit).v if unit else value.v
    return number, (f'{number:.3f} {UNIT_LABELS.get(unit, unit)}' if unit else f'{number:.3f}')
