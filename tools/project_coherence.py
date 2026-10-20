"""Read-only source/issue checks. Only --write-report writes generated views.

This is an inventory and bounded consistency check, not a native design solver.
It never modifies the tracker, source register, journal, or calculation files.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {'Open', 'In progress', 'Awaiting source', 'Deferred', 'Closed', 'Not applicable'}
CLOSED = {'Closed', 'Not applicable'}
HEADERS = ['Item ID', 'Status', 'Area', 'Item', 'Finding', 'Next action',
           'Your response', 'Owner', 'Due date', 'Resolution / evidence',
           'Source references', 'Last reviewed']
# Assumptions-and-gaps register: hand-edited, committed, never generated.
ASSUMPTIONS = 'project_current/coherence/assumptions.json'
ASSUMPTION_SCHEMA = 'd2mpdb.assumptions-register'
ASSUMPTION_KINDS = ('assumption', 'gap', 'placeholder', 'judgment')
DISPOSITIONS = ('accepted-negligible', 'pending', 'closed')
OPEN_DISPOSITIONS = {'pending'}


def read_assumptions(path):
    """Read the register without reinterpreting it. Absent file -> None."""
    path = Path(path)
    if not path.is_file(): return None
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or data.get('schema') != ASSUMPTION_SCHEMA or data.get('schema_version') != 1:
        raise ValueError('Unsupported assumptions register schema: ' + str(path))
    if not isinstance(data.get('entries'), list) or not all(isinstance(e, dict) for e in data['entries']):
        raise ValueError('Assumptions register entries must be a list of objects.')
    return data


def assumption_state(entry, sources):
    """Compare an entry's recorded basis hashes with the current register.

    Stale means the register now adopts a different revision of a basis source
    than the one the entry was judged against. A source that is on disk but
    differs from its registered revision is reported by SOURCE checks, not here.
    """
    registered = {s['source_id']: (s.get('sha256') or '').lower() for s in sources}
    basis = entry.get('basis') if isinstance(entry.get('basis'), dict) else {}
    current, stale, unknown = {}, [], []
    for key, recorded in basis.items():
        if key not in registered:
            unknown.append(key); continue
        current[key] = registered[key] or None
        if (str(recorded) if recorded is not None else '').lower() != registered[key]:
            stale.append(key)
    status = (entry.get('disposition') or {}).get('status') if isinstance(entry.get('disposition'), dict) else None
    return dict(stale=bool(stale), stale_sources=sorted(stale), unknown_sources=sorted(unknown),
                current_basis=current, open=status in OPEN_DISPOSITIONS)


def assumption_checks(register, sources, items):
    """Validate the register and report stale entries; nothing is re-judged."""
    results = []
    if register is None: return results
    entries = register['entries']
    counts = Counter(str(e.get('id', '')) for e in entries)
    source_ids = {s['source_id'] for s in sources}
    item_ids = {i['Item ID'] for i in items}
    for entry in entries:
        key = str(entry.get('id', ''))
        reasons = []
        if not re.fullmatch(r'A-\d{3,}', key): reasons.append('Set a stable A-### ID.')
        if counts[key] > 1: reasons.append('Duplicate entry ID.')
        if entry.get('kind') not in ASSUMPTION_KINDS: reasons.append('Choose a kind: ' + ', '.join(ASSUMPTION_KINDS) + '.')
        for field in ('statement', 'where', 'owner'):
            if not str(entry.get(field) or '').strip(): reasons.append('Missing ' + field + '.')
        nodes = entry.get('nodes')
        if not isinstance(nodes, list) or not nodes or not all(isinstance(n, str) and n for n in nodes):
            reasons.append('Name at least one atlas node id in nodes.')
        magnitude = entry.get('magnitude')
        if not isinstance(magnitude, dict) or not str(magnitude.get('sized_by') or '').strip():
            reasons.append('Magnitude needs value, unit and sized_by.')
        elif magnitude.get('value') is not None and not isinstance(magnitude.get('value'), (int, float)):
            reasons.append('Magnitude value must be a number or null.')
        disposition = entry.get('disposition')
        if not isinstance(disposition, dict) or disposition.get('status') not in DISPOSITIONS:
            reasons.append('Choose a disposition status: ' + ', '.join(DISPOSITIONS) + '.')
        else:
            decision = str(disposition.get('decision') or '')
            if decision and not re.fullmatch(r'D-\d{3,}', decision): reasons.append('Decision reference must look like D-0xx.')
            if disposition['status'] != 'pending' and not decision: reasons.append('A settled disposition needs its decision reference.')
            on = str(disposition.get('on') or '')
            try: datetime.strptime(on, '%Y-%m-%d')
            except ValueError: reasons.append('Disposition date must be YYYY-MM-DD.')
        coh = entry.get('coherence_items', [])
        if not isinstance(coh, list): reasons.append('coherence_items must be a list.')
        else:
            for ref in coh:
                if ref not in item_ids: reasons.append('Unknown tracker item ' + str(ref) + '.')
        basis = entry.get('basis')
        if not isinstance(basis, dict) or not basis: reasons.append('Basis must map at least one register source id to its SHA-256.')
        else:
            for src, digest in basis.items():
                if src not in source_ids: reasons.append('Unknown basis source ' + str(src) + '.')
                elif not re.fullmatch(r'[a-fA-F0-9]{64}', str(digest or '')): reasons.append('Basis ' + src + ' needs the 64-hex SHA-256 it was judged against.')
        state = assumption_state(entry, sources)
        if reasons:
            results.append(dict(check_id='ASSUMPTION:' + (key or '?'), status='ERROR', detail=' '.join(reasons),
                                source_ids=[s for s in (basis or {}) if s in source_ids] if isinstance(basis, dict) else [], entry_id=key))
        elif state['stale']:
            results.append(dict(check_id='ASSUMPTION:' + key, status='REVIEW',
                                detail='Basis moved in the register (' + ', '.join(state['stale_sources']) + '); re-judge the entry and record new basis hashes.',
                                source_ids=sorted(basis), entry_id=key))
        else:
            results.append(dict(check_id='ASSUMPTION:' + key, status='MATCH', detail='Basis hashes equal the current register.',
                                source_ids=sorted(basis), entry_id=key))
    return results


def assumption_summary(register, sources):
    entries = []
    for entry in (register or {}).get('entries', []):
        entries.append({**entry, **assumption_state(entry, sources)})
    entries.sort(key=lambda e: (not e['stale'], not e['open'], str(e.get('id', ''))))
    return dict(present=register is not None, count=len(entries), open=sum(e['open'] for e in entries),
                stale=sum(e['stale'] for e in entries), entries=entries)


def magnitude_text(entry):
    m = entry.get('magnitude') if isinstance(entry.get('magnitude'), dict) else {}
    value = m.get('value')
    if value is None: return 'not sized'
    unit = str(m.get('unit') or '').strip()
    return (f'{value:g}' if isinstance(value, (int, float)) else str(value)) + (' ' + unit if unit and unit != 'unitless' else '')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(path, basis='exact_bytes'):
    data=path.read_bytes()
    if basis=='lf_text': data=data.replace(b'\r\n',b'\n')
    elif basis!='exact_bytes': raise ValueError('Unknown fingerprint basis: '+basis)
    return hashlib.sha256(data).hexdigest()


def local_path(root, relative):
    p = (root / relative).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError(f'Path leaves repository: {relative}')
    return p


def source_checks(root, sources):
    results = []
    ids = Counter(s['source_id'] for s in sources)
    changed = set()
    for source in sources:
        key = source['source_id']
        status, detail = 'MATCH', 'Exact registered bytes are present.'
        actual = ''
        if ids[key] != 1 or not key:
            status, detail = 'ERROR', 'Source ID is blank or duplicated.'
        elif not source['path']:
            status, detail = 'MISSING', 'No source file has been selected.'
        else:
            try:
                p = local_path(root, source['path'])
                if not p.is_file():
                    status, detail = 'MISSING', 'Registered file is absent.'
                else:
                    actual = source_digest(p, source.get('hash_basis') or 'exact_bytes')
                    if not re.fullmatch(r'[a-fA-F0-9]{64}', source['sha256']):
                        status, detail = 'REVIEW', 'File exists without a valid adopted fingerprint.'
                    elif actual.lower() != source['sha256'].lower():
                        status, detail = 'CHANGED', 'File differs from the registered revision; review its consumers before adoption.'
                        changed.add(key)
                    elif source['status'] in {'Missing', 'Not selected', 'Candidate'}:
                        status, detail = 'REVIEW', 'File now exists but has not been adopted in the register.'
            except (OSError, ValueError) as e:
                status, detail = 'ERROR', str(e)
        if status=='MATCH' and source.get('hash_basis')=='lf_text':
            detail='Registered text content matches after CRLF/LF normalization.'
        results.append(dict(check_id='SOURCE:'+key, status=status, detail=detail,
                            source_ids=[key], path=source['path'], expected_sha256=source['sha256'], actual_sha256=actual))
    by_id = {r['check_id'][7:]: r for r in results}
    for source in sources:
        for dependency in filter(None, source.get('depends_on', '').split(';')):
            dependency = dependency.strip()
            if dependency not in by_id:
                results.append(dict(check_id=f'DEP:{source["source_id"]}:{dependency}', status='ERROR',
                    detail='Dependency source ID is not registered.', source_ids=[source['source_id'], dependency]))
            elif by_id[dependency]['status'] != 'MATCH':
                results.append(dict(check_id=f'DEP:{source["source_id"]}:{dependency}', status='REVIEW',
                    detail='A registered dependency is missing, changed or awaiting adoption. Review the consumer.',
                    source_ids=[source['source_id'], dependency]))
    return results


def safe_value(node):
    """Read the notebook's literal input dictionary without running its code."""
    if isinstance(node, ast.Constant): return node.value
    if isinstance(node, ast.Dict): return {safe_value(k): safe_value(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, (ast.List, ast.Tuple)): return [safe_value(x) for x in node.elts]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return (-1 if isinstance(node.op, ast.USub) else 1) * safe_value(node.operand)
    if isinstance(node, ast.BinOp):
        a, b = safe_value(node.left), safe_value(node.right)
        if isinstance(node.op, ast.Add): return a + b
        if isinstance(node.op, ast.Sub): return a - b
        if isinstance(node.op, ast.Mult): return a * b
        if isinstance(node.op, ast.Div): return a / b
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id == 'np'
        and node.func.attr == 'float64' and len(node.args) == 1 and not node.keywords):
        return float(safe_value(node.args[0]))
    raise ValueError('Unsupported notebook input expression: ' + ast.dump(node)[:120])


