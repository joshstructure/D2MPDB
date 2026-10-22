"""Apply the registered FB-MultiPier export to a project cap case and export the dated case and report.

    .venv\\Scripts\\python.exe scripts\\apply_fbmp_to_cap_case.py --support pier --date 10-21 --decision D-073
    .venv\\Scripts\\python.exe scripts\\apply_fbmp_to_cap_case.py --support pier --date 10-21 --decision D-073 --register

The D-051 rerun (19 October 2026) did this through the portable cap notebook: load the selected case, stage and
apply the XML in the fixed-depth import panel, recalculate, export. This script is the same path without the
notebook UI, so a rerun is reproducible:

1. read `project_current/cap_design/<folder>/selected_case.json` with `pier_cap.io.load_case` and confirm the
   loaded case equals the saved file;
2. read the export registered under the case's XML source id, confirm its SHA-256 equals the register, and build
   the proposed case with `pier_cap.fbmp.import_fbmp_xml(xml, base=case)` (the XMLImportPanel's reader): the
   force envelopes and the analysis provenance come from the XML, trial reinforcing and covers are retained;
3. evaluate the case before and after and record every input, status and ratio that changed;
4. archive the previous `selected_case.json` under `archive/<date>-before-fbmp-rerun/`, write the new
   `selected_case.json` and the byte-identical `<Title> <m-d>.json`, write `<Title> <m-d>.html` with
   `pier_cap.calculation_report.write_calculation_report` and confirm the report embeds the saved case;
5. rewrite the folder README and write the receipt `coherence/evidence/2026-<m-d>-cap-rerun/source_receipt.json`.

`--register` then moves the case and report rows of the source register to the new files with the decision text in
front of their notes (scripts/register_update.py). Nothing else in the register changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CAP_DESIGN = ROOT / 'project_current' / 'cap_design'
EVIDENCE = ROOT / 'project_current' / 'coherence' / 'evidence'
YEAR = '2026'
SUPPORTS = {
    'pier': {'folder': 'pier', 'title': 'Pier Cap Design', 'label': 'Pier', 'xml': 'PIER-XML', 'case': 'PIER-CASE', 'report': 'PIER-REPORT'},
    'end_bents': {'folder': 'end_bents', 'title': 'End Bent 1 Cap Design', 'label': 'End Bent 1', 'xml': 'EB-XML', 'case': 'EB-CASE', 'report': 'EB-REPORT'},
    'end_bent_2': {'folder': 'end_bent_2', 'title': 'End Bent 2 Cap Design', 'label': 'End Bent 2', 'xml': 'EB2-XML', 'case': 'EB2-CASE', 'report': 'EB2-REPORT'},
}
FORCE_INPUTS = ('Mu_N', 'Mu_P', 'Mu_B', 'MI_N', 'MI_P', 'MI_B', 'Vu_G', 'Vu_L', 'Tu')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _summary(e) -> dict:
    counts: dict[str, int] = {}
    for c in e.checks:
        counts[c.status] = counts.get(c.status, 0) + 1
    return {'status': e.status, 'counts': counts, 'max_dc': e.max_dc, 'stale_geometry': list(e.stale), 'issues': list(e.issues),
            'failed_checks': [{'key': c.key, 'label': c.label, 'status': c.status, 'ratio': c.ratio} for c in e.checks if 'FAIL' in str(c.status)]}


def _check_changes(before, after) -> list[dict]:
    b = {c.key: c for c in before.checks}
    a = {c.key: c for c in after.checks}
    out = []
    for key in list(dict.fromkeys(list(b) + list(a))):
        cb, ca = b.get(key), a.get(key)
        if cb is None or ca is None:
            out.append({'key': key, 'label': (cb or ca).label, 'before_status': cb.status if cb else None, 'after_status': ca.status if ca else None,
                        'before_ratio': cb.ratio if cb else None, 'after_ratio': ca.ratio if ca else None, 'note': 'check added or removed'})
        elif cb.status != ca.status or cb.ratio != ca.ratio:
            out.append({'key': key, 'label': ca.label, 'before_status': cb.status, 'after_status': ca.status, 'before_ratio': cb.ratio, 'after_ratio': ca.ratio})
    return out


def readme(s: dict, label: str, receipt: dict, decision: str) -> str:
    from urllib.parse import quote
    r = receipt['run']
    today = receipt['date']
    day = f'{int(today[-2:])} {date.fromisoformat(today).strftime("%B")}'
    files = r['files']
    link = lambda key: quote(Path(files[key]['path']).name)
    changed = ', '.join(f'{k} {v["before"]:g} to {v["after"]:g}' for k, v in r['inputs_changed'].items()) or 'none'
    after = r['after']
    fails = after['counts'].get('FAIL', 0)
    pending = sum(n for st, n in after['counts'].items() if 'PENDING' in st)
    return f"""# {s['label']} current cap design

The [{day} report]({link('report')}) and [dated JSON]({link('dated_case')}) are selected under {decision}.
`selected_case.json` is byte-identical to the dated JSON.

