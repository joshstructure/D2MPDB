"""Export the project pier cap cheek wall calculation report and case from the pier_cheek_wall package (C018).

    .venv\\Scripts\\python.exe scripts\\export_project_pier_cheek_wall_report.py --date 10-22 --decision D-081
    .venv\\Scripts\\python.exe scripts\\export_project_pier_cheek_wall_report.py --register --date 10-22 --decision D-081
    .venv\\Scripts\\python.exe scripts\\export_project_pier_cheek_wall_report.py --check

Pattern: scripts/export_project_pier_wall_report.py (D-071). The starting case of the pier_cheek_wall package (the engine of
Pier_Cheek_Wall_Design.ipynb; the CAD walls and mats of D-059/D-061 with the C001 wind values) is evaluated and written under
project_current/pier_cheek_wall/:

    Pier Cheek Wall Design <m-d>.html          calculation report (calc_common.report)
    Pier Cheek Wall Design <m-d>.json          case
    selected_case.json                         byte-identical copy of the dated case
    Pier Cheek Wall Design <m-d> checks.csv    check register
    README.md                                  what was run and the results

and a source receipt under project_current/coherence/evidence/<folder>/ (the folder is named by the decision below, since the
2026-10-22-pier-cheek-walls folder already holds the D-080 receipt of the tool re-registration). `--register` appends the three
register rows (CHEEK-TOOL, CHEEK-REPORT, CHEEK-CASE) when absent, the decision row, the README index row and the README section
sentence; it never changes an existing row (a later rerun needs a new decision and `--replace`, as the pier wall script does).
The report embeds its generation time and random Plotly figure ids, so a rerun gives new bytes; `--check` regenerates the
report and check register from the saved case with the current package and compares them with the registered files (time and
figure ids masked).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PC = ROOT / 'project_current'
FOLDER = PC / 'pier_cheek_wall'
REGISTER = PC / 'source_register.csv'
EVIDENCE = PC / 'coherence' / 'evidence'
DECISION = 'D-081'          # set from --decision
YEAR = '2026'
TITLE = 'Pier Cheek Wall Design'
STATUS = 'User-selected current - engineering review retained'
FIELDS = ['source_id', 'topic', 'path', 'status', 'scope', 'sha256', 'registered_on', 'depends_on', 'origin', 'notes', 'hash_basis']
MONTHS = {'10': 'October', '11': 'November', '12': 'December'}
AUTHORIZATIONS = {
    'D-081': ('User direction, 22 October 2026 (relayed by the coordinating session): select the pier cap cheek wall calculation as a current '
              'project source and add it to the project journal as calculation C018.'),
}
EVIDENCE_FOLDERS = {'D-081': '2026-10-22-pier-cheek-wall-selection'}
UPSTREAM = 'CAD-MODEL;PIER-CASE;JOURNAL'          # the registered sources the package reads (pier_cheek_wall/data/sources.json)
FIGURE_ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
GENERATED = re.compile(r'Generated \d{4}-\d\d-\d\d \d\d:\d\d UTC')
LABEL = re.compile(r'^(\d\d)-(\d\d)([a-z]?)$')
README_ROW_START = '| Pier cap cheek walls |'
README_UNREGISTERED = ('The run with the CAD case is in `pier_cheek_wall/report/`. The\n'
                       'notebook, report and case are **not** registered sources; select them with a\n'
                       'dated decision when adopted.')


def date_phrase(label: str) -> str:
    m = LABEL.match(label)
    if not m:
        raise ValueError(f'label {label!r}: expected m-d with an optional trailing letter, for example 10-22 or 10-22b')
    return f'{int(m[2])} {MONTHS[m[1]]}'


def iso_date(label: str) -> str:
    m = LABEL.match(label)
    if not m:
        raise ValueError(f'label {label!r}: expected m-d with an optional trailing letter, for example 10-22 or 10-22b')
    return f'{YEAR}-{m[1]}-{m[2]}'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def masked(markup: str) -> str:
    return GENERATED.sub('Generated <time>', FIGURE_ID.sub('<figure-id>', markup))


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


def evidence_folder() -> Path:
    return EVIDENCE / EVIDENCE_FOLDERS[DECISION]


def names(label: str) -> dict[str, Path]:
    return {'report': FOLDER / f'{TITLE} {label}.html', 'dated_case': FOLDER / f'{TITLE} {label}.json',
            'selected_case': FOLDER / 'selected_case.json', 'checks_csv': FOLDER / f'{TITLE} {label} checks.csv'}


def package():
    from calc_common.exports import Exports
    from calc_common import notebook
    from pier_cheek_wall.model import SPEC
    return SPEC, Exports(SPEC), notebook


def outputs(x, e) -> dict[str, bytes]:
    case = x.WRITERS[x.CASE](e)
    return {'report': x.WRITERS[x.REPORT](e), 'dated_case': case, 'selected_case': case, 'checks_csv': x.WRITERS[x.CHECKS](e)}


def summary(e) -> dict:
    counts: dict[str, int] = {}
    for c in e.checks:
        counts[c.status] = counts.get(c.status, 0) + 1
    v = e.value
    at_limit = sorted(c.key for c in e.checks if isinstance(c.ratio, float) and abs(c.ratio - 1.0) < 1e-9)
    return {'checks': len(e.checks), 'status_counts': dict(sorted(counts.items())),
            'failed': [c.key for c in e.checks if 'FAIL' in c.status], 'pending': [c.key for c in e.checks if 'PENDING' in c.status],
            'at_limit': at_limit, 'status': e.status, 'blockpad_status': e.blockpad_status, 'strength_dc': e.strength_dc,
            'P_III_ksf': v('P_III', 'ksf'), 'F_T_III_per_wall_kip': v('F_T_III', 'kip'), 'F_L_III_per_wall_kip': v('F_L_III', 'kip'),
            'F_T_III_both_kip': v('F_T_III_both', 'kip'), 'F_L_III_both_kip': v('F_L_III_both', 'kip'),
            'M_u_A_kip_ft': v('M_u_A', 'kip*ft'), 'V_u_kip': v('V_u', 'kip'), 'DC_flex_A': v('DC_flex_A'), 'DC_develop': v('DC_develop'),
            'l_d_full_in': v('l_d_full', 'in'), 'ratios': {c.key: c.ratio for c in e.checks}}


def readme(e, s: dict, files: dict[str, Path], label: str, case_sha: str, revision: str) -> str:
    from urllib.parse import quote
    link = lambda key: quote(files[key].name)
    p = e.case['inputs']
    return f"""# Pier cap cheek wall current calculation

