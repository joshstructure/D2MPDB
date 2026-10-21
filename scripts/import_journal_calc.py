"""Snapshot one hand-authored journal calculation into a calculation package's data folder.

    .venv\\Scripts\\python.exe scripts\\import_journal_calc.py FenceWind fence_wind

Writes ``<package>/data/journal_import.json``: every definition of the journal module in document order with its
heading path, caption (the bold line under the equation), hidden equation notes, cited provisions and the value the
journal's own formula gives when evaluated independently (scripts/bpad_sheet.py BpEngine with the referenced values
of the other journal modules); the result tables; the native canvases and the prose blocks (as XML, with their
anchor ids) that the Blockpad edition carries forward; the qualified names other journal modules read from this one
and the native links that point into it. The package author turns this snapshot into ``definitions.json``,
``inputs.json`` and the layout; nothing here is engineering acceptance.
"""
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import bpad_sheet as bs  # noqa: E402
from report_cards import prose_pieces  # noqa: E402

JOURNAL = ROOT / 'journal' / 'D2_I95_Project_Journal.bpad'
SKIP = ('Today(', 'Any(', '[')                       # formula features the independent evaluator does not read


def text_of(el, links=True):
    parts = []

    def rec(node):
        if node.tag == 'dynexp':
            parts.append('⟨' + (node.get('formula') or '') + '⟩')
            return
        if node.tag == 'link':
            parts.append(node.text or '')
            return
        if node.text:
            parts.append(node.text)
        for c in node:
            rec(c)
            if c.tail:
                parts.append(c.tail)
    rec(el)
    return ' '.join(' '.join(p.split()) for p in parts if p and p.strip())


def cache_text(d):
    for tag in ('expresult', 'num', 'bool', 'textvalue', 'error'):
        x = d.find(tag)
        if x is not None:
            return (x.text or '').strip()
    return ''


def normalise(formula):
    """'name = rhs' with single spaces around the first '='; the rhs as written."""
    m = bs.JournalLinks.DEFINITION.match(formula or '')
    if not m:
        return None, formula
    return m.group(1), m.group(2)


def qualified_names(formula):
    try:
        lhs, rhs = normalise(formula)
        expr, _ = bs.split_to(rhs)
        names, _ = bs.tree_names(bs.parse(expr))
    except Exception:
        return set()
    return {n for n in names if '.' in n}


def walk(report):
    """Document-order items with heading context, hidden flag and enclosing section name."""
    items, heading = [], []

    def rec(el, hidden, section):
        tag = el.tag
        if tag == 'section':
            h = hidden or (el.get('hide') or '').lower() == 'true'
            for c in el:
                rec(c, h, el.get('name'))
            return
        if tag == 'heading':
            level = int(el.get('level') or 0)
            del heading[level:]
            heading.append(text_of(el))
            items.append(dict(kind='heading', level=level, text=text_of(el), id=el.get('id'), hidden=hidden, section=section,
                              style=el.get('style'), pagebreak=el.get('pagebreakbefore'), xml=ET.tostring(el, encoding='unicode')))
            return
        if tag == 'paragraph':
            dyns = el.findall('.//dynexp')
            for field in el.findall('.//valuefield'):
                text = field.findtext('textvalue') or ''
                options = re.findall(r'"([^"]*)"', field.get('valuedef') or '')
                items.append(dict(kind='def', name=field.get('name'), rhs='"' + text + '"', formula=f'{field.get("name")} = "{text}"',
                                  cache=text, hidden=hidden, section=section, heading=' / '.join(heading), options=options,
                                  inline=text_of(el), valuefield=True))
            if dyns:
                for d in dyns:
                    name, rhs = normalise(d.get('formula') or '')
                    items.append(dict(kind='def' if name and '(' not in name else 'function' if name else 'show',
                                      name=name, rhs=rhs, formula=d.get('formula'), cache=cache_text(d), hidden=hidden, section=section,
                                      heading=' / '.join(heading), style=d.get('style'), showresult=d.get('showresult'), id=el.get('id'),
                                      inline=text_of(el).replace('⟨' + (d.get('formula') or '') + '⟩', '').strip()))
            else:
                items.append(dict(kind='prose', id=el.get('id'), text=text_of(el), hidden=hidden, section=section, heading=' / '.join(heading),
                                  bold=el.get('fontweight') == 'bold', fontsize=el.get('fontsize'), background=el.get('background'),
                                  xml=ET.tostring(el, encoding='unicode')))
            return
        if tag == 'table':
            rows = []
            has_formula = False
            for row in el.findall('row'):
                cells = []
                for cell in row:
                    f = cell.get('formula')
                    if f:
                        has_formula = True
                        cells.append(dict(formula=f, cache=cache_text(cell)))
                    else:
                        dyn = [d.get('formula') for d in cell.findall('.//dynexp')]
                        cells.append(dict(text=text_of(cell), dyn=dyn))
                rows.append(cells)
            items.append(dict(kind='table', name=el.get('name'), title=el.get('title'), colwidths=el.get('colwidths'), rows=rows,
                              formulas=has_formula, hidden=hidden, section=section, heading=' / '.join(heading),
                              xml=ET.tostring(el, encoding='unicode')))
            return
        if tag == 'canvas':
            qualified = set()
            for c in el.iter():
                if c.get('formula'):
                    qualified |= qualified_names('x = ' + c.get('formula'))
            items.append(dict(kind='canvas', name=el.get('name'), title=el.get('title'), size=el.get('size'), hidden=hidden, section=section,
                              heading=' / '.join(heading), qualified=sorted(qualified), xml=ET.tostring(el, encoding='unicode')))
            return
        if tag == 'embed':
            for c in el:
                rec(c, hidden, section)
            return
        for c in el:
            rec(c, hidden, section)

    for child in report:
        rec(child, False, None)
    return items


