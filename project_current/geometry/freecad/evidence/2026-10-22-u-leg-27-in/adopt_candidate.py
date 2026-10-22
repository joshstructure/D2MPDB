"""Install the verified 27-in U leg candidate and record its bounded adoption (D-085).

Runs with the project .venv Python (no FreeCAD), after the D-079 job
(evidence/2026-10-22-ring-plate-half-inch/adopt_candidate.py). Reads the headless
build record, backs up the current model, writes the candidate bytes in place, and
records the revision in the FreeCAD README, update report, API notes, manifest,
decisions and source register. The assumptions register is re-judged by hand.
"""
from pathlib import Path
import json, re, hashlib, shutil, zipfile, os, sys
ROOT = Path('C:/github/D2MPDB'); MAIN = ROOT / 'project_current/geometry/freecad'
OUT = ROOT / '.validation/pier-wall-u-leg'; EVID = MAIN / 'evidence/2026-10-22-u-leg-27-in'
sys.path.insert(0, str(ROOT))
from scripts.register_update import update_rows, read_rows  # noqa: E402


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p, v): p.write_text(json.dumps(v, indent=2) + '\n', encoding='utf-8', newline='\n')


def prepend(p, text, heading=False):
    b = p.read_bytes(); nl = b'\r\n' if b'\r\n' in b else b'\n'; addition = text.replace('\n', nl.decode()).encode()
    if heading:
        first, rest = b.split(nl, 1); b = first + nl + nl + addition + rest.lstrip(b'\r\n')
    else: b = addition + nl + b
    p.write_bytes(b)


qa = json.loads((OUT / 'build.json').read_text()); snapshot = json.loads((OUT / 'case-snapshot.json').read_text())
assert qa['status'] == 'VERIFIED' and qa['cold_reopen'] and qa['native_edit_restore'] and qa['ordinary_native_recompute']
assert qa['validation']['status'] == 'PASS' and qa['cold_reopen_validation']['status'] == 'PASS'
assert qa['file_preservation']['status'] == 'PASS' and qa['snapshot_sha256'] == snapshot['sha256']
manifest = json.loads((MAIN / 'manifest.json').read_text()); model = MAIN / manifest['model']['path']
assert sha(model) == qa['source_sha256'] == manifest['model']['sha256']
assert sha(qa['candidate']) == qa['candidate_sha256']
assert not (EVID / 'adoption-summary.json').exists(), 'Inspect completed adoption before retry'
for p, h in manifest['runtime_files'].items(): assert sha(MAIN / p) == h, p
calc = ROOT / 'project_current/pier_wall/selected_case.json'; calc_hash = sha(calc); assert calc_hash == snapshot['sha256']
tracker = ROOT / 'project_current/coherence/Coherence_Tracker.xlsx'; tracker_hash = sha(tracker)
journal = ROOT / 'journal/D2_I95_Project_Journal.bpad'; journal_hash = sha(journal)
decision = ROOT / 'project_current/decisions.md'; decbytes = decision.read_bytes()
assert max(map(int, re.findall(rb'\| D-(\d+) \|', decbytes))) == 84
register = ROOT / 'project_current/source_register.csv'
tracked = [MAIN / 'manifest.json', MAIN / 'README.md', MAIN / 'runtime/API.md', MAIN / 'Open_Current_Bridge.FCMacro',
           MAIN / 'evidence/Model-update-report.txt', register, decision]