The [{date_phrase(label)} report]({link('report')}) and [dated JSON]({link('dated_case')}) are selected under {DECISION}.
`selected_case.json` is byte-identical to the dated JSON. The [check register]({link('checks_csv')}) comes from the same case.

The pier_cheek_wall package (case SHA-256 `{case_sha[:16]}`, package revision `{revision[:16]}`, the engine of
`Pier_Cheek_Wall_Design.ipynb`) evaluated its starting case: the two D-059 pier cap cheek walls, {p['H_w']:g} × {p['w_w']:g} × {p['t_w']:g} in
with the {p['r_rec']:g}-in recessed panel, each with its centred mat of {p['n_v']} {p['bar_v']} verticals at {p['s_v']:g} in (developed {p['L_emb']:g} in
straight into the cap, D-061) and {p['n_h']} {p['bar_h']} horizontals at {p['s_h']:g} in, {p['c_edge']:g} in cover; wind directly on the walls per
LRFD 3.8.1.2.1 and 3.8.1.2.3b with the C001 journal values (V {p['V_III']:g} / {p['V_V']:g} / {p['V_SI']:g} mph, K_Z {p['K_Z_III']:.4f} for Strength III,
G {p['G_f']:g}) and the C002 substructure drag coefficient {p['C_D']:g}; concrete {p['fc']:g} ksi and Grade {p['fy']:g} steel from the pier cap case.
No input was changed by hand (D-080 starting case).

