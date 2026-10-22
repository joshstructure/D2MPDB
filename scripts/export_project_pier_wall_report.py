"""Export the project pier-wall (annular pile ring) calculation report and case from the ring_wall package.

    .venv\\Scripts\\python.exe scripts\\export_project_pier_wall_report.py --date 10-21
    .venv\\Scripts\\python.exe scripts\\export_project_pier_wall_report.py --register --date 10-21
    .venv\\Scripts\\python.exe scripts\\export_project_pier_wall_report.py --date 10-22 --decision D-075
    .venv\\Scripts\\python.exe scripts\\export_project_pier_wall_report.py --register --replace --date 10-22 --decision D-075
    .venv\\Scripts\\python.exe scripts\\export_project_pier_wall_report.py --check

The starting case of the ring_wall package (the engine of Pier_Wall_Design.ipynb) is evaluated and written under
project_current/pier_wall/:

    Pier Wall Design <m-d>.html              calculation report (ring_wall.output.render_report)
    Pier Wall Design <m-d>.json              case
    selected_case.json                       byte-identical copy of the dated case
    Pier Wall Design <m-d> checks.csv        check register
    Pier Wall Design <m-d> ring forces.csv   ring actions
    README.md                                what was run and the results

and a source receipt under project_current/coherence/evidence/2026-<m-d>-pier-wall/. `--register` appends the three
register rows (PIER-WALL-TOOL, PIER-WALL-REPORT, PIER-WALL-CASE) when absent, the decision row and the README index row;
it never changes an existing row unless `--replace` is given, which rewrites the three rows in place (the new decision text
goes in front of the row's notes, scripts/register_update.py) and the README index row. `--decision` names the decision
the export records (D-071 for the 21 October 2026 selection; D-075 for the 22 October 2026 rerun on the CAD wall geometry);
the decision row text and the authorization are keyed by it below. The report embeds the case and package hashes but also
random Plotly figure ids, so a rerun gives new bytes; `--check` regenerates the report, check register and ring forces from
the saved case with the current package and compares them with the registered files (figure ids masked).
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
FOLDER = PC / 'pier_wall'
REGISTER = PC / 'source_register.csv'
EVIDENCE = PC / 'coherence' / 'evidence'
DECISION = 'D-071'          # set from --decision
YEAR = '2026'
TITLE = 'Pier Wall Design'
STATUS = 'User-selected current - engineering review retained'
FIELDS = ['source_id', 'topic', 'path', 'status', 'scope', 'sha256', 'registered_on', 'depends_on', 'origin', 'notes', 'hash_basis']
MONTHS = {'10': 'October', '11': 'November', '12': 'December'}
AUTHORIZATIONS = {
    'D-071': 'User instruction, 21 October 2026: "run that notebook and update the calc report and the bpad calc in the journal."',
    'D-075': ('User instruction, 22 October 2026: reconcile the pier wall to the CAD geometry (219 in long, 36 in thick, bottom 1 ft below terrain '
              'at EL 24.5264, top at cap bottom): update the journal gravity row, C006/C017 inputs, the ring wall case and the pile free length, '
              'then rerun the editions.'),
}
# What the starting geometry is, per decision (README and receipt text).
GEOMETRY_NOTES = {
    'D-071': 'The starting dimensions were the earlier study snapshot (213 × 36 × 172.375 in; free length 127 in from the pile cutoff).',
    'D-075': ('The starting dimensions follow the CAD pier wall (D-075): 219 × 36 in, bottom 1 ft below terrain at EL 24.5264 ft, top at the cap bottom '
              'EL 40.76494 ft (194.8625 in high), 19.5 in from each wall end to the outer pile; the free length to fixity (92.4 in) is measured from that '
              'bottom (110.7 in sand depth to fixity below the pile-case ground EL 26.05 less the 18.3 in of wall below it). The journal gravity sheet '
              'row, C006 and this case agree with the CAD model and the drawings.'),
}
FIGURE_ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def date_phrase(label: str) -> str:
    month, day = label.split('-')
    return f'{int(day)} {MONTHS[month]}'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def masked(markup: str) -> str:
    return FIGURE_ID.sub('<figure-id>', markup)


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


def names(label: str) -> dict[str, Path]:
    return {'report': FOLDER / f'{TITLE} {label}.html', 'dated_case': FOLDER / f'{TITLE} {label}.json', 'selected_case': FOLDER / 'selected_case.json',
            'checks_csv': FOLDER / f'{TITLE} {label} checks.csv', 'ring_forces_csv': FOLDER / f'{TITLE} {label} ring forces.csv'}


def outputs(r) -> dict[str, bytes]:
    from ring_wall.output import csv_bytes, render_report
    case = json.dumps(r['case'], indent=2, allow_nan=False, ensure_ascii=False).encode()
    return {'report': render_report(r).encode('utf-8'), 'dated_case': case, 'selected_case': case,
            'checks_csv': csv_bytes(r['checks']), 'ring_forces_csv': csv_bytes(r['rings'])}


def summary(r) -> dict:
    t = r['totals']
    counts: dict[str, int] = {}
    for c in r['checks']:
        counts[c['status']] = counts.get(c['status'], 0) + 1
    worst = max(r['rings'], key=lambda a: a['e_equivalent'])
    return {'checks': len(r['checks']), 'status_counts': dict(sorted(counts.items())), 'failed': [c['id'] for c in r['checks'] if c['status'] == 'FAIL'],
            'pending': [c['id'] for c in r['checks'] if c['status'] == 'PENDING'], 'overall': r['overall'],
            'service_weight_kip': t['service_weight'], 'factored_weight_kip': t['factored_weight'], 'wall_rotation_rad': t['wall_rotation'],
            'pile_head_moment_kip_in': t['pile_head_moment'], 'ring_moment_kip_in': t['ring_moment'], 'kern_limit_in': t['kern_limit'],
            'largest_equivalent_eccentricity_in': worst['e_equivalent'], 'largest_equivalent_eccentricity_ring': f'R{worst["row"]}-P{worst["pile"]}',
            'rings_without_contact': sum(not a['contact_ok'] for a in r['rings']), 'largest_design_ring_load_kip': max(a['R_design'] for a in r['rings']),
            'largest_qmax_ksi': max(a['qmax'] for a in r['rings']), 'grid': f'#{r["grid"]["bar"]} at {r["grid"]["spacing"]:g} in',
            'weld_leg_provided_in': r['case']['weld_leg_in'], 'largest_trial_weld_leg_in': max(a['weld_req'] for a in r['rings']),
            'scope_items': [k for k, _ in r['pending']]}


def readme(r, s: dict, files: dict[str, Path], label: str, case_sha: str, source_sha: str) -> str:
    from urllib.parse import quote
    link = lambda key: quote(files[key].name)
    p = r['case']
    return f"""# Pier wall (annular pile rings) current calculation

