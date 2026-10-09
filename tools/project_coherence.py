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
            audit_length = cases[prefix]['analysis']['xml_audit']['cap_length_ft']*12
            same = abs(length-audit_length) <= 0.01
            add(f'GEOMETRY:{prefix}:length', 'MATCH' if same else 'CHANGED',
                f'Notebook {length:g} in; source audit {audit_length:g} in. Comparison tolerance 0.01 in for printed coordinates.',
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
    outstanding=[i for i in items if i['Status'] not in CLOSED]
    totals=dict(Counter(c['status'] for c in checks))
    return dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),
        scope='Exact source identity, file relationships, selected geometry and issue-log completeness; no native design reruns.',
        register_sha256=digest(hub/'source_register.csv'),tracker_sha256=digest(workbook),
        source_count=len(sources),item_count=len(items),outstanding_count=len(outstanding),
        status_counts=dict(Counter(i['Status'] for i in items)),check_counts=totals,
        checks=checks,items=items)


def escape(s): return str(s).replace('|','\\|').replace('\n',' ')


def write_report(root, result):
    out=root/'project_current/coherence'
    out.mkdir(parents=True,exist_ok=True)
    (out/'machine_checks.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with (out/'items_snapshot.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=HEADERS,extrasaction='ignore');w.writeheader();w.writerows(result['items'])
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
    lines+=['','## Verified scope','',
        '- Present-source identity is compared with the source register. Only registered notebook CRLF/LF endings are normalized; native/report files use exact bytes.',
        '- Current journal identity is compared with its existing acceptance receipt; that receipt keeps its original scope.',
        '- Saved cap cases are compared with their report JSON, and raw XML with the analysis fingerprint.',
        '- Selected notebook cap widths, depths, pile counts/sizes/spacings, embedment and lengths are compared with saved cases.',
        '- Mathcad XML readability is checked. Its formulas and external inputs are not recalculated.',
        '- Tracker IDs, statuses, required descriptions and closure evidence are checked.',
        '- Detailed results and exact source/tracker fingerprints are in [machine_checks.json](machine_checks.json).','',
        'Automatic matches do not resolve the outstanding workbook items. Responses and original source documents are unchanged.','']
    (out/'latest_review.md').write_text('\n'.join(lines),encoding='utf-8')


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
    print(json.dumps({k:result[k] for k in ('source_count','item_count','outstanding_count','status_counts','check_counts')},indent=2))
    if any(c['status'] in {'ERROR','CHANGED'} for c in result['checks']): return 1
    if result['outstanding_count'] or any(c['status']!='MATCH' for c in result['checks']): return 2
    return 0


if __name__=='__main__': sys.exit(main())