Results: {s['status'].lower()}. Strength III pressure {s['P_III_ksf']:.4f} ksf; {s['F_T_III_per_wall_kip']:.2f} kip transverse and
{s['F_L_III_per_wall_kip']:.2f} kip longitudinal per wall ({s['F_T_III_both_kip']:.2f} / {s['F_L_III_both_kip']:.2f} kip for both). Cantilever moment at the
cap top {s['M_u_A_kip_ft']:.3f} kip-ft, shear {s['V_u_kip']:.3f} kip; flexure {s['DC_flex_A']:.3f} of capacity. The straight development of the
verticals ({s['DC_develop']:.2f}; the 12-in LRFD floor once the excess-reinforcement factor applies, {s['l_d_full_in']:.2f} in for full yield
without it) and the cover sit exactly at their limits. The register holds {s['checks']} entries: {s['status_counts']}. Failed:
{', '.join(s['failed']) or 'none'}. Pending: {', '.join(s['pending']) or 'none'} (the one-centred-mat shrinkage and temperature convention
awaits confirmation, as for the end bents under D-039).

The journal-owned inputs (C001 wind values) are literal in this case and live references in the journal edition; the case
names the journal revision whose values they equal (`sources` in the case). Selection is not engineering acceptance. The
Blockpad edition of this report is journal module C018 (PierCheekWalls). Regenerate with
`scripts/export_project_pier_cheek_wall_report.py --date {label} --decision {DECISION}`; the report embeds its generation time and
random figure ids, so a rerun gives new bytes. `--check` regenerates the report from the saved case and compares. Calculation,
source and preservation checks are in the [receipt](../coherence/evidence/{EVIDENCE_FOLDERS[DECISION]}/source_receipt.json).
"""


def register_sources(spec) -> dict:
    """The package's declared sources against the register (hash equality per registered id)."""
    with REGISTER.open(newline='', encoding='utf-8-sig') as f:
        rows = {row['source_id']: row for row in csv.DictReader(f)}
    out = {}
    for sid, src in spec.sources.get('sources', {}).items():
        row = rows.get(sid)
        out[sid] = {'path': src['path'], 'package_sha256': src['sha256'], 'registered_sha256': row['sha256'] if row else None,
                    'registered': row is not None, 'equal_to_register': bool(row) and row['sha256'] == src['sha256']}
    return out


