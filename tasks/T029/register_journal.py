"""T029: after promotion, move the JOURNAL row of project_current/source_register.csv to the promoted revision (covers T028; idempotent)."""
from pathlib import Path
import csv
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T027', 'T028', 'T029')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T029']['journal_sha256']
assert completed['T029']['previous_sha256'] == completed['T028']['journal_sha256']
assert completed['T028']['previous_sha256'] == completed['T027']['journal_sha256']
previous = completed['T027']['journal_sha256']                  # the revision the register holds
NOTE = ('T028-T029 / D-071 (21 October 2026): C017 Pier Wall, Annular Pile Rings (report PierWallRings) added from the Pier Wall Design notebook '
        'package (ring_wall, starting case; 673 values and 178 statuses evaluated independently to 1e-9; live project stamp; D-070 ring moment basis) '
        'and placed after C016; PedBridge index and DecisionLog entry; no existing value changed; FBMP not rerun; native recalculation, appearance '
        'and engineering reviews not performed. ')
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
    row.update(sha256=actual, status='Current - calculations C001-C017 in order with project stamps; D-065 as-cast override; final bearing fit unresolved',
               depends_on=row['depends_on'] + ';PIER-WALL-CASE;PIER-WALL-TOOL',
               scope=row['scope'].replace('the cap, pile and end-bent backwall design calculations', 'the cap, pile, end-bent backwall and pier-wall ring design calculations'))
    row['notes'] = NOTE + row['notes']
    buf = io.StringIO(newline='')
    csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator='\r\n' if line.endswith('\r\n') else '\n').writerow([row[f] for f in fields])
    lines[i] = buf.getvalue()
    changed += 1
assert changed == 1
reg.write_bytes((b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + ''.join(lines).encode('utf-8'))
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-071', tasks=['T028', 'T029'], date='2026-10-21', journal_sha256=actual,
                                                     previous_sha256=previous), indent=2) + '\n', encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered'}))
