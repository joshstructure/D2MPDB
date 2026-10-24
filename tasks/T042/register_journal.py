"""T042: after promotion, move the JOURNAL row of project_current/source_register.csv to the promoted revision and append
decision D-087 to project_current/decisions.md (both idempotent; the decisions file keeps its own line endings)."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T041', 'T042')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T042']['journal_sha256'], (actual, completed['T042']['journal_sha256'])
assert completed['T042']['previous_sha256'] == completed['T041']['journal_sha256']
previous = completed['T041']['journal_sha256']

# --- decision row ---
DECISION = ('| D-087 | 2026-10-23 | List every input of the journal calculation packages under the section it belongs to: input groups match '
            'section titles without their number, and inputs no equation reads get a named home section (`extra_inputs` in sections.json); '
            'C001-C004, C015 and C016 are regenerated into the journal (T042). | User question and direction, 23 October 2026: "In my calc report '
            'C001 section 1.2 has nothing under it. Whats up with that", then "Fix it in calc_common/report.py so groups match section titles '
            'without the number prefix, then rebuild C001 and anything else affected through the rebuild chain", "Fix the inputs that never appear '
            'in the C004, C015 and C016 reports, then rebuild and commit" and "Register a journal task and promote the rebuilt C001-C004, C015 and '
            'C016 journal fragments into the project journal". The generator compared an input group ("Wind speed and exposure") with the numbered '
            'title ("1.2 Wind speed and exposure"), so no group ever matched and each input sat beside its first use; inputs read only by tables or '
            'other calculations (16 in C004, 1 in C015, 14 in C016) had no inputs box in the HTML report and stood in a closing reference list in '
            'Blockpad. Fixed in calc_common (commits 3809637 and dc19137; a test now fails when an input is missing from the report), every package '
            'rebuilt (notebooks, standalone and journal editions, report folders, C018). In the journal (T042) only the position of input '
            'definitions changes: each of the six modules keeps the formula and cached-value multisets and the visible text of the previous '
            'revision; PedBridge revision note and DecisionLog entry added. The JOURNAL row moves to the new hash, and the CHEEK-TOOL row to the '
            'rebuilt C018 notebook (embedded package only; C018 places its inputs as before). Not changed: values, checks, '
            'cases, C006, C017, C018 in the journal and the external analyses. Native recalculation, appearance and engineering reviews not '
            'performed. See tasks/T042/verification.json. |')
path = ROOT / 'project_current' / 'decisions.md'
raw = path.read_bytes().decode('utf-8')
nl = '\r\n' if '\r\n' in raw else '\n'
if '| D-087 |' not in raw:
    anchor = 'seat-planes/source_receipt.json). |' + nl
    assert raw.count(anchor) == 1 and '| D-086 |' in raw, 'decision anchor'
    raw = raw.replace(anchor, anchor + DECISION + nl)
    path.write_bytes(raw.encode('utf-8'))
    print('D-087 appended')

# --- JOURNAL row ---
NOTE = ('T042 / D-087 (23 October 2026): C001-C004, C015 and C016 regenerated with every input under its own section (groups match section '
        'titles without the number; inputs read only by tables or other calculations placed by sections.json); only the position of input '
        'definitions changed, formulas, cached values and visible text equal the previous revision; PedBridge revision note; DecisionLog entry. '
        'Native recalculation, appearance and engineering reviews not performed. See tasks/T042/verification.json.')
row = read_rows()['JOURNAL']
if row['sha256'] == actual:
    print('JOURNAL row already registered')
    raise SystemExit(0)
assert row['sha256'] == previous, row['sha256']
old = 'LRFD 10th edition development with 27-in U legs (D-084)'
assert old in row['status'], row['status']
status = row['status'].replace(old, old + '; inputs listed in their own sections (D-087)')
written = update_rows({'JOURNAL': {'sha256': actual, 'registered_on': '2026-10-23', 'status': status, 'notes': NOTE}}, prepend_notes=True)
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-087', task='T042', date='2026-10-23', journal_sha256=actual, previous_sha256=previous), indent=2) + '\n',
                                    encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered', 'row_status': written['JOURNAL']['status']}))
