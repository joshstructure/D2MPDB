"""D-082: re-judge the assumptions whose basis names the T039 journal against the T040 journal (C006 deleted; no value changed).

    .venv\\Scripts\\python.exe project_current\\coherence\\evidence\\2026-10-22-pier-wall-fins-sequestered\\rejudge_assumptions.py

The only journal change between the two revisions is task T040: module C006 (PierWallFins) deleted, its index entry removed
with a revision note, C017 replaced by its regenerated edition with identical definitions, caches and canvases, and a
decision-log entry (every other component byte-identical, verified by the workflow checks). No statement below depends on
the fin-plate module (no other module read a value from it), so each keeps its disposition and moves its JOURNAL basis hash,
with the re-judgement sentence appended to its statement (the pattern of the T037 and T039 re-judgements). Line-level
surgery on the hand-formatted register; idempotent: entries already on the new hash are left alone. The receipt beside
this script records what moved.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OLD, NEW = 'b582cce60ac3d36015c104401a64d066053ffecec159fa352dcd26f311d59b6f', '0c505b2c1db96828e4f637c321045b0a655e80aa2010ade8c6042c43be66c3ff'
SENTENCE = (' Re-judged 22 October 2026 against the T040 journal (C006 Pier Wall, Hairpins and Fin Plates withdrawn under D-082; C017 '
            'regenerated with identical values; every other module byte-identical to the T039 revision).')

path = ROOT / 'project_current' / 'coherence' / 'assumptions.json'
raw = path.read_bytes()
nl = '\r\n' if b'\r\n' in raw else '\n'
lines = raw.decode('utf-8').split(nl)
before = json.loads(raw.decode('utf-8'))
targets = {e['id'] for e in before['entries'] if e.get('basis', {}).get('JOURNAL') == OLD}
current, moved, statement_done = None, [], set()
for i, line in enumerate(lines):
    m = re.match(r'^\s*"id": "(A-\d{3})",$', line)
    if m:
        current = m.group(1)
        continue
    if current in targets and re.match(r'^\s*"statement": ".*",$', line):
        assert current not in statement_done and SENTENCE.strip() not in line, current
        lines[i] = line[:-2] + json.dumps(SENTENCE, ensure_ascii=False)[1:-1] + '",'
        statement_done.add(current)
    elif current in targets and f'"JOURNAL": "{OLD}"' in line:
        lines[i] = line.replace(OLD, NEW)
        moved.append(current)
assert set(moved) == targets == statement_done, (moved, targets, statement_done)
if moved:
    path.write_bytes(nl.join(lines).encode('utf-8'))
after = json.loads(path.read_bytes().decode('utf-8'))
for e_old, e_new in zip(before['entries'], after['entries']):
    if e_old['id'] in targets:
        assert e_new['basis']['JOURNAL'] == NEW and e_new['statement'] == e_old['statement'].rstrip() + SENTENCE
        assert {k: v for k, v in e_old.items() if k not in ('statement', 'basis')} == {k: v for k, v in e_new.items() if k not in ('statement', 'basis')}
    else:
        assert e_old == e_new, e_old['id']
receipt_path = HERE / 'source_receipt.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.is_file() else {'decision': 'D-082', 'date': '2026-10-22'}
receipt['assumptions_rejudged'] = {'from_journal': OLD, 'to_journal': NEW, 'entries': sorted(targets),
                                   'basis': 'The T040 journal change deletes module C006 and regenerates C017 with identical values; no statement depends on C006, dispositions unchanged.',
                                   'script': 'project_current/coherence/evidence/2026-10-22-pier-wall-fins-sequestered/rejudge_assumptions.py'}
receipt_path.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'moved': moved}))
