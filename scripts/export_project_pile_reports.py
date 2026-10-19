"""Export the project pile design reports and cases from the pile analysis and design package.

    .venv\\Scripts\\python.exe scripts\\export_project_pile_reports.py --date 10-19
    .venv\\Scripts\\python.exe scripts\\export_project_pile_reports.py --register
    .venv\\Scripts\\python.exe scripts\\export_project_pile_reports.py --check

For each support (End Bent 1, End Bent 2, Pier) the preset case `default_case(support)` (the
D-049 FB-MultiPier fixed-run exports registered in pile_design/data/sources.json, 18 tons of
downdrag at the end bents) is evaluated and written under project_current/pile_design/<folder>/:

    <Support> Pile Design <m-d>.html        calculation report (pile_design.report.build_report)
    <Support> Pile Design <m-d>.json        case (pile_design.exports.case_json)
    selected_case.json                      byte-identical copy of the dated case
    <Support> Pile Design <m-d> checks.csv  check register
    <Support> Pile Data Table <m-d>.xlsx    SDM 11.4 Pile Data Table and basis
    README.md                               what was run and the results

and a source receipt under project_current/coherence/evidence/2026-<m-d>-pile-reports/.
`--register` appends the six register rows (PILE-EB1-REPORT ... PILE-PIER-CASE) when absent;
it never changes an existing row.

The report embeds its generation time and random figure ids, and a saved case holds the load
time of its FBMP receipt, so a rerun gives new bytes. The report does not embed the case or
the package revision. `--check` therefore regenerates each report, checks table and workbook
from the saved case with the current package and compares them with the registered files
(generation time and figure ids masked); it also checks that the saved case equals a fresh
preset case apart from the receipt load time, and that the case names the registered export.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PILE_DESIGN = ROOT / 'project_current' / 'pile_design'
REGISTER = ROOT / 'project_current' / 'source_register.csv'
EVIDENCE = ROOT / 'project_current' / 'coherence' / 'evidence'
DECISION = 'D-054'
YEAR = '2026'
AUTHORIZATION = ('User instruction, 19 October 2026: "Run the pile design analysis for both end bents and pier and export '
                 'the calculation reports and save to the source and then export the bpad distills and add to the journal."')

# (support, folder, register prefix)
SUPPORTS = (('End Bent 1', 'end_bent_1', 'PILE-EB1'), ('End Bent 2', 'end_bent_2', 'PILE-EB2'), ('Pier', 'pier', 'PILE-PIER'))
STATUS = 'User-selected current - engineering review retained'
FIELDS = ['source_id', 'topic', 'path', 'status', 'scope', 'sha256', 'registered_on', 'depends_on', 'origin', 'notes', 'hash_basis']
SHORT = {'exposure': 'environment classification', 'head_connection': 'pile-to-cap connection', 'steel_grade': 'pipe steel grade',
         'corrosion': 'corrosion allowance', 'downdrag_source': 'downdrag source documentation', 'analysis_current': 'FBMP export currency',
         'min_tip': 'minimum tip elevation', 'scour': 'scour resistance and elevations', 'drivability': 'drivability'}

STAMP = re.compile(r'Generated \d{4}-\d\d-\d\d \d\d:\d\d UTC')
FIGURE_ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def masked(markup: str) -> str:
    """The report with its generation time and random Plotly figure ids replaced."""
    return FIGURE_ID.sub('<figure-id>', STAMP.sub('Generated <time>', markup))


def names(support: str, folder: str, label: str) -> dict[str, Path]:
    base = PILE_DESIGN / folder
    return {'report': base / f'{support} Pile Design {label}.html', 'dated_case': base / f'{support} Pile Design {label}.json',
            'selected_case': base / 'selected_case.json', 'checks_csv': base / f'{support} Pile Design {label} checks.csv',
            'data_table_xlsx': base / f'{support} Pile Data Table {label}.xlsx'}


def git_head() -> str:
    """Short commit id read from .git/HEAD and the ref file (no git command)."""
    git = ROOT / '.git'
    head = (git / 'HEAD').read_text(encoding='utf-8').strip()
    if not head.startswith('ref:'):
        return head[:7]
    ref = head.split(None, 1)[1]
    if (git / ref).is_file():
        return (git / ref).read_text(encoding='utf-8').strip()[:7]
    packed = git / 'packed-refs'
    if packed.is_file():
        for line in packed.read_text(encoding='utf-8').splitlines():
            if line.endswith(' ' + ref):
                return line.split()[0][:7]
    raise ValueError(f'Cannot resolve {ref} from .git')


def evaluate_preset(support: str):
    from pile_design.model import default_case, evaluate
    case = default_case(support)
    e = evaluate(case)
    if e.case != case:
        raise ValueError(f'{support}: the evaluated case differs from the preset case.')
    return e


def outputs(e) -> dict[str, bytes]:
    """The five files of one support, from the notebook's own writers."""
    from pile_design import exports
    return {'report': exports.WRITERS[exports.REPORT](e), 'dated_case': exports.WRITERS[exports.CASE](e),
            'selected_case': exports.WRITERS[exports.CASE](e), 'checks_csv': exports.WRITERS[exports.CHECKS](e),
            'data_table_xlsx': exports.WRITERS[exports.TABLE](e)}


