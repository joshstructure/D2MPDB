"""Blockpad (.bpad) editions of a journal calculation: the standalone sheet and the journal edition with live references.

The sheet is written from the same definition list the notebook evaluates, through scripts/bpad_sheet.py (the native
elements the project has recalculated in Blockpad before), and verified before it is returned: every formula is
parsed and evaluated by the independent Blockpad-syntax evaluator, every input equals the case, every definition
equals the notebook to 1 part in 10⁹, the names other journal modules read are present, the check strings and the
Status agree with the notebook's check register, and (journal edition) every journal-owned input is written as a
live reference after the coherence gate compared the journal value with the case. The journal's own figures,
content boxes and design-basis prose travel with the sheet from ``data/journal_blocks.xml``.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

from lxml import etree as ET

from scripts import bpad_sheet as bs
from .spec import PASS, FAIL, ALL_PASS, FAILURES

TOL = 1e-9
INPUT_TOL = 1e-12
REFERENCE_CAPTION = 'shared value —'
LEGEND = 'Inputs are highlighted amber; results are the green tables.'
CLOSING_NOTE = ('A ✓ status covers only the recomputed numerical checks; it is not design acceptance. '
                'The equation notes of the calculation are in its report.')
FUNCTION_NAMES = {'If', 'And', 'Or', 'Not', 'Min', 'Max', 'Sqrt', 'Abs', 'Round', 'Floor', 'Tan', 'Sin', 'Cos', 'Atan', 'Asin', 'Acos',
                  'Ln', 'Exp', 'PlotLines'}
QUALIFIED = re.compile(r'(?<![\w.])([A-Za-z_][A-Za-z_0-9]*)\.([A-Za-z_Ͱ-Ͽ][A-Za-z_0-9Ͱ-Ͽ]*)')
JOURNAL_PATH = bs.REPO_ROOT / 'journal' / 'D2_I95_Project_Journal.bpad'
UNIT_TEXT = {'ksf*ft': 'kip/ft'}


class BuildError(AssertionError):
    pass


def clean(v):
    return round(float(v), 12)


def in_unit(q, unit):
    if unit is None:
        if q.d != bs.NODIM:
            raise bs.BpError(f'{q!r} is not a plain number')
        return q.v
    u = bs.BpEngine().unit_q(unit)
    q.same(u, f'unit {unit}')
    return q.v / u.v


def bp_unit(unit):
    if unit and unit.replace(' ', '') == 'ftin':
        unit = 'ft'
    u = bs.bp_unit(unit)
    return UNIT_TEXT.get(u, u)


def literal_text(value, unit):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return '"' + value.replace('"', '') + '"'
    return bs.bp_num(value) + (f' {bp_unit(unit)}' if unit else '')


def case_sha(e):
    return hashlib.sha256(json.dumps(e.case, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# ----------------------------------------------------------------------------- journal context (live references)
class JournalContext:
    def __init__(self, links, stamp, refs, rows, externals):
        self.links, self.stamp, self.refs, self.rows, self.externals = links, stamp, refs, rows, externals

    def apply(self, eng):
        for qualified, value in self.externals.items():
            eng.add_external(qualified, value)

    def summary(self):
        kept = [r for r in self.rows if r['status'] not in ('reference',)]
        return dict(rows=self.rows, references=sum(r['status'] == 'reference' for r in self.rows), literals=kept, context=[])


def journal_context(spec, links, e):
    """The coherence gate: every journal-owned input must equal the journal value, else the build stops."""
    from scripts.build_cap_bpad import check_project_info, PROJECT_STAMP
    stamp = check_project_info(links)
    case = e.case['inputs']
    rows, bad, externals, refs = [], [], dict(stamp), {}
    for d in spec.input_spec:
        owner = d.get('journal')
        if not owner:
            continue
        name, unit, kind = d['name'], d.get('unit'), d.get('kind', 'number')
        value = case[name]
        try:
            q = links.value(owner)
        except bs.BpError as ex:
            bad.append(f'  {name}: {owner} cannot be evaluated: {ex}')
            continue
        externals[owner] = q
        if kind == 'number':
            try:
                journal_value = in_unit(q, unit)
            except bs.BpError as ex:
                bad.append(f'  {name}: {owner}: {ex}')
                continue
            agree = abs(journal_value - float(value)) <= TOL * max(abs(float(value)), 1e-12)
            shown_j, shown_c = clean(journal_value), clean(float(value))
        else:
            journal_value = q if not isinstance(q, bs.Q) else q.v
            agree = str(journal_value) == str(value) if kind != 'bool' else bool(journal_value) == bool(value)
            shown_j, shown_c = journal_value, value
        if d.get('literal_reason'):
            rows.append(dict(input=name, owner=owner, journal_value=shown_j, case_value=shown_c, status='literal_incoherent_journal',
                             note=d['literal_reason']))
            if agree:
                bad.append(f'  {name} is kept as a literal because {owner} disagreed, but they agree now: make it a reference')
            continue
        if not agree:
            bad.append(f'  {name}: the case holds {shown_c!r}{" " + unit if unit else ""} but the journal owner {owner} holds {shown_j!r}')
        refs[name] = (owner, unit, kind)
        rows.append(dict(input=name, owner=owner, journal_value=shown_j, case_value=shown_c, status='reference',
                         note=f'{REFERENCE_CAPTION} {owner}' + (f' ({unit})' if unit else ' (no unit)' if kind == 'number' else ' (text)')))
    if bad:
        raise BuildError(f'coherence gate: the journal disagrees with the {spec.title} case\n' + '\n'.join(bad))
    stamp_values = {k.partition('.')[2]: v for k, v in stamp.items()}
    if stamp_values != PROJECT_STAMP:
        raise BuildError('the ProjectInfo strings differ from PROJECT_STAMP')
    return JournalContext(links, stamp_values, refs, rows, externals)


# ----------------------------------------------------------------------------- the sheet
class Sheet:
    def __init__(self, spec, e, revision, journal=None, extra_provenance=None):
        self.spec, self.e, self.revision, self.journal = spec, e, revision, journal
        self.name = spec.name
        self.doc = bs.new_document()
        self.rep = bs.new_report(self.doc, spec.name, spec.full_title)
        self.case_sha = case_sha(e)
        self.input_names, self.canvases, self.defined = [], {}, []
        self.blocks = {}
        if spec.blocks_xml:
            for block in ET.fromstring(spec.blocks_xml):
                self.blocks[block.get('id')] = block
        self.extra_provenance = extra_provenance
        self.ref_map = {d['journal']: d['name'] for d in spec.input_spec if d.get('journal')}
        self.cur = self.rep                          # where the next element goes: the report, or an open journal section
        self.native_stack = []                       # the open journal sections (name, element), outermost first

    # -- helpers
    def input_formula(self, d):
        name, unit, kind = d['name'], d.get('unit'), d.get('kind', 'number')
        value = self.e.case['inputs'][name]
        if self.journal is not None and name in self.journal.refs:
            owner, unit, kind = self.journal.refs[name]
            return f'{name} = {owner}' + (f' to {bp_unit(unit)}' if unit and kind == 'number' else '')
        return f'{name} = {literal_text(value, unit)}'

    def input_caption(self, d):
        name = d['name']
        if self.journal is not None and name in self.journal.refs:
            return f'{REFERENCE_CAPTION} {self.journal.refs[name][0]}; {d["caption"]}'
        return d['caption']

    def rewrite_formula(self, text):
        """A journal block formula for this edition: display 'ft in' as feet, standalone references as the local inputs."""
        text = re.sub(r'\s+to\s+ft\s+in\b', ' to ft', text)
        if self.journal is not None:
            return text

        def local(m):
            owner, name = m.group(1), m.group(2)
            if owner == self.name:
                return m.group(0)
            qualified = f'{owner}.{name}'
            if qualified in self.ref_map:
                return self.ref_map[qualified]
            raise BuildError(f'the journal block reads {qualified}, which is not an input of this calculation')
        return QUALIFIED.sub(local, text)

    def copy_block(self, block_id):
        block = self.blocks.get(block_id)
        if block is None:
            raise BuildError(f'journal block {block_id} is not in data/journal_blocks.xml')
        out = []
        for child in block:
            el = copy.deepcopy(child)
            for node in el.iter():
                if not isinstance(node.tag, str):
                    continue
                if node.tag in ('paragraph', 'link', 'dynexp', 'break', 'textcell') or node.getparent() is not None and node.getparent().tag in ('paragraph', 'textcell'):
                    if node.text and node.tag not in ('expbody', 'expresult', 'textvalue'):
                        node.text = re.sub(r'\s+', ' ', node.text)
                    if node.tail:
                        node.tail = re.sub(r'\s+', ' ', node.tail)
                if node.get('formula'):
                    node.set('formula', self.rewrite_formula(node.get('formula')))
                if node.tag == 'expbody' and node.text:
                    node.text = self.rewrite_formula(node.text)
                if node.get('valuedef'):
                    raise BuildError(f'journal block {block_id} holds a native value field; write it as an input instead')
            if self.journal is None:
                for link in list(el.iter('link')):
                    parent = link.getparent()
                    text = (link.text or '') + (link.tail or '')
                    prev = link.getprevious()
                    if prev is not None:
                        prev.tail = (prev.tail or '') + text
                    else:
                        parent.text = (parent.text or '') + text
                    parent.remove(link)
            if el.tag == 'canvas':
                self.canvases[el.get('name')] = el
                embed = ET.SubElement(self.cur, 'embed', spacingbefore='4', spacingafter='5')
                embed.append(el)
            else:
                self.cur.append(el)
            out.append(el)
        return out

    def open_native(self, name):
        """Open the journal section `name` (one wrapper per name): later writes go inside it. Sections nest as the journal's do."""
        names = [n for n, _ in self.native_stack]
        if name in names:
            while self.native_stack[-1][0] != name:          # back out of the sections nested inside it
                self.native_stack.pop()
            self.cur = self.native_stack[-1][1]
            return self.cur
        sec = ET.SubElement(self.cur, 'section', name=name, capture='False', hide='false')
        self.native_stack.append((name, sec))
        self.cur = sec
        return sec

    def close_native(self, name=None):
        """Close `name` and everything nested inside it (all open sections when `name` is None)."""
        if name is None:
            self.native_stack.clear()
        elif name in [n for n, _ in self.native_stack]:
            while self.native_stack and self.native_stack.pop()[0] != name:
                pass
        self.cur = self.native_stack[-1][1] if self.native_stack else self.rep

    @property
    def open_name(self):
        return self.native_stack[-1][0] if self.native_stack else None

    def place_block(self, block, index=None, closes=None):
        kind = block['kind']
        if kind in ('canvas', 'prose'):
            self.copy_block(block['id'])
        elif kind == 'prose_section':
            self.open_native(block['name'])
            if block.get('title'):
                bs.subheading(self.cur, block['title'])
            for bid in block['ids']:
                self.copy_block(bid)
            if closes is not None and index == closes.get(block['name']):
                self.close_native(block['name'])
        elif kind == 'table':
            self.table(self.spec.table_by_name[block['name']])
        else:
            raise BuildError(f'unknown block kind {kind}')

    def table(self, t):
        rows = []
        for row in t['rows']:
            cells = []
            for j, cell in enumerate(row):
                if isinstance(cell, dict):
                    if 'v' in cell:
                        unit = cell.get('unit') or self.e.units.get(cell['v'])
                        value = self.e.engine.get(cell['v'])
                        text = cell['v'] + (f' to {bp_unit(unit)}' if unit and hasattr(value, 'd') else '')
                        cells.append(('formula', text))
                    elif 'f' in cell:
                        unit = cell.get('unit')
                        cells.append(('formula', cell['f'] + (f' to {bp_unit(unit)}' if unit else '')))
                    else:
                        cells.append(str(cell.get('t', '')))
                else:
                    cells.append(str(cell))
            rows.append(cells)
        if t.get('title'):
            bs.note(self.cur, t['title'], size=10, fontweight='bold', keepwithnext='True')
        widths = t.get('widths') or [max(60, int(540 / len(t['headers'])))] * len(t['headers'])
        bs.table(self.cur, t['name'], t['headers'], rows, widths, palette=t.get('palette', 'output'))

    # -- the document
    def build(self):
        spec, e, rep = self.spec, self.e, self.rep
        live = self.journal is not None
        bs.project_stamp_table(rep, bs.PROJECT_STAMP, live=live)
        bs.para(rep, 'D2 I-95 PEDESTRIAN BRIDGE', fontsize='16', fontweight='bold', spacingafter='2')
        bs.para(rep, spec.full_title, fontsize='14', fontweight='bold', spacingafter='6')
        if spec.sources.get('editions'):
            bs.note(rep, 'Design basis: ' + spec.sources['editions'], size=10)
        notes = bs.working_notes(rep)
        edition = 'Journal edition' if live else 'Blockpad edition'
        provenance = (f'{edition} written by calc_common/bpad.py ({spec.package}) from the notebook case {self.case_sha[:12]}'
                      + ('' if live else f' (package {self.revision})') + '. Every definition was evaluated independently and compared with '
                      'the notebook to 1 part in 10⁹' + ('; the inputs the journal owns are live references, compared with the case by the '
                                                         'coherence gate before the build.' if live else '.'))
        bs.para(notes, provenance, fontsize='10', textcolor=bs.NOTE_COLOR)
        if self.extra_provenance:
            bs.para(notes, self.extra_provenance, fontsize='10', textcolor=bs.NOTE_COLOR)
        for item in spec.text.get('working_notes', []):
            bs.para(notes, item, fontsize='10', textcolor=bs.NOTE_COLOR)
        pending = spec.text.get('pending', [])
        if pending:
            bs.para(notes, 'Pending items: ' + ' '.join(pending), fontsize='10', textcolor=bs.NOTE_COLOR)
        bs.note(notes, CLOSING_NOTE, size=9)
        bs.note(rep, LEGEND)
        # overview
        bs.heading(rep, 'Overview')
        for p in spec.text.get('overview', []):
            bs.para(rep, p, background=bs.PALETTE['discussion'][0])
        if spec.text.get('outside'):
            bs.para(rep, 'Outside this calculation: ' + spec.text['outside'], background=bs.PALETTE['discussion'][0])
        for block in spec.text.get('overview_blocks', []):
            self.place_block(block)
        # sections
        used = set()
        order = [d['name'] for d in spec.input_spec]
        from pier_cap.engine import parse
        from .model import names_in
        used_by_defs = set()
        for d in e.definitions:
            if 'function' not in d:
                names_in(parse(d['expr']), used_by_defs)
        by_group = {}
        titles = {s['title'] for s in spec.sections} | {s['key'] for s in spec.sections}
        for d in spec.input_spec:
            # an input sits under the section named like its group (the journal's own input headings), else at first use
            if d['name'] not in used_by_defs or d.get('group') in titles:
                by_group.setdefault(d.get('group'), []).append(d['name'])
        grouped = {n for names in by_group.values() for n in names if spec.inputs[n].get('group') in titles}
        # a journal section may span several sheet sections: one wrapper per name, open until its last use
        last_use = {}
        for si, section in enumerate(spec.sections):
            if section.get('native_section'):
                last_use[section['native_section']] = (si, -1)
            for d in e.definitions:
                if d['section'] == section['key'] and d.get('native_section'):
                    last_use[d['native_section']] = (si, -2)          # closed only by a later block or at the end
            for bi, b in enumerate(section.get('blocks', [])):
                if b['kind'] == 'prose_section':
                    last_use[b['name']] = (si, bi)
        for si, section in enumerate(spec.sections):
            key = section['key']
            level = section.get('level', 0)
            blocks = section.get('blocks', [])
            closes = {name: bi for name, (s, bi) in last_use.items() if s == si}
            for name in [n for n, _ in self.native_stack]:
                if last_use.get(name, (-1, -1))[0] < si:
                    self.close_native(name)
            if section.get('native_section'):
                self.open_native(section['native_section'])
            if level == 0:
                h = bs.heading(self.cur, section['title'], page_break=bool(section.get('page_break')))
            else:
                h = bs.subheading(self.cur, section['title'])
            if key in spec.anchors:
                h.set('id', spec.anchors[key])
            text = section.get('text')
            for p in ([text] if isinstance(text, str) else (text or [])):
                bs.note(self.cur, p)
            if closes.get(section.get('native_section')) == -1:
                self.close_native(section['native_section'])
            for i, b in enumerate(blocks):
                if b.get('at', 'start') == 'start':
                    self.place_block(b, i, closes)
            defs = [d for d in e.definitions if d['section'] == key]
            names = set()
            for d in defs:
                if 'function' not in d:
                    names_in(parse(d['expr']), names)
            inputs = [n for n in sorted(names, key=lambda n: order.index(n) if n in order else 1e9) if n in spec.inputs and n not in used and n not in grouped]
            for n in section.get('extra_inputs', []) + by_group.get(section['title'], []) + by_group.get(key, []):
                if n not in used and n in spec.inputs and n not in inputs:
                    inputs.append(n)
            for n in inputs:
                d = spec.inputs[n]
                bs.equation(self.cur, self.input_formula(d), self.input_caption(d), style='Required Input', inline=True)
                self.input_names.append(n)
                used.add(n)
            after = {}
            for i, b in enumerate(blocks):
                if b.get('at') not in ('start', 'end', None):
                    after.setdefault(b['at'], []).append((i, b))
            hidden_parent = None
            for d in defs:
                if d.get('native_section') and d['native_section'] != self.open_name:
                    self.open_native(d['native_section'])
                    hidden_parent = None
                parent = self.cur
                if d['hidden']:
                    if hidden_parent is None:
                        hidden_parent = bs.section(self.cur, f'{key}Rows', hide=True)
                        bs.note(hidden_parent, section.get('hidden_title', 'Working rows (hidden): the row-by-row definitions behind the tables.'), size=10)
                    parent = hidden_parent
                formula = d['formula'] + (f' to {bp_unit(d["unit"])}' if d.get('unit') and 'function' not in d and d.get('show_unit', True) else '')
                dyn = bs.equation(parent, formula, d['caption'] + (f' ({spec.refs_text(d["refs"])})' if d['refs'] else ''))
                if d.get('anchor'):
                    dyn.getparent().set('id', d['anchor'])
                self.defined.append(d['name'])
                for i, b in after.get(d['name'], []):
                    self.place_block(b, i, closes)
                    hidden_parent = None if self.cur is not parent and parent is not hidden_parent else hidden_parent
            for i, b in enumerate(blocks):
                if b.get('at') == 'end':
                    self.place_block(b, i, closes)
        self.close_native()
        leftover = [n for n in order if n not in used and n not in spec.text.get('unused_inputs', [])]
        if leftover:
            bs.subheading(rep, 'Reference values')
            bs.note(rep, 'Values read by the figures and tables of this calculation.')
            for n in leftover:
                d = spec.inputs[n]
                bs.equation(rep, self.input_formula(d), self.input_caption(d), style='Required Input', inline=True)
                self.input_names.append(n)
                used.add(n)
        self.cur = rep
        # checks
        n = sum(1 for s in spec.sections if s.get('level', 0) == 0)
        bs.heading(rep, f'{n + 1}. Checks')
        if spec.checks:
            rows = []
            for c in spec.checks:
                demand = c.get('demand', '')
                capacity = c.get('capacity', '')
                dem = ('formula', self.cell_ref(demand)) if demand in e.units else str(demand)
                cap = ('formula', self.cell_ref(capacity)) if capacity in e.units else str(capacity)
                ratio = ('formula', c['ratio_name']) if c.get('ratio_name') else '—'
                result = ('formula', c['flag']) if c.get('flag') else ('formula', f'If({c["ratio_name"]} <= 1, "{PASS}", "{FAIL}")') if c.get('ratio_name') else '—'
                rows.append([c['label'], dem, cap, ratio, result])
            bs.table(rep, 'Checks', ['Check', 'Demand', 'Capacity / limit', 'Ratio', 'Result'], rows, [250, 95, 95, 60, 90])
        conditions = []
        for c in spec.checks:
            if c.get('flag'):
                for value in c.get('fail_values', [FAIL]):
                    conditions.append(f'{c["flag"]} == "{value}"')
            if c.get('ratio_name') and c.get('kind', 'ratio') == 'ratio':
                conditions.append(f'{c["ratio_name"]} > 1')
        if conditions:
            status = f'Status = If(Or({", ".join(conditions)}), "{FAILURES}", "{ALL_PASS}")' if len(conditions) > 1 else \
                f'Status = If({conditions[0]}, "{FAILURES}", "{ALL_PASS}")'
        else:
            status = f'Status = "{ALL_PASS}"'
        bs.equation(rep, status, 'Overall status of the recomputed numerical checks.')
        bs.rewrite_visible_text(rep, [(old, new) for old, new in spec.text.get('visible_rules', [])])
        return self

    def cell_ref(self, name):
        unit = self.e.units.get(name)
        return name + (f' to {bp_unit(unit)}' if unit else '')