def attach_captions(items):
    """Caption = the bold paragraph after a definition; notes = the EqNotes hidden section that follows; references nearby."""
    for i, it in enumerate(items):
        if it['kind'] not in ('def', 'function'):
            continue
        caption, notes, refs = '', [], []
        j = i + 1
        while j < len(items):
            nxt = items[j]
            if nxt['kind'] in ('def', 'function', 'heading', 'canvas', 'table'):
                break
            if nxt['kind'] == 'prose':
                if nxt['hidden'] and (nxt['section'] or '').startswith('EqNotes'):
                    if nxt['text']:
                        notes.append(nxt['text'])
                    nxt['role'] = 'note'
                elif not nxt['hidden'] and nxt['bold'] and not caption and not nxt['text'].startswith('STEP'):
                    caption = nxt['text']
                    nxt['role'] = 'caption'
                elif not nxt['hidden'] and nxt['text'].startswith(('Reference:', 'Code basis:')):
                    refs.append(nxt['text'])
                    nxt['role'] = 'reference'
                elif not nxt['hidden'] and not caption and not nxt['text'].startswith('STEP'):
                    break
            if nxt['kind'] == 'show' and nxt['hidden']:
                pass
            j += 1
        it['caption'] = caption
        it['notes'] = notes
        pieces = []
        for text in [caption] + refs + notes + [it.get('inline', '')]:
            for p in prose_pieces(text or ''):
                if p not in pieces:
                    pieces.append(p)
        it['refs'] = pieces


