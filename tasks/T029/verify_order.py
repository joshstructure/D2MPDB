"""T029: the candidate holds exactly the base components' bytes, with PierWallRings directly after BearingDesign (rerunnable)."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal  # noqa: E402

BUILD = Path(sys.argv[1])
base = Journal.load(TASK / 'base.bpad')
cand = Journal.load(BUILD / 'candidate.bpad')
record = json.loads((TASK / 'order.json').read_text(encoding='utf-8'))
assert record['order'] is not None and record['writes'] == [] and record['adds'] == [] and record['deletes'] == []
assert sorted(base.order) == sorted(cand.order) == sorted(record['order'])
assert cand.order == record['order'], 'candidate order differs from the registered order'
changed = [k for k in base.order if base.part(k) != cand.part(k)]
assert not changed, f'component bytes changed: {changed}'
i = cand.order.index('report:BearingDesign')
assert cand.order[i + 1] == 'report:PierWallRings', cand.order[i:i + 3]
assert base.order[-1] == 'report:PierWallRings' and cand.order[-1] != 'report:PierWallRings'
modules = [k for k in cand.order if k.split(':', 1)[0] in ('report', 'spreadsheet', 'drawing')]
(TASK / 'verification.json').write_text(json.dumps({
    'task': 'T029', 'base_sha256': base.sha256, 'candidate_sha256': hashlib.sha256(cand.data).hexdigest(), 'components': len(cand.order),
    'moved': {'report:PierWallRings': {'from': base.order.index('report:PierWallRings'), 'to': i + 1, 'after': 'report:BearingDesign'}},
    'component_bytes_changed': changed, 'module_order': modules, 'status': 'PASS',
    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T029', 'status': 'PASS', 'modules_around': modules[modules.index('report:BearingDesign') - 1:modules.index('report:BearingDesign') + 3]}))
