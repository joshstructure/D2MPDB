"""T030: replace report:PierWallRings with the rebuilt journal edition (captions only; formulas and caches unchanged). Rerunnable."""
import hashlib
import json
import re
import sys
from pathlib import Path

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402

NAME, TITLE = 'PierWallRings', 'C017 - Pier Wall, Annular Pile Rings'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def formulas(root):
    return sorted((d.get('formula'), (d.find('expresult').text if d.find('expresult') is not None else None)) for d in root.iter('dynexp'))


base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert set(mapping) == {f'report:{NAME}'}, sorted(mapping)
folder = ROOT / 'ring_wall' / 'bpad' / 'journal'
v = json.loads((folder / 'verification.json').read_text(encoding='utf-8'))[0]
data = strip_nl((folder / f'{NAME}.xml').read_bytes())
assert v['report_name'] == NAME and v['title'] == TITLE and sha(data) == v['fragment_sha256'], 'fragment differs from its verification record'
root = E.fromstring(data)
old = E.fromstring(base.part(f'report:{NAME}'))
assert root.get('name') == NAME == old.get('name') and root.get('title') == TITLE == old.get('title')
assert formulas(root) == formulas(old), 'definitions or caches differ from the promoted module'
for el, text in bs.visible_text_elements(root):
    m = bs.SUBMISSION_FORBIDDEN.search(text)
    assert not m, f'{NAME}: working language {m.group(0)!r}: {text[:100]}'
assert [s.get('name') for s in root.iter('section') if s.get('name') == bs.WORKING_NOTES] == [bs.WORKING_NOTES]
old_text = {t for _, t in bs.visible_text_elements(old)}
new_text = {t for _, t in bs.visible_text_elements(root)}
assert '(former basis)' in ' '.join(old_text) and 'ring moment basis (former basis)' not in ' '.join(new_text)
(TASK / 'components' / mapping[f'report:{NAME}']).write_bytes(data)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T030', 'base_sha256': base.sha256, 'components': {NAME: {
    'source': f'ring_wall/bpad/journal/{NAME}.xml', 'fragment_sha256': v['fragment_sha256'], 'definitions': len(formulas(root)),
    'formulas_and_caches_equal_promoted_module': True, 'changed_captions': sorted(new_text - old_text)[:40],
    'removed_captions': sorted(old_text - new_text)[:40]}}, 'status': 'PASS',
    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T030', 'bytes': len(data), 'sha256': sha(data)[:12], 'changed_captions': len(new_text - old_text)}))