# ----------------------------------------------------------------------------- verification
def check_submission_text(rep, accepted=()):
    bad = []
    for el, text in bs.visible_text_elements(rep):
        m = bs.SUBMISSION_FORBIDDEN.search(text)
        if m and not any(a in text for a in accepted):
            bad.append(f'  {el.tag} ({m.group(0)!r}): {text[:120]}')
    if bad:
        raise BuildError(f'working language in the visible text of {rep.get("name")}:\n' + '\n'.join(bad))


def check_formula_rules(rep):
    """No exponent notation, no bare-unit division or multiplication, only the case-sensitive function names."""
    for el in rep.iter():
        if not isinstance(el.tag, str):
            raise BuildError('XML comment in the report')
        formula = el.get('formula')
        if not formula:
            continue
        stripped = re.sub(r'"[^"]*"', '""', formula)
        stripped = re.sub(r'\s+to\s+[A-Za-z0-9^*/ ]+$', '', stripped)
        if re.search(r'(?<![A-Za-z_0-9.])\d+(\.\d+)?[eE][+-]?\d+', stripped):
            raise BuildError(f'exponent notation in {formula!r}')
        for fn in re.findall(r'([A-Za-z_][A-Za-z_0-9]*)\(', stripped):
            lhs, _ = bs.split_definition(formula)
            if fn in FUNCTION_NAMES or (lhs and lhs.startswith(fn + '(')):
                continue
            raise BuildError(f'function {fn} in {formula!r}')
    for p in rep.iter('paragraph'):
        if p.text and ('\n' in p.text or '\r' in p.text):
            raise BuildError('newline in paragraph text')


