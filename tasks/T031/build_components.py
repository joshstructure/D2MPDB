"""T031: write the seven registered component files (rerunnable); the four CodeReferencesC00x modules are registered deletions.

* C001, C002, C003, C004: `<package>/bpad/journal/<Report>.xml` (scripts/build_journal_calc_bpads.py --journal), each checked
  against its verification record, against the base module (same report name and title; every name another journal module
  reads from it still defined; every inbound native link target from a surviving module still present), against the
  visible-text rule, and for the absence of any link into a CodeReferences module;
* PedBridge: the four "C00x - References" index paragraphs removed and one revision paragraph inserted before the latest one;
* CodeReferencesGeneral: every link into a deleted module becomes its plain text; the intro paragraph says where the excerpts live;
* DecisionLog: one section appended inside the report.
"""
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

PACKAGES = {'C001WindLoadOnPedBridgeSuperstructure': 'wind_superstructure', 'FenceWind': 'fence_wind', 'BridgeMovement': 'bridge_movement',
            'SuperstructureUplift': 'superstructure_uplift'}
DELETED = ['CodeReferencesC001', 'CodeReferencesC002', 'CodeReferencesC003', 'CodeReferencesC004']
ACCEPTED = {'FenceWind': ('Task Work Order',), 'SuperstructureUplift': ('Task Work Order',)}
TNR = 'Times New Roman'
REVISION_NOTE = ('Revision: 21 October 2026, code-reference modules retired (T031): the four modules C001 - References to C004 - References '
                 '(GetRefs code excerpts) are removed from the journal. Every provision cited by C001 to C004, C006, C015 and C016 now opens as a '
                 'citation card with the highlighted code excerpt in the calculation report of its notebook package; the journal keeps the '
                 'distilled calculation editions with their citations as plain text. The General References module keeps its own pages and its '
                 'index; entries that pointed into the retired modules are listed without links. No formula, cache, value or figure changed.')
DECISION_SECTION = 'CodeReferencesRetired20261021'
DECISION_HEADING = '2026-10-21 - C001 to C004 code-reference modules retired (T031)'
DECISION = ('User direction of 21 October 2026: the calculation reference modules of the journal are removed now that the calculation reports '
            'carry every citation as a card with the highlighted provision from the code PDFs; the journal keeps the distilled calculation '
            'editions. The modules C001 - References, C002 - References, C003 - References and C004 - References are deleted. The index entries in '
            'the Project Index that pointed at them are removed; the General References catalogue keeps every entry as plain text and its own '
            'pages 10, 11, 14 and 16 (read by Loads - General and Collision, Loads - Combinations and FBMP Entry - Pier). The journal editions of '
            'C001 to C004 are regenerated from their notebook packages with every citation link unwrapped to its text and the reference-packet '
            'pointer paragraphs dropped; definitions, caches, units, figures and the names other modules read are unchanged. The References '
            'folder and the registered reference PDFs stay beside the journal. Native recalculation, appearance and engineering reviews not '
            'performed; no engineering value changed.')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def once(text, old, label):
    found = text.count(old)
    assert found == 1, f'{label}: expected 1 occurrence, found {found}: {old[:90]!r}'


def nl_of(text):
    return '\r\n' if '\r\n' in text else '\n'


def inbound(base, name):
    """(names other components read from `name`, inbound link addresses) from the base journal, ignoring the deleted modules."""
    qual = re.compile(r'\b' + re.escape(name) + r'\.([A-Za-z_Ͱ-Ͽ][A-Za-z_0-9Ͱ-Ͽ]*)')
    names, links = set(), set()
    for key, el in base.elements.items():
        owner = key.split(':', 1)[1]
        if owner == name or owner in DELETED:
            continue
        for node in el.iter():
            for text in (node.get('formula'), node.text if node.tag == 'expbody' else None):
                if text:
                    names.update(m.group(1) for m in qual.finditer(text))
            if node.tag == 'link' and (node.get('address') or '').startswith('#' + name):
                links.add(node.get('address'))
    return names, links


def link_targets_present(root, name, links):
    ids = {n.get('id') for n in root.iter() if n.get('id')}
    sections = {s.get('name') for s in root.iter('section')}
    missing = []
    for addr in sorted(links):
        m = re.match(r'#' + re.escape(name) + r'(?:\.([A-Za-z0-9_]+))?(?:;([A-Za-z0-9_]+))?$', addr)
        if not m:
            missing.append(addr)
            continue
        section, pid = m.group(1), m.group(2)
        if section and section not in sections:
            missing.append(addr)
        elif pid and pid not in ids:
            missing.append(addr)
    return missing


def reference_links(root):
    return sorted({n.get('address') for n in root.iter('link') if (n.get('address') or '').startswith('#CodeReferences')})


base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert {k.split(':', 1)[1] for k in mapping} == set(PACKAGES) | set(DELETED) | {'PedBridge', 'CodeReferencesGeneral', 'DecisionLog'}, sorted(mapping)
out, record = {}, {}
for name in DELETED:                       # a deletion is an empty component fragment
    assert f'report:{name}' in base.elements, name
    out[f'report:{name}'] = b''
    record[name] = {'source': 'deleted', 'bytes_before': len(base.part(f'report:{name}'))}
