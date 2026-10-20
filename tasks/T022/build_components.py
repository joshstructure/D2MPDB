"""T022: write the 17 registered component files from base.bpad and the rebuilt generator outputs (rerunnable).

* CapDesignBasis, CapDesignEndBentOne/Two, CapDesignPier: cap_bpad/journal/<name>.xml (scripts/build_cap_bpad.py --journal)
* EndBentBackwallDesign: end_bent_walls/bpad/journal/EndBentBackwallDesign.xml (scripts/build_backwall_bpad.py --journal)
* PileDesignEndBentOne/Two, PileDesignPier: pile_bpad/fragments/<name>.xml (scripts/build_pile_bpad.py)
* the other nine: submission_format.transform on the base component text (exact-substring surgery, CRLF kept)

Each generated fragment is checked against its verification record and against the base: the same report name, every
dynexp formula of the base still present (multiset), the only new definitions the eight Stamp_* references of the live project
stamp, no formula-bearing value cell lost except the eight stamp cells it replaces. Each hand-authored module keeps every
formula string (multiset equality). Then the visible-text rule of scripts/bpad_sheet.py is applied to all 15 calculation
modules; leftovers are listed in independent-checks.json and stop the build unless they are in ACCEPTED.
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
sys.path.insert(0, str(TASK))
from tools.bpad_workflow import Journal  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402
from scripts.build_backwall_mathcad import notebook_revision as backwall_revision  # noqa: E402
from pile_design.mathcad import package_revision as pile_revision  # noqa: E402
import submission_format as sf  # noqa: E402

CAPS = ['CapDesignBasis', 'CapDesignEndBentOne', 'CapDesignEndBentTwo', 'CapDesignPier']
PILES = ['PileDesignEndBentOne', 'PileDesignEndBentTwo', 'PileDesignPier']
BACKWALL = 'EndBentBackwallDesign'
GENERATED = {**{n: ROOT / 'cap_bpad' / 'journal' / f'{n}.xml' for n in CAPS},
             **{n: ROOT / 'pile_bpad' / 'fragments' / f'{n}.xml' for n in PILES},
             BACKWALL: ROOT / 'end_bent_walls' / 'bpad' / 'journal' / f'{BACKWALL}.xml'}
CALCS = CAPS + PILES + [BACKWALL, 'MSEWallExclusion', 'BearingDesign', 'C001WindLoadOnPedBridgeSuperstructure', 'FenceWind',
                        'BridgeMovement', 'SuperstructureUplift', 'PierWallFins']
TITLES = {'CapDesignBasis': 'C007 - Cap Design Basis (shared factors)', 'CapDesignEndBentOne': 'C008 - End Bent 1 Cap Design',
          'CapDesignEndBentTwo': 'C009 - End Bent 2 Cap Design', 'CapDesignPier': 'C010 - Pier Cap Design',
          'PileDesignEndBentOne': 'C011 - End Bent 1 Pile Design', 'PileDesignEndBentTwo': 'C012 - End Bent 2 Pile Design',
          'PileDesignPier': 'C013 - Pier Pile Design', BACKWALL: 'C014 - End Bent 1 Backwall, Cheek Walls and Tie-Back Straps',
          'MSEWallExclusion': 'C015 - MSE Wall Exclusion - Both End Bents', 'BearingDesign': 'C016 - Bearings and Support Details'}
STAMP_DEFS = Counter(f'{bs.STAMP_PREFIX}{k} = {bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS)
STAMP_CELLS = Counter(f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS)
# Visible wording that the marker regex flags but that is engineering text, not working language (module -> fragments of text)
ACCEPTED = {'FenceWind': ('Task Work Order',), 'SuperstructureUplift': ('Task Work Order',)}   # the RFQ contract term


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def iter_tags(el, tags):
    """Elements with one of `tags` (works for lxml and the standard-library trees the workflow's Journal builds)."""
    return (e for e in el.iter() if e.tag in tags)


def dynexp_formulas(el):
    return Counter(d.get('formula') for d in el.iter('dynexp'))


def cell_formulas(el):
    return Counter(e.get('formula') for e in iter_tags(el, ('c', 'planecontainer', 'lineardim', 'plot')) if e.get('formula'))


def static_value_cells(el):
    return [''.join(c.itertext()) for c in el.iter('c') if not c.get('formula') and c.find('textvalue') is not None]


def leftovers(el, name):
    out = []
    for node, text in bs.visible_text_elements(el):
        m = bs.SUBMISSION_FORBIDDEN.search(text)
        if m and not any(a in text for a in ACCEPTED.get(name, ())):
            out.append({'element': node.tag, 'marker': m.group(0), 'text': text[:200]})
    return out


base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert len(mapping) == 17 and {k.split(':', 1)[1] for k in mapping} == set(CALCS) | {'PedBridge', 'DecisionLog'}, sorted(mapping)
out, record = {}, {}

# ----------------------------------------------------------------------------- generated modules
cap_journal = json.loads((ROOT / 'cap_bpad' / 'journal' / 'verification.json').read_text(encoding='utf-8'))
cap_v = {e['report_name']: e for e in cap_journal['reports'] + [cap_journal['basis']]}
assert cap_journal['journal_file'] == 'journal/D2_I95_Project_Journal.bpad'
pile_v = {e['report_name']: e for e in json.loads((ROOT / 'pile_bpad' / 'verification.json').read_text(encoding='utf-8'))}
bw_v = json.loads((ROOT / 'end_bent_walls' / 'bpad' / 'journal' / 'verification.json').read_text(encoding='utf-8'))[0]
assert bw_v['package_revision'] == backwall_revision(), 'backwall journal edition is for another package: rebuild it'
assert bw_v['report_name'] == BACKWALL and bw_v['status'] == '✓ All Checks Pass'
for name in PILES:
    assert pile_v[name]['package_revision'] == pile_revision(), f'{name}: pile_bpad is for another package: rebuild it'
    assert pile_v[name]['status'] == '✓ All Checks Pass'
for name in CAPS:
    assert name in cap_v, f'{name}: not in cap_bpad/journal/verification.json'
for name, path in GENERATED.items():
    data = strip_nl(path.read_bytes())
    if name == BACKWALL:
        assert sha(data) == bw_v['fragment_sha256'], 'backwall fragment differs from its verification record'
    root = E.fromstring(data)
    assert root.tag == 'report' and root.get('name') == name and root.get('title') == TITLES[name], (name, root.get('title'))
    old = base.elements[f'report:{name}']
    old_d, new_d = dynexp_formulas(old), dynexp_formulas(root)
    assert not (old_d - new_d), f'{name}: definitions lost: {list((old_d - new_d).elements())[:5]}'
    added = new_d - old_d
    expected = STAMP_DEFS if name not in PILES else Counter()
    assert added == expected, f'{name}: unexpected new definitions: {list(added.elements())[:8]}'
    old_c, new_c = cell_formulas(old), cell_formulas(root)
    assert old_c - new_c == (STAMP_CELLS if name not in PILES else Counter()), f'{name}: value-cell formulas lost: {list((old_c - new_c).elements())[:5]}'
    assert not (new_c - old_c), f'{name}: new value-cell formulas: {list((new_c - old_c).elements())[:5]}'
    assert not static_value_cells(root), f'{name}: static value cells remain'
    assert [s.get('name') for s in root.iter('section') if s.get('name') == bs.WORKING_NOTES] == [bs.WORKING_NOTES]
    out[f'report:{name}'] = data
    record[name] = {'source': path.relative_to(ROOT).as_posix(), 'definitions': sum(new_d.values()), 'stamp_definitions': sum(added.values()),
                    'title': root.get('title')}

# ----------------------------------------------------------------------------- hand-authored modules
for name in ['MSEWallExclusion', 'BearingDesign', 'C001WindLoadOnPedBridgeSuperstructure', 'FenceWind', 'BridgeMovement',
             'SuperstructureUplift', 'PierWallFins', 'PedBridge', 'DecisionLog']:
    text = base.part(f'report:{name}').decode('utf-8')
    new = sf.transform(name, text)
    root = E.fromstring(new.encode('utf-8'))
    old = base.elements[f'report:{name}']
    assert dynexp_formulas(old) == dynexp_formulas(root), f'{name}: dynexp formulas changed'
    assert cell_formulas(old) == cell_formulas(root), f'{name}: cell formulas changed'
    figures = ('canvas', 'image', 'plot', 'resource')
    assert Counter(c.tag for c in iter_tags(old, figures)) == Counter(c.tag for c in iter_tags(root, figures)), f'{name}: figures changed'
    if name in TITLES:
        assert root.get('title') == TITLES[name]
    converted = len(static_value_cells(old)) - len(static_value_cells(root))
    if name in CALCS:
        assert not static_value_cells(root), f'{name}: static value cells remain: {static_value_cells(root)[:5]}'
    out[f'report:{name}'] = new.encode('utf-8')
    record[name] = {'source': 'base.bpad + submission_format.transform', 'cells_converted': converted,
                    'definitions': sum(dynexp_formulas(root).values()), 'title': root.get('title')}

# ----------------------------------------------------------------------------- the visible-text rule over the 15 calculation modules
flagged = {}
for name in CALCS:
    found = leftovers(E.fromstring(out[f'report:{name}']), name)
    if found:
        flagged[name] = found
checks = {'task': 'T022', 'base_sha256': base.sha256, 'components': record, 'visible_text_leftovers': flagged,
          'rule': bs.SUBMISSION_FORBIDDEN.pattern, 'accepted_wording': ACCEPTED}
(TASK / 'independent-checks.json').write_text(json.dumps(checks, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
if flagged:
    print(json.dumps(flagged, indent=1, ensure_ascii=False))
    sys.exit('visible working language remains (see independent-checks.json)')

components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'definitions.json').write_text(json.dumps({
    'edited_formulas': [], 'derived_cache_refreshes': {},
    'added_definitions': {name: list(STAMP_DEFS.elements()) for name in CAPS + [BACKWALL]},
    'note': 'Presentation only: titles, prose, hidden sections, table cell kinds and the live stamp as result-only definitions; every '
            'existing formula string and cache value is unchanged (result-only caches drop the "= " prefix).'},
    indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T022', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)} for k, v in sorted(out.items())}},
                 indent=2, ensure_ascii=False))
