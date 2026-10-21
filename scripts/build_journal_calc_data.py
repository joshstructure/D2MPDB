"""Draft a calculation package's data files from its journal snapshot (scripts/import_journal_calc.py).

    .venv\\Scripts\\python.exe scripts\\build_journal_calc_data.py bridge_movement [--force]

Writes, when absent (``--force`` rewrites every draft, so hand edits are lost): ``inputs.json`` (the journal-owned values
the module reads and its literal definitions), ``definitions.json`` (every other definition, in document order, with the
section it sits in, its display unit, caption and cited provisions), ``sections.json`` (the journal headings with their
prose and the figures, content boxes and tables that belong to them), ``tables.json`` (the result tables),
``text.json`` (titles, equation notes, inbound names and anchors), ``references.json`` and ``sources.json``, and
``journal_blocks.xml`` (the canvases, content boxes and prose paragraphs copied from the journal module). The drafts are
then edited by hand: captions of the referenced values, check ratios, overview text, key results.
"""
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import bpad_sheet as bs  # noqa: E402

QUALIFIED = re.compile(r'(?<![\w.])([A-Za-z_][A-Za-z_0-9]*)\.([A-Za-z_Ͱ-Ͽ][A-Za-z_0-9Ͱ-Ͽ]*)')
EXPONENT = re.compile(r'(?<![A-Za-z_0-9.])(\d+(?:\.\d+)?[eE][+-]?\d+)')
LITERAL = re.compile(r'^\s*(-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-z][A-Za-z0-9^*/ ]*)?\s*$')
STEP = re.compile(r'^STEP (\d+) OF (\d+)\s*\|\s*(.*)$')
NAV = re.compile(r'^(STEP \d+ OF \d+|Go to Step|RESULTS PREVIEW|CALCULATION EXECUTION|PROJECT INFORMATION|Project Name|Project Number|'
                 r'Designed By|Checked By|Code references and calculation backlinks|D2 MPDB PEDESTRIAN BRIDGE|D2 I-95 PEDESTRIAN BRIDGE|Reference packet)')


def tidy(text):
    """Caption text without the stray punctuation that link tails leave behind."""
    text = re.sub(r'\s+([.,;:)])', r'\1', text or '')
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'(\s*\.)+$', '.', text)
    return re.sub(r'\s{2,}', ' ', text).strip()
MODULE_TITLES = {'BridgeGeometry_2Beam': 'Bridge Geometry - 2 Beam', 'Materials': 'Materials', 'PedBridgeWeights_2Beams': 'Loads - Gravity - 2 Beam',
                 'PileProperties': 'Pile Section Properties', 'C001WindLoadOnPedBridgeSuperstructure': 'C001 - Superstructure Wind',
                 'FenceWind': 'C002 - Fence Wind', 'BridgeMovement': 'C003 - Temperature Movement', 'SuperstructureUplift': 'C004 - Uplift'}
DIM_UNITS = {(0, 0, 0): None, (1, 0, 0): 'in', (2, 0, 0): 'in^2', (3, 0, 0): 'in^3', (4, 0, 0): 'in^4', (0, 1, 0): 'kip', (-2, 1, 0): 'ksi',
             (-1, 1, 0): 'kip/ft', (1, 1, 0): 'kip*ft', (2, 1, 0): 'kip*in^2', (-3, 1, 0): 'pcf', (0, 0, 1): 'deg', (0, 0, 2): 'rad^2',
             (-2, 1, 1): 'ksi', (-1, 0, 0): '1/in'}


def slug(text):
    s = re.sub(r'[^A-Za-z0-9]+', '_', text).strip('_').lower()
    return s or 'x'


def ref_key(piece):
    return slug(piece)


def unit_from_dims(dims, hint=''):
    key = tuple(int(round(d)) for d in dims)
    if key == (1, 0, 0):
        return 'ft' if re.search(r'\bft\b', hint) and not re.search(r'\bin\b', hint) else 'in'
    if key == (-2, 1, 0):
        if 'ksf' in hint or 'psf' in hint:
            return 'ksf'
        if 'psi' in hint:
            return 'psi'
        return 'ksi'
    if key == (1, 1, 0):
        return 'kip*in' if 'kip*in' in hint else 'kip*ft'
    if key == (2, 0, 0):
        return 'ft^2' if 'ft^2' in hint else 'in^2'
    if key == (3, 0, 0):
        return 'ft^3' if 'ft^3' in hint else 'in^3'
    if key == (0, 0, 1):
        return 'rad' if 'rad' in hint else 'deg'
    return DIM_UNITS.get(key, None)


