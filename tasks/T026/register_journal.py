"""T026: move the JOURNAL row of project_current/source_register.csv to the promoted T026 revision (idempotent)."""
from pathlib import Path
import csv
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
completed = json.loads((ROOT / 'workflow' / 'completed' / 'T026.json').read_text(encoding='utf-8'))
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['journal_sha256']
previous = completed['previous_sha256']
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
    assert row['sha256'] == previous, row['sha256']
    row['sha256'] = actual
    row['notes'] = ('T026 (20 October 2026): the pile calculations C011-C013 re-promoted with their journal edition tied to the case alone '
                    '(hidden provenance without the package revision); no value changed. ' + row['notes'])
    buf = io.StringIO(newline='')
    csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator='\r\n' if line.endswith('\r\n') else '\n').writerow([row[f] for f in fields])
    lines[i] = buf.getvalue()
    changed += 1
assert changed == 1
reg.write_bytes((b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + ''.join(lines).encode('utf-8'))
(TASK / 'adoption.json').write_text(json.dumps(dict(task='T026', date='2026-10-20', journal_sha256=actual, previous_sha256=previous), indent=2) + '\n', encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered'}))