def export(label: str) -> dict:
    spec, x, notebook = package()
    from calc_common.bpad import case_sha as case_hash
    from calc_common.model import evaluate
    e = evaluate(spec)
    data = outputs(x, e)
    files = names(label)
    FOLDER.mkdir(parents=True, exist_ok=True)
    for key, path in files.items():
        path.write_bytes(data[key])
    s = summary(e)
    revision = notebook.embedded_revision(spec, ROOT) or 'working copy'
    (FOLDER / 'README.md').write_text(readme(e, s, files, label, case_hash(e), revision), encoding='utf-8', newline='\n')
    committed = spec.dir / 'report'
    same_as_package_run = {
        'case': (committed / x.CASE).read_bytes() == data['dated_case'],
        'checks_csv': (committed / x.CHECKS).read_bytes() == data['checks_csv'],
        'report_masked': masked((committed / x.REPORT).read_text(encoding='utf-8')) == masked(data['report'].decode('utf-8')),
    }
    receipt = {
        'date': iso_date(label), 'label': label, 'decision': DECISION, 'authorization': AUTHORIZATIONS[DECISION],
        'scope': ('Pier cap cheek wall calculation report and case exported to project_current/pier_cheek_wall/ from the starting case of the '
                  'pier_cheek_wall package (D-080: the D-059/D-061 CAD walls and mats, C001 wind values, C002 substructure drag coefficient, '
                  'pier cap case materials). No input, case, FBMP export, CAD geometry, tracker row or engineering disposition changed in this '
                  'step. The Blockpad edition goes to the journal as C018 (PierCheekWalls).'),
        'generator': {'script': 'scripts/export_project_pier_cheek_wall_report.py',
                      'command': f'.venv\\Scripts\\python.exe scripts\\export_project_pier_cheek_wall_report.py --date {label} --decision {DECISION}',
                      'package': 'pier_cheek_wall', 'package_revision': revision, 'case_sha256': case_hash(e), 'git_head': git_head(),
                      'git_head_note': 'Read from .git/HEAD and the ref file; the working tree was not inspected for uncommitted changes.',
                      'python': sys.version.split()[0],
                      'note': 'The report embeds its generation time and random Plotly figure ids, so a rerun gives new bytes; --check regenerates '
                              'it from the saved case and compares with both masked.'},
        'files': {key: {'path': rel(files[key]), 'sha256': sha256(data[key]), 'bytes': len(data[key])} for key in files},
        'selected_case_equals_dated_case': data['selected_case'] == data['dated_case'],
        'same_as_committed_package_run': {'folder': rel(committed), **same_as_package_run},
        'package_sources_vs_register': register_sources(spec),
        'results': s,
        'register_rows': ['CHEEK-TOOL', 'CHEEK-REPORT', 'CHEEK-CASE'],
        'limitations': ('Notebook package run and export only. The numerical checks are the notebook\'s; the straight development of the verticals '
                        'and the cover sit exactly at their limits (ratio 1.00) and the one-centred-mat shrinkage and temperature convention is '
                        'pending confirmation. Wind is the only load considered (LRFD 3.8.1.3, 3.8.2 and 3.8.3 not applicable; no vehicular, '
                        'pedestrian or seismic action on the walls). The cap anchorage is the straight embedment of D-061; the joint transfer is '
                        'the interface shear check. Selection is not engineering acceptance.'),
    }
    folder = evidence_folder()
    receipt['receipt'] = rel(folder / 'source_receipt.json')
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'source_receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return receipt


def lf_digest(path: Path) -> str:
    return sha256(path.read_bytes().replace(b'\r\n', b'\n'))