def compare(eng, e, names):
    """[(name, sheet value, notebook value)] for every name; raises on a difference beyond TOL."""
    out, bad = [], []
    for name in names:
        mine = eng.get(name)
        theirs = e.engine.get(name)
        if isinstance(theirs, bool) or isinstance(mine, bool):
            ok = mine == theirs
            a, b = mine, theirs
        elif isinstance(theirs, str) or isinstance(mine, str):
            ok = mine == theirs
            a, b = mine, theirs
        else:
            a, b = mine.v, theirs.v
            ok = abs(a - b) <= TOL * max(1.0, abs(b)) and all(abs(p - q) < 1e-8 for p, q in zip(mine.d, theirs.d))
        out.append((name, a, b))
        if not ok:
            bad.append(f'  {name}: {a!r} vs {b!r}')
    if bad:
        raise BuildError('Blockpad values differ from the notebook:\n' + '\n'.join(bad[:40]))
    return out


def build(spec, e, revision='working copy', journal=None, extra_provenance=None):
    """Build and verify one edition: (sheet, engine, meta). `journal` is a bs.JournalLinks for the journal edition."""
    jctx = journal_context(spec, journal, e) if journal is not None else None
    sheet = Sheet(spec, e, revision, jctx, extra_provenance).build()
    rep = sheet.rep
    check_submission_text(rep, accepted=tuple(spec.text.get('accepted_wording', [])))
    eng = bs.BpEngine(report=spec.name)
    if jctx is not None:
        jctx.apply(eng)
    n_defs = n_funcs = 0
    for dyn in rep.iter('dynexp'):
        formula = dyn.get('formula')
        body = dyn.find('expbody')
        if body is None or body.text != formula:
            raise BuildError(f'expbody differs from the formula: {formula!r}')
        lhs, _ = bs.split_definition(formula)
        if lhs is None:
            eng.check(formula)
            continue
        name = eng.add(formula)
        if name in eng.functions:
            n_funcs += 1
        else:
            n_defs += 1
    if eng.unresolved_calls():
        raise BuildError(f'undefined functions: {eng.unresolved_calls()}')
    eng.all()
    taken = set(eng.defs) | set(eng.functions)
    for name in sorted(taken):
        if re.fullmatch(r'[A-Za-z]{1,3}[0-9]+', name):
            raise BuildError(f'{name} looks like a spreadsheet cell address')
    for el in rep.iter('table', 'canvas', 'textcell', 'section'):
        if el.get('name') in taken:
            raise BuildError(f'{el.tag} name {el.get("name")} is also a definition')
    names = [el.get('name') for el in rep.iter('table', 'canvas', 'section') if el.get('name')]
    if len(names) != len(set(names)):
        raise BuildError(f'duplicate table, canvas or section name: {sorted({n for n in names if names.count(n) > 1})}')
    n_cells = bs.write_caches(rep, eng, spec.name)
    for el in rep.iter('c', 'planecontainer', 'lineardim', 'plot'):
        if el.get('formula'):
            if el.tag == 'plot':
                m = re.match(r'\s*PlotLines\s*\((.*)\)\s*$', el.get('formula'), re.S)
                if not m:
                    raise BuildError(f'unreadable plot {el.get("formula")!r}')
                continue
            eng.evaluate(el.get('formula'))
    check_formula_rules(rep)
    # (b) inputs
    case = e.case['inputs']
    for name in sheet.input_names:
        d = spec.inputs[name]
        kind = d.get('kind', 'number')
        mine = eng.get(name)
        tol = TOL if (jctx is not None and name in jctx.refs) else INPUT_TOL      # a live reference: the gate already compared it
        if kind == 'number':
            unit = bp_unit(d.get('unit')) if d.get('unit') else None
            value = in_unit(mine, unit)
            if not abs(value - float(case[name])) <= tol * max(abs(float(case[name])), 1e-12):
                raise BuildError(f'input {name}: the sheet holds {value!r}, the notebook {case[name]!r}')
        elif kind == 'bool':
            if mine is not bool(case[name]):
                raise BuildError(f'input {name}: the sheet holds {mine!r}, the notebook {case[name]!r}')
        elif str(mine) != str(case[name]):
            raise BuildError(f'input {name}: the sheet holds {mine!r}, the notebook {case[name]!r}')
    missing = set(spec.inputs) - set(sheet.input_names) - set(spec.text.get('unused_inputs', []))
    if missing:
        raise BuildError(f'notebook inputs missing from the sheet: {sorted(missing)}')
    # (c) against the notebook
    shown = compare(eng, e, [d['name'] for d in e.definitions if 'function' not in d] + list(sheet.input_names))
    # (d) published names
    absent = [n for n in spec.published if n not in taken]
    if absent:
        raise BuildError(f'names other journal modules read are not defined: {absent}')
    # (e) checks and status
    for c in spec.checks:
        if c.get('flag'):
            want = e.engine.get(c['flag'])
            if eng.get(c['flag']) != want:
                raise BuildError(f'{c["flag"]} is {eng.get(c["flag"])!r} in the sheet, {want!r} in the notebook')
    status = eng.get('Status')
    if status not in (ALL_PASS, FAILURES):
        raise BuildError(f'Status {status!r}')
    if (status == ALL_PASS) != (e.blockpad_status == ALL_PASS):
        failed = [c.key for c in e.checks if 'FAIL' in c.status]
        raise BuildError(f'Status {status!r} disagrees with the notebook checks (failing: {failed})')
    if jctx is not None:
        check_journal_edition(spec, rep, jctx)
    meta = dict(definitions=n_defs, functions=n_funcs, cells=n_cells, comparisons=len(shown), mathcad_values=None, status=status,
                case_sha256=sheet.case_sha, revision=revision)
    if jctx is not None:
        meta['journal'] = jctx.summary()
    return sheet, eng, meta