The [{date_phrase(label)} report]({link('report')}) and [dated JSON]({link('dated_case')}) are selected under {DECISION}.
`selected_case.json` is byte-identical to the dated JSON. The [check register]({link('checks_csv')}) and
[ring forces]({link('ring_forces_csv')}) come from the same case.

The ring_wall package (case SHA-256 `{case_sha[:16]}`, package source SHA-256 `{source_sha[:16]}`, the engine of
`Pier_Wall_Design.ipynb`) evaluated its starting case: a {p['length_in']:g} × {p['thickness_in']:g} × {p['height_in']:g} in wall on
{p['pile_count']} pipe piles of {p['pile_od_in']:g} in at {p['pile_spacing_in']:g} in, {p['ring_count']} rows of {p['ring_od_in']:g}/{p['ring_id_in']:g} × {p['ring_t_in']:g} in
annular plates with two {p['weld_leg_in'] * 16:g}/16 in fillets, radial placement tolerance {p['placement_tolerance_in']:g} in. The ring moment basis is
D-070 (pile-head compatibility moment; tolerance as pile-group redistribution); the pile stiffness lengths default to the
pier pile case (PILE-PIER-CASE), free length {p['pile_free_length_in']:g} in. No input was changed by hand.
{GEOMETRY_NOTES[DECISION]}