def evaluate_module(items, links, report_name):
    """Evaluate the journal's own formulas with the independent evaluator: name -> (value, dims) or text."""
    eng = bs.BpEngine(report=report_name)
    externals = {}
    skipped = []
    for it in items:
        if it['kind'] not in ('def', 'function'):
            continue
        if any(s in it['rhs'] for s in SKIP):
            skipped.append(it['name'])
            continue
        for q in qualified_names(it['formula']):
            owner = q.split('.', 1)[0]
            if owner == report_name or q in externals:
                continue
            externals[q] = links.value(q)
        try:
            eng.add(f'{it["name"]} = {it["rhs"]}')
        except bs.BpError as e:
            skipped.append(f'{it["name"]} ({e})')
    # values the tables and canvases read from other modules (not reached by the definitions)
    for it in items:
        formulas = []
        if it['kind'] == 'table':
            formulas = [c['formula'] for row in it['rows'] for c in row if 'formula' in c] + [f for row in it['rows'] for c in row for f in c.get('dyn', [])]
        elif it['kind'] == 'canvas':
            formulas = ['x = ' + q for q in it['qualified']]
        for f in formulas:
            for q in qualified_names(f if ' = ' in f else 'x = ' + f):
                owner = q.split('.', 1)[0]
                if owner == report_name or q in externals:
                    continue
                try:
                    externals[q] = links.value(q)
                except bs.BpError as e:
                    skipped.append(f'{q} ({e})')
    for q, v in externals.items():
        eng.add_external(q, v)
    values = {}
    for name in eng.order:
        if name in eng.defs:
            try:
                v = eng.get(name)
            except bs.BpError as e:
                values[name] = {'error': str(e)}
                continue
            values[name] = {'text': v} if isinstance(v, str) else {'bool': v} if isinstance(v, bool) else {'v': v.v, 'dims': list(v.d)}
    return values, externals, skipped, eng


def inbound(root, report_name):
    calc = re.escape(report_name)
    qual = re.compile(r'\b' + calc + r'\.([A-Za-z_Ͱ-Ͽ][A-Za-z_0-9Ͱ-Ͽ]*)')
    names, link_targets = defaultdict(set), defaultdict(set)
    for comp in root:
        owner = comp.get('name')
        if owner == report_name or not isinstance(comp.tag, str):
            continue
        for node in comp.iter():
            for text in (node.get('formula'), node.text if node.tag == 'expbody' else None):
                if text:
                    for m in qual.finditer(text):
                        names[m.group(1)].add(f'{comp.tag}:{owner}')
            if node.tag == 'link' and (node.get('address') or '').startswith('#' + report_name):
                link_targets[node.get('address')].add(f'{comp.tag}:{owner}')
    return {n: sorted(v) for n, v in sorted(names.items())}, {a: sorted(v) for a, v in sorted(link_targets.items())}


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    report_name, package = argv[0], argv[1]
    links = bs.JournalLinks.load(JOURNAL)
    rep = links.reports[report_name]
    items = walk(rep)
    attach_captions(items)
    values, externals, skipped, eng = evaluate_module(items, links, report_name)
    ext = {}
    for q, v in externals.items():
        owner = q.split('.', 1)[0]
        entry = {'kind': links.owner_kind(owner)}
        if isinstance(v, str):
            entry['text'] = v
        elif isinstance(v, bool):
            entry['bool'] = v
        else:
            entry.update(v=v.v, dims=list(v.d))
        if entry['kind'] == 'report':
            entry['journal_formula'] = links.formula(q)
        else:
            cached, formula = links.cells(owner).get(q.split('.', 1)[1], (None, None))
            entry.update(cache=cached, journal_formula=formula)
        ext[q] = entry
    for it in items:
        if it['kind'] in ('def', 'function') and it['name'] in values:
            it['evaluated'] = values[it['name']]
            if it['name'] in eng.units and eng.units[it['name']]:
                it['unit'] = eng.units[it['name']]
    names_in, links_in = inbound(links.root, report_name)
    internal = sorted({n.get('address') for n in rep.iter('link') if (n.get('address') or '').startswith('#' + report_name)})
    out = {
        'journal': bs.display_path(JOURNAL), 'journal_sha256': hashlib.sha256(JOURNAL.read_bytes()).hexdigest(),
        'report': report_name, 'title': rep.get('title'), 'items': items, 'externals': ext, 'skipped': skipped,
        'inbound_names': names_in, 'inbound_links': links_in, 'internal_links': internal,
        'anchors': [(n.tag, n.get('id')) for n in rep.iter() if n.get('id')],
    }
    folder = ROOT / package / 'data'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'journal_import.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
    n_def = sum(1 for i in items if i['kind'] == 'def')
    print(f'{report_name}: {n_def} definitions, {len(ext)} external values, {len(skipped)} skipped {skipped}, '
          f'{len(names_in)} names read by other modules, {len(links_in)} inbound link targets -> {package}/data/journal_import.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