def notebook_inputs(path):
    found = {}
    for cell in json.loads(path.read_text(encoding='utf-8'))['cells']:
        if cell.get('cell_type') != 'code': continue
        code = ''.join(cell.get('source', []))
        if 'CONFIG =' not in code and 'END_BENT_DEFAULTS =' not in code: continue
        for node in ast.parse(code).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {'CONFIG', 'END_BENT_DEFAULTS'}:
                        if target.id in found: raise ValueError('Multiple input dictionary definitions: '+target.id)
                        found[target.id] = safe_value(node.value)
    return found['CONFIG'], found['END_BENT_DEFAULTS']


def report_case(path):
    text = html.unescape(path.read_text(encoding='utf-8'))
    decoder = json.JSONDecoder()
    cases = []
    for match in re.finditer(r'\{\s*"schema_version"\s*:', text):
        try:
            case, _ = decoder.raw_decode(text[match.start():])
            if isinstance(case, dict) and 'inputs' in case and 'analysis' in case: cases.append(case)
        except json.JSONDecodeError:
            pass
    if len(cases) != 1: raise ValueError(f'Expected one embedded cap case; found {len(cases)}.')
    return cases[0]


def relationship_checks(root, sources):
    records = {s['source_id']: s for s in sources}
    checks = []
    def path(key): return local_path(root, records[key]['path'])
    def add(id, status, detail, ids): checks.append(dict(check_id=id, status=status, detail=detail, source_ids=ids))
    try:
        accepted = json.loads((root/'workflow/accepted.json').read_text(encoding='utf-8'))
        equal = accepted['journal_sha256'] == digest(path('JOURNAL'))
        add('JOURNAL:acceptance', 'MATCH' if equal else 'CHANGED',
            f'Journal {"matches" if equal else "differs from"} acceptance receipt {accepted.get("task", "unknown")}. Review scope remains as recorded.', ['JOURNAL'])
    except (OSError, KeyError, ValueError) as e:
        add('JOURNAL:acceptance', 'ERROR', str(e), ['JOURNAL'])
    cases = {}
    for prefix in ('PIER', 'EB'):
        case_id, report_id, xml_id = [prefix+'-'+x for x in ('CASE', 'REPORT', 'XML')]
        try:
            case = json.loads(path(case_id).read_text(encoding='utf-8'))
            cases[prefix] = case
            same = case == report_case(path(report_id))
            add(prefix+':report-case', 'MATCH' if same else 'CHANGED',
                'Saved case '+('equals' if same else 'differs from')+' the case embedded in the registered report.', [case_id, report_id])
            expected = case['analysis']['xml_audit']['sha256']
            if path(xml_id).is_file():
                same = digest(path(xml_id)) == expected
                add(prefix+':analysis-identity', 'MATCH' if same else 'CHANGED',
                    'Raw XML '+('matches' if same else 'does not match')+' the case analysis fingerprint.', [case_id, xml_id])
            else:
                add(prefix+':analysis-identity', 'MISSING', 'Exact XML required by the case is absent: '+expected, [case_id, xml_id])
        except (OSError, KeyError, ValueError) as e:
            add(prefix+':case-links', 'ERROR', str(e), [case_id, report_id, xml_id])
    try:
        config, bent = notebook_inputs(path('GEOMETRY'))
        pier = config['pier']
        maps = {
            'PIER': dict(b=pier['width_ft']*12, h=pier['depth_ft']*12,
                N_pile=pier['pile_count'], D_pile=pier['pile_diameter_in'],
                S_pile=pier['pile_spacing_diameters']*pier['pile_diameter_in']/12,
                Pile_embed=pier['pile_embedment_in']),
            'EB': dict(b=bent['width_ft']*12, h=bent['depth_ft']*12,
                N_pile=bent['pile_count'], D_pile=bent['pile_width_in'],
                S_pile=bent['pile_spacing_in']/12, Pile_embed=bent['pile_embedment_in'])}
        for prefix, values in maps.items():
            if prefix not in cases: continue
            inputs = cases[prefix]['inputs']
            for key, value in values.items():
                other = inputs[key]
                same = isinstance(other, (int, float)) and abs(value-other) <= 1e-8
                add(f'GEOMETRY:{prefix}:{key}', 'MATCH' if same else 'CHANGED',
                    f'Notebook {value:g}; saved case {other}. Units: '+('ft' if key=='S_pile' else 'count' if key=='N_pile' else 'in')+'.',
                    ['GEOMETRY', prefix+'-CASE'])
            shape = pier if prefix == 'PIER' else bent
            spacing = values['S_pile']*12
            derived = (values['N_pile']-1)*spacing+values['D_pile']+2*shape['pile_end_clear_in']
            explicit = shape.get('length_ft')
            length = derived if explicit is None else explicit*12
            # D-027: end-bent cap cases span the cap body plus both cheek webs.
            cheeks = 2*shape.get('cheek_thickness_in', 0) if prefix == 'EB' else 0
            audit_length = cases[prefix]['analysis']['xml_audit']['cap_length_ft']*12
            same = abs(length+cheeks-audit_length) <= 0.01
            basis = f'Notebook {length:g} in' + (f' + 2 x {cheeks/2:g} in cheek webs = {length+cheeks:g} in' if cheeks else '')
            add(f'GEOMETRY:{prefix}:length', 'MATCH' if same else 'CHANGED',
                f'{basis}; source audit {audit_length:g} in. Comparison tolerance 0.01 in for printed coordinates.',
                ['GEOMETRY', prefix+'-CASE'])
    except (OSError, KeyError, ValueError, SyntaxError, TypeError) as e:
        add('GEOMETRY:inputs', 'REVIEW', str(e), ['GEOMETRY'])
    for span in (1, 2):
        key = f'MCAD-S{span}'
        try:
            ET.parse(path(key))
            add(key+':parse', 'MATCH', 'Native worksheet XML is readable. No native recalculation or engineering acceptance is implied.', [key])
        except (OSError, ET.ParseError) as e:
            add(key+':parse', 'ERROR', str(e), [key])
    return checks