def summary(e) -> dict:
    """Check register summary, results and the Pile Data Table row of an evaluation."""
    from pile_design.model import CONFIRMATIONS
    raw: dict[str, int] = {}
    for c in e.checks:
        raw[c.status] = raw.get(c.status, 0) + 1
    pending = [c for c in e.checks if 'PENDING' in c.status]
    unconfirmed = [k for k in CONFIRMATIONS if not e.case['confirmations'].get(k) and not (e.family != 'pipe' and k in ('steel_grade', 'corrosion'))]
    return {
        'checks': len(e.checks), 'status_counts': dict(sorted(raw.items())),
        'PASS': sum(n for s, n in raw.items() if s.startswith('PASS')), 'PASS_with_pending_input': raw.get('PASS · PENDING INPUT', 0),
        'PENDING': raw.get('PENDING', 0), 'INFO': raw.get('INFO', 0), 'FAIL': sum(n for s, n in raw.items() if 'FAIL' in s),
        'pending_items': len(pending), 'pending_check_labels': [c.label for c in pending],
        'other_pending_checks': [c.label for c in pending if c.status == 'PENDING' and c.group != 'Prerequisites'],
        'unconfirmed_prerequisites': unconfirmed,
        'strength_dc': round(e.strength_dc, 6), 'max_ratio': round(e.max_ratio, 6), 'status_text': e.status,
        'NBR_tons': round(e.value('NBR_tons'), 4), 'FDL_tons': round(e.value('FDL_tons'), 4),
        'pile_data_table_row': e.data_table}


def readme(support: str, e, s: dict, files: dict[str, Path], label: str) -> str:
    from pile_design.mathcad import package_revision
    from urllib.parse import quote
    a = e.case['analysis']
    link = lambda key: quote(files[key].name)
    unconfirmed = ', '.join(SHORT[k] for k in s['unconfirmed_prerequisites'])
    other = '; '.join(s['other_pending_checks'])
    pile = ('18 in square prestressed concrete piles (Standard Plans Index 455-018, 12 x 0.6 in strands) with 18 tons of downdrag per pile'
            if e.family == 'psc' else '20 in x 0.48 in steel pipe piles (noncomposite), no downdrag')
    return f"""# {support} current pile design

The [19 October report]({link('report')}) and [dated JSON]({link('dated_case')}) are selected under {DECISION}.
`selected_case.json` is byte-identical to the dated JSON. The [check register]({link('checks_csv')})
and [Pile Data Table]({link('data_table_xlsx')}) come from the same case.

The pile analysis and design package (`pile_design`, revision `{package_revision()[:16]}`, the engine of
`Pile_Design.ipynb`) evaluated its preset case for {support}: {pile}. The FB-MultiPier export is
`{a['filename']}` ({a['registered_id']}, SHA-256 `{a['sha256']}`), the D-049 fixed run; the case's receipt records that it
matches the register. No input was changed by hand.

Results: all numerical checks pass. The largest structural demand/capacity ratio is {s['strength_dc']:.3f}; the largest
ratio of any check is {s['max_ratio']:.2f} (the pile spacing check, exactly 3 diameters). Nominal Bearing Resistance
{s['NBR_tons']:.2f} tons ({e.data_table['Nominal Bearing Resistance (tons)']} in the Pile Data Table) for a Factored Design Load of
{s['FDL_tons']:.2f} tons. The register holds {s['checks']} entries: {s['PASS']} PASS (of which {s['PASS_with_pending_input']} rest on an unconfirmed prerequisite),
{s['PENDING']} PENDING, {s['INFO']} INFO and {s['FAIL']} FAIL.

The report counts {s['pending_items']} pending entries: {s['PENDING']} PENDING and {s['PASS_with_pending_input']} PASS entries that rest on an unconfirmed
prerequisite. Open prerequisites: {unconfirmed}. Other pending checks: {other}.
The report's section 13 lists them. Selection is not engineering acceptance.

The Blockpad edition of this report is in the journal under task T015
(`pile_bpad/{support} Pile Design.bpad`). Regenerate with `scripts/export_project_pile_reports.py --date {label}`; the report
embeds its generation time, so a rerun gives new bytes. `--check` regenerates the report from the saved case and compares.
Calculation, source and preservation checks are in the
[receipt](../../coherence/evidence/{YEAR}-{label}-pile-reports/source_receipt.json).
"""


