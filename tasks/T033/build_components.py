"""T033: write the four registered component files (rerunnable, byte-surgical).

* CapDesignEndBentOne and CapDesignEndBentTwo: the committed journal editions (`cap_bpad/journal/<name>.xml`, written by
  scripts/build_cap_bpad.py --journal from the registered 10-20 reports), checked against their verification records and the
  base modules: every dynexp formula, cached result and canvas formula identical; only the hidden provenance paragraph differs.
* PedBridge: one revision paragraph before the T032 note. DecisionLog: one section appended inside the report.
"""
import csv
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

TNR = 'Times New Roman'
NAMES = {'CapDesignEndBentOne': ('EB-REPORT', 'End Bent 1 Cap Design 10-20.html'), 'CapDesignEndBentTwo': ('EB2-REPORT', 'End Bent 2 Cap Design 10-20.html')}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def once(text, old, label):
    found = text.count(old)
    assert found == 1, f'{label}: expected 1 occurrence, found {found}: {old[:90]!r}'


def nl_of(text):
    return '\r\n' if '\r\n' in text else '\n'


with (ROOT / 'project_current' / 'source_register.csv').open(newline='', encoding='utf-8-sig') as f:
    register = {r['source_id']: r for r in csv.DictReader(f)}
base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert set(mapping) == {'report:CapDesignEndBentOne', 'report:CapDesignEndBentTwo', 'report:PedBridge', 'report:DecisionLog'}, sorted(mapping)
out, record = {}, {}
dyn = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
cel = lambda el: Counter(e.get('formula') for e in el.iter() if e.tag in ('c', 'planecontainer', 'lineardim', 'plot') and e.get('formula'))
caches = lambda el: Counter((d.get('formula'), (d.findtext('expresult') or '').strip()) for d in el.iter('dynexp'))
texts = lambda el: Counter(' '.join(''.join(p.itertext()).split()) for p in el.iter('paragraph'))

verification = {r['report_name']: r for r in json.loads((ROOT / 'cap_bpad/journal/verification.json').read_text(encoding='utf-8'))['reports']}
for name, (report_id, report_file) in NAMES.items():
    v = verification[name]
    assert v['report_file'] == report_file and register[report_id]['path'].endswith(report_file), (name, v['report_file'], register[report_id]['path'])
    # status is the cap report's own verdict (the End Bent caps carry recorded detailing failures); the edition check is tool_comparisons
    assert v['status'] in ('✓ All Checks Pass', '⊗ There are FAILURES') and v['literals_kept'] == [] and v['tool_comparisons'] > 800, name
    data = strip_nl((ROOT / 'cap_bpad' / 'journal' / f'{name}.xml').read_bytes())
    assert sha(data) == v['fragment_sha256'], f'{name}: fragment differs from its verification record; rebuild the journal edition'
    root, old = E.fromstring(data), base.elements[f'report:{name}']
    assert root.get('name') == name and root.get('title') == old.get('title')
    assert dyn(old) == dyn(root) and caches(old) == caches(root) and cel(old) == cel(root), f'{name}: a definition, cache or canvas differs'
    removed, added = list((texts(old) - texts(root)).elements()), list((texts(root) - texts(old)).elements())
    assert len(removed) == len(added) == 1 and '10-19.html' in removed[0] and '10-20.html' in added[0], (name, removed, added)
    for el, text in bs.visible_text_elements(root):
        m = bs.SUBMISSION_FORBIDDEN.search(text)
        assert not m, f'{name}: working language {m.group(0)!r}: {text[:100]}'
    out[f'report:{name}'] = data
    record[name] = {'source': f'cap_bpad/journal/{name}.xml', 'fragment_sha256': v['fragment_sha256'], 'report_file': report_file,
                    'case_sha256': v['case_sha256'], 'definitions_unchanged': sum(dyn(root).values()), 'paragraph_removed': removed[0], 'paragraph_added': added[0]}

# PedBridge: revision note before the T032 note
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
anchor = ' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: 21 October 2026, pier modules follow the 21 October FBMP rerun (T032, D-073):'
once(text, anchor, 'PedBridge T032 revision paragraph')
REVISION_NOTE = ('Revision: 21 October 2026, C008 End Bent 1 Cap Design and C009 End Bent 2 Cap Design replaced by their regenerated journal editions (T033): the registered '
                 'End Bent cap reports are the 20 October re-exports from the unchanged cases (D-068, definition and citation cards), and the editions now name them; every '
                 'definition, cached value and canvas is identical to the prior modules. Native recalculation, appearance and engineering reviews not performed; no value changed.')
note = ' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
text = text.replace(anchor, note + nl + anchor)
E.fromstring(text.encode('utf-8'))
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + revision note'}

# DecisionLog: the entry
text = base.part('report:DecisionLog').decode('utf-8')
nl = nl_of(text)
DECISION_SECTION = 'EndBentCapEditions20261021'
DECISION_HEADING = '2026-10-21 - C008 and C009 editions follow the 20 October End Bent cap reports (T033)'
DECISION = ('Housekeeping after D-068 (20 October 2026): the End Bent 1 and End Bent 2 cap reports were re-exported from their unchanged cases with definition and citation '
            'cards and registered as the 10-20 reports, but the journal editions C008 and C009 still named the 10-19 reports. They are replaced by the regenerated editions '
            '(scripts/build_cap_bpad.py --journal) whose hidden provenance names the 10-20 reports; the same case and formula hashes; every definition, cached value and '
            'canvas unchanged. The pier edition C010 was brought to its 10-21 report by T032 (D-073). Native recalculation, appearance and engineering reviews not performed; '
            'no engineering value changed.')
tail = ' ' * 8 + '</section>' + nl + ' ' * 4 + '</report>'
assert text.endswith(tail), 'DecisionLog does not end with a section inside the report'
assert f'name="{DECISION_SECTION}"' not in text
entry = nl.join([' ' * 8 + f'<section name="{DECISION_SECTION}" capture="False" hide="false">',
                 ' ' * 12 + f'<heading level="1" keepwithnext="True">{DECISION_HEADING}</heading>',
                 ' ' * 12 + f'<paragraph fontfamily="{TNR}" fontsize="11" leftindent="0" spacingafter="7">{DECISION}</paragraph>',
                 ' ' * 8 + '</section>'])
text = text[:-len(' ' * 4 + '</report>') - len(nl)] + nl + entry + nl + ' ' * 4 + '</report>'
E.fromstring(text.encode('utf-8'))
out['report:DecisionLog'] = text.encode('utf-8')
record['DecisionLog'] = {'source': 'base.bpad + decision entry'}

for key in ('report:PedBridge', 'report:DecisionLog'):
    new, old = E.fromstring(out[key]), base.elements[key]
    assert dyn(old) == dyn(new) and caches(old) == caches(new) and cel(old) == cel(new), f'{key}: a definition, cache or canvas changed'
components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T033', 'base_sha256': base.sha256, 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T033', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