def register_rows(receipt: dict) -> list[dict]:
    s = receipt['results']
    files = receipt['files']
    date = receipt['date']
    label = receipt.get('label', date[5:])
    when = f'{date_phrase(label)} {YEAR}'
    rev = receipt['generator']['package_revision'][:12]
    note = (f'{DECISION}. Pier cap cheek wall calculation from the pier_cheek_wall package (CHEEK-TOOL, revision {rev}) on its starting case '
            f'(D-080: the D-059/D-061 CAD walls and mats of CAD-MODEL, the C001 wind values of JOURNAL, the C002 drag coefficient, materials of '
            f'PIER-CASE). {s["status"]}: failed {", ".join(s["failed"]) or "none"}; pending {", ".join(s["pending"]) or "none"}; at their limits '
            f'{", ".join(s["at_limit"]) or "none"}. Strength III pressure {s["P_III_ksf"]:.4f} ksf, {s["F_T_III_per_wall_kip"]:.2f} kip transverse per '
            f'wall; flexure {s["DC_flex_A"]:.3f} of capacity. ')
    origin = f'Notebook package run requested by the user, {when} (scripts/export_project_pier_cheek_wall_report.py)'
    receipt_note = f'See coherence/evidence/{EVIDENCE_FOLDERS[DECISION]}/source_receipt.json. Selection is not engineering acceptance.'
    tool = ROOT / 'Pier_Cheek_Wall_Design.ipynb'
    return [
        {'source_id': 'CHEEK-TOOL', 'topic': 'Pier cap cheek wall notebook', 'path': 'Pier_Cheek_Wall_Design.ipynb', 'status': 'Current tool - bounded verification',
         'scope': 'Pier cap cheek wall wind loading (LRFD 3.8.1.2.1, 3.8.1.2.3b), cantilever flexure, shear, interface shear, crack control, '
                  'development, shrinkage and temperature steel and detailing checks (LRFD 10th ed., FDOT SDG/SDM 2026); reads CAD-MODEL geometry '
                  'and mats, the C001 wind values of JOURNAL and the materials of PIER-CASE',
         'sha256': lf_digest(tool), 'registered_on': date, 'depends_on': UPSTREAM, 'origin': 'Repository main',
         'notes': f'{DECISION} ({when}): portable notebook embedding the pier_cheek_wall package (revision {rev}) on the calc_common framework; '
                  f'report with overview, design basis, schematics and definition and citation cards; standalone and journal Blockpad editions. ' + receipt_note,
         'hash_basis': 'lf_text'},
        {'source_id': 'CHEEK-REPORT', 'topic': 'Pier cap cheek wall report', 'path': files['report']['path'], 'status': STATUS,
         'scope': 'Calculation report for the two pier cap cheek walls under wind (flexure, minimum flexure, shear, interface shear, service, '
                  'development, shrinkage and temperature steel, spacing, cover, thickness)',
         'sha256': files['report']['sha256'], 'registered_on': date, 'depends_on': 'CHEEK-CASE;CHEEK-TOOL;' + UPSTREAM, 'origin': origin,
         'notes': note + 'The report embeds its generation time and random figure ids; --check regenerates it from the case. ' + receipt_note,
         'hash_basis': 'exact_bytes'},
        {'source_id': 'CHEEK-CASE', 'topic': 'Pier cap cheek wall saved case', 'path': files['selected_case']['path'], 'status': STATUS,
         'scope': 'Editable cheek wall case (d2mpdb-pier-cheek-wall schema 1), byte-identical to the dated case beside the report',
         'sha256': files['selected_case']['sha256'], 'registered_on': date, 'depends_on': 'CHEEK-TOOL;' + UPSTREAM, 'origin': origin,
         'notes': note + receipt_note, 'hash_basis': 'exact_bytes'}]


def register(receipt: dict, replace: bool = False) -> list[str]:
    text = REGISTER.read_bytes()
    with REGISTER.open(newline='', encoding='utf-8-sig') as f:
        existing = {row['source_id']: row for row in csv.DictReader(f)}
    if not text.endswith(b'\n') or b'\r\n' in text:
        raise ValueError('The register must use LF line endings and end with a newline.')
    rows = register_rows(receipt)
    new, added, replaced = [], [], {}
    for row in rows:
        old = existing.get(row['source_id'])
        if old is None:
            new.append(row)
            added.append(row['source_id'])
        elif old != row:
            if not replace:
                raise ValueError(f'{row["source_id"]} is registered with different content; record a disposition before replacing it (--replace).')
            if old['notes'].startswith(DECISION + ' ') or old['notes'].startswith(DECISION + '.'):
                raise ValueError(f'{row["source_id"]} already carries {DECISION} in its notes; a second rerun under the same decision needs a new disposition.')
            replaced[row['source_id']] = {k: v for k, v in row.items() if k != 'source_id'}
    if replaced:
        from scripts.register_update import update_rows
        update_rows(replaced, prepend_notes=True)
        added += [f'{sid} (replaced)' for sid in replaced]
    if new:
        buffer = io.StringIO()
        csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator='\n').writerows([[row[f] for f in FIELDS] for row in new])
        with REGISTER.open('ab') as f:
            f.write(buffer.getvalue().encode('utf-8'))
    return added