def read_tracker(path):
    ns = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', ns)]
        book = ET.fromstring(z.read('xl/workbook.xml'))
        sheet = next(s for s in book.findall('s:sheets/s:sheet', ns) if s.get('name') == 'Coherence items')
        rel_id = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = next(r.get('Target') for r in rels if r.get('Id') == rel_id)
        target = target.lstrip('/') if target.startswith('/') else 'xl/'+target
        rows = []
        for row in ET.fromstring(z.read(target)).findall('s:sheetData/s:row', ns):
            values = {}
            for cell in row.findall('s:c', ns):
                col = re.match('[A-Z]+', cell.get('r')).group()
                kind = cell.get('t')
                v = cell.find('s:v', ns)
                if kind == 'inlineStr': value = ''.join(cell.find('s:is', ns).itertext())
                elif v is None: value = ''
                elif kind == 's': value = strings[int(v.text)]
                else: value = v.text or ''
                values[col] = value
            rows.append((int(row.get('r')), values))
    header_row = next(n for n, values in rows if values.get('A') == 'Item ID')
    actual_headers = next(v for n, v in rows if n == header_row)
    if [actual_headers.get(chr(65+i),'') for i in range(len(HEADERS))] != HEADERS:
        raise ValueError('Tracker headers changed. Update the reader mapping deliberately.')
    items = []
    for n, values in rows:
        if n <= header_row: continue
        item = {h: values.get(chr(65+i),'') for i, h in enumerate(HEADERS)}
        if not any(item.values()): continue
        item['_row'] = n
        for field in ('Due date','Last reviewed'):
            if item[field]:
                try: item[field] = (datetime(1899,12,30)+timedelta(days=float(item[field]))).date().isoformat()
                except ValueError: pass
        items.append(item)
    return items