def export(label: str) -> dict:
    """Write the reports, cases, tables, READMEs and the receipt; return the receipt."""
    import openpyxl
    import plotly
    from pile_design.mathcad import package_revision
    from pile_design.model import PRESETS
    reports = []
    for support, folder, prefix in SUPPORTS:
        e = evaluate_preset(support)
        data = outputs(e)
        files = names(support, folder, label)
        files['selected_case'].parent.mkdir(parents=True, exist_ok=True)
        for key, path in files.items():
            path.write_bytes(data[key])
        s = summary(e)
        (files['selected_case'].parent / 'README.md').write_text(readme(support, e, s, files, label), encoding='utf-8', newline='\n')
        a = e.case['analysis']
        xml_id = PRESETS[support]['xml']
        reports.append({
            'support': support, 'family': e.family, 'case_name': e.case['name'], 'schema_version': e.case['schema_version'],
            'source_ids': {'report': f'{prefix}-REPORT', 'case': f'{prefix}-CASE', 'fbmp_export': xml_id},
            'files': {key: {'path': rel(files[key]), 'sha256': sha256(data[key]), 'bytes': len(data[key])} for key in files},
            'selected_case_equals_dated_case': data['selected_case'] == data['dated_case'],
            'case_sha256': sha256(data['selected_case']),
            'fbmp_export': {'id': xml_id, 'filename': a['filename'], 'sha256': a['sha256'], 'matches_register': a['matches_register']},
            'check_register': {k: v for k, v in s.items() if k != 'pile_data_table_row'},
            'pile_data_table_row': s['pile_data_table_row']})
    receipt = {
        'date': f'{YEAR}-{label}', 'decision': DECISION, 'authorization': AUTHORIZATION,
        'scope': ('Pile analysis and design reports and cases for End Bent 1, End Bent 2 and Pier exported to project_current/pile_design/ '
                  'from the preset cases of the pile_design package (D-049 FBMP fixed-run exports, 18 tons end-bent downdrag, D-050). '
                  'No cap design, FBMP export, geometry, journal, tracker row or engineering disposition changed in this step. '
                  'The Blockpad editions go to the journal under T015.'),
        'generator': {
            'script': 'scripts/export_project_pile_reports.py', 'command': f'.venv\\Scripts\\python.exe scripts\\export_project_pile_reports.py --date {label}',
            'package': 'pile_design', 'package_revision': package_revision(),
            'package_revision_basis': 'pile_design.mathcad.package_revision(): SHA-256 of pile_design/*.py and data/*.json, newline-normalised',
            'git_head': git_head(), 'git_head_note': 'Read from .git/HEAD and the ref file; the working tree was not inspected for uncommitted changes.',
            'python': sys.version.split()[0], 'plotly': plotly.__version__, 'openpyxl': openpyxl.__version__,
            'note': 'Each report embeds its generation time and random figure ids, a saved case holds the load time of its FBMP receipt, and the '
                    'workbook holds a zip timestamp, so a rerun gives new bytes. scripts/export_project_pile_reports.py --check regenerates the '
                    'reports, check registers and workbooks from the saved cases and compares them with the registered files.'},
        'reports': reports,
        'register_rows': [r['source_ids'][k] for r in reports for k in ('report', 'case')],
        'limitations': ('Notebook package run and export only. The numerical checks are the notebook\'s; the pending items (downdrag source documentation, '
                        'pile-to-cap connection, pipe steel grade and corrosion, minimum tip, scour, drivability, environment classification, '
                        'FBMP export currency) remain open. FB-MultiPier was not rerun. Selection is not engineering acceptance.')}
    folder = EVIDENCE / f'{YEAR}-{label}-pile-reports'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'source_receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return receipt