def add_decision(receipt: dict) -> bool:
    path = PC / 'decisions.md'
    text = path.read_text(encoding='utf-8')
    if f'| {DECISION} |' in text:
        return False
    s = receipt['results']
    rev = receipt['generator']['package_revision'][:12]
    results = (f'{s["status"].lower()}; failed {", ".join(s["failed"]) or "none"}; pending {", ".join(s["pending"]) or "none"} (one-centred-mat '
               f'shrinkage and temperature convention); development and cover exactly at their limits (1.00); Strength III pressure {s["P_III_ksf"]:.4f} ksf, '
               f'{s["F_T_III_per_wall_kip"]:.2f} kip transverse and {s["F_L_III_per_wall_kip"]:.2f} kip longitudinal per wall, cantilever moment '
               f'{s["M_u_A_kip_ft"]:.3f} kip-ft and shear {s["V_u_kip"]:.3f} kip at the cap top, flexure {s["DC_flex_A"]:.3f} of capacity.')
    row = (f'| {DECISION} | {receipt["date"]} | Select the pier cap cheek wall calculation as a current project source: the Pier Cheek Wall Design '
           f'notebook (CHEEK-TOOL), its {date_phrase(receipt["label"])} report (CHEEK-REPORT) and saved case (CHEEK-CASE) under '
           f'`project_current/pier_cheek_wall/`, and add its Blockpad edition to the journal as calculation C018 (PierCheekWalls) after C017. | '
           f'{AUTHORIZATIONS[DECISION]} Starting case of the pier_cheek_wall package (revision {rev}; D-080): the D-059/D-061 walls and mats of '
           f'CAD-MODEL, the C001 wind values of JOURNAL (live references in the journal edition through the coherence gate), the C002 substructure '
           f'drag coefficient and the materials of PIER-CASE; no input changed by hand. Results: {results} The journal edition is generated by '
           f'scripts/build_pier_cheek_wall.py --journal (every definition evaluated independently by the Blockpad-syntax evaluator and compared with '
           f'the notebook to 1 part in 10⁹; live project stamp; hidden working notes) and added by task T038, then moved after C017 by task T039; '
           f'native recalculation, appearance and engineering reviews not performed. The case names the T037 journal revision (ceeb8ebb) as the '
           f'journal whose C001 values its wind inputs equal; the C018 edition enters the following revision, as the C006/C004 editions of T035 do. '
           f'Not changed: the CAD model and drawings, the pier cap case and FBMP exports, the end-bent backwall calculation (C014 keeps the end-bent '
           f'cheek walls), the other journal modules and the tracker responses. Wind is the only action considered; the straight 12-in cap embedment '
           f'and the 2-in cover sit exactly at their limits and the one-mat convention awaits confirmation. Selection is not engineering acceptance. '
           f'See [receipt](coherence/evidence/{EVIDENCE_FOLDERS[DECISION]}/source_receipt.json). |')
    lines = text.split('\n')
    idx = max(i for i, line in enumerate(lines) if re.match(r'\| D-\d{3} \|', line))
    lines.insert(idx + 1, row)
    path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    return True


def add_readme_row(receipt: dict) -> bool:
    path = PC / 'README.md'
    text = path.read_text(encoding='utf-8')
    report = receipt['files']['report']['path'].replace('project_current/', '', 1).replace(' ', '%20')
    when = date_phrase(receipt.get('label', receipt['date'][5:]))
    row = (f'{README_ROW_START} [Report]({report}), [saved case](pier_cheek_wall/selected_case.json) — wind directly on the D-059 walls '
           f'(LRFD 3.8.1.2.1 and 3.8.1.2.3b with the C001 values), D-059/D-061 CAD mats as the starting case, {when} run ({DECISION}); every numerical '
           f'check passes, development and cover at their limits, one-mat convention pending; Blockpad edition C018 in the journal (T038/T039) |')
    changed = False
    lines = text.split('\n')
    hits = [i for i, line in enumerate(lines) if line.startswith(README_ROW_START)]
    if len(hits) > 1:
        raise ValueError('more than one pier cheek wall README row')
    if hits:
        if lines[hits[0]] != row:
            lines[hits[0]] = row
            changed = True
        text = '\n'.join(lines)
    else:
        anchor = '\n| Report cards (D-068) |'
        if text.count(anchor) != 1:
            raise ValueError('README anchor not found')
        text = text.replace(anchor, '\n' + row + anchor, 1)
        changed = True
    if README_UNREGISTERED in text:
        text = text.replace(README_UNREGISTERED, (
            f'The run with the CAD case is in `pier_cheek_wall/report/`; the same\n'
            f'starting case is selected under {DECISION} as CHEEK-TOOL, CHEEK-REPORT and CHEEK-CASE\n'
            f'(`project_current/pier_cheek_wall/`, {when} export) and its Blockpad edition is\n'
            f'journal calculation C018 (tasks T038 and T039; see the\n'
            f'[selection receipt](coherence/evidence/{EVIDENCE_FOLDERS[DECISION]}/source_receipt.json)).'), 1)
        changed = True
    if changed:
        path.write_text(text, encoding='utf-8', newline='\n')
    return changed