def tracker_checks(items):
    results=[]
    counts=Counter(i['Item ID'] for i in items)
    for item in items:
        reasons=[]
        if not re.fullmatch(r'COH-\d{3,}', item['Item ID']): reasons.append('Set a stable COH-### ID.')
        if counts[item['Item ID']] > 1: reasons.append('Duplicate issue ID.')
        if item['Status'] not in STATUSES: reasons.append('Choose a valid status.')
        for field in ('Area', 'Item', 'Finding', 'Next action', 'Source references', 'Last reviewed'):
            if not item[field].strip(): reasons.append('Missing '+field+'.')
        if item.get('_row',0)>1008:
            reasons.append('Row is beyond the summary/validation capacity; extend those ranges before continuing.')
        if item['Status'] in CLOSED and not item['Resolution / evidence'].strip():
            reasons.append('Closed / not-applicable item requires resolution evidence.')
        if reasons:
            results.append(dict(check_id='TRACKER:'+str(item.get('_row','?')), status='ERROR',
                detail=' '.join(reasons), source_ids=[], issue_id=item['Item ID']))
    return results


def run(root):
    hub=root/'project_current'
    with (hub/'source_register.csv').open(encoding='utf-8-sig', newline='') as f:
        sources=list(csv.DictReader(f))
    checks=source_checks(root,sources)+relationship_checks(root,sources)
    workbook=hub/'coherence/Coherence_Tracker.xlsx'
    items=read_tracker(workbook)
    checks+=tracker_checks(items)
    register=read_assumptions(root/ASSUMPTIONS)
    checks+=assumption_checks(register,sources,items)
    assumptions=assumption_summary(register,sources)
    outstanding=[i for i in items if i['Status'] not in CLOSED]
    totals=dict(Counter(c['status'] for c in checks))
    return dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),
        scope='Exact source identity, file relationships, selected geometry, issue-log completeness and the assumptions register; no native design reruns.',
        register_sha256=digest(hub/'source_register.csv'),tracker_sha256=digest(workbook),
        assumptions_sha256=digest(root/ASSUMPTIONS) if register is not None else None,
        source_count=len(sources),item_count=len(items),outstanding_count=len(outstanding),
        status_counts=dict(Counter(i['Status'] for i in items)),check_counts=totals,
        assumption_counts={k:assumptions[k] for k in ('count','open','stale')},
        checks=checks,items=items,assumptions=assumptions)