Results: {s['overall'].lower()}. Wall rotation {s['wall_rotation_rad']:.3e} rad; pile-head moment {s['pile_head_moment_kip_in']:.3f} kip-in;
{s['ring_moment_kip_in']:.3f} kip-in per ring; largest equivalent eccentricity {s['largest_equivalent_eccentricity_in']:.3f} in at
{s['largest_equivalent_eccentricity_ring']} against the {s['kern_limit_in']:.3f} in kern; {s['rings_without_contact']} rings without full contact. Largest
design ring load {s['largest_design_ring_load_kip']:.3f} kip; peak bearing {s['largest_qmax_ksi']:.4f} ksi. Grid {s['grid']} each way each face. Weld leg
{p['weld_leg_in'] * 16:g}/16 in provided against a largest trial requirement of {s['largest_trial_weld_leg_in'] * 16:g}/16 in. The register holds {s['checks']} entries:
{s['status_counts']}. Failed: {', '.join(s['failed']) or 'none'}. Pending: {len(s['pending'])}.

Open scope items ({', '.join(s['scope_items'])}) stay in every result; selection is not engineering acceptance. The Blockpad
edition of this report is journal module C017 (PierWallRings, task T028). Regenerate with
`scripts/export_project_pier_wall_report.py --date {label}`; the report embeds random figure ids, so a rerun gives new bytes.
`--check` regenerates the report from the saved case and compares. Calculation, source and preservation checks are in the
[receipt](../coherence/evidence/{YEAR}-{label}-pier-wall/source_receipt.json).
"""


def export(label: str) -> dict:
    import plotly
    from ring_wall.model import analyze, default_case
    from ring_wall.output import case_hash, source_hash
    case = default_case()
    r = analyze(case)
    if r['case'] != case:
        raise ValueError('the evaluated case differs from the starting case')
    data = outputs(r)
    files = names(label)
    FOLDER.mkdir(parents=True, exist_ok=True)
    for key, path in files.items():
        path.write_bytes(data[key])
    s = summary(r)
    (FOLDER / 'README.md').write_text(readme(r, s, files, label, case_hash(r), source_hash()), encoding='utf-8', newline='\n')
    receipt = {
        'date': f'{YEAR}-{label}', 'decision': DECISION, 'authorization': AUTHORIZATIONS[DECISION],
        'scope': ('Pier wall annular-ring calculation report and case exported to project_current/pier_wall/ from the starting case of the ring_wall '
                  'package (D-070 ring moment basis; pile stiffness defaults from PILE-PIER-CASE). ' + GEOMETRY_NOTES[DECISION] + ' No other case, FBMP '
                  'export, CAD geometry, tracker row or engineering disposition changed in this step. The Blockpad edition goes to the journal as C017.'),
        'geometry_basis': GEOMETRY_NOTES[DECISION],
        'generator': {'script': 'scripts/export_project_pier_wall_report.py', 'command': f'.venv\\Scripts\\python.exe scripts\\export_project_pier_wall_report.py --date {label}',
                      'package': 'ring_wall', 'package_source_sha256': source_hash(), 'case_sha256': case_hash(r), 'git_head': git_head(),
                      'git_head_note': 'Read from .git/HEAD and the ref file; the working tree was not inspected for uncommitted changes.',
                      'python': sys.version.split()[0], 'plotly': plotly.__version__,
                      'note': 'The report embeds random Plotly figure ids, so a rerun gives new bytes; --check regenerates it from the saved case and compares with the ids masked.'},
        'files': {key: {'path': rel(files[key]), 'sha256': sha256(data[key]), 'bytes': len(data[key])} for key in files},
        'selected_case_equals_dated_case': data['selected_case'] == data['dated_case'],
        'results': s,
        'register_rows': ['PIER-WALL-TOOL', 'PIER-WALL-REPORT', 'PIER-WALL-CASE'],
        'limitations': ('Notebook package run and export only. The numerical checks are the notebook\'s; the five scope items (sharing among rows, pile '
                        'stiffness confirmation, wall load paths, connection scope, geometry basis) remain open; the failed checks of the 23-in ring '
                        f'trial ({", ".join(s["failed"]) or "none"}) remain. Which pier-wall support concept governs (C006 fin plates and hairpins or '
                        'these welded rings) is not decided by this export. Selection is not engineering acceptance.')}
    folder = EVIDENCE / f'{YEAR}-{label}-pier-wall'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'source_receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return receipt


def lf_digest(path: Path) -> str:
    return sha256(path.read_bytes().replace(b'\r\n', b'\n'))


def register_rows(receipt: dict) -> list[dict]:
    s = receipt['results']
    files = receipt['files']
    date = receipt['date']
    when = f'{date_phrase(date[5:])} {YEAR}'
    geometry = ('CAD wall geometry (219 x 36 x 194.8625 in, free length 92.4 in from the wall bottom). ' if DECISION != 'D-071' else '')
    note = (f'{DECISION}. Pier wall annular-ring calculation from the ring_wall package (PIER-WALL-TOOL, source {receipt["generator"]["package_source_sha256"][:12]}) '
            f'on its starting case; ring moment basis D-070 with pile stiffness defaults from PILE-PIER-CASE. {geometry}{s["overall"]}: failed {", ".join(s["failed"]) or "none"}; '
            f'{len(s["pending"])} pending; largest equivalent eccentricity {s["largest_equivalent_eccentricity_in"]:.3f} in against the {s["kern_limit_in"]:.3f} in kern. '
            f'Open: {", ".join(s["scope_items"])}; support concept (C006 fin plates vs welded rings) undecided. ')
    origin = f'Notebook package run requested by the user, {when} (scripts/export_project_pier_wall_report.py)'
    receipt_note = f'See coherence/evidence/{date}-pier-wall/source_receipt.json. Selection is not engineering acceptance.'
    tool = ROOT / 'Pier_Wall_Design.ipynb'
    return [
        {'source_id': 'PIER-WALL-TOOL', 'topic': 'Pier wall ring design notebook', 'path': 'Pier_Wall_Design.ipynb', 'status': 'Current tool - bounded verification',
         'scope': 'Pier wall minimum steel, detailing and welded annular pile-ring connection checks (LRFD 10th ed.); reads PILE-PIER-CASE for the default pile stiffness lengths',
         'sha256': lf_digest(tool), 'registered_on': date, 'depends_on': 'PILE-PIER-CASE', 'origin': 'Repository main',
         'notes': f'{DECISION} ({when}): portable notebook embedding the ring_wall package (source {receipt["generator"]["package_source_sha256"][:12]}), '
                  f'D-070 ring moment basis, {geometry.lower() if geometry else ""}weld legs in sixteenths, report with overview, design basis and drawings. ' + receipt_note,
         'hash_basis': 'lf_text'},
        {'source_id': 'PIER-WALL-REPORT', 'topic': 'Pier wall ring design report', 'path': files['report']['path'], 'status': STATUS,
         'scope': 'Calculation report for the pier wall on welded annular pile rings (minimum steel, detailing, contact, bearing, plate, welds, base metal)',
         'sha256': files['report']['sha256'], 'registered_on': date, 'depends_on': 'PIER-WALL-CASE;PIER-WALL-TOOL;PILE-PIER-CASE', 'origin': origin,
         'notes': note + 'The report embeds random figure ids; --check regenerates it from the case. ' + receipt_note, 'hash_basis': 'exact_bytes'},
        {'source_id': 'PIER-WALL-CASE', 'topic': 'Pier wall saved ring case', 'path': files['selected_case']['path'], 'status': STATUS,
         'scope': 'Editable ring-wall case (schema 3), byte-identical to the dated case beside the report',
         'sha256': files['selected_case']['sha256'], 'registered_on': date, 'depends_on': 'PIER-WALL-TOOL;PILE-PIER-CASE', 'origin': origin,
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
        update_rows(replaced, prepend_notes=True)      # the new decision text goes in front of the row's history
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
    results = (f'{s["overall"].lower()}; failed {", ".join(s["failed"]) or "none"}; {len(s["pending"])} pending; wall rotation {s["wall_rotation_rad"]:.3e} rad, '
               f'{s["ring_moment_kip_in"]:.3f} kip-in per ring, largest equivalent eccentricity {s["largest_equivalent_eccentricity_in"]:.3f} in against the '
               f'{s["kern_limit_in"]:.3f} in kern, {s["rings_without_contact"]} rings without contact; grid {s["grid"]}; weld leg {s["weld_leg_provided_in"] * 16:g}/16 in.')
    if DECISION == 'D-071':
        row = (f'| {DECISION} | {receipt["date"]} | Select the pier wall annular-ring calculation as a current project source: the Pier Wall Design notebook '
               f'(PIER-WALL-TOOL), its 21 October report (PIER-WALL-REPORT) and saved case (PIER-WALL-CASE) under `project_current/pier_wall/`, and add its '
               f'Blockpad edition to the journal as calculation C017 (PierWallRings). | {AUTHORIZATIONS[DECISION]} Starting case of the ring_wall package with the D-070 '
               f'ring moment basis and pile stiffness defaults from PILE-PIER-CASE: {results} The journal edition is generated by scripts/build_ring_wall_bpad.py '
               f'(every value and status evaluated independently to 1e-9; the lost-contact status reads NO CONTACT there) and added by task T028, then moved '
               f'after C016 by task T029; native recalculation, appearance and engineering reviews not performed. C006 (fin plates and hairpins) stays in the '
               f'journal: which pier-wall support concept governs is undecided and not settled by this selection. The five scope items of the calculation and '
               f'the 23-in ring end-cover and grid-clearance failures remain open. Selection is not engineering acceptance. See '
               f'[receipt](coherence/evidence/{receipt["date"]}-pier-wall/source_receipt.json). |')
    else:
        row = (f'| {DECISION} | {receipt["date"]} | Reconcile the pier wall to the CAD geometry: 219 in long, 36 in thick, bottom 1 ft below terrain at EL 24.5264 ft, '
               f'top at the cap bottom (194.8625 in high); the journal gravity row, C006 and C017 inputs, the ring wall starting case and the pile free length '
               f'follow it, and the editions are rerun ({date_phrase(receipt["date"][5:])} report, PIER-WALL-REPORT, and case, PIER-WALL-CASE). | '
               f'{AUTHORIZATIONS[DECISION]} Before this decision three pier walls existed: the journal gravity sheet, C006 and the ring wall case used '
               f'213 × 36 × 172.375 in (an earlier study snapshot tied to no registered elevation); the CAD model and the FDOT drawings use 219 × 36 in from '
               f'EL 24.5264 (terrain 25.5264 less 1 ft burial) to the cap bottom EL 40.76494; the wind calculation C002 uses the 230-in cap face. The CAD wall '
               f'governs by user direction. Ring wall package defaults: length 219 in, height 194.8625 in, free length to fixity 92.4 in from the wall bottom '
               f'(110.7 in sand depth to fixity below the pile-case ground EL 26.05, LRFD C10.7.3.13.4, less the 18.3 in of wall below that ground; the former '
               f'127 in measured from the pile cutoff, 12 in inside the cap). Journal: gravity row 42 of PedBridgeWeights_2Beams (E42 18 ft 3 in, G42 16 ft '
               f'2.8625 in; H42, J42 and K42 caches recomputed, wall weight 114.737 to 133.359 kip), C006 and C004 regenerated by their packages with the new '
               f'journal values (C004 shows the wall weight for information only; no result changes), C017 regenerated from this case (task T034). '
               f'Results of this case: {results} The former RING-END failure was an artefact of the 213-in length (2 in end cover at tolerance; now 5 in). '
               f'Not changed: the CAD model and drawings (they govern), the geometry notebook (it does not own a pier wall; notebook ownership stays a '
               f'reconciliation item), C002 (cap-face wind area, conservative), the FBMP pier export (its pile-row wall load was entered from the 114.7 kip '
               f'wall; the 133.4 kip CAD wall is +18.6 kip, recorded as assumption A-012 for the next FBMP rerun decision) and the pile case ground EL 26.05 '
               f'against the journal/CAD terrain 25.5264 (A-013). Native recalculation, appearance and engineering reviews not performed; selection is not '
               f'engineering acceptance. See [receipt](coherence/evidence/{receipt["date"]}-pier-wall/source_receipt.json). |')
    lines = text.split('\n')
    idx = max(i for i, line in enumerate(lines) if re.match(r'\| D-\d{3} \|', line))
    lines.insert(idx + 1, row)
    path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    return True


def add_readme_row(receipt: dict) -> bool:
    path = PC / 'README.md'
    text = path.read_text(encoding='utf-8')
    report = receipt['files']['report']['path'].replace('project_current/', '', 1).replace(' ', '%20')
    when = date_phrase(receipt['date'][5:])
    if DECISION == 'D-071':
        row = (f'| Pier wall on annular pile rings | [Report]({report}), [saved case](pier_wall/selected_case.json) — welded-ring support concept, '
               f'D-070 moment basis, {when} run ({DECISION}); Blockpad edition C017 in the journal (T028/T029); the C006 fin-plate concept is not superseded |')
    else:
        row = (f'| Pier wall on annular pile rings | [Report]({report}), [saved case](pier_wall/selected_case.json) — welded-ring support concept, '
               f'D-070 moment basis, CAD wall geometry (219 × 36 × 194.8625 in, {DECISION}), {when} run; Blockpad edition C017 in the journal (T028/T029/T034); '
               f'the C006 fin-plate concept is not superseded |')
    lines = text.split('\n')
    hits = [i for i, line in enumerate(lines) if line.startswith('| Pier wall on annular pile rings |')]
    if len(hits) > 1:
        raise ValueError('more than one pier wall README row')
    if hits:
        if lines[hits[0]] == row:
            return False
        lines[hits[0]] = row
        path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
        return True
    anchor = '\n| Report cards (D-068) |'
    if text.count(anchor) != 1:
        raise ValueError('README anchor not found')
    text = text.replace(anchor, '\n' + row + anchor, 1)
    path.write_text(text, encoding='utf-8', newline='\n')
    return True


def registered_paths() -> dict[str, Path]:
    with REGISTER.open(newline='', encoding='utf-8-sig') as f:
        return {row['source_id']: ROOT / row['path'] for row in csv.DictReader(f) if row['source_id'].startswith('PIER-WALL-')}


def check() -> list[str]:
    from ring_wall.model import analyze, upgrade_case
    problems = []
    paths = registered_paths()
    for tag in ('PIER-WALL-REPORT', 'PIER-WALL-CASE', 'PIER-WALL-TOOL'):
        if tag not in paths:
            problems.append(f'{tag}: not in the source register')
    if problems:
        return problems
    report, case_path = paths['PIER-WALL-REPORT'], paths['PIER-WALL-CASE']
    dated = report.with_suffix('.json')
    checks = report.with_name(report.stem + ' checks.csv')
    forces = report.with_name(report.stem + ' ring forces.csv')
    missing = [p for p in (report, case_path, dated, checks, forces) if not p.is_file()]
    problems += [f'missing {rel(p)}' for p in missing]
    if missing:
        return problems
    saved_bytes = case_path.read_bytes()
    if saved_bytes != dated.read_bytes():
        problems.append(f'{case_path.name} differs from {dated.name}')
    saved = json.loads(saved_bytes.decode('utf-8-sig'))
    case, notes = upgrade_case(saved)
    if notes or case != saved:
        problems.append('the saved case changes when loaded by the current package')
    r = analyze(saved)
    data = outputs(r)
    if masked(report.read_text(encoding='utf-8')) != masked(data['report'].decode('utf-8')):
        problems.append('the report differs from one regenerated from the saved case with the current package')
    if checks.read_bytes() != data['checks_csv']:
        problems.append('the check register differs from the regenerated one')
    if forces.read_bytes() != data['ring_forces_csv']:
        problems.append('the ring forces differ from the regenerated ones')
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--date', help='m-d suffix for the file names, for example 10-21')
    parser.add_argument('--decision', default='D-071', choices=sorted(AUTHORIZATIONS), help='the decision this export records (default D-071)')
    parser.add_argument('--register', action='store_true', help='append the register rows, the decision row and the README row from the receipt of --date')
    parser.add_argument('--replace', action='store_true', help='with --register: rewrite existing PIER-WALL-* rows and the README row for a new decision')
    parser.add_argument('--check', action='store_true', help='verify the registered report instead of exporting')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    global DECISION
    DECISION = args.decision
    if args.check:
        problems = check()
        print('\n'.join(problems) if problems else 'The registered pier wall report equals one regenerated from its saved case with the current package.')
        return 1 if problems else 0
    if args.register:
        if not args.date:
            parser.error('--date is required to register')
        receipt = json.loads((EVIDENCE / f'{YEAR}-{args.date}-pier-wall' / 'source_receipt.json').read_text(encoding='utf-8'))
        if receipt['decision'] != DECISION:
            parser.error(f'the receipt of {args.date} records {receipt["decision"]}, not {DECISION}')
        added = register(receipt, replace=args.replace)
        print('Registered ' + ', '.join(added) if added else 'All pier wall rows are already registered.')
        print('Decision row added' if add_decision(receipt) else 'Decision row already present')
        print('README row added' if add_readme_row(receipt) else 'README row already present')
        return 0
    if not args.date:
        parser.error('--date is required to export')
    receipt = export(args.date)
    for key, info in receipt['files'].items():
        print(f'Wrote {info["path"]} ({info["bytes"]:,} bytes)')
    print(f'Wrote project_current/coherence/evidence/{receipt["date"]}-pier-wall/source_receipt.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