def check_journal_edition(spec, rep, jctx):
    defs = {}
    for dyn in rep.iter('dynexp'):
        lhs, rhs = bs.split_definition(dyn.get('formula'))
        if lhs:
            defs[lhs] = rhs
    for name, (owner, unit, kind) in jctx.refs.items():
        want = owner + (f' to {bp_unit(unit)}' if unit and kind == 'number' else '')
        if defs.get(name) != want:
            raise BuildError(f'{name} is {defs.get(name)!r} in the report; the reference {want!r} is required')
    tables = [t for t in rep.iter('table') if t.get('name') == 'ProjectStamp']
    if len(tables) != 1:
        raise BuildError(f'the report holds {len(tables)} ProjectStamp tables, not 1')
    first = next(el for el in rep if el.tag not in ('include', 'stylerule'))
    if first.tag != 'embed' or first.find('table') is not tables[0]:
        raise BuildError('the ProjectStamp table is not the first thing after the report stylerules')
    cells = bs.stamp_cells(tables[0])
    if [owner for _, _, owner in cells] != [f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS]:
        raise BuildError('the ProjectStamp cells are not live ProjectInfo references')
    if [text for _, text, _ in cells] != [jctx.stamp[k] for k in bs.STAMP_KEYS]:
        raise BuildError('the ProjectStamp caches differ from the ProjectInfo strings')


