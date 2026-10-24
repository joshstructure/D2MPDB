"""D-087: move the CHEEK-TOOL row to the rebuilt C018 notebook (idempotent). Only the embedded package changed (calc_common
input placement); the cheek wall calculation, its case and its report are unchanged, so CHEEK-REPORT/CHEEK-CASE keep their rows."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

GIT = next(Path.home().glob(r'AppData/Local/GitHubDesktop/app-*/resources/app/git/cmd/git.exe'))
PATH = 'Pier_Cheek_Wall_Design.ipynb'
BEFORE = '83c44b2'          # the last commit before the calc_common input-placement change
lf = lambda b: b.replace(b'\r\n', b'\n')
new = lf((ROOT / PATH).read_bytes())
old = lf(subprocess.run([str(GIT), '-C', str(ROOT), 'show', f'{BEFORE}:{PATH}'], capture_output=True, check=True).stdout)
row = read_rows()['CHEEK-TOOL']
actual = hashlib.sha256(new).hexdigest()
if row['sha256'] == actual:
    print('CHEEK-TOOL already registered')
    raise SystemExit(0)
assert row['sha256'] == hashlib.sha256(old).hexdigest(), 'CHEEK-TOOL row is not the pre-change notebook'
nb_old, nb_new = json.loads(old), json.loads(new)
assert [c['cell_type'] for c in nb_old['cells']] == [c['cell_type'] for c in nb_new['cells']]
changed = [(i, a, b) for i, (co, cn) in enumerate(zip(nb_old['cells'], nb_new['cells']))
           for a, b in zip(co['source'], cn['source']) if a != b]
assert changed and all(a.split('=')[0].strip() == b.split('=')[0].strip() in ('revision', 'PACKAGE') for _, a, b in changed), \
    [(i, a[:40], b[:40]) for i, a, b in changed]
NOTE = ('D-087 (23 October 2026): notebook rebuilt to embed the calc_common input-placement change (input groups match section titles '
        'without their number; sections.json extra_inputs); only the embedded package and its revision changed; the cheek wall '
        'calculation places its inputs exactly as before, so CHEEK-REPORT and CHEEK-CASE are unchanged.')
update_rows({'CHEEK-TOOL': {'sha256': actual, 'registered_on': '2026-10-23', 'notes': NOTE}}, prepend_notes=True)
print(json.dumps({'CHEEK-TOOL': actual, 'changed_lines': [(i, a.split('=')[0].strip()) for i, a, _ in changed]}))