def value_in(v, dims, unit):
    """The case value in its display unit: the journal's exact value, shortened only where a shorter decimal reproduces it."""
    x = v if unit is None else v / bs.BpEngine().unit_q(unit).v
    for digits in range(6, 17):
        short = float(f'{x:.{digits}g}')
        if short == x or (unit and abs(short * bs.BpEngine().unit_q(unit).v - v) <= 1e-13 * max(1.0, abs(v))):
            return short
    return x


def decimal_literals(expr):
    return EXPONENT.sub(lambda m: bs.bp_num(float(m.group(1))), expr)


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    package = argv[0]
    force = '--force' in argv
    data = ROOT / package / 'data'
    imp = json.loads((data / 'journal_import.json').read_text(encoding='utf-8'))
    report = imp['report']
    items = imp['items']
    ext = imp['externals']
    link_targets = {a.split(';', 1)[1] for a in list(imp.get('inbound_links', {})) + list(imp.get('internal_links', [])) if ';' in a}

    def write(name, payload, xml=False):
        path = data / name
        if path.exists() and not force:
            print(f'  keep {path.relative_to(ROOT)}')
            return
        if xml:
            path.write_bytes(payload)
        else:
            path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
        print(f'  wrote {path.relative_to(ROOT)}')

    # ---- aliases for the qualified names used inside expressions
    defs = [it for it in items if it['kind'] in ('def', 'function')]
    def_names = {it['name'] for it in defs}
    alias = {}                    # qualified -> local input name
    inputs = OrderedDict()
    refs_json = OrderedDict()
    sections = []
    section_key = None
    tables = []
    blocks = ET.Element('blocks')
    definitions = []
    notes = {}
    skipped = []
    lists = {}
    current_blocks = None
    last_def = None
    used_keys = set()

    def new_section(text, level, anchor=None, native=None):
        nonlocal section_key, current_blocks, last_def
        base = slug(re.sub(r'\(.*?\)', '', text))[:40]
        key = base
        i = 2
        while key in used_keys:
            key = f'{base}_{i}'
            i += 1
        used_keys.add(key)
        section_key = key
        current_blocks = []
        last_def = None
        entry = OrderedDict(key=key, level=level, title=text.strip(), text=[], blocks=current_blocks, anchor=anchor)
        if native and not native.startswith('EqNotes'):
            entry['native_section'] = native
        sections.append(entry)

    def add_block(kind, bid, el_xml, native=None):
        if 'valuedef=' in el_xml:
            return                                   # a native option field: the input covers it
        block = ET.SubElement(blocks, 'block', id=bid, kind=kind)
        block.append(ET.fromstring(el_xml))
        if current_blocks is None:
            new_section('Introduction', 0)
        at = last_def or 'start'
        if kind == 'prose' and native and not native.startswith('EqNotes'):
            # consecutive paragraphs of one named journal section stay inside a section of that name (inbound links)
            if current_blocks and current_blocks[-1].get('kind') == 'prose_section' and current_blocks[-1]['name'] == native and current_blocks[-1]['at'] == at:
                current_blocks[-1]['ids'].append(bid)
                return
            current_blocks.append(OrderedDict(kind='prose_section', name=native, ids=[bid], at=at))
            return
        current_blocks.append(OrderedDict(kind=kind, id=bid, at=at))

    def register_refs(pieces, caption):
        keys = []
        for p in pieces:
            k = ref_key(p)
            code, _, article = p.partition(' ')
            if k not in refs_json:
                refs_json[k] = OrderedDict(code=code, article=article, governs=caption[:120])
            keys.append(k)
        return keys

    def local_expr(expr):
        def repl(m):
            owner, name = m.group(1), m.group(2)
            if owner == report:
                return name
            q = f'{owner}.{name}'
            if q not in alias:
                local = name
                if re.fullmatch(r'[A-Za-z]{1,3}[0-9]+', local):          # a spreadsheet address is not a Blockpad name
                    local = f'cell_{name}'
                if local in def_names or local in inputs or local in alias.values():
                    local = f'{slug(owner)[:4]}_{name}'
                alias[q] = local
                entry = ext.get(q, {})
                if 'v' in entry:
                    unit = unit_from_dims(entry['dims'], (entry.get('journal_formula') or '') + ' ' + (entry.get('cache') or ''))
                    value = value_in(entry['v'], entry['dims'], unit)
                    kind = 'number'
                elif 'text' in entry:
                    unit, value, kind = None, entry['text'], 'text'
                elif 'bool' in entry:
                    unit, value, kind = None, entry['bool'], 'bool'
                else:
                    unit, value, kind = None, 0.0, 'number'
                inputs[local] = OrderedDict(name=local, value=value, unit=unit, kind=kind, group=MODULE_TITLES.get(owner, owner),
                                            caption=f'{name} ({MODULE_TITLES.get(owner, owner)})',
                                            source=f'{MODULE_TITLES.get(owner, owner)} · {q}', status='journal', journal=q)
            return alias[q]
        return QUALIFIED.sub(repl, expr)

    for it in items:
        kind = it['kind']
        if kind == 'heading':
            if it['hidden']:
                continue
            new_section(it['text'], min(it['level'], 1), it.get('id'))
            continue
        if kind == 'prose':
            if it['hidden'] or not it['text']:
                continue
            step = STEP.match(it['text'])
            size = int(float(it.get('fontsize') or 11))
            anchored = bool(it.get('id')) and it['id'] in link_targets
            if step and size >= 12:
                new_section(f'Step {step.group(1)}. {step.group(3).strip()}', 0, it.get('id'), it.get('section'))
                continue
            if it['bold'] and len(it['text']) < 90 and not it['text'].endswith('.') and not step and not NAV.match(it['text']):
                level = 0 if size >= 14 or re.match(r'^\d+\.\s', it['text']) or it['text'].isupper() else 1
                new_section(it['text'], level, it.get('id'), it.get('section'))
                continue
            if anchored:
                # a paragraph another module links to (the reference packets' return links) stays, whatever it says
                if section_key is None:
                    new_section('Introduction', 0)
                add_block('prose', it['id'], it['xml'], it.get('section'))
                continue
            if it.get('role') in ('caption', 'reference', 'note') or NAV.match(it['text']):
                continue
            if it['bold'] and len(it['text']) < 90:
                continue
            if section_key is None:
                new_section('Introduction', 0)
            bid = it.get('id') or f'p{len(list(blocks))}'
            add_block('prose', bid, it['xml'], it.get('section'))
            continue
        if kind == 'canvas':
            for q in it.get('qualified', []):
                if not q.startswith(report + '.'):
                    local_expr(q)                    # an input alias for every value the canvas reads from another module
            add_block('canvas', it['name'], it['xml'])
            continue
        if kind == 'table':
            if it['hidden'] or it['name'] == 'ProjectStamp':
                continue
            if not it['formulas']:
                add_block('prose', it['name'], it['xml'], it.get('section'))
                continue
            headers = [c.get('text', '') for c in it['rows'][0]]
            rows = []
            for row in it['rows'][1:]:
                cells = []
                for c in row:
                    if 'formula' in c:
                        f = local_expr(c['formula'])
                        expr, unit = bs.split_to(f)
                        if unit:
                            unit = unit.strip().replace('ft in', 'ft')
                        if re.fullmatch(r'[A-Za-z_Ͱ-Ͽ][A-Za-z_0-9Ͱ-Ͽ]*', expr.strip()):
                            cells.append(OrderedDict(v=expr.strip(), **({'unit': unit} if unit else {})))
                        else:
                            cells.append(OrderedDict(f=decimal_literals(expr.strip()), **({'unit': unit} if unit else {})))
                    else:
                        cells.append(c.get('text', ''))
                rows.append(cells)
            tables.append(OrderedDict(name=it['name'], title=it.get('title') or '', headers=headers, rows=rows))
            if current_blocks is None:
                new_section('Introduction', 0)
            current_blocks.append(OrderedDict(kind='table', name=it['name'], at=last_def or 'start'))
            continue
        if kind in ('def', 'function'):
            name, rhs = it['name'], it['rhs']
            if rhs.strip().startswith('['):
                lists[name] = [x.strip() for x in rhs.strip()[1:-1].split(',')]
                skipped.append(it['formula'])
                continue
            any_match = re.match(r'^\s*If\(Any\((\w+),\s*==\s*"([^"]*)"\),\s*"([^"]*)",\s*"([^"]*)"\)\s*$', rhs)
            if any_match and any_match.group(1) in lists:
                # the journal's list test, written as an Or() the evaluators read
                members = lists[any_match.group(1)]
                rhs = f'If(Or({", ".join(f"{m} == \"{any_match.group(2)}\"" for m in members)}), "{any_match.group(3)}", "{any_match.group(4)}")'
                it = dict(it, rhs=rhs)
            elif 'Today(' in rhs or 'Any(' in rhs:
                skipped.append(it['formula'])
                continue
            if section_key is None:
                new_section('Inputs', 0)
            expr, unit = bs.split_to(rhs)
            expr = expr.strip()
            if unit:
                unit = unit.strip().replace('ft in', 'ft')
            caption = tidy(it.get('caption') or '')
            if it['hidden'] and (re.match(r'^\d+\.\s', caption) or (caption.isupper() and len(caption) > 10)):
                caption = ''                         # a hidden row picked up the next heading as its caption
            if it.get('notes'):
                notes[name] = [tidy(n) for n in it['notes']]
            refs = register_refs(it.get('refs', []), caption or name)
            ev = it.get('evaluated', {})
            m = LITERAL.match(expr) if kind == 'def' else None
            literal_unit = m.group(2).strip() if m and m.group(2) else None
            qualified_only = QUALIFIED.fullmatch(expr.strip()) if kind == 'def' else None
            if kind == 'def' and it.get('valuefield'):
                inputs[name] = OrderedDict(name=name, value=it['cache'], unit=None, kind='option', options=it.get('options', []),
                                           group=sections[-1]['title'], caption=caption or name, source='Selected value', status='journal')
                last_def = None
                continue
            if kind == 'def' and (m or expr.startswith('"') or expr in ('true', 'false')) and 'If(' not in expr:
                if expr.startswith('"'):
                    value, kindv, u = expr.strip('"'), 'text', None
                elif expr in ('true', 'false'):
                    value, kindv, u = expr == 'true', 'bool', None
                else:
                    u = unit or literal_unit
                    value, kindv = float(m.group(1)), 'number'
                    q = bs.BpEngine()
                    if literal_unit and re.search(r'[*/]', literal_unit):      # '3 in/2': evaluate, display in the first unit
                        u = unit or literal_unit.split('/')[0].split('*')[0].strip()
                        value = q.evaluate(expr).v / q.unit_q(u).v
                    elif literal_unit and unit and literal_unit != unit:
                        value = value * q.unit_q(literal_unit).v / q.unit_q(unit).v
                    if u:
                        u = u.replace('ft in', 'ft')
                    value = float(f'{value:.12g}')
                inputs[name] = OrderedDict(name=name, value=value, unit=u, kind=kindv, group=sections[-1]['title'], caption=caption or name,
                                           source='; '.join(it.get('refs', [])) or f'{imp["title"]} (journal value)',
                                           status='code' if it.get('refs') else 'journal')
                if it['hidden']:
                    inputs[name]['hidden'] = True
                last_def = None
                continue
            if qualified_only:
                owner, qname = qualified_only.group(1), qualified_only.group(2)
                q = f'{owner}.{qname}'
                if owner != report:
                    entry = ext.get(q, {})
                    if 'v' in entry:
                        u = unit or unit_from_dims(entry['dims'], (entry.get('journal_formula') or '') + ' ' + (entry.get('cache') or ''))
                        value, kindv = value_in(entry['v'], entry['dims'], u), 'number'
                    elif 'text' in entry:
                        u, value, kindv = None, entry['text'], 'text'
                    else:
                        u, value, kindv = None, entry.get('bool', False), 'bool'
                    alias[q] = name
                    inputs[name] = OrderedDict(name=name, value=value, unit=u, kind=kindv, group=sections[-1]['title'], caption=caption or name,
                                               source=f'{MODULE_TITLES.get(owner, owner)} · {q}', status='journal', journal=q)
                    if it['hidden']:
                        inputs[name]['hidden'] = True
                    last_def = None
                    continue
            expr = decimal_literals(local_expr(expr))
            if unit is None and 'v' in ev:
                unit = unit_from_dims(ev['dims'], it.get('cache', ''))
            entry = OrderedDict(section=section_key, name=name, expr=expr, unit=unit, caption=caption or name, refs=refs)
            if it.get('id') and it['id'] in link_targets:
                entry['anchor'] = it['id']                 # another module links to this equation's paragraph
            if it.get('section') and not it['section'].startswith('EqNotes') and not it['hidden']:
                entry['native_section'] = it['section']    # the journal section the equation sits in (inbound link addresses)
            if kind == 'function':
                entry = OrderedDict(section=section_key, function=name if '(' in name else it['formula'].split(' =')[0], expr=expr, caption=caption or name, refs=refs)
                entry['function'] = it['formula'].split(' = ')[0].strip()
            if it['hidden']:
                entry['hidden'] = True
            definitions.append(entry)
            last_def = name if kind == 'def' else last_def
            continue

    # ---- checks draft: every string definition that yields PASS/FAIL-like values
    checks = []
    for d in definitions:
        if re.search(r'"(✓ PASS|PASS|MEETS CLEAR|VALID)"', d['expr']) and re.search(r'"(⊗ FAIL|FAIL|SHORTFALL|INVALID[^"]*|REVIEW[^"]*)"', d['expr']):
            fails = sorted(set(re.findall(r'"(⊗ FAIL|FAIL|SHORTFALL|INVALID[^"]*|REVIEW[^"]*)"', d['expr'])))
            passes = sorted(set(re.findall(r'"(✓ PASS|PASS|MEETS CLEAR|VALID)"', d['expr'])))
            checks.append(OrderedDict(key=slug(d['name']), group='Checks', label=d['caption'][:100] or d['name'], kind='flag', flag=d['name'],
                                      pass_values=passes, fail_values=fails, demand='', capacity='', basis=d['caption'], refs=d.get('refs', []),
                                      names=[d['name']]))

    text = OrderedDict(
        report_name=report, cnumber=imp['title'].split(' - ')[0], title=imp['title'].split(' - ', 1)[1] if ' - ' in imp['title'] else imp['title'],
        prefix=package.split('_')[0], bpad_file=imp['title'].split(' - ', 1)[-1] + '.bpad', notebook=re.sub(r'[^A-Za-z0-9]+', '_', imp['title'].split(' - ', 1)[-1]).strip('_') + '.ipynb',
        tool_prefix=package.replace('_', '-') + '-tool-', case_name=f'{imp["title"]} (journal values, {imp["journal_sha256"][:12]})',
        intro=[], overview=[], outside='', flow=[], key_results=[], summary_tables=[], published=sorted(imp['inbound_names']),
        anchors={s['key']: s['anchor'] for s in sections if s.get('anchor')}, notes=notes, working_notes=[
            f'The calculation was ported from the journal module {report} (journal {imp["journal_sha256"][:12]}); every definition of the module '
            'was evaluated independently from the journal file and reproduced by the notebook to 1 part in 10⁹ before this edition was written.'],
        pending=[], symbols={}, accepted_wording=['Task Work Order'], visible_rules=[], unused_inputs=[], confirmations={},
        skipped_journal_definitions=skipped)
    for s in sections:
        s.pop('anchor', None)
        if not s['blocks'] and not any(d['section'] == s['key'] for d in definitions) and not any(i.get('group') == s['title'] for i in inputs.values()) and not s.get('native_section') and s['key'] not in text['anchors']:
            s['empty'] = True
    sections[:] = [s for s in sections if not s.get('empty')]
    sources = OrderedDict(note=f'Inputs are the values the project journal holds for {imp["title"]}; the journal-owned values are live references in the journal edition.',
                          sources={'JOURNAL': OrderedDict(label='Project journal', path=imp['journal'], sha256=imp['journal_sha256'])},
                          decisions=[], editions='AASHTO LRFD Bridge Design Specifications, 10th edition (2024); FDOT Structures Manual January 2026 (SDG Volume 1, SDM Volume 2)')
    write('inputs.json', list(inputs.values()))
    write('definitions.json', definitions)
    write('sections.json', sections)
    write('tables.json', tables)
    write('checks.json', checks)
    write('references.json', refs_json)
    write('sources.json', sources)
    write('text.json', text)
    write('journal_blocks.xml', ET.tostring(blocks, pretty_print=True, encoding='utf-8'), xml=True)
    # ---- the thin package modules that bind calc_common
    pkg = ROOT / package
    modules = {
        '__init__.py': f'"""{imp["title"]}: the journal calculation as a notebook package (see calc_common)."""\n',
        'model.py': ('"""Definitions, case handling and checks: the shared engine over this package\'s data."""\n'
                     'from pathlib import Path\n\nfrom calc_common.spec import CalcSpec\nfrom calc_common import model as _m\n\n'
                     'SPEC = CalcSpec(Path(__file__).resolve().parent)\nINPUT_SPEC = SPEC.input_spec\nINPUTS = SPEC.inputs\n'
                     'SECTIONS = [(s["key"], s["title"]) for s in SPEC.sections]\nREFERENCES = SPEC.references\nSOURCES = SPEC.sources\n'
                     'FORMAT = SPEC.format\n\n\n'
                     'def default_case():\n    return _m.default_case(SPEC)\n\n\n'
                     'def upgrade_case(case):\n    return _m.upgrade_case(SPEC, case)\n\n\n'
                     'def validate_case(case):\n    return _m.validate_case(SPEC, case)\n\n\n'
                     'def evaluate(case=None):\n    return _m.evaluate(SPEC, case)\n\n\n'
                     'def formula_trace(e):\n    return _m.formula_trace(e)\n'),
        'notation.py': ('"""MathML symbols of this calculation (calc_common.notation bound to the package symbol table)."""\n'
                        'from calc_common.notation import Notation\nfrom .model import SPEC\n\n_N = Notation(SPEC)\nsymbol = _N.symbol\n'
                        'expression = _N.expression\ndefinition_mathml = _N.definition_mathml\nunit_mathml = _N.unit_mathml\n'),
        'report.py': ('"""Self-contained HTML calculation report (calc_common.report over this package)."""\n'
                      'from calc_common.report import build_report as _build, write_report as _write\nfrom .model import SPEC\n\n\n'
                      'def build_report(e, title=None):\n    return _build(SPEC, e, title)\n\n\n'
                      'def write_report(e, path):\n    return _write(SPEC, e, path)\n'),
        'exports.py': ('"""Case, register, report and distilled Blockpad exports (calc_common.exports over this package)."""\n'
                       'from calc_common.exports import Exports\nfrom .model import SPEC\n\n_X = Exports(SPEC)\nWRITERS = _X.WRITERS\n'
                       'DISTILLED_BPAD = _X.DISTILLED_BPAD\nBPAD_VERIFICATION = _X.BPAD_VERIFICATION\nBUNDLE = _X.BUNDLE\n'
                       'case_json = _X.case_json\nload_case = _X.load_case\nchecks_csv = _X.checks_csv\ndistilled_bpad = _X.distilled_bpad\n'
                       'bpad_summary = _X.bpad_summary\nexport_file = _X.export_file\nexport_bundle = _X.export_bundle\n'),
        'widgets.py': ('"""Jupyter / Colab interface (calc_common.widgets over this package)."""\n'
                       'from calc_common.widgets import CalcNotebook\nfrom .model import SPEC\n\n\n'
                       'class Notebook(CalcNotebook):\n    def __init__(self, case=None, export_root="exports"):\n'
                       '        super().__init__(SPEC, case, export_root)\n'),
        'schematics.py': ('"""\'What it represents\' blocks (calc_common.schematics over this package)."""\n'
                          'from calc_common.schematics import schematic as _schematic, meaning as _meaning\nfrom .model import SPEC\n\n\n'
                          'def schematic(e, name):\n    return _schematic(SPEC, e, name)\n\n\n'
                          'def meaning(name):\n    return _meaning(SPEC, name)\n'),
    }
    for name, source in modules.items():
        path = pkg / name
        if not path.exists():
            path.write_text(source, encoding='utf-8', newline='\n')
            print(f'  wrote {path.relative_to(ROOT)}')
    print(f'{package}: {len(inputs)} inputs ({sum(1 for i in inputs.values() if i.get("journal"))} journal references), {len(definitions)} definitions, '
          f'{len(sections)} sections, {len(tables)} tables, {len(checks)} flag checks, {len(skipped)} skipped {skipped}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
