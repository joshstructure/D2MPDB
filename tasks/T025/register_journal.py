"""T025: move the JOURNAL row of project_current/source_register.csv to the promoted T025 revision (covers T024; idempotent)."""
from pathlib import Path
import csv
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T024', 'T025')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T025']['journal_sha256'] and completed['T025']['previous_sha256'] == completed['T024']['journal_sha256']
previous = completed['T024']['previous_sha256']                 # the T023 revision the register holds
NOTE = ('D-067 / T024-T025 (20 October 2026): every calculation opens with the live project stamp in multiline cells (the pile designs '
        'C011-C013 through the journal edition of their generator; C001-C004, C006, C015, C016 converted from value cells); the modules '
        'are ordered basis first, then C001-C016 in numerical order (reference packets after their calculations), then quantities, '
        'decisions, notes, references and archives (registered order, tools/bpad_workflow.py prepare --order); the index lists the '
        'calculations the same way. Only Stamp_* definitions added; every other formula and cache unchanged; FBMP not rerun; native '
        'recalculation, appearance and engineering reviews not performed. See tasks/T024/verification.json and tasks/T025/verification.json. '
        'Historical basis: ')
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
    assert row['sha256'] == previous, row['sha256']        # the T023 revision the register held before T024/T025
    row.update(sha256=actual, status='Current - calculations C001-C016 in order with project stamps; D-065 as-cast override; final bearing fit unresolved')
    row['notes'] = NOTE + row['notes']
    buf = io.StringIO(newline='')
    csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator='\r\n' if line.endswith('\r\n') else '\n').writerow([row[f] for f in fields])
    lines[i] = buf.getvalue()
    changed += 1
assert changed == 1
after = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + ''.join(lines).encode('utf-8')
reg.write_bytes(after)
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-067', tasks=['T024', 'T025'], date='2026-10-20', journal_sha256=actual,
                                                     previous_sha256=previous), indent=2) + '\n', encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered'}))
