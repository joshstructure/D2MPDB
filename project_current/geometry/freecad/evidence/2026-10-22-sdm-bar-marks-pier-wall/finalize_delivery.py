"""D-083 adoption: archive, replace the registered model, record evidence, decision, register,
assumptions and coherence views (as the D-042, D-060 and D-079 jobs).  Runs with the project
.venv Python (no FreeCAD)."""
from pathlib import Path
import json, hashlib, shutil, zipfile, csv, io, sys, re
OUT = Path(__file__).resolve().parent
REPO = Path('C:/github/D2MPDB'); BASE = REPO/'project_current/geometry/freecad'
MAIN = BASE/'B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd'
DECISION, DATE, TAG = 'D-083', '2026-10-22', 'sdm-bar-marks-pier-wall'
EVID = BASE/('evidence/%s-%s' % (DATE, TAG))
TRACKER = REPO/'project_current/coherence/Coherence_Tracker.xlsx'
JOURNAL = REPO/'journal/D2_I95_Project_Journal.bpad'
REGISTER = REPO/'substructure_drawings/output/bar_mark_register.csv'
ASSUMPTIONS = REPO/'project_current/coherence/assumptions.json'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, obj): p.write_bytes((json.dumps(obj, indent=2, ensure_ascii=False) + '\n').encode())
def write(p, text): p.write_bytes(text.encode())

native = json.loads((OUT/'native-update.json').read_text())
pres = json.loads((OUT/'preservation.json').read_text())
cold = json.loads((OUT/'cold-reopen.json').read_text())
assert native['status'] == pres['status'] == cold['status'] == 'PASS'
assert sha(OUT/'Delivery.FCStd') == pres['model_sha256'] == cold['model_sha256']
assert sha(MAIN) == pres['before_sha256'] == sha(OUT/'Before.FCStd') == native['before_sha256']
m = json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))
assert m['model']['sha256'] == pres['before_sha256']
dxf = json.loads((REPO/'substructure_drawings/output/manifest.json').read_text(encoding='utf-8'))
assert dxf['model_sha256'] == pres['before_sha256'] and dxf['version'] == '2.8.0'
for key in ['runtime_files', 'evidence_files', 'archive_files', 'extra_macros']:
    assert all(sha(BASE/rel) == h for rel, h in m[key].items()), key
tracker_hash, journal_hash = sha(TRACKER), sha(JOURNAL)
prior_review = json.loads((REPO/'project_current/coherence/machine_checks.json').read_text(encoding='utf-8'))
sys.path.insert(0, str(REPO/'tools')); sys.path.insert(0, str(REPO))
import project_coherence as coherence
from scripts.register_update import update_rows, read_rows
items = coherence.read_tracker(TRACKER)
assert items == prior_review['items']
decision = REPO/'project_current/decisions.md'
decbytes = decision.read_bytes()
assert ('| %s |' % DECISION).encode() not in decbytes
assert max(map(int, re.findall(rb'\| D-(\d+) \|', decbytes))) == 82
assert not EVID.exists(); EVID.mkdir()
archive = BASE/('archive/B4-before-%s-%s.FCStd' % (TAG, DATE.replace('-', '')))
record = BASE/('archive/B4-before-%s-record-%s.zip' % (TAG, DATE.replace('-', '')))
assert not archive.exists() and not record.exists()
shutil.copy2(OUT/'Before.FCStd', archive)
tracked = [BASE/'manifest.json', BASE/'README.md', BASE/'runtime/API.md', BASE/'evidence/Model-update-report.txt', decision,
           REPO/'project_current/source_register.csv', ASSUMPTIONS, REPO/'project_current/README.md']
