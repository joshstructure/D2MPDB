"""D-083 adoption, second half: finalize_delivery.py had installed the model and written the
evidence, README, decision, report, API notes, manifest and register rows, then stopped in the
assumptions re-judge (a bookkeeping slip, fixed in finalize_delivery.py; nothing was written).
This resumes from that step: assumptions, summary, manifest evidence hashes, project README row,
coherence views and the checkpoint."""
from pathlib import Path
import json, hashlib, shutil, sys, re
OUT = Path(__file__).resolve().parent
REPO = Path('C:/github/D2MPDB'); BASE = REPO/'project_current/geometry/freecad'
MAIN = BASE/'B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd'
DECISION, DATE, TAG = 'D-083', '2026-10-22', 'sdm-bar-marks-pier-wall'
EVID = BASE/('evidence/%s-%s' % (DATE, TAG))
TRACKER = REPO/'project_current/coherence/Coherence_Tracker.xlsx'
JOURNAL = REPO/'journal/D2_I95_Project_Journal.bpad'
ASSUMPTIONS = REPO/'project_current/coherence/assumptions.json'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, obj): p.write_bytes((json.dumps(obj, indent=2, ensure_ascii=False) + '\n').encode())
def write(p, text): p.write_bytes(text.encode())

pres = json.loads((OUT/'preservation.json').read_text())
cold = json.loads((OUT/'cold-reopen.json').read_text())
assert sha(MAIN) == cold['model_sha256'], 'The delivery is not installed'
m = json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))
assert m['model']['sha256'] == sha(MAIN) and m['current_update']['decision'] == DECISION
summary = json.loads((EVID/'update-summary.json').read_text(encoding='utf-8'))
assert summary['decision'] == DECISION and 'assumptions_rejudged' not in summary
tracker_hash, journal_hash = sha(TRACKER), sha(JOURNAL)
assert tracker_hash == summary['tracker_sha256'] and journal_hash == summary['journal_sha256']
prior_review = json.loads((REPO/'project_current/coherence/machine_checks.json').read_text(encoding='utf-8'))
sys.path.insert(0, str(REPO/'tools')); sys.path.insert(0, str(REPO))
import project_coherence as coherence
from scripts.register_update import update_rows, read_rows
items = coherence.read_tracker(TRACKER)
assert items == prior_review['items']
archive = BASE/('archive/B4-before-%s-%s.FCStd' % (TAG, DATE.replace('-', '')))
record = BASE/('archive/B4-before-%s-record-%s.zip' % (TAG, DATE.replace('-', '')))
assert sha(archive) == pres['before_sha256'] and record.exists()
tracked = [BASE/'manifest.json', BASE/'README.md', BASE/'runtime/API.md', BASE/'evidence/Model-update-report.txt',
           REPO/'project_current/decisions.md', REPO/'project_current/source_register.csv', ASSUMPTIONS, REPO/'project_current/README.md']

# Assumptions carrying the CAD-MODEL basis: re-judged with a sentence and the new hash (line surgery keeps the hand layout)
old_hash, new_hash = pres['before_sha256'], sha(MAIN)
sentence = (' Re-judged 22 October 2026 against the %s CAD model (pier wall SDM bar marks 5G1/5G2/5G3 written on the 124 wall '
            'bars; naming only, no geometry, quantity or exposed face changed, so the judgment stands).' % DECISION)
atext = ASSUMPTIONS.read_text(encoding='utf-8')
assert new_hash not in atext
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
parsed = json.loads(atext)
for e in parsed['entries']:
    if e['id'] in rejudged:
        assert e['basis']['CAD-MODEL'] == new_hash and e['statement'].endswith(sentence.strip())
ASSUMPTIONS.write_text(atext, encoding='utf-8', newline='\n')
summary['assumptions_rejudged'] = rejudged
dump(EVID/'update-summary.json', summary)

# The job scripts as run (finalize_delivery.py with the surgery fixed, and this resume)
for src in [OUT/'finalize_delivery.py', Path(__file__)]:
    shutil.copy2(src, EVID/src.name)
for q in EVID.iterdir():
    m['evidence_files'][q.relative_to(BASE).as_posix()] = sha(q)
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
rows = read_rows()
assert rows['CAD-MODEL']['sha256'] == sha(MAIN) and rows['CAD-RUNTIME']['sha256'] == sha(BASE/'manifest.json')
assert rows['CAD-REPORT']['sha256'] == sha(BASE/'evidence/Model-update-report.txt')
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
