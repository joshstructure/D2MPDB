"""T039: after promotion, move the JOURNAL row of project_current/source_register.csv to the promoted revision (covers T038; idempotent)."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T037', 'T038', 'T039')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T039']['journal_sha256'], (actual, completed['T039']['journal_sha256'])
assert completed['T039']['previous_sha256'] == completed['T038']['journal_sha256']
assert completed['T038']['previous_sha256'] == completed['T037']['journal_sha256']
previous = completed['T037']['journal_sha256']                  # the revision the register holds
NOTE = ('T038-T039 / D-081 (22 October 2026): C018 Pier Cap Cheek Wall Design (report PierCheekWalls) added from the Pier Cheek Wall Design notebook '
        'package (pier_cheek_wall, starting case of D-080: the D-059/D-061 CAD walls and mats, the C001 wind values as live references through the '
        'coherence gate, the C002 drag coefficient; 183 definitions, 174 values compared with the notebook to 1e-9; live project stamp) and placed '
        'after C017; every numerical check passes, development and cover at their limits, one-mat convention pending; PedBridge index and '
        'DecisionLog entry; no existing value changed; FBMP not rerun; native recalculation, appearance and engineering reviews not performed. '
        'See tasks/T038/verification.json and tasks/T039/verification.json.')
row = read_rows()['JOURNAL']
if row['sha256'] == actual:
    print('JOURNAL row already registered')
    raise SystemExit(0)
assert row['sha256'] == previous, row['sha256']
status = row['status'].replace('calculations C001-C017 in order with project stamps', 'calculations C001-C018 in order with project stamps')
assert status != row['status'], row['status']
scope = row['scope'].replace('the cap, pile, end-bent backwall and pier-wall ring design calculations',
                             'the cap, pile, end-bent backwall, pier-wall ring and pier cap cheek wall design calculations')
assert scope != row['scope'], row['scope']
assert 'CHEEK-CASE' not in row['depends_on']
written = update_rows({'JOURNAL': {'sha256': actual, 'registered_on': '2026-10-22', 'status': status, 'scope': scope,
                                   'depends_on': row['depends_on'] + ';CHEEK-CASE;CHEEK-TOOL', 'notes': NOTE}}, prepend_notes=True)
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-081', tasks=['T038', 'T039'], date='2026-10-22', journal_sha256=actual,
                                                     previous_sha256=previous), indent=2) + '\n', encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered', 'row_status': written['JOURNAL']['status']}))