guards = {p: sha(p) for p in tracked}
backup = MAIN / 'archive/B4-before-u-leg-27-in-20261022.FCStd'
records = MAIN / 'archive/B4-before-u-leg-27-in-record-20261022.zip'
if backup.exists(): assert sha(backup) == qa['source_sha256']
else: shutil.copy2(model, backup)
if not records.exists():
    with zipfile.ZipFile(records, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in tracked: z.write(p, p.relative_to(ROOT).as_posix())
        for rel in manifest['runtime_files']: z.write(MAIN / rel, rel)
EVID.mkdir(parents=True, exist_ok=True)
for src, dst in [(OUT / 'build.json', 'geometry-verification.json'), (OUT / 'case-snapshot.json', 'calculation-snapshot.json'),
                 (OUT / 'build_u_leg.py', 'build_candidate.py'), (OUT / 'make_snapshot.py', 'make_snapshot.py'), (Path(__file__), 'adopt_candidate.py')]:
    shutil.copy2(src, EVID / dst)
shutil.copy2(calc, EVID / 'selected-case-at-transfer.json')
assert all(sha(p) == h for p, h in guards.items())
candidate_bytes = Path(qa['candidate']).read_bytes(); old_bytes = backup.read_bytes()
assert sha(model) == qa['source_sha256'] and sha(backup) == qa['source_sha256']
try:
    with model.open('r+b') as f:
        f.write(candidate_bytes); f.truncate(); f.flush(); os.fsync(f.fileno())
    assert sha(model) == qa['candidate_sha256']
except Exception:
    with model.open('r+b') as f: f.write(old_bytes); f.truncate(); f.flush(); os.fsync(f.fileno())
    assert sha(model) == qa['source_sha256']
    raise
installation = dict(status='INSTALLED', method='Guarded in-place binary write with exact-byte backup',
                    backup=str(backup), old_sha256=qa['source_sha256'], new_sha256=qa['candidate_sha256'])
v = qa['validation']; cv = qa['cold_reopen_validation']; pairs = next(c['pairs'] for c in v['checks'] if c['name'] == 'nominal_steel_intersections')
b, a = qa['before'], qa['after']
scope = ('Set the end U return legs of the pier wall reinforcement in the CAD model to 27 in (2 ft 3 in; 72 in under D-076), '
         'matching the selected D-084 calculation case (LRFD 10th edition 5.10.8.2.1 development, 26-in Class B lap).')
summary = (f"Live input ULeg 27 in; the controller regenerated the wall steel: the 38 end U returns (5G3) keep their bends, faces and levels and "
           f"lose 45 in from each straight leg (bar length {b['u_returns']['PierWallSteelE1U01']['length_in']:.1f} in to "
           f"{a['u_returns']['PierWallSteelE1U01']['length_in']:.1f} in), the 86 face and end-face bars, their SDM marks (D-083), the twenty "
           f"1/2-in ring plates, the wall, the piles and all {qa['objects'] - len(qa['changed_objects'])} unrelated objects are unchanged. "
           f"Nominal reinforcement {a['steel_weight_lb']:.1f} lb ({b['steel_weight_lb']:.1f} lb before). The immutable case snapshot on "
           f"PierWallSteelInputs now names the D-084 case ({snapshot['sha256'][:8]}; only u_leg_in differs from the D-078 snapshot; the "
           f"RING-GRID failure unchanged).")
limits = ('The legs were produced by the ordinary native regenerate of the ULeg input (the user workflow); native edit round trip, file-level '
          'record preservation and cold reopen verified. RING-GRID and all source scope limitations remain open without rejudgment; U bends and '
          'contact lap routing remain CAD detailing assumptions; weld solids are not modeled; drawing exports follow under the substructure DXF '
          'generator; fabrication and engineering acceptance remain pending. Existing bearing-fit and other project findings remain. No '
          'calculation, journal or tracker changes in this step.')
adoption = dict(status='ADOPTED_CAD_U_LEG_27_IN_RING_GRID_TOLERANCE_REMAINS_OPEN', decision='D-085', date='2026-10-22',
                scope=scope, summary=summary, limitations=limits, model_sha256=sha(model), previous_model_sha256=qa['source_sha256'],
                objects=qa['objects'], changed_objects=qa['changed_objects'], protected_existing_objects=qa['protected_objects'],
                checks_passed=len(v['checks']), cold_reopen_checks_passed=len(cv['checks']), pairs_checked=pairs,
                native_edit_restore=True, ordinary_native_recompute=True, cold_reopen=True, file_preservation=qa['file_preservation'],
                u_leg_in=dict(before=b['u_leg_in'], after=a['u_leg_in']),
                total_steel_length_in=dict(before=b['total_steel_length_in'], after=a['total_steel_length_in']),
                steel_weight_lb=dict(before=b['steel_weight_lb'], after=a['steel_weight_lb']),
                bar_count=v['bar_count'], rings=v['rings'], minimum_bar_cover_in=v['minimum_bar_cover_in'],
                reinforcement_weight_lb=v['steel_weight_lb'],
                calculation_snapshot_sha256=snapshot['sha256'], previous_calculation_snapshot_sha256=manifest.get('current_update', {}).get('calculation_snapshot_sha256', ''),
                source_calculation_unchanged_by_this_task=True, journal_unchanged=True, tracker_unchanged=True, installation=installation)
dump(EVID / 'adoption-summary.json', adoption)
prepend(MAIN / 'README.md', '## D-085: 27-in end U return legs, 22 October 2026\n\n' + scope + ' ' + summary + '\n\n' +
        f'Native geometry/cover and {pairs:,} intersecting-box steel pairs pass with no positive overlaps ({len(v["checks"])} checks before saving, {len(cv["checks"])} after cold reopen). ' + limits +
        ' See [adoption](evidence/2026-10-22-u-leg-27-in/adoption-summary.json) and [verification](evidence/2026-10-22-u-leg-27-in/geometry-verification.json).\n\n', True)
prepend(MAIN / 'evidence/Model-update-report.txt', 'D-085 - 27-IN END U RETURN LEGS, 22 OCTOBER 2026\n\n' + scope + '\n\n' + summary + '\n\n' + limits + '\n\n' +
        f'{len(v["checks"])} checks PASS, {pairs} candidate pairs, zero positive steel overlaps. Native edit round trip, ordinary regenerate, cold reopen and {qa["protected_objects"]} protected existing objects verified. Nominal rebar {a["steel_weight_lb"]:.3f} lb ({b["steel_weight_lb"]:.3f} lb before).\n\nPREVIOUS UPDATES (historical)\n')
api = MAIN / 'runtime/API.md'; ab = api.read_bytes(); nl = b'\r\n' if b'\r\n' in ab else b'\n'
addition = ('\n\n## 27-in end U return legs (D-085)\n\n'
            'No controller change. `PierWallSteelInputs.ULeg` reads 27 in; `pier_wall_rings.regenerate(inputs)` rebuilt the wall steel, which changes the '
            '38 end U return paths and bars only (bends, faces and levels kept; the 72-in contact lap legs of D-076 answered a Class B lap computed '
            'without confinement credit; LRFD 10th edition 5.10.8.2.1 gives 26 in). `SourceCaseJSON`, `SourceCaseSHA256`, `SourceFailuresJSON`, '
            '`SourcePath` and `EngineeringStatus` name the D-084 case; the D-083 bar marks are kept. ' + limits + '\n')
api.write_bytes(ab + addition.replace('\n', nl.decode()).encode())
manifest['previous_update'] = manifest['current_update']
manifest['current_update'] = dict(date='2026-10-22', decision='D-085', scope=scope, summary='evidence/2026-10-22-u-leg-27-in/adoption-summary.json',
                                  previous_model_sha256=qa['source_sha256'], calculation_snapshot_sha256=snapshot['sha256'], follow_up=limits)
manifest['model'].update(sha256=sha(model), bytes=model.stat().st_size, objects=qa['objects'])
manifest['updated_on'] = '2026-10-22'
manifest['known_review_status'] = 'D-085: 27-in U legs PASS; source RING-GRID tolerance failure remains. ' + limits + ' Prior: ' + manifest['known_review_status']
manifest['runtime_changes'].append('D-085: no controller change; the U leg input set to the selected D-084 case (27 in) through the controller regenerate; provenance strings updated.')
for rel in ['runtime/API.md']: manifest['runtime_files'][rel] = sha(MAIN / rel)
for p in (backup, records): manifest['archive_files'][p.relative_to(MAIN).as_posix()] = sha(p)
for p in [*EVID.iterdir(), MAIN / 'evidence/Model-update-report.txt']: manifest['evidence_files'][p.relative_to(MAIN).as_posix()] = sha(p)
dump(MAIN / 'manifest.json', manifest)
nl = b'\r\n' if b'\r\n' in decbytes else b'\n'; anchor = nl + nl + b'The current journal'; assert anchor in decbytes
row = ('| D-085 | 2026-10-22 | Set the CAD model pier wall end U return legs to 27 in (2 ft 3 in), matching the selected D-084 case; D-076 had placed them at 72 in. | '
       'Follows the user\'s D-084 direction (tension development on LRFD 10th edition 5.10.8.2.1: the 72-in legs answered a 71-in Class B lap computed without confinement credit; the code lap is 26 in). '
       'The CAD model (CAD-MODEL) and the ring wall case (PIER-WALL-CASE) disagreed on the U leg since D-084; this closes that gap. '
       + summary + ' ' + limits + f' {len(v["checks"])} geometry/cover/link/spacing/intersection checks PASS before saving and {len(cv["checks"])} after cold reopen; '
       f'{qa["protected_objects"]} existing objects preserved. See [CAD adoption](geometry/freecad/evidence/2026-10-22-u-leg-27-in/adoption-summary.json). |')
decision.write_bytes(decbytes.replace(anchor, nl + row.encode() + anchor, 1))
note = 'D-085: ' + scope + ' ' + summary + ' ' + limits + ' Prior:'
rows = {sid: dict(sha256=sha(MAIN / 'manifest.json' if sid == 'CAD-RUNTIME' else MAIN / 'evidence/Model-update-report.txt') if sid != 'CAD-MODEL' else sha(model),
                  registered_on='2026-10-22', notes=note) for sid in ('CAD-MODEL', 'CAD-RUNTIME', 'CAD-REPORT')}
current = read_rows()
rows['CAD-MODEL']['scope'] = current['CAD-MODEL']['scope'] + '; D-085 27-in U return legs matching the D-084 case'
rows['CAD-MODEL']['status'] = 'Current - pier wall steel with SDM marks, 1/2-in rings and 27-in U legs; ring-grid tolerance and bearing fit unresolved'
update_rows(rows, prepend_notes=True)
assert sha(tracker) == tracker_hash and sha(calc) == calc_hash and sha(journal) == journal_hash
paths = sorted({p.relative_to(ROOT).as_posix() for p in [model, backup, records, *tracked, *EVID.iterdir()]})
dump(OUT / 'adoption.json', dict(status=adoption['status'], commit_paths=paths))
(OUT / 'commit-paths.txt').write_text('\n'.join(paths) + '\n')
print(json.dumps({k: v for k, v in adoption.items() if k not in ('file_preservation',)}, indent=2))
