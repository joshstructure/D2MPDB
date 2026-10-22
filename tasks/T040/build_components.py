"""T040: write the registered component files (rerunnable, byte-surgical); PierWallFins (C006) is a registered deletion.

* PierWallFins: deleted (empty component fragment). No surviving module reads a `PierWallFins.` name; the only native link
  into the module is the index paragraph removed below.
* PierWallRings (C017): the rebuilt journal edition `ring_wall/bpad/journal/PierWallRings.xml`, checked against its verification
  record, the registered case and the base module: same name, title, definitions, formulas and caches (only the hidden working
  notes and one visible sentence changed), the visible-text rule and the hidden WorkingNotes section.
* PedBridge: the C006 index paragraph removed and one revision paragraph inserted before the newest one.
* DecisionLog: one section appended inside the report.
"""
import hashlib
import json
import re
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
DECISION_ID = 'D-082'
DELETED = ['PierWallFins']
REVISION_NOTE = ('Revision: 22 October 2026, C006 Pier Wall, Hairpins and Fin Plates withdrawn (T040, D-082): by user direction the fin-plate and '
                 'hairpin hanger calculation is sequestered from the project (kept intact in the repository under sequestered/ for revival) and its '
                 'module is removed from the journal; the welded annular-ring calculation C017 is the pier-wall support calculation the project '
                 'carries, matching the CAD model (D-076, D-079). Calculation numbers are permanent identifiers from this revision on: C006 stays '
                 'retired like C005, no calculation is renumbered, and the index heading spans the numbers in use. C017 is regenerated from its '
                 'unchanged starting case with the same definitions, values, caches and figures; only its hidden working notes and the "Outside '
                 'this calculation" sentence no longer present C006 as the undecided alternative. Native recalculation, appearance and engineering '
                 'reviews not performed; no engineering value changed.')
DECISION_SECTION = 'PierWallFinsWithdrawn20261022'
DECISION_HEADING = '2026-10-22 - C006 Pier Wall, Hairpins and Fin Plates withdrawn; calculation numbers permanent (T040)'
DECISION = ('User direction of 22 October 2026 (project decision D-082): "Lets sequester the pier wall fin and hairpin calc from the project. Dont '
            'delete it but lets make it an unused unreferenced calc unless we need to revive it later" and "Lets actually give each calc a unique '
            'number so we dont have to keep renumbering them". The module C006 - Pier Wall, Hairpins and Fin Plates (report PierWallFins; the journal '
            'edition of the pier_wall_fins notebook package) is deleted from the journal; the package, its notebook, editions and committed run are '
            'kept intact under sequestered/ in the repository, removed from every build list, test, the code-excerpt library and the design atlas, '
            'and can be revived by the steps in sequestered/README.md. The project carries the welded annular-ring support concept: C017 Pier Wall, '
            'Annular Pile Rings, matching the CAD model rings of D-076 and D-079; this withdrawal is a scope decision, not an engineering acceptance '
            'of C017, whose grid-clearance failure and five scope items keep their recorded status. Calculation numbers are permanent identifiers: '
            'a withdrawn calculation keeps its number and the number is never reused (C005 and C006 are retired), no module is renumbered, and a new '
            'calculation takes the next unused number after C018. C017 is regenerated from its unchanged starting case with identical definitions, '
            'caches and figures; its hidden working notes and the "Outside this calculation" sentence now record the withdrawal instead of an '
            'undecided support concept. The index entry of C006 is removed; the "Calculations C001 to C018" heading, the stylerules of C006, the '
            'gravity sheet, C004 and C002 are unchanged. Native recalculation, appearance and engineering reviews not performed; no engineering '
            'value changed.')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def nl_of(text):
    return '\r\n' if '\r\n' in text else '\n'


dyn = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
caches = lambda el: Counter((d.get('formula'), (d.findtext('expresult') or '').strip()) for d in el.iter('dynexp'))


def inbound(base, name):
    """(names other components read from `name`, inbound link addresses) from the base journal, ignoring the deleted modules."""
    qual = re.compile(r'\b' + re.escape(name) + r'\.([A-Za-z_Ͱ-Ͽ][A-Za-z_0-9Ͱ-Ͽ]*)')
    names, links = set(), {}
    for key, el in base.elements.items():
        owner = key.split(':', 1)[1]
        if owner == name or owner in DELETED:
            continue
        for node in el.iter():
            for text in (node.get('formula'), node.text if node.tag == 'expbody' else None):
                if text:
                    names.update(m.group(1) for m in qual.finditer(text))
            if node.tag == 'link' and (node.get('address') or '').startswith('#' + name):
                links.setdefault(key, []).append(node.get('address'))
    return names, links


base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert set(mapping) == {'report:PierWallFins', 'report:PierWallRings', 'report:PedBridge', 'report:DecisionLog'}, sorted(mapping)
out, record = {}, {}