# ----------------------------------------------------------------------------- outputs
def entry_of(spec, sheet, meta, data):
    return {
        'report_name': spec.name, 'case_sha256': meta['case_sha256'], 'package_revision': meta['revision'],
        'definitions': meta['definitions'], 'functions': meta['functions'], 'cells_and_labels': meta['cells'],
        'tool_comparisons': meta['comparisons'], 'mathcad_values_compared': meta['mathcad_values'], 'status': meta['status'],
        'bpad_sha256': hashlib.sha256(data).hexdigest(),
    }


def json_bytes(value):
    return json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True).encode('utf-8')


def write_outputs(spec, sheet, eng, meta, out_dir=None):
    """<package>/<bpad file> and <package>/bpad/{fragments/<name>.xml, verification.json}; returns the verification entry."""
    out = Path(out_dir) if out_dir else spec.dir
    side = out / 'bpad'
    (side / 'fragments').mkdir(parents=True, exist_ok=True)
    data = bs.serialize(sheet.doc)
    (out / spec.bpad_file).write_bytes(data)
    (side / 'fragments' / f'{spec.name}.xml').write_bytes(bs.serialize(sheet.rep, declaration=False).rstrip())
    entry = entry_of(spec, sheet, meta, data)
    entry['bpad_file'] = f'{spec.package}/{spec.bpad_file}' if out_dir is None else f'{out.name}/{spec.bpad_file}'
    (side / 'verification.json').write_bytes(json_bytes([entry]))
    return entry


