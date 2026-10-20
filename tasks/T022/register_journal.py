"""T022: update the JOURNAL row of project_current/source_register.csv to the promoted revision (rerunnable, idempotent)."""
from pathlib import Path
import csv
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
verification = json.loads((TASK / 'verification.json').read_text(encoding='utf-8'))
completed = json.loads((ROOT / 'workflow' / 'completed' / 'T022.json').read_text(encoding='utf-8'))
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['journal_sha256'] == verification['candidate_sha256'], 'the journal is not the promoted T022 candidate'
NOTE = ('D-066 / T022 (20 October 2026): submission formatting of the design and analysis calculations. Modules numbered C007 '
        '(CapDesignBasis), C008-C010 (cap designs), C011-C013 (pile designs), C014 (EndBentBackwallDesign), C015 (MSEWallExclusion), '
        'C016 (BearingDesign); C005 stays retired. Working language (provenance, hashes, tool status, pending items, decision/task '
        'identifiers, superseded history) moved into hidden sections; table text in multiline cells; "distilled" removed from titles '
        'and visible text; live project stamp as result-only Stamp_* definitions. Every formula and cache value unchanged (result-only '
        'caches without the "= " prefix); FBMP not rerun; native recalculation, appearance and engineering reviews not performed. '
        'See tasks/T022/verification.json. Historical basis: ')
reg = ROOT / 'project_current' / 'source_register.csv'
raw = reg.read_bytes()
lines = raw.decode('utf-8-sig').splitlines(keepends=True)
fields = next(csv.reader([lines[0]]))
changed = 0
for i, line in enumerate(lines[1:], 1):
    row = dict(zip(fields, next(csv.reader([line]))))
    if row['source_id'] != 'JOURNAL':
        continue
    if row['sha256'] == actual:
        print('JOURNAL row already registered')
        raise SystemExit(0)
    assert row['sha256'] == verification['base_sha256'], row['sha256']
    row.update(sha256=actual, registered_on='2026-10-20', status='Current - submission formatting (C007-C016); D-065 as-cast override; final bearing fit unresolved',
               scope='Adopted project geometry, assumptions, decisions, live journal quantities and the cap, pile and end-bent backwall design calculations')
    row['notes'] = NOTE + row['notes']
    buf = io.StringIO(newline='')
    csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator='\r\n' if line.endswith('\r\n') else '\n').writerow([row[f] for f in fields])
    lines[i] = buf.getvalue()
    changed += 1
assert changed == 1
after = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + ''.join(lines).encode('utf-8')
before_rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
after_rows = list(csv.DictReader(io.StringIO(after.decode('utf-8-sig'))))
assert [r for r in before_rows if r['source_id'] != 'JOURNAL'] == [r for r in after_rows if r['source_id'] != 'JOURNAL']
reg.write_bytes(after)
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-066', task='T022', date='2026-10-20', journal_sha256=actual,
                                                     previous_sha256=verification['base_sha256'],
                                                     source_register_before_sha256=hashlib.sha256(raw).hexdigest(),
                                                     source_register_after_sha256=hashlib.sha256(after).hexdigest()), indent=2) + '\n',
                                     encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered'}))
