"""D-068: re-export the seven registered calculation reports with definition and citation cards.

    .venv\\Scripts\\python.exe project_current\\coherence\\evidence\\2026-10-20-report-cards\\adopt_reports.py

Each report is regenerated from its unchanged selected_case.json with the current packages
(report_cards commits 18b47cb and a866e6b), written beside the 19 October report as
"<name> 10-20.html", and its register row moved to the new file with a D-068 note. The
check registers of the old and new reports are compared (labels, statuses and ratios);
the result is recorded in source_receipt.json, never assumed. Cases, FBMP exports, the
journal, tracker rows and engineering dispositions are untouched; the 10-19 reports are
retained. The pile reports also get the dated case copy, check CSV and Pile Data Table
that scripts/export_project_pile_reports.py --check expects beside a report.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html as html_lib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

PC = ROOT / 'project_current'
REGISTER = PC / 'source_register.csv'
HERE = Path(__file__).resolve().parent
LABEL, DATE, DECISION = '10-20', '2026-10-20', 'D-068'
AUTHORIZATION = ('User instruction, 20 October 2026: "Yes, re-export the registered project reports so the project_current '
                 'copies carry the cards."')
CARDS = 'definition and citation cards (report_cards; commits 18b47cb and a866e6b)'
FIELDS = ['source_id', 'topic', 'path', 'status', 'scope', 'sha256', 'registered_on', 'depends_on', 'origin', 'notes', 'hash_basis']


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def git_head() -> str:
    git = ROOT / '.git'
    head = (git / 'HEAD').read_text(encoding='utf-8').strip()
    if not head.startswith('ref:'):
        return head[:7]
    ref = head.split(None, 1)[1]
    if (git / ref).is_file():
        return (git / ref).read_text(encoding='utf-8').strip()[:7]
    for line in (git / 'packed-refs').read_text(encoding='utf-8').splitlines():
        if line.endswith(' ' + ref):
            return line.split()[0][:7]
    raise ValueError(ref)


STATUS_WORDS = ('PASS', 'FAIL', 'PENDING', 'INFO', 'CONFIRMED', 'REFERENCE', 'NOT REQUIRED', 'SOURCE', 'CONDITIONAL')


def check_rows(markup: str) -> list[str]:
    """Text of every table row that carries a check status, tags stripped (report-cards attributes do not matter)."""
    rows = []
    for row in re.findall(r'<tr>(.*?)</tr>', markup, re.S):
        text = html_lib.unescape(re.sub(r'<[^>]+>', ' ', row))
        text = re.sub(r'\s+', ' ', text).strip()
        if any(w in text for w in STATUS_WORDS) and 'Check' not in text[:6]:
            rows.append(text)
    return sorted(rows)


def compare(old: Path, new: Path) -> dict:
    a, b = check_rows(old.read_text(encoding='utf-8')), check_rows(new.read_text(encoding='utf-8'))
    only_old, only_new = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    return {'rows_old': len(a), 'rows_new': len(b), 'equal': a == b, 'only_in_old': only_old[:20], 'only_in_new': only_new[:20]}


def register_rows() -> tuple[list[str], dict[str, dict]]:
    text = REGISTER.read_bytes().decode('utf-8-sig')
    if '\r\n' in text:
        raise ValueError('register uses CRLF')
    lines = text.split('\n')
    with REGISTER.open(newline='', encoding='utf-8-sig') as f:
        rows = {row['source_id']: row for row in csv.DictReader(f)}
    return lines, rows


def write_row(lines: list[str], row: dict) -> None:
    """Replace the single register line of row['source_id'] in place (other lines byte-identical)."""
    import io
    buffer = io.StringIO()
    csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator='\n').writerow([row[f] for f in FIELDS])
    new_line = buffer.getvalue().rstrip('\n')
    hits = [i for i, line in enumerate(lines) if line.startswith(f'"{row["source_id"]}",')]
    if len(hits) != 1:
        raise ValueError(f'{row["source_id"]}: {len(hits)} register lines')
    lines[hits[0]] = new_line


# ------------------------------------------------------------------ exports

def export_cap() -> list[dict]:
    import export_project_cap_reports as cap
    out = []
    written = {p.name: p for p in cap.export(LABEL)}
    for report_id, case_id, folder, title in cap.REPORTS:
        path = written[f'{title} {LABEL}.html']
        markup = path.read_text(encoding='utf-8')
        case_path = cap.CAP_DESIGN / folder / 'selected_case.json'
        out.append(dict(source_id=report_id, case_id=case_id, path=path, case=case_path,
                        embedded_case_equals_saved=cap.embedded_case(markup) == json.loads(case_path.read_text(encoding='utf-8-sig')),
                        schematic_problems=cap.schematic_problems(markup)))
    return out


def export_pile() -> list[dict]:
    from pile_design import exports
    from pile_design.model import evaluate
    import export_project_pile_reports as pile
    out = []
    for support, folder, prefix in pile.SUPPORTS:
        base = pile.PILE_DESIGN / folder
        saved_bytes = (base / 'selected_case.json').read_bytes()
        e = evaluate(exports.load_case(saved_bytes))
        files = pile.names(support, folder, LABEL)
        files['report'].write_bytes(exports.WRITERS[exports.REPORT](e))
        files['dated_case'].write_bytes(saved_bytes)            # the case is unchanged; the dated copy pairs with the report
        files['checks_csv'].write_bytes(exports.WRITERS[exports.CHECKS](e))
        files['data_table_xlsx'].write_bytes(exports.WRITERS[exports.TABLE](e))
        old_checks = base / f'{support} Pile Design 10-19 checks.csv'
        out.append(dict(source_id=f'{prefix}-REPORT', case_id=f'{prefix}-CASE', path=files['report'], case=base / 'selected_case.json',
                        companions={k: rel(v) for k, v in files.items() if k != 'report'},
                        check_csv_equals_10_19=old_checks.read_bytes() == files['checks_csv'].read_bytes() if old_checks.is_file() else None))
    return out


def export_backwall() -> list[dict]:
    from end_bent_walls import exports
    from end_bent_walls.model import evaluate
    from end_bent_walls.report import build_report
    base = PC / 'cap_design' / 'backwall'
    case_path = base / 'selected_case.json'
    e = evaluate(exports.load_case(case_path.read_bytes()))
    path = base / f'Backwall Design {LABEL}.html'
    path.write_text(build_report(e), encoding='utf-8')
    return [dict(source_id='BACKWALL-REPORT', case_id='BACKWALL-CASE', path=path, case=case_path)]


# ------------------------------------------------------------------ record

def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise ValueError(f'{rel(path)}: expected one occurrence of {old!r}, found {text.count(old)}')
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')


def update_readmes(exports_done: list[dict]) -> list[str]:
    changed = []
    top = PC / 'README.md'
    for item in exports_done:
        new_name = item['path'].name
        old_name = item['previous']['path'].rsplit('/', 1)[-1] if item['previous'] else None
        folder_readme = item['path'].parent / 'README.md'
        if old_name and folder_readme.is_file():
            raw = folder_readme.read_bytes()
            nl = '\r\n' if b'\r\n' in raw else '\n'   # keep each README's own line endings
            text = raw.decode('utf-8')
            quoted_old, quoted_new = old_name.replace(' ', '%20'), new_name.replace(' ', '%20')
            if quoted_old in text:
                text = text.replace(f'[19 October report]({quoted_old})', f'[20 October report]({quoted_new})', 1)
                text = text.replace(quoted_old, quoted_new)
                if DECISION not in text:
                    text = text.rstrip('\r\n') + nl + nl + (f'{DECISION} (20 October): the report was re-exported from the unchanged saved case with the '
                                                            f'current package, adding {CARDS}. Results are unchanged; the 19 October report is retained. '
                                                            f'See the [receipt](../../coherence/evidence/2026-10-20-report-cards/source_receipt.json).') + nl
                folder_readme.write_bytes(text.encode('utf-8'))
                changed.append(rel(folder_readme))
    # Top-level index: point the report links at the new files.
    text = top.read_text(encoding='utf-8')
    for item in exports_done:
        new_q = rel(item['path']).replace('project_current/', '', 1).replace(' ', '%20')
        pattern = re.compile(r'\((' + re.escape(new_q.rsplit('%20', 1)[0]) + r'%20\d\d-\d\d\.html)\)')
        text, n = pattern.subn(f'({new_q})', text)
        if n == 0:
            raise ValueError(f'README.md: no link for {new_q}')
        text = re.sub(r'\[\d+ October report\]\(' + re.escape(new_q) + r'\)', f'[20 October report]({new_q})', text)
    if DECISION not in text:
        text = text.replace('\n| FBMP source variants |', f'\n| Report cards ({DECISION}) | All seven calculation reports above were re-exported on 20 October 2026 with {CARDS}: hover a variable for its definition, a code reference for the highlighted provision. Results unchanged; 19 October reports retained; see [receipt](coherence/evidence/2026-10-20-report-cards/source_receipt.json) |\n| FBMP source variants |', 1)
    top.write_text(text, encoding='utf-8', newline='\n')
    changed.append(rel(top))
    return changed


def add_decision() -> None:
    path = PC / 'decisions.md'
    text = path.read_text(encoding='utf-8')
    if f'| {DECISION} |' in text:
        return
    lines = text.split('\n')
    idx = max(i for i, line in enumerate(lines) if line.startswith('| D-067 |'))
    row = (f'| {DECISION} | {DATE} | Re-export the seven registered calculation reports (pier, End Bent 1 and End Bent 2 caps; End Bent 1, '
           f'End Bent 2 and Pier piles; backwall) from their unchanged selected cases with the current packages, adding {CARDS}: '
           f'hovering a variable shows where and how it is defined, hovering a code reference shows the highlighted provision from '
           f'the code PDFs. The new 10-20 reports are registered; the 10-19 reports, all cases, FBMP exports and the journal are unchanged. '
           f'| User direction. Report check registers compared with the 19 October reports (see the receipt); the cards change no '
           f'calculation. Code excerpts are copyrighted pages for the internal calculation record. See '
           f'[receipt](coherence/evidence/2026-10-20-report-cards/source_receipt.json). |')
    lines.insert(idx + 1, row)
    path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8')
    lines, rows = register_rows()
    done = export_cap() + export_pile() + export_backwall()
    receipt_reports = []
    for item in done:
        row = rows[item['source_id']]
        previous = {'path': row['path'], 'sha256': row['sha256'], 'retained_unchanged': (ROOT / row['path']).is_file()
                    and sha256((ROOT / row['path']).read_bytes()) == row['sha256']}
        item['previous'] = previous
        new_bytes = item['path'].read_bytes()
        case_row = rows[item['case_id']]
        entry = {
            'source_id': item['source_id'], 'path': rel(item['path']), 'sha256': sha256(new_bytes), 'bytes': len(new_bytes),
            'previous': previous,
            'case': {'source_id': item['case_id'], 'path': case_row['path'], 'sha256_registered': case_row['sha256'],
                     'sha256_now': sha256(item['case'].read_bytes()), 'unchanged': sha256(item['case'].read_bytes()) == case_row['sha256']},
            'check_register_vs_previous': compare(ROOT / previous['path'], item['path']) if (ROOT / previous['path']).is_file() else None,
            'cards': {'definition_cards': 'data-var="' in new_bytes.decode('utf-8'), 'citation_data': 'id="cite-data"' in new_bytes.decode('utf-8')},
        }
        for key in ('embedded_case_equals_saved', 'schematic_problems', 'companions', 'check_csv_equals_10_19'):
            if key in item:
                entry[key] = item[key]
        receipt_reports.append(entry)
        note = (f'{DECISION}. Re-exported 20 October 2026 from the unchanged saved case with the current package (repository commit '
                f'{git_head()}), adding {CARDS}. Check register compared with the 19 October report: '
                f'{"identical" if entry["check_register_vs_previous"] and entry["check_register_vs_previous"]["equal"] else "see receipt"}; '
                f'the prior report is retained unchanged. See coherence/evidence/2026-10-20-report-cards/source_receipt.json. ')
        if not row['notes'].startswith(DECISION):
            row['notes'] = note + row['notes']
        row.update(path=rel(item['path']), sha256=entry['sha256'], registered_on=DATE,
                   origin=f'Project re-export of {previous["path"].rsplit("/", 1)[-1]} from the selected saved case, 20 October 2026')
        write_row(lines, row)
    REGISTER.write_bytes('\n'.join(lines).encode('utf-8'))
    add_decision()
    readmes = update_readmes(done)
    receipt = {
        'date': DATE, 'decision': DECISION, 'authorization': AUTHORIZATION,
        'scope': ('Re-export of the seven registered calculation reports from their unchanged selected cases with the current packages, '
                  'adding definition and citation cards. No case, input, FBMP export, journal, tracker row or engineering disposition changed. '
                  'Pile reports also receive the dated case copy, check CSV and Pile Data Table that the pile --check expects beside a report.'),
        'generator': {'script': rel(Path(__file__)), 'repository_commit': git_head(), 'cards': CARDS,
                      'python': sys.version.split()[0], 'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
                      'note': 'Reports embed their generation time (and the pile reports random figure ids), so a rerun gives new bytes. '
                              'scripts/export_project_cap_reports.py --check and scripts/export_project_pile_reports.py --check verify the registered reports.'},
        'reports': receipt_reports, 'register_rows_updated': [r['source_id'] for r in receipt_reports],
        'readmes_updated': readmes,
        'limitations': ('Report formatting change only. Every pending item, failed check and open coherence item of the 19 October reports '
                        'remains. Selection is not engineering acceptance. Code excerpts in the reports are copyrighted pages for the internal '
                        'calculation record.'),
    }
    (HERE / 'source_receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    for r in receipt_reports:
        cmp_ = r['check_register_vs_previous']
        print(f"{r['source_id']:18s} {r['path']}  {r['bytes']:,} bytes  checks {'identical' if cmp_ and cmp_['equal'] else cmp_}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