def review_document(spec, sheet):
    doc = bs.new_document()
    rep = copy.deepcopy(sheet.rep)
    stamp = next(i for i, el in enumerate(rep) if el.tag == 'embed')
    banner = bs.para(rep, 'Review copy: the references to other journal modules (Bridge Geometry, Materials, the load modules and ProjectInfo) '
                     'resolve only inside the project journal (D2_I95_Project_Journal.bpad). Opened on its own, this file shows them as undefined; '
                     'the values stored in it are the journal values at the time of the build.', fontsize='10', textcolor='#8A2B1F',
                     background='#FBE9E5', spacingafter='8')
    rep.remove(banner)
    rep.insert(stamp + 1, banner)
    doc.append(rep)
    return bs.serialize(doc)


def write_journal_outputs(spec, links, sheet, eng, meta, out_dir=None):
    base = (Path(out_dir) if out_dir else spec.dir / 'bpad') / 'journal'
    base.mkdir(parents=True, exist_ok=True)
    shown_base = f'{spec.package}/bpad/journal' if out_dir is None else f'{Path(out_dir).name}/journal'
    data = bs.serialize(sheet.rep, declaration=False).rstrip()
    (base / f'{spec.name}.xml').write_bytes(data)
    review = review_document(spec, sheet)
    review_file = f'{spec.title} - Journal Edition (review).bpad'
    (base / review_file).write_bytes(review)
    summary = meta['journal']
    entry = entry_of(spec, sheet, meta, data)
    entry.pop('bpad_sha256')
    entry.update({
        'fragment': f'{shown_base}/{spec.name}.xml', 'fragment_sha256': hashlib.sha256(data).hexdigest(),
        'journal_file': links.source, 'project_stamp': {'owner': bs.PROJECT_INFO, **sheet.journal.stamp},
        'journal_references': summary['references'], 'literals_kept': [r['input'] for r in summary['literals']],
        'references': sorted({r['owner'] for r in summary['rows'] if r['status'] == 'reference'}),
        'review_document': f'{shown_base}/{review_file}', 'review_sha256': hashlib.sha256(review).hexdigest(),
    })
    (base / 'coherence.json').write_text(json.dumps({spec.name: summary['rows']}, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
    (base / 'verification.json').write_bytes(json_bytes([entry]))
    return entry


def distill(spec, e, revision='working copy'):
    """(bpad bytes, verification.json bytes) of an evaluated case, for the notebook export; touches no files."""
    sheet, eng, meta = build(spec, e, revision, extra_provenance='Exported from the notebook for the current case.')
    data = bs.serialize(sheet.doc)
    return data, json_bytes([entry_of(spec, sheet, meta, data)])