for name, package in PACKAGES.items():
    folder = ROOT / package / 'bpad' / 'journal'
    v = json.loads((folder / 'verification.json').read_text(encoding='utf-8'))[0]
    raw = (folder / f'{name}.xml').read_bytes()
    data = strip_nl(raw)
    assert v['report_name'] == name and v['journal_file'] == 'journal/D2_I95_Project_Journal.bpad', name
    assert sha(data) == v['fragment_sha256'], f'{name}: fragment differs from its verification record; rebuild the journal edition'
    assert v['project_stamp']['owner'] == bs.PROJECT_INFO
    root = E.fromstring(data)
    old = base.elements[f'report:{name}']
    assert root.get('name') == name and root.get('title') == old.get('title'), (name, root.get('title'), old.get('title'))
    assert not reference_links(root), f'{name}: links into code-reference modules remain: {reference_links(root)[:5]}'
    defined = {bs.split_definition(d.get('formula'))[0] for d in root.iter('dynexp')} - {None}
    before = {bs.split_definition(d.get('formula'))[0] for d in old.iter('dynexp')} - {None}
    assert defined == before, f'{name}: definitions changed: {sorted(defined ^ before)[:8]}'
    names, links = inbound(base, name)
    missing_names = sorted(names - defined)
    assert not missing_names, f'{name}: names other modules read are no longer defined: {missing_names}'
    missing_links = link_targets_present(root, name, links)
    assert not missing_links, f'{name}: inbound link targets missing: {missing_links}'
    for el, text in bs.visible_text_elements(root):
        m = bs.SUBMISSION_FORBIDDEN.search(text)
        assert not m or any(a in text for a in ACCEPTED.get(name, ())), f'{name}: working language {m.group(0)!r}: {text[:100]}'
    out[f'report:{name}'] = data
    record[name] = {'source': f'{package}/bpad/journal/{name}.xml', 'fragment_sha256': v['fragment_sha256'], 'definitions': len(defined),
                    'journal_references': v['journal_references'], 'status': v['status'], 'names_read_by_other_modules': sorted(names),
                    'inbound_links_from_surviving_modules': len(links), 'reference_links_before': len(reference_links(old)), 'reference_links_after': 0}

# PedBridge: drop the four index paragraphs, add the revision note before the newest one
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
removed = 0
for name in DELETED:
    pattern = re.compile(r'[ \t]*<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">' + nl
                         + r'[ \t]*<link address="#' + name + r'">[^<]*</link>' + nl + r'[ \t]*</paragraph>' + nl)
    text, k = pattern.subn('', text)
    assert k == 1, f'PedBridge: index paragraph for {name}: {k} matches'
    removed += k
anchor_m = re.search(r'[ \t]*<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: ', text)
assert anchor_m, 'PedBridge: no revision paragraph to insert before'
indent = anchor_m.group(0)[:anchor_m.group(0).index('<')]
note = indent + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>' + nl
text = text[:anchor_m.start()] + note + text[anchor_m.start():]
assert '#CodeReferencesC00' not in text
E.fromstring(text.encode('utf-8'))
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + index paragraphs removed + revision note', 'index_entries_removed': removed}

# CodeReferencesGeneral: links into the deleted modules become plain text; the intro paragraph says where the excerpts live
text = base.part('report:CodeReferencesGeneral').decode('utf-8')
link_re = re.compile(r'<link address="#(?:' + '|'.join(DELETED) + r')[^"]*">([^<]*)</link>')
text, unlinked = link_re.subn(r'\1', text)
assert unlinked == 32, unlinked
old_intro = ('Keep the References folder beside this journal. C001-C004 each have one reference module; this module holds the full index and '
             'references used outside those calculations. Shared excerpts reuse the same named external PDF.')
new_intro = ('Keep the References folder beside this journal. The C001 to C004 reference modules were retired on 21 October 2026 (T031): the '
             'provisions they held now open as citation cards with the highlighted excerpt in the calculation reports of the notebook packages. '
             'This module holds the full index and the references used outside those calculations; index entries without a link name excerpts '
             'that live in the calculation reports. Shared excerpts reuse the same named external PDF.')
once(text, old_intro, 'CodeReferencesGeneral intro')
text = text.replace(old_intro, new_intro)
assert '#CodeReferencesC00' not in text
E.fromstring(text.encode('utf-8'))
out['report:CodeReferencesGeneral'] = text.encode('utf-8')
record['CodeReferencesGeneral'] = {'source': 'base.bpad + links into the deleted modules unwrapped + intro paragraph', 'links_unwrapped': unlinked}

# DecisionLog: the entry
text = base.part('report:DecisionLog').decode('utf-8')
nl = nl_of(text)
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

# no surviving component may still link into a deleted module
for key, el in base.elements.items():
    owner = key.split(':', 1)[1]
    if owner in DELETED or key in out:
        continue
    bad = [n.get('address') for n in el.iter('link') if any((n.get('address') or '').startswith('#' + d) for d in DELETED)]
    assert not bad, f'{key}: unregistered links into deleted modules: {bad[:5]}'

components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T031', 'base_sha256': base.sha256, 'deleted': DELETED, 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T031', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