# --- the deletion: nothing outside the module reads its names; the only inbound link is the index paragraph ---
for name in DELETED:
    assert f'report:{name}' in base.elements, name
    names, links = inbound(base, name)
    assert not names, f'{name}: names read by other modules: {sorted(names)}'
    assert set(links) == {'report:PedBridge'} and len(links['report:PedBridge']) == 1, links
    old = base.elements[f'report:{name}']
    out[f'report:{name}'] = b''
    record[name] = {'source': 'deleted', 'title': old.get('title'), 'bytes_before': len(base.part(f'report:{name}')),
                    'definitions_before': sum(dyn(old).values()), 'names_read_by_other_modules': [], 'inbound_links': links,
                    'kept_at': 'sequestered/pier_wall_fins/bpad/journal/PierWallFins.xml (repository)'}

# --- C017 ---
NAME, TITLE = 'PierWallRings', 'C017 - Pier Wall, Annular Pile Rings'
folder = ROOT / 'ring_wall' / 'bpad' / 'journal'
v = json.loads((folder / 'verification.json').read_text(encoding='utf-8'))[0]
data = strip_nl((folder / f'{NAME}.xml').read_bytes())
assert v['report_name'] == NAME and v['title'] == TITLE and sha(data) == v['fragment_sha256'], 'C017 fragment differs from its verification record'
case = json.loads((ROOT / 'project_current' / 'pier_wall' / 'selected_case.json').read_text(encoding='utf-8-sig'))
assert (case['length_in'], case['thickness_in'], case['height_in'], case['pile_free_length_in'], case['ring_t_in']) == (219.0, 36.0, 194.8625, 92.4, 0.5), case
from ring_wall.output import case_hash  # noqa: E402
from ring_wall.model import analyze  # noqa: E402
assert v['case_sha256'] == case_hash(analyze(case)), 'C017 edition was not built from the registered case'
root = E.fromstring(data)
old = E.fromstring(base.part(f'report:{NAME}'))
assert root.get('name') == NAME == old.get('name') and root.get('title') == TITLE == old.get('title')
assert dyn(root) == dyn(old) and caches(root) == caches(old), 'C017: a definition, formula or cache changed'
old_canvases = [E.tostring(c) for c in old.iter('canvas')]
new_canvases = [E.tostring(c) for c in root.iter('canvas')]
assert old_canvases == new_canvases, 'C017: a canvas changed'
for el, t in bs.visible_text_elements(root):
    m = bs.SUBMISSION_FORBIDDEN.search(t)
    assert not m, f'{NAME}: working language {m.group(0)!r}: {t[:100]}'
assert [s.get('name') for s in root.iter('section') if s.get('name') == bs.WORKING_NOTES] == [bs.WORKING_NOTES]
visible_old = {t for _, t in bs.visible_text_elements(old)}
visible_new = {t for _, t in bs.visible_text_elements(root)}
changed_visible = sorted(visible_new - visible_old)
assert len(changed_visible) == 1 and 'former C006' in changed_visible[0], changed_visible
assert 'C006 (Pier Wall, Hairpins and Fin Plates) sizes' not in data.decode('utf-8')
out[f'report:{NAME}'] = data
record[NAME] = {'source': f'ring_wall/bpad/journal/{NAME}.xml', 'fragment_sha256': v['fragment_sha256'], 'case_sha256': v['case_sha256'],
                'definitions': sum(dyn(root).values()), 'status': v['status'], 'failed_checks': v['failed_checks'],
                'definitions_formulas_caches_canvases': 'identical to the base module', 'visible_sentences_changed': changed_visible}

# --- PedBridge: drop the C006 index paragraph, add the revision note before the newest one ---
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
pattern = re.compile(r'[ \t]*<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">' + nl
                     + r'[ \t]*<link address="#PierWallFins">[^<]*</link>' + nl + r'[ \t]*</paragraph>' + nl)
text, k = pattern.subn('', text)
assert k == 1, f'PedBridge: index paragraph for PierWallFins: {k} matches'
assert '#PierWallFins' not in text
assert '<heading level="1" keepwithnext="True">Calculations C001 to C018</heading>' in text, 'index heading'
m = re.search(r'^( {8}<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: )', text, re.M)
assert m, 'PedBridge revision paragraph anchor'
note = ' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
assert REVISION_NOTE[:60] not in text
text = text[:m.start()] + note + nl + text[m.start():]
E.fromstring(text.encode('utf-8'))
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + index paragraph removed + revision note', 'index_entries_removed': k}

# --- DecisionLog ---
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

for key in ('report:PedBridge', 'report:DecisionLog'):
    new, old = E.fromstring(out[key]), base.elements[key]
    assert dyn(old) == dyn(new) and caches(old) == caches(new), f'{key}: a definition or cache changed'

# no surviving component may still link into the deleted module
for key, el in base.elements.items():
    owner = key.split(':', 1)[1]
    if owner in DELETED or key in out:
        continue
    bad = [n.get('address') for n in el.iter('link') if any((n.get('address') or '').startswith('#' + d) for d in DELETED)]
    assert not bad, f'{key}: unregistered links into deleted modules: {bad[:5]}'

components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T040', 'base_sha256': base.sha256, 'decision': DECISION_ID, 'deleted': DELETED,
                                                    'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T040', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
