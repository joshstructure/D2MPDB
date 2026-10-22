"""T035: replace C006 and C004 with their regenerated journal editions (provenance text only; rerunnable).

The editions in `<package>/bpad/journal/<Report>.xml` were built by scripts/build_journal_calc_bpads.py --journal against
the current (T034) journal through their coherence gates. Against the base modules every dynexp formula, cached result and
canvas or cell formula must be identical; only paragraph text may differ (the case name and the provenance sentence that
name the journal whose values the inputs equal).
"""
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

PACKAGES = {'PierWallFins': 'pier_wall_fins', 'SuperstructureUplift': 'superstructure_uplift'}
ACCEPTED = {'SuperstructureUplift': ('Task Work Order',)}
NEW_JOURNAL = '82e7d3e1246fbb0f9d61360b958b21777287e7efb9e8a6c4f3d3057b5ffb753e'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


dyn = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
cel = lambda el: Counter(e.get('formula') for e in el.iter() if e.tag in ('c', 'planecontainer', 'lineardim', 'plot') and e.get('formula'))
caches = lambda el: Counter((d.get('formula'), (d.findtext('expresult') or '').strip()) for d in el.iter('dynexp'))
texts = lambda el: Counter(' '.join(''.join(p.itertext()).split()) for p in el.iter('paragraph'))

base = Journal.load(TASK / 'base.bpad')
assert base.sha256 == NEW_JOURNAL, base.sha256
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert set(mapping) == {f'report:{n}' for n in PACKAGES}, sorted(mapping)
out, record = {}, {}
for name, package in PACKAGES.items():
    folder = ROOT / package / 'bpad' / 'journal'
    v = json.loads((folder / 'verification.json').read_text(encoding='utf-8'))[0]
    data = strip_nl((folder / f'{name}.xml').read_bytes())
    assert v['report_name'] == name and v['journal_file'] == 'journal/D2_I95_Project_Journal.bpad', (name, v['journal_file'])
    assert sha(data) == v['fragment_sha256'], f'{name}: fragment differs from its verification record; rebuild the journal edition'
    sources = json.loads((ROOT / package / 'data' / 'sources.json').read_text(encoding='utf-8'))
    assert sources['sources']['JOURNAL']['sha256'] == NEW_JOURNAL, name
    root, old = E.fromstring(data), base.elements[f'report:{name}']
    assert root.get('name') == name and root.get('title') == old.get('title'), (name, root.get('title'))
    assert dyn(old) == dyn(root), f'{name}: definitions differ'
    assert caches(old) == caches(root), f'{name}: cached results differ'
    assert cel(old) == cel(root), f'{name}: canvas or cell formulas differ'
    removed, added = list((texts(old) - texts(root)).elements()), list((texts(root) - texts(old)).elements())
    assert removed and added, (name, removed, added)
    # the case hash sentence moves with the case name; the provenance sentence names the new journal
    assert all('feb1bb316d08' in t or 'from the notebook case' in t for t in removed), (name, removed)
    assert all(NEW_JOURNAL[:12] in t or 'from the notebook case' in t for t in added), (name, added)
    assert any(NEW_JOURNAL[:12] in t for t in added) and len(removed) == len(added), (name, removed, added)
    for el, t in bs.visible_text_elements(root):
        m = bs.SUBMISSION_FORBIDDEN.search(t)
        assert not m or any(a in t for a in ACCEPTED.get(name, ())), f'{name}: working language {m.group(0)!r}: {t[:100]}'
    assert [s.get('name') for s in root.iter('section') if s.get('name') == bs.WORKING_NOTES] == [bs.WORKING_NOTES]
    out[f'report:{name}'] = data
    record[name] = {'source': f'{package}/bpad/journal/{name}.xml', 'fragment_sha256': v['fragment_sha256'], 'journal_references': v['journal_references'],
                    'status': v['status'], 'definitions_unchanged': sum(dyn(root).values()), 'caches_unchanged': True, 'canvases_unchanged': True,
                    'paragraphs_removed': removed, 'paragraphs_added': added}

components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T035', 'base_sha256': base.sha256, 'decision': 'D-075', 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T035', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