def escape(s): return str(s).replace('|','\\|').replace('\n',' ')


def write_report(root, result):
    out=root/'project_current/coherence'
    out.mkdir(parents=True,exist_ok=True)
    # Generated views are committed with LF endings on every platform.
    (out/'machine_checks.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    with (out/'items_snapshot.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=HEADERS,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(result['items'])
    lines=['# Latest project coherence review','',
        f'Checked at {result["checked_at_utc"]}. **{result["outstanding_count"]} outstanding items remain.**','',
        'The [workbook](Coherence_Tracker.xlsx) owns item status and responses. This report is a generated view.',
        'The initial findings were carried forward from the latest adopted pier/end-bent reviews plus source-inventory gaps.',
        'Previously resolved decisions were excluded. This run did not perform native calculations or a complete engineering review.','',
        f'Registered sources: {result["source_count"]}. Tracker items: {result["item_count"]}.',
        'Automatic results: '+', '.join(f'{v} {k.lower()}' for k,v in sorted(result['check_counts'].items()))+'.','',
        '## Files and relationships needing attention','',
        '| Check | Status | Finding |','| --- | --- | --- |']
    flagged=[c for c in result['checks'] if c['status']!='MATCH']
    for c in flagged: lines.append('| '+ ' | '.join(escape(c[k]) for k in ('check_id','status','detail'))+' |')
    if not flagged: lines.append('| Registered automatic checks | Match | No issues within the automated scope. |')
    lines+=['','## Outstanding items','', '| ID | Status | Subject | Next action |','| --- | --- | --- | --- |']
    for item in result['items']:
        if item['Status'] not in CLOSED:
            lines.append('| '+' | '.join(escape(item[k]) for k in ('Item ID','Status','Item','Next action'))+' |')
    assumptions=result.get('assumptions') or {}
    lines+=['','## Assumptions and gaps','']
    if not assumptions.get('present'):
        lines.append('No assumptions register is present at `'+ASSUMPTIONS+'`.')
    else:
        lines+=[f'The [register]({Path(ASSUMPTIONS).name}) records {assumptions["count"]} entries: **{assumptions["open"]} open** (pending disposition) and **{assumptions["stale"]} stale** (basis moved in the source register since the judgment).',
            'Open and stale entries are listed below; accepted entries stay in the register and in the design atlas. This check never re-judges an entry.','',
            '| ID | Kind | State | Statement | Magnitude | Decision |','| --- | --- | --- | --- | --- | --- |']
        listed=[e for e in assumptions['entries'] if e['open'] or e['stale']]
        for e in listed:
            state=' / '.join(s for s,flag in (('stale: '+', '.join(e['stale_sources']),e['stale']),('open',e['open'])) if flag)
            disposition=e.get('disposition') if isinstance(e.get('disposition'),dict) else {}
            decision=' '.join(str(disposition.get(k) or '') for k in ('status','decision','on')).strip()
            lines.append('| '+' | '.join(escape(x) for x in (e.get('id',''),e.get('kind',''),state,e.get('statement',''),magnitude_text(e),decision))+' |')
        if not listed: lines.append('| Register entries | — | current | Every entry is settled and its basis hashes equal the register. | — | — |')
    lines+=['','## Verified scope','',
        '- Present-source identity is compared with the source register. Only registered notebook CRLF/LF endings are normalized; native/report files use exact bytes.',
        '- Current journal identity is compared with its existing acceptance receipt; that receipt keeps its original scope.',
        '- Saved cap cases are compared with their report JSON, and raw XML with the analysis fingerprint.',
        '- Selected notebook cap widths, depths, pile counts/sizes/spacings, embedment and lengths are compared with saved cases.',
        '- Mathcad XML readability is checked. Its formulas and external inputs are not recalculated.',
        '- Tracker IDs, statuses, required descriptions and closure evidence are checked.',
        '- Assumptions-register entries are validated (stable IDs, kinds, dispositions, registered basis sources, tracker references) and their recorded basis hashes are compared with the current register. A moved basis is reported for re-judgment, never re-judged here.',
        '- Detailed results and exact source/tracker fingerprints are in [machine_checks.json](machine_checks.json).','',
        'Automatic matches do not resolve the outstanding workbook items. Responses and original source documents are unchanged.','']
    (out/'latest_review.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-report',action='store_true',help='Refresh generated Markdown/JSON/CSV views; never edits the tracker.')
    parser.add_argument('--root',type=Path,default=ROOT,help=argparse.SUPPRESS)
    args=parser.parse_args()
    try:
        result=run(args.root.resolve())
        if args.write_report: write_report(args.root.resolve(),result)
    except (OSError, ValueError, KeyError, StopIteration, zipfile.BadZipFile, ET.ParseError) as e:
        print('Coherence check could not complete: '+str(e),file=sys.stderr); return 1
    print(json.dumps({k:result[k] for k in ('source_count','item_count','outstanding_count','status_counts','check_counts','assumption_counts')},indent=2))
    if any(c['status'] in {'ERROR','CHANGED'} for c in result['checks']): return 1
    if result['outstanding_count'] or any(c['status']!='MATCH' for c in result['checks']): return 2
    return 0


if __name__=='__main__': sys.exit(main())