`scripts/apply_fbmp_to_cap_case.py` loaded the previously selected case, applied the registered
`{r['xml']['filename']}` ({s['xml']}, SHA-256 `{r['xml']['sha256']}`) with the cap package's XML importer,
recalculated and wrote the report. Geometry, reinforcement, covers and design factors are unchanged
(geometry and reinforcement preserved: {r['geometry_and_reinforcement_preserved']}). Imported force envelopes that changed: {changed}.
Analysis provenance is refreshed; the report's embedded case equals the saved JSON and its analysis SHA-256 equals the registered XML.

Check statuses: {len(r['check_changes'])} register entries changed ratio or status ({r['status_changes']} status changes).
{fails} FAIL entries (including the aggregate summary) and {pending} pending/conditional entries remain.
See the report's complete check register; source selection does not close those findings.

The previous selected case is [archived]({quote(r['archived']['path'].split('/' + s['folder'] + '/', 1)[1])}).
Earlier reports remain as historical snapshots. Calculation, source and preservation checks are in the
[receipt](../../coherence/evidence/{receipt['date']}-cap-rerun/source_receipt.json).
"""


def run(support: str, label: str, decision: str, authorization: str) -> dict:
    from pier_cap.calculation_report import write_calculation_report
    from pier_cap.fbmp import import_fbmp_xml
    from pier_cap.io import load_case, write_case
    from pier_cap.model import evaluate, upgrade_case, validate_case
    from scripts.export_project_cap_reports import embedded_case, schematic_problems
    from scripts.register_update import read_rows

    s = SUPPORTS[support]
    register = read_rows()
    folder = CAP_DESIGN / s['folder']
    selected = folder / 'selected_case.json'
    saved_bytes = selected.read_bytes()
    saved = json.loads(saved_bytes.decode('utf-8-sig'))
    case = load_case(selected)
    if case != saved:
        raise ValueError(f'{rel(selected)} changes when loaded by the current package.')
    xml_row = register[s['xml']]
    xml_path = ROOT / xml_row['path']
    xml = xml_path.read_bytes()
    if sha256(xml) != xml_row['sha256']:
        raise ValueError(f'{rel(xml_path)} does not carry the registered {s["xml"]} SHA-256; register the export first.')
    before = evaluate(deepcopy(case))
    proposed = import_fbmp_xml(xml, base=case, filename=xml_path.name)
    proposed = upgrade_case(proposed)
    validate_case(proposed)
    after = evaluate(proposed)
    audit = proposed['analysis']['xml_audit']
    if audit['sha256'] != xml_row['sha256']:
        raise ValueError('The proposed case does not record the registered XML SHA-256.')
    inputs_changed = {k: {'before': case['inputs'][k], 'after': proposed['inputs'][k]} for k in proposed['inputs']
                      if k in case['inputs'] and case['inputs'][k] != proposed['inputs'][k]}
    other_changed = sorted(k for k in inputs_changed if k not in FORCE_INPUTS)
    preserved = not other_changed and all(case.get(k) == proposed.get(k) for k in ('transverse_detail', 'added_bar_layout', 'end_grid', 'screening', 'fdot', 'lrfd'))
    changes = _check_changes(before, after)

    today = f'{YEAR}-{int(label.split("-")[0]):02d}-{int(label.split("-")[1]):02d}'
    archive = folder / 'archive' / f'{today}-before-fbmp-rerun' / 'selected_case.json'
    if archive.exists():
        raise FileExistsError(f'{rel(archive)} already exists; choose another date or clear the archive folder.')
    archive.parent.mkdir(parents=True)
    shutil.move(str(selected), str(archive))
    if sha256(archive.read_bytes()) != sha256(saved_bytes):
        raise ValueError('Archived case bytes differ from the previous selected case.')
    dated = folder / f'{s["title"]} {label}.json'
    report = folder / f'{s["title"]} {label}.html'
    for p in (dated, report):
        if p.exists():
            raise FileExistsError(f'{rel(p)} already exists.')
    write_case(proposed, selected)
    write_case(proposed, dated)
    if selected.read_bytes() != dated.read_bytes():
        raise ValueError('selected_case.json and the dated JSON differ.')
    reloaded = load_case(selected)
    if reloaded != json.loads(selected.read_bytes().decode('utf-8-sig')):
        raise ValueError('The written case changes when reloaded.')
    write_calculation_report(reloaded, report)
    markup = report.read_text(encoding='utf-8')
    problems = schematic_problems(markup)
    if problems:
        raise ValueError('Report schematics: ' + '; '.join(problems))
    if embedded_case(markup) != json.loads(selected.read_bytes().decode('utf-8-sig')):
        raise ValueError('The report does not embed the saved case.')
    rerun = evaluate(reloaded)
    if [(c.key, c.status, c.ratio) for c in rerun.checks] != [(c.key, c.status, c.ratio) for c in after.checks]:
        raise ValueError('The reloaded case evaluates differently from the applied case.')

    files = {'selected_case': selected, 'dated_case': dated, 'report': report}
    receipt = {
        'date': today, 'decision': decision, 'authorization': authorization,
        'workflow': ('scripts/apply_fbmp_to_cap_case.py: pier_cap.io.load_case on the selected case, pier_cap.fbmp.import_fbmp_xml with the registered '
                     'export as base-preserving import (the notebook XMLImportPanel reader), pier_cap.model.evaluate before and after, pier_cap.io.write_case, '
                     'pier_cap.calculation_report.write_calculation_report. No steel search or manual input change.'),
        'support': s['label'],
        'run': {
            'prefix': s['case'].split('-')[0], 'folder': s['folder'], 'title': s['title'],
            'previous_case_sha256': sha256(saved_bytes), 'archived': {'path': rel(archive), 'sha256': sha256(archive.read_bytes())},
            'xml': {'source_id': s['xml'], 'path': rel(xml_path), 'filename': xml_path.name, 'sha256': sha256(xml), 'bytes': len(xml)},
            'files': {k: {'path': rel(p), 'sha256': sha256(p.read_bytes()), 'bytes': p.stat().st_size} for k, p in files.items()},
            'case_name': proposed.get('name'), 'analysis_id': proposed['analysis'].get('id'),
            'inputs_changed': inputs_changed, 'non_force_inputs_changed': other_changed, 'geometry_and_reinforcement_preserved': preserved,
            'before': _summary(before), 'after': _summary(after), 'check_changes': changes,
            'status_changes': sum(1 for c in changes if c['before_status'] != c['after_status']),
            'exported_checks_match_reloaded_evaluation': True,
        },
        'register_rows': [s['case'], s['report']],
        'limitations': ('Cap package rerun and export only. The analysis export was not re-solved here; existing detailing failures, pending checks, '
                        'tracker rows and engineering dispositions are unchanged. Selection is not engineering acceptance.'),
    }
    folder_evidence = EVIDENCE / f'{today}-cap-rerun'
    folder_evidence.mkdir(parents=True, exist_ok=True)
    (folder_evidence / 'source_receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    (folder / 'README.md').write_text(readme(s, label, receipt, decision), encoding='utf-8', newline='\n')
    return receipt


def register(support: str, label: str, note: str) -> dict:
    from scripts.register_update import read_rows, update_rows
    s = SUPPORTS[support]
    today = f'{YEAR}-{int(label.split("-")[0]):02d}-{int(label.split("-")[1]):02d}'
    receipt = json.loads((EVIDENCE / f'{today}-cap-rerun' / 'source_receipt.json').read_text(encoding='utf-8'))
    files = receipt['run']['files']
    rows = read_rows()
    for key, sid in (('selected_case', s['case']), ('report', s['report'])):
        actual = sha256((ROOT / files[key]['path']).read_bytes())
        if actual != files[key]['sha256']:
            raise ValueError(f'{files[key]["path"]} changed since the receipt was written.')
    origin = f'Cap package rerun with the registered {s["xml"]} export (scripts/apply_fbmp_to_cap_case.py), {int(today[-2:])} {date.fromisoformat(today).strftime("%B %Y")}'
    updates = {
        s['case']: {'sha256': files['selected_case']['sha256'], 'registered_on': today, 'origin': origin,
                    'notes': f'{note} Dated JSON copy: {files["dated_case"]["path"]}.'},
        s['report']: {'path': files['report']['path'], 'sha256': files['report']['sha256'], 'registered_on': today, 'origin': origin, 'notes': note},
    }
    if rows[s['case']]['depends_on'] != s['xml']:
        updates[s['case']]['depends_on'] = s['xml']
    return update_rows(updates, prepend_notes=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--support', required=True, choices=sorted(SUPPORTS))
    parser.add_argument('--date', required=True, help='m-d suffix for the new file names, for example 10-21')
    parser.add_argument('--decision', required=True, help='decision id recorded in the receipt, for example D-073')
    parser.add_argument('--authorization', default='', help='the user request that authorizes the rerun (quoted)')
    parser.add_argument('--register', action='store_true', help='update the case and report register rows from the receipt instead of rerunning')
    parser.add_argument('--note', default='', help='with --register: the disposition text placed in front of the row notes')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    if args.register:
        if not args.note:
            parser.error('--note is required with --register')
        for sid, row in register(args.support, args.date, args.note).items():
            print(f'Updated {sid}: {row["path"]} {row["sha256"][:12]}')
        return 0
    receipt = run(args.support, args.date, args.decision, args.authorization)
    r = receipt['run']
    for key, info in r['files'].items():
        print(f'Wrote {info["path"]} ({info["bytes"]:,} bytes)')
    print(f'Archived previous case to {r["archived"]["path"]}')
    print(f'Inputs changed: {json.dumps(r["inputs_changed"])}')
    print(f'Geometry and reinforcement preserved: {r["geometry_and_reinforcement_preserved"]}')
    print(f'Check changes: {len(r["check_changes"])} ({r["status_changes"]} status changes); after: {r["after"]["status"]}')
    print(f'Wrote project_current/coherence/evidence/{receipt["date"]}-cap-rerun/source_receipt.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
