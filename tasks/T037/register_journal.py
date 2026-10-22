"""T037: after promotion, move the JOURNAL row of project_current/source_register.csv to the promoted revision (idempotent)."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T036', 'T037')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T037']['journal_sha256'], (actual, completed['T037']['journal_sha256'])
assert completed['T037']['previous_sha256'] == completed['T036']['journal_sha256']
previous = completed['T036']['journal_sha256']
NOTE = ('T037 / D-078 (22 October 2026): C017 Pier Wall, Annular Pile Rings regenerated from the second 22 October ring wall case with a 1/2-in ring plate '
        '(3/4 in before; the thinnest standard plate with every check at or under 0.95 of its limit is 7/16 in, set by the maximum fillet at the ring '
        'edge); wall, diameters, fillets, forces, rotation, moment, contact and bearing unchanged; 1 failed check (grid clearance) as before; PedBridge '
        'revision note; DecisionLog entry. The CAD rings (D-076) are 3/4 in until reconciled. Native recalculation, appearance and engineering reviews '
        'not performed. See tasks/T037/verification.json.')
row = read_rows()['JOURNAL']
if row['sha256'] == actual:
    print('JOURNAL row already registered')
    raise SystemExit(0)
assert row['sha256'] == previous, row['sha256']
status = row['status'].replace('pier wall on the CAD geometry (D-075)', 'pier wall on the CAD geometry (D-075) with 1/2-in ring plates (D-078)')
assert status != row['status'], row['status']
written = update_rows({'JOURNAL': {'sha256': actual, 'registered_on': '2026-10-22', 'status': status, 'notes': NOTE}}, prepend_notes=True)
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-078', task='T037', date='2026-10-22', journal_sha256=actual, previous_sha256=previous), indent=2) + '\n',
                                    encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered', 'row_status': written['JOURNAL']['status']}))