def register_rows(receipt: dict) -> list[dict]:
    """The six source-register rows of an export receipt."""
    rows = []
    for r in receipt['reports']:
        support, ids, xml, files = r['support'], r['source_ids'], r['fbmp_export']['id'], r['files']
        s = r['check_register']
        pending = '; '.join(SHORT[k] for k in s['unconfirmed_prerequisites'])
        what = {'End Bent 1': 'End Bent 1', 'End Bent 2': 'End Bent 2', 'Pier': 'Pier'}[support]
        note = (f'{DECISION}. Pile analysis and design of the {what} piles from the pile design package (PILE-TOOL, package '
                f'{receipt["generator"]["package_revision"][:12]}) with the D-049 fixed-run export {xml}. All numerical checks pass '
                f'(structural D/C {s["strength_dc"]:.3f}); {s["pending_items"]} pending entries remain ({s["PENDING"]} PENDING, {s["PASS_with_pending_input"]} PASS resting on '
                f'an unconfirmed prerequisite). Open: {pending}; {"; ".join(s["other_pending_checks"])}. ')
        origin = 'Notebook package run requested by the user, 19 October 2026 (scripts/export_project_pile_reports.py)'
        receipt_note = f'See coherence/evidence/{receipt["date"]}-pile-reports/source_receipt.json. Selection is not engineering acceptance.'
        rows.append({
            'source_id': ids['report'], 'topic': f'{what} pile design report', 'path': files['report']['path'], 'status': STATUS,
            'scope': f'Pile analysis and design calculation report for the {what} piles ({r["case_name"].split(": ", 1)[-1]})',
            'sha256': files['report']['sha256'], 'registered_on': receipt['date'], 'depends_on': f'{ids["case"]};PILE-TOOL;{xml}', 'origin': origin,
            'notes': note + 'The report embeds its generation time; --check regenerates it from the case. ' + receipt_note, 'hash_basis': 'exact_bytes'})
        rows.append({
            'source_id': ids['case'], 'topic': f'{what} saved pile case', 'path': files['selected_case']['path'], 'status': STATUS,
            'scope': f'Editable pile case for the {what} piles, byte-identical to the dated case beside the report',
            'sha256': files['selected_case']['sha256'], 'registered_on': receipt['date'], 'depends_on': f'{xml};PILE-TOOL', 'origin': origin,
            'notes': note + receipt_note, 'hash_basis': 'exact_bytes'})
    return rows


def register(receipt: dict) -> list[str]:
    """Append rows that are absent; refuse to alter or contradict an existing row."""
    text = REGISTER.read_bytes()
    with REGISTER.open(newline='', encoding='utf-8-sig') as f:
        existing = {row['source_id']: row for row in csv.DictReader(f)}
    if not text.endswith(b'\n'):
        raise ValueError('The register does not end with a newline.')
    if b'\r\n' in text:
        raise ValueError('The register is expected to use LF line endings.')
    rows = register_rows(receipt)
    new, added = [], []
    for row in rows:
        old = existing.get(row['source_id'])
        if old is None:
            new.append(row)
            added.append(row['source_id'])
        elif old != row:
            raise ValueError(f'{row["source_id"]} is registered with different content; record a disposition before replacing it.')
    if new:
        import io
        buffer = io.StringIO()
        csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator='\n').writerows([[row[f] for f in FIELDS] for row in new])
        with REGISTER.open('ab') as f:
            f.write(buffer.getvalue().encode('utf-8'))
    return added