def registered_paths() -> dict[str, Path]:
    with REGISTER.open(newline='', encoding='utf-8-sig') as f:
        return {row['source_id']: ROOT / row['path'] for row in csv.DictReader(f) if row['source_id'].startswith('CHEEK-')}


def check() -> list[str]:
    spec, x, _ = package()
    from calc_common.model import evaluate
    problems = []
    paths = registered_paths()
    for tag in ('CHEEK-REPORT', 'CHEEK-CASE', 'CHEEK-TOOL'):
        if tag not in paths:
            problems.append(f'{tag}: not in the source register')
    if problems:
        return problems
    report, case_path = paths['CHEEK-REPORT'], paths['CHEEK-CASE']
    dated = report.with_suffix('.json')
    checks = report.with_name(report.stem + ' checks.csv')
    missing = [p for p in (report, case_path, dated, checks) if not p.is_file()]
    problems += [f'missing {rel(p)}' for p in missing]
    if missing:
        return problems
    saved_bytes = case_path.read_bytes()
    if saved_bytes != dated.read_bytes():
        problems.append(f'{case_path.name} differs from {dated.name}')
    case = x.load_case(saved_bytes)
    if x.case_json(case).encode('utf-8') != saved_bytes:
        problems.append('the saved case changes when loaded by the current package')
    e = evaluate(spec, case)
    data = outputs(x, e)
    if masked(report.read_text(encoding='utf-8')) != masked(data['report'].decode('utf-8')):
        problems.append('the report differs from one regenerated from the saved case with the current package')
    if checks.read_bytes() != data['checks_csv']:
        problems.append('the check register differs from the regenerated one')
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--date', help='m-d suffix for the file names, for example 10-22; a trailing letter (10-22b) marks a second export on the same day')
    parser.add_argument('--decision', default='D-081', choices=sorted(AUTHORIZATIONS), help='the decision this export records (default D-081)')
    parser.add_argument('--register', action='store_true', help='append the register rows, the decision row and the README row from the receipt of --date')
    parser.add_argument('--replace', action='store_true', help='with --register: rewrite existing CHEEK-* rows for a new decision')
    parser.add_argument('--check', action='store_true', help='verify the registered report instead of exporting')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    global DECISION
    DECISION = args.decision
    if args.check:
        problems = check()
        print('\n'.join(problems) if problems else 'The registered pier cheek wall report equals one regenerated from its saved case with the current package.')
        return 1 if problems else 0
    if args.register:
        if not args.date:
            parser.error('--date is required to register')
        receipt = json.loads((evidence_folder() / 'source_receipt.json').read_text(encoding='utf-8'))
        if receipt['decision'] != DECISION or receipt['label'] != args.date:
            parser.error(f'the receipt records {receipt["decision"]} / {receipt["label"]}, not {DECISION} / {args.date}')
        added = register(receipt, replace=args.replace)
        print('Registered ' + ', '.join(added) if added else 'All pier cheek wall rows are already registered.')
        print('Decision row added' if add_decision(receipt) else 'Decision row already present')
        print('README updated' if add_readme_row(receipt) else 'README already current')
        return 0
    if not args.date:
        parser.error('--date is required to export')
    receipt = export(args.date)
    for key, info in receipt['files'].items():
        print(f'Wrote {info["path"]} ({info["bytes"]:,} bytes)')
    print(f'Wrote {receipt["receipt"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
