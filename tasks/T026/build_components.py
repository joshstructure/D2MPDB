"""T026: copy the pile journal edition (provenance without the package revision) into the three registered component files."""
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
from scripts import bpad_sheet as bs  # noqa: E402
from pile_design.mathcad import package_revision  # noqa: E402

PILES = ['PileDesignEndBentOne', 'PileDesignEndBentTwo', 'PileDesignPier']
base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert {k.split(':', 1)[1] for k in mapping} == set(PILES)
verification = {v['report_name']: v for v in json.loads((ROOT / 'pile_bpad' / 'journal' / 'verification.json').read_text(encoding='utf-8'))}
dyn = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
cel = lambda el: Counter(e.get('formula') for e in el.iter() if e.tag in ('c', 'planecontainer', 'lineardim', 'plot') and e.get('formula'))
caches = lambda el: Counter((d.get('formula'), (d.findtext('expresult') or '').strip()) for d in el.iter('dynexp'))
texts = lambda el: Counter(' '.join(''.join(p.itertext()).split()) for p in el.iter('paragraph'))
record = {}
for name in PILES:
    v = verification[name]
    assert v['package_revision'] == package_revision() and v['status'] == '✓ All Checks Pass' and v['stamp'] == 'live'
    raw = (ROOT / 'pile_bpad' / 'journal' / f'{name}.xml').read_bytes()
    data = raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw
    assert hashlib.sha256(data).hexdigest() == v['fragment_sha256']
    root, old = E.fromstring(data), base.elements[f'report:{name}']
    assert root.get('title') == old.get('title') and dyn(old) == dyn(root) and cel(old) == cel(root) and caches(old) == caches(root), name
    removed, added = texts(old) - texts(root), texts(root) - texts(old)
    assert len(removed) == 1 and len(added) == 1 and '(package ' in next(iter(removed)) and '(package ' not in next(iter(added)), name
    assert not bs.SUBMISSION_FORBIDDEN.search(' '.join(t for _, t in bs.visible_text_elements(root)))
    (TASK / 'components' / mapping[f'report:{name}']).write_bytes(data)
    record[name] = {'fragment_sha256': v['fragment_sha256'], 'removed': list(removed), 'added': list(added)}
(TASK / 'verification.json').write_text(json.dumps({'task': 'T026', 'base_sha256': base.sha256, 'package_revision': package_revision(),
                                                    'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T026', 'package_revision': package_revision(), 'reports': list(record)}))