def registered_files() -> dict[str, tuple[Path, Path]]:
    """Report and case paths from the source register, keyed by the report source id."""
    with REGISTER.open(newline='', encoding='utf-8-sig') as f:
        paths = {row['source_id']: ROOT / row['path'] for row in csv.DictReader(f)}
    return {f'{prefix}-REPORT': (paths[f'{prefix}-REPORT'], paths[f'{prefix}-CASE']) for _, _, prefix in SUPPORTS if f'{prefix}-REPORT' in paths}


def _sheet_values(data: bytes) -> dict:
    import io
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data))
    return {ws.title: [[cell.value for cell in row] for row in ws.iter_rows()] for ws in wb.worksheets}


def _blank_load_time(case: dict) -> dict:
    case = json.loads(json.dumps(case))
    for receipt in case.get('receipts', {}).values():
        receipt.pop('loaded_utc', None)
    return case


def check() -> list[str]:
    from pile_design import exports
    from pile_design.model import PRESETS, SOURCES, default_case, evaluate
    problems = []
    registered = registered_files()
    for support, folder, prefix in SUPPORTS:
        tag = f'{prefix}-REPORT'
        if tag not in registered:
            problems.append(f'{tag}: not in the source register')
            continue
        report, case_path = registered[tag]
        dated = report.with_suffix('.json')
        checks, table = (report.with_name(report.stem + ' checks.csv'), report.with_name(report.stem.replace('Pile Design', 'Pile Data Table') + '.xlsx'))
        missing = [path for path in (report, case_path, dated, checks, table) if not path.is_file()]
        problems += [f'{tag}: missing {rel(path)}' for path in missing]
        if missing:
            continue
        saved_bytes = case_path.read_bytes()
        if saved_bytes != dated.read_bytes():
            problems.append(f'{tag}: {case_path.name} differs from {dated.name}')
        saved = json.loads(saved_bytes.decode('utf-8-sig'))
        if exports.load_case(saved_bytes) != saved:
            problems.append(f'{tag}: the saved case changes when loaded by the current package')
        if saved.get('support') != support:
            problems.append(f'{tag}: the saved case is for {saved.get("support")!r}')
        fresh = default_case(support)
        if _blank_load_time(fresh) != _blank_load_time(saved):
            problems.append(f'{tag}: the saved case differs from the preset case of the current package and registered export')
        xml_id = PRESETS[support]['xml']
        analysis = saved.get('analysis') or {}
        disk = (ROOT / SOURCES['sources'][xml_id]['path']).read_bytes()
        if not (analysis.get('sha256') == SOURCES['sources'][xml_id]['sha256'] == sha256(disk)):
            problems.append(f'{tag}: the case analysis does not carry the registered {xml_id} SHA-256')
        e = evaluate(saved)
        if masked(report.read_text(encoding='utf-8')) != masked(exports.WRITERS[exports.REPORT](e).decode('utf-8')):
            problems.append(f'{tag}: the report differs from one regenerated from the saved case with the current package')
        if checks.read_bytes() != exports.WRITERS[exports.CHECKS](e):
            problems.append(f'{tag}: the check register differs from the regenerated one')
        if _sheet_values(table.read_bytes()) != _sheet_values(exports.WRITERS[exports.TABLE](e)):
            problems.append(f'{tag}: the Pile Data Table differs from the regenerated one')
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--date', help='m-d suffix for the new file names, for example 10-19')
    parser.add_argument('--register', action='store_true', help='append the six source-register rows from the receipt of --date')
    parser.add_argument('--check', action='store_true', help='verify the registered reports instead of exporting')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    if args.check:
        problems = check()
        print('\n'.join(problems) if problems else 'Registered pile reports equal reports regenerated from their saved cases with the current package.')
        return 1 if problems else 0
    if args.register:
        if not args.date:
            parser.error('--date is required to register')
        receipt = json.loads((EVIDENCE / f'{YEAR}-{args.date}-pile-reports' / 'source_receipt.json').read_text(encoding='utf-8'))
        added = register(receipt)
        print('Appended ' + ', '.join(added) if added else 'All pile rows are already registered.')
        return 0
    if not args.date:
        parser.error('--date is required to export')
    receipt = export(args.date)
    for r in receipt['reports']:
        for key, info in r['files'].items():
            print(f'Wrote {info["path"]} ({info["bytes"]:,} bytes)')
    print(f'Wrote project_current/coherence/evidence/{YEAR}-{args.date}-pile-reports/source_receipt.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
