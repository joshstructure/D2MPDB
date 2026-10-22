"""T041: after promotion, move the JOURNAL row of project_current/source_register.csv to the promoted revision (idempotent)."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T040', 'T041')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T041']['journal_sha256'], (actual, completed['T041']['journal_sha256'])
assert completed['T041']['previous_sha256'] == completed['T040']['journal_sha256']
previous = completed['T040']['journal_sha256']
NOTE = ('T041 / D-084 (22 October 2026): C017 Pier Wall, Annular Pile Rings regenerated from the third 22 October ring wall case: tension development '
        'on LRFD 10th edition 5.10.8.2.1 (basic length 2.4 db fy / sqrt(f\'c), location and confinement factors; two ledger values added) and 27-in '
        'end U return legs (72 in before, set by a 71-in lap from a basic length without confinement credit; the code lap is 26 in); wall, rings, '
        'fillets, forces, rotation, moment, contact and bearing unchanged; 1 failed check (grid clearance) as before; PedBridge revision note; '
        'DecisionLog entry. Native recalculation, appearance and engineering reviews not performed. See tasks/T041/verification.json.')
row = read_rows()['JOURNAL']
if row['sha256'] == actual:
    print('JOURNAL row already registered')
    raise SystemExit(0)
assert row['sha256'] == previous, row['sha256']
old = '1/2-in ring plates (D-078)'
assert old in row['status'], row['status']
status = row['status'].replace(old, old + ' and LRFD 10th edition development with 27-in U legs (D-084)')
written = update_rows({'JOURNAL': {'sha256': actual, 'registered_on': '2026-10-22', 'status': status, 'notes': NOTE}}, prepend_notes=True)
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-084', task='T041', date='2026-10-22', journal_sha256=actual, previous_sha256=previous), indent=2) + '\n',
                                    encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered', 'row_status': written['JOURNAL']['status']}))