with zipfile.ZipFile(record, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in tracked:
        z.write(p, p.relative_to(REPO).as_posix())
pending = MAIN.with_suffix('.sdm-marks-update.FCStd')
shutil.copy2(OUT/'Delivery.FCStd', pending); pending.replace(MAIN)
assert sha(MAIN) == cold['model_sha256']
for source, target in [(OUT/'native-update.json', 'native-update.json'), (OUT/'preservation.json', 'native-preservation.json'),
                       (OUT/'cold-reopen.json', 'cold-reopen.json'), (OUT/'mark-changes.json', 'mark-changes.json'),
                       (REGISTER, 'sdm-bar-marks.csv'), (OUT/'native_update.py', 'native_update.py'),
                       (OUT/'prepare_delivery.py', 'prepare_delivery.py'), (OUT/'verify_native.py', 'verify_native.py'),
                       (Path(__file__), 'finalize_delivery.py')]:
    shutil.copy2(source, EVID/target)
counts = {}
with REGISTER.open(encoding='utf-8') as f:
    for r in csv.DictReader(f):
        counts.setdefault(r['support'], {}).setdefault(r['mark'], 0)
        counts[r['support']][r['mark']] += 1
changes = json.loads((OUT/'mark-changes.json').read_text())
by_change = {}
for c in changes:
    key = '%s -> %s' % (c['old'][:4] + '*', c['new'])
    by_change[key] = by_change.get(key, 0) + 1
wall = cold['pier_wall_marks']
scope = ('Write the FDOT SDM 4.3 bar marks of the D-076 pier wall reinforcement into the Mark property of its 124 native '
         'rebars (controller identifiers PW-<id> to 5G1 for the 48 face and end-face verticals, 5G2 for the 38 horizontals '
         'and 5G3 for the 38 end U returns), into their schedule, and record on PierWallSteelInputs that the drawing marks '
         'are written; the pier uses G for the wall as the end bent and pier DXF (generator 2.8.0) lists it.')
limits = ('Naming only: no geometry, reinforcement, quantity, calculation input, journal or tracker change. The PW- identifiers '
          'remain the bar object names and labels; the controller gives any newly regenerated bar a PW- mark again, so rerun '
          'substructure_drawings/freecad_marks.py after a pier wall regeneration. RING-GRID and all source scope limitations '
          'remain open without rejudgment; U bends and contact lap routing remain CAD detailing assumptions; weld solids are '
          'not modeled; drawing exports, fabrication and engineering acceptance remain pending. Existing bearing-fit and other '
          'project findings remain.')
summary = dict(decision=DECISION, date=DATE, status='ADOPTED_IN_PROJECT_SOURCE',
    model_sha256=sha(MAIN), previous_model_sha256=pres['before_sha256'], scope=scope,
    convention='SDM January 2026 4.3.C-E and 4.3.10.B as D-042 and D-060. End bents: A cap longitudinal, B cap stirrups/hoops, '
               'C cap U-bars between piles, D backwall, E cheek walls, F pedestals. Pier: A, B, C as above, D cap end '
               'U-bars, E cheek walls (D-059/D-060), F pedestals, G pier wall (D-076).',
    mark_source='substructure_drawings/output/bar_mark_register.csv (copied here as sdm-bar-marks.csv), generated from model '
                '%s with the FDOT end bent and pier DXF (generator 2.8.0, sheets B4-9 to B4-11); drawings and model share one '
                'mapping.' % pres['before_sha256'][:8],
    marks_by_support=counts, pier_wall_marks=wall, mark_changes=by_change, mark_status=pres['mark_status'],
    changed=dict(mark_properties=pres['mark_values_changed'], schedule_cells=pres['schedule_cells_changed'],
                 schedule_sheets=pres['schedule_sheets_changed'], schedule_json_mark_fields=pres['schedule_json_marks_changed'],
                 mark_status_strings=1),
    unchanged='Every other bar mark (%d), the lug WWR wire designations (%d), labels, geometry, placements, expressions, '
              'dependencies, controllers, quantities, check statuses and all other property values; all view records and '
              'other archive members.' % (cold['bars_marked'] - pres['mark_values_changed'], cold['wwr_wire_marks_unchanged']),
    verification=cold['validation'],
    source_preservation=pres['method'],
    limitations=limits,
    regeneration_note='The pier_wall_rings controller gives a bar it creates the PW-<id> mark (existing bars keep their Mark '
                      'through a regeneration; the schedule is rewritten from the bars). After a regeneration, rebuild the DXF '
                      'snapshot and rerun substructure_drawings/freecad_marks.py; its MarkStatus string says when every wall '
                      'bar carries its SDM mark.',
    downstream_review='Naming only. The substructure DXF and model plan snapshots are re-extracted from this model so their '
                      'registers record the model marks and the bar list MODEL CHECK note about the PW- identifiers goes '
                      'silent. The D-076 follow-ups (RING-GRID tolerance, calculation reconciliation, drawing exports, '
                      'fabrication and engineering acceptance) remain open.',
    tracker_sha256=tracker_hash, tracker_disposition='Byte-identical; existing statuses, responses and outstanding findings retained.',
    journal_sha256=journal_hash, journal_disposition='Byte-identical; no journal change.',
    backups=[archive.relative_to(BASE).as_posix(), record.relative_to(BASE).as_posix()],
    job='CAD_AI/reports/%s-%s (native_update.py, prepare_delivery.py, verify_native.py, finalize_delivery.py; copied here)'
        % (TAG, DATE.replace('-', '')))
dump(EVID/'update-summary.json', summary)

# FreeCAD README
p = BASE/'README.md'; text = p.read_text(encoding='utf-8')
head = '# Current FreeCAD bridge model\n\n'
assert text.startswith(head)
intro = ('## %s: SDM bar marks for the pier wall, 22 October 2026\n\n'
         'The 124 D-076 pier wall bars carry their FDOT SDM 4.3 marks in their **Mark** property: 5G1 for the 48 face and '
         'end-face verticals, 5G2 for the 38 horizontals and 5G3 for the 38 end U returns (G names the pier wall; the '
         'PW-<id> controller identifiers remain the object names and labels). PierWallSteelSchedule follows, and '
         '`PierWallSteelInputs.MarkStatus` now reads "%s" in place of the D-076 "drawing SDM marks pending". The marks come '
         'from the bar-mark register of the generated [end bent and pier DXF](../../../substructure_drawings/README.md) '
         '(generator 2.8.0, which draws the pier wall on sheets B4-9 to B4-11). Geometry, quantities, controllers and saved '
         'view records are preserved; cold reopen verified (%d objects). See [%s evidence](evidence/%s-%s/update-summary.json). '
         '%s\n\n' % (DECISION, pres['mark_status']['new'], cold['objects'], DECISION, DATE, TAG, limits))
write(p, head + intro + text[len(head):])

# Decision row
row = ('| %s | %s | Write the SDM 4.3 bar marks of the D-076 pier wall reinforcement into the CAD model (CAD-MODEL): 5G1 verticals, '
       '5G2 horizontals, 5G3 end U returns on the 124 wall bars and their schedule; the PW- identifiers remain the object names. | '
       'Follows the D-076 note that the PW identifiers were CAD instance identifiers with the drawing SDM marks pending, and the '
       'D-042 / D-060 pattern that the drawings and the model carry one mapping. The FDOT DXF (generator 2.8.0, commit 66605e1) draws '
       'the pier wall steel on sheets B4-9 to B4-11 and assigns the G family (5G1 48 verticals, 5G2 38 horizontals, 5G3 38 end U '
       'returns); its bar-mark register, generated from the prior model (%s), is the source. 124 Mark properties, their 124 '
       'PierWallSteelSchedule cells and the PierWallSteelInputs MarkStatus string changed; every other property, all view records '
       'and archive members preserved; cold reopen verified (%d objects). Both DXF snapshots are re-extracted from this model, so the '
       'bar list MODEL CHECK note about the PW- identifiers goes silent. %s Prior model and source record archived. See '
       '[evidence](geometry/freecad/evidence/%s-%s/update-summary.json). |\n'
       % (DECISION, DATE, pres['before_sha256'][:8], cold['objects'], limits, DATE, TAG))
anchor = '\n\nThe current journal at setup'
text = decbytes.decode('utf-8'); assert anchor in text
write(decision, text.replace(anchor, '\n' + row + anchor, 1))

# Model update report
p = BASE/'evidence/Model-update-report.txt'
report_text = p.read_text(encoding='utf-8')
section = ('%s - SDM BAR MARKS FOR THE PIER WALL, 22 OCTOBER 2026\n\n' % DECISION + scope + '\n\n'
           + summary['verification'] + '\n\n' + limits + '\n\n' + summary['regeneration_note'] + '\n\n' + summary['downstream_review']
           + '\n\nEvidence: %s-%s/update-summary.json\n\n' % (DATE, TAG))
write(p, section + report_text)

# Runtime API notes (freecad_marks is the writer; no controller change)
api = BASE/'runtime/API.md'; ab = api.read_bytes(); nl = b'\r\n' if b'\r\n' in ab else b'\n'
addition = ('\n\n## SDM bar marks for the pier wall (%s)\n\n'
            'No controller change. The 124 `PierWallSteel*` rebars carry their SDM marks (5G1/5G2/5G3) in `Mark`, '
            '`PierWallSteelSchedule` column A follows, and `PierWallSteelInputs.MarkStatus` reads "%s". '
            '`substructure_drawings/freecad_marks.py` (apply/verify) is the writer, from the DXF bar-mark register; its '
            'SCHEDULE_PREFIXES now include `PierWallSteel`. `pier_wall_rings.sync` still gives a bar it creates the PW-<id> mark '
            'and leaves existing marks alone, so rerun freecad_marks after a regeneration. %s\n' % (DECISION, pres['mark_status']['new'], limits))
api.write_bytes(ab + addition.replace('\n', nl.decode()).encode())

# Manifest
m['model'].update(sha256=sha(MAIN), bytes=MAIN.stat().st_size, objects=cold['objects'])
m['previous_update'] = m['current_update']
m['current_update'] = dict(date=DATE, decision=DECISION, scope=scope,
                           summary='evidence/%s-%s/update-summary.json' % (DATE, TAG),
                           previous_model_sha256=pres['before_sha256'],
                           calculation_snapshot_sha256=m['previous_update'].get('calculation_snapshot_sha256'),
                           follow_up=limits, cold_reopen='evidence/%s-%s/cold-reopen.json' % (DATE, TAG))
m['updated_on'] = DATE
m['known_review_status'] = ('%s: pier wall SDM bar marks written (5G1/5G2/5G3); naming only. ' % DECISION) + limits + ' Prior: ' + m['known_review_status']
m['runtime_changes'].append('%s: no controller change; substructure_drawings/freecad_marks.py wrote the pier wall SDM marks, schedule cells and MarkStatus; API notes updated.' % DECISION)
m['runtime_files']['runtime/API.md'] = sha(BASE/'runtime/API.md')
for q in EVID.iterdir():
    m['evidence_files'][q.relative_to(BASE).as_posix()] = sha(q)
m['evidence_files']['evidence/Model-update-report.txt'] = sha(BASE/'evidence/Model-update-report.txt')
for q in [archive, record]:
    m['archive_files'][q.relative_to(BASE).as_posix()] = sha(q)
dump(BASE/'manifest.json', m)

# Source register rows (prepend the disposition to the notes, as D-079)
note = '%s: %s %s Prior:' % (DECISION, scope, limits)
current = read_rows()
rows = {'CAD-MODEL': dict(sha256=sha(MAIN), registered_on=DATE, notes=note,
                          scope=current['CAD-MODEL']['scope'] + '; %s pier wall SDM bar marks' % DECISION,
                          status='Current - pier wall steel with 1/2-in rings and SDM bar marks; ring-grid tolerance and bearing fit unresolved'),
        'CAD-RUNTIME': dict(sha256=sha(BASE/'manifest.json'), registered_on=DATE,
                            notes='%s records the pier wall SDM bar marks (freecad_marks.py is the writer); controller files unchanged, API notes updated. Prior:' % DECISION),
        'CAD-REPORT': dict(sha256=sha(BASE/'evidence/Model-update-report.txt'), registered_on=DATE,
                           notes='%s records the pier wall SDM bar marks. Prior:' % DECISION)}
update_rows(rows, prepend_notes=True)

# Assumptions carrying the CAD-MODEL basis: re-judged with a sentence and the new hash (line surgery keeps the hand layout)
old_hash, new_hash = pres['before_sha256'], sha(MAIN)
sentence = (' Re-judged 22 October 2026 against the %s CAD model (pier wall SDM bar marks 5G1/5G2/5G3 written on the 124 wall '
            'bars; naming only, no geometry, quantity or exposed face changed, so the judgment stands).' % DECISION)
atext = ASSUMPTIONS.read_text(encoding='utf-8')
starts = [mm.start() for mm in re.finditer(r'\n    \{\n      "id": "A-\d{3}"', atext)]
segments = [atext[:starts[0]]] + [atext[a:b] for a, b in zip(starts, starts[1:] + [len(atext)])]
rejudged = []
for i, seg in enumerate(segments[1:], 1):
    if '"CAD-MODEL": "%s"' % old_hash not in seg:
        continue
    aid = re.search(r'"id": "(A-\d{3})"', seg).group(1)
    assert seg.count(old_hash) == 1, aid
    seg = seg.replace('"CAD-MODEL": "%s"' % old_hash, '"CAD-MODEL": "%s"' % new_hash)
    sm = re.search(r'"statement": "(.*?)",\n', seg)
    assert sm and '"' not in sentence, aid
    segments[i] = seg[:sm.end(1)] + sentence + seg[sm.end(1):]
    rejudged.append(aid)
atext = ''.join(segments)
assert rejudged == ['A-002', 'A-007', 'A-010', 'A-012', 'A-013'], rejudged
assert old_hash not in atext
json.loads(atext)
ASSUMPTIONS.write_text(atext, encoding='utf-8', newline='\n')
summary['assumptions_rejudged'] = rejudged
dump(EVID/'update-summary.json', summary)
m['evidence_files']['evidence/%s-%s/update-summary.json' % (DATE, TAG)] = sha(EVID/'update-summary.json')
dump(BASE/'manifest.json', m)
update_rows({'CAD-RUNTIME': dict(sha256=sha(BASE/'manifest.json'))}, prepend_notes=False)

# Project README row
p = REPO/'project_current/README.md'; t = p.read_text(encoding='utf-8')
old = 'pier wall steel and 1/2-in annular pile rings (D-076/D-079); calculation/detailing reconciliation remains open |'
assert t.count(old) == 1
write(p, t.replace(old, 'pier wall steel and 1/2-in annular pile rings (D-076/D-079) carrying their SDM marks 5G1-5G3 (D-083); '
                        'calculation/detailing reconciliation remains open |'))

for key in ['runtime_files', 'evidence_files', 'archive_files', 'extra_macros']:
    assert all(sha(BASE/rel) == h for rel, h in m[key].items()), key
result = coherence.run(REPO)
selected = [c for c in result['checks'] if c['check_id'] in ['SOURCE:CAD-MODEL', 'SOURCE:CAD-RUNTIME', 'SOURCE:CAD-REPORT']]
assert len(selected) == 3 and all(c['status'] == 'MATCH' for c in selected), selected
assert result['items'] == items and sha(TRACKER) == tracker_hash and sha(JOURNAL) == journal_hash
assert result['assumption_counts']['stale'] <= prior_review['assumption_counts']['stale'], (result['assumption_counts'], prior_review['assumption_counts'])
coherence.write_report(REPO, result)
for n in ['latest_review.md', 'machine_checks.json', 'items_snapshot.csv']:
    q = REPO/'project_current/coherence'/n; q.write_bytes(q.read_bytes().replace(b'\r\n', b'\n'))
checkpoint = dict(status='SAVED_VERIFIED', decision=DECISION, model=str(MAIN), sha256=sha(MAIN), objects=cold['objects'],
                  assumptions_rejudged=rejudged, assumption_counts=result['assumption_counts'],
                  assumption_counts_before=prior_review['assumption_counts'],
                  coherence_outstanding=result['outstanding_count'], coherence_checks=result['check_counts'],
                  coherence_checks_before=prior_review['check_counts'],
                  commit_paths=sorted({p.relative_to(REPO).as_posix() for p in [MAIN, archive, record, *tracked, *EVID.iterdir()]}
                                      | {'project_current/coherence/latest_review.md', 'project_current/coherence/machine_checks.json',
                                         'project_current/coherence/items_snapshot.csv'}))
dump(OUT/'session-checkpoint.json', checkpoint)
print(json.dumps(checkpoint, indent=2))
