"""T023: copy the final backwall journal edition into the registered component file (rerunnable) and verify it against the base."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal  # noqa: E402
from scripts.build_backwall_mathcad import notebook_revision  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402

NAME = 'EndBentBackwallDesign'
EDITION = ROOT / 'end_bent_walls' / 'bpad' / 'journal'
base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert list(mapping) == [f'report:{NAME}'], mapping
v = json.loads((EDITION / 'verification.json').read_text(encoding='utf-8'))[0]
assert v['report_name'] == NAME and v['status'] == '✓ All Checks Pass'
assert v['package_revision'] == notebook_revision(), 'the journal edition is for another package: rebuild it'
raw = (EDITION / f'{NAME}.xml').read_bytes()
data = raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw
assert hashlib.sha256(data).hexdigest() == v['fragment_sha256']
root = E.fromstring(data)
old = base.elements[f'report:{NAME}']
assert root.get('name') == NAME and root.get('title') == old.get('title') == 'C014 - End Bent 1 Backwall, Cheek Walls and Tie-Back Straps'
forms = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
assert forms(old) == forms(root), 'definitions changed'
cells = lambda el: Counter(e.get('formula') for e in el.iter() if e.tag in ('c', 'planecontainer', 'lineardim', 'plot') and e.get('formula'))
assert cells(old) == cells(root), 'value-cell formulas changed'
caches = lambda el: Counter((d.get('formula'), (d.findtext('expresult') or '').strip()) for d in el.iter('dynexp'))
assert caches(old) == caches(root), 'cached results changed'
texts = lambda el: Counter(' '.join(''.join(p.itertext()).split()) for p in el.iter('paragraph'))
diff_old, diff_new = texts(old) - texts(root), texts(root) - texts(old)
assert len(diff_old) == 1 and len(diff_new) == 1, (list(diff_old), list(diff_new))
assert 'calculation package' in next(iter(diff_old)) and 'calculation package' not in next(iter(diff_new))
assert not bs.SUBMISSION_FORBIDDEN.search(' '.join(t for _, t in bs.visible_text_elements(root)))
(TASK / 'components' / mapping[f'report:{NAME}']).write_bytes(data)
(TASK / 'verification.json').write_text(json.dumps({
    'task': 'T023', 'base_sha256': base.sha256, 'package_revision': v['package_revision'], 'fragment_sha256': v['fragment_sha256'],
    'definitions': sum(forms(root).values()), 'journal_references': v['journal_references'],
    'changed_paragraphs': {'removed': list(diff_old), 'added': list(diff_new)}, 'status': 'PASS',
    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}}, indent=2, ensure_ascii=False) + '\n',
    encoding='utf-8')
print(json.dumps({'task': 'T023', 'package_revision': v['package_revision'], 'fragment_sha256': v['fragment_sha256']}, indent=2))
