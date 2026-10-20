"""T024: write the five registered component files from base.bpad and the pile journal edition (rerunnable, byte-surgical).

* PileDesignEndBentOne/Two, PileDesignPier: pile_bpad/journal/<name>.xml (scripts/build_pile_bpad.py; live project stamp),
  checked against its verification record and against the base (every definition and value-cell formula kept, only the
  eight Stamp_* definitions added, the stamp table first).
* PedBridge: the index groups the calculations C001 to C016 in numerical order (exact-substring surgery; every anchor once).
* DecisionLog: entry appended.
"""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402
from pile_design.mathcad import package_revision  # noqa: E402

PILES = ['PileDesignEndBentOne', 'PileDesignEndBentTwo', 'PileDesignPier']
TNR = 'Times New Roman'
STAMP_DEFS = Counter(f'{bs.STAMP_PREFIX}{k} = {bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS)
DECISION_SECTION = 'SubmissionFormatting20261020b'
DECISION_HEADING = '2026-10-20 - Project stamp on the pile calculations and module order C001 to C016 (T024)'
DECISION = ('User direction of 20 October 2026: every calculation carries the project information table at the top and the modules '
            'are organised with all calculations together in numerical order. The three pile design reports (C011 to C013) are '
            'replaced by the journal edition of their generator (scripts/build_pile_bpad.py, pile_bpad/journal/), which opens with the '
            'live project stamp (Stamp_<Key> = ProjectInfo.<Key> in multiline cells, as the cap and backwall editions); every other '
            'definition, value cell, cache and canvas is unchanged; the standalone pile sheets carry the stamp as static text. The '
            'component order is a registered permutation (tools/bpad_workflow.py prepare --order, new): basis modules (index, project '
            'information, materials, geometry, access, pile section properties, loads, FBMP entries, foundation modeling), then C001 '
            'to C004 each followed by its reference packet, C006, C007 to C016, then quantities, decision log, notes, the general '
            'reference index and the archives; references, styles, includes and resources keep their slots and every component '
            'keeps its bytes. The index lists the calculations in one group in the same order. Native recalculation, appearance and '
            'engineering reviews not performed; FBMP not rerun; no engineering value changed.')
REVISION_NOTE = ('Revision: 20 October 2026, project stamp and module order (T024): the pile calculations C011 to C013 open with the '
                 'live project stamp like every other calculation; the modules are ordered basis first, then C001 to C016 in numerical '
                 'order (reference packets after their calculations), then quantities, decisions, notes, references and archives; the '
                 'index groups the calculations the same way.')
# (link target, label) of the index, in the new order
BASIS_LINKS = [('PedBridgeWeights_2Beams', 'Gravity Loads - 2 Beam'), ('GeneralLoads', 'General and Collision Loads'),
               ('PedBridgeWind', 'Wind - Design Basis'), ('LoadCombinations', 'Load Combinations'), ('FBMPPier', 'FBMP Entry - Pier'),
               ('FBMPEndBent', 'FBMP Entry - End Bent (15 / 34)'), ('PileProperties', 'Pile Section Properties'),
               ('FoundationModeling', 'Foundation Modeling')]
CALC_LINKS = [('C001WindLoadOnPedBridgeSuperstructure', 'C001 - Superstructure Wind'), ('CodeReferencesC001', 'C001 - References'),
              ('FenceWind', 'C002 - Fence Wind'), ('CodeReferencesC002', 'C002 - References'),
              ('BridgeMovement', 'C003 - Temperature Movement'), ('CodeReferencesC003', 'C003 - References'),
              ('SuperstructureUplift', 'C004 - Uplift and Bearing Reactions'), ('CodeReferencesC004', 'C004 - References'),
              ('PierWallFins', 'C006 - Pier Wall, Hairpins and Fin Plates'),
              ('CapDesignBasis', 'C007 - Cap Design Basis (shared factors, 19 October 2026)'),
              ('CapDesignEndBentOne', 'C008 - End Bent 1 Cap Design (19 October 2026 case)'),
              ('CapDesignEndBentTwo', 'C009 - End Bent 2 Cap Design (19 October 2026 case)'),
              ('CapDesignPier', 'C010 - Pier Cap Design (19 October 2026 case)'),
              ('PileDesignEndBentOne', 'C011 - End Bent 1 Pile Design (19 October 2026 case)'),
              ('PileDesignEndBentTwo', 'C012 - End Bent 2 Pile Design (19 October 2026 case)'),
              ('PileDesignPier', 'C013 - Pier Pile Design (19 October 2026 case)'),
              ('EndBentBackwallDesign', 'C014 - End Bent 1 Backwall, Cheek Walls and Tie-Back Straps (19 October 2026 case, live references)'),
              ('MSEWallExclusion', 'C015 - MSE Wall Exclusion - Both End Bents'),
              ('BearingDesign', 'C016 - Bearings and Support Details')]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(text, old, label):
    assert text.count(old) == 1, f'{label}: expected one occurrence, found {text.count(old)}: {old[:90]!r}'


def rep(text, old, new, label):
    once(text, old, label)
    return text.replace(old, new)


def iter_tags(el, tags):
    return (e for e in el.iter() if e.tag in tags)


def dynexps(el):
    return Counter(d.get('formula') for d in el.iter('dynexp'))


def cells(el):
    return Counter(e.get('formula') for e in iter_tags(el, ('c', 'planecontainer', 'lineardim', 'plot')) if e.get('formula'))


base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert {k.split(':', 1)[1] for k in mapping} == set(PILES) | {'PedBridge', 'DecisionLog'}, sorted(mapping)
out, record = {}, {}

# ----------------------------------------------------------------------------- the pile journal edition
verification = {v['report_name']: v for v in json.loads((ROOT / 'pile_bpad' / 'journal' / 'verification.json').read_text(encoding='utf-8'))}
for name in PILES:
    v = verification[name]
    assert v['package_revision'] == package_revision(), f'{name}: pile_bpad/journal is for another package: rebuild it'
    assert v['status'] == '✓ All Checks Pass' and v['stamp'] == 'live'
    raw = (ROOT / 'pile_bpad' / 'journal' / f'{name}.xml').read_bytes()
    data = raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw
    assert sha(data) == v['fragment_sha256'], f'{name}: the fragment differs from its verification record'
    root = E.fromstring(data)
    old = base.elements[f'report:{name}']
    assert root.get('name') == name and root.get('title') == old.get('title')
    lost, added = dynexps(old) - dynexps(root), dynexps(root) - dynexps(old)
    assert not lost and added == STAMP_DEFS, (name, list(lost.elements())[:3], list(added.elements())[:9])
    assert cells(old) == cells(root), f'{name}: value-cell formulas changed'
    first = next(el for el in root if el.tag not in ('include', 'stylerule'))
    assert first.tag == 'embed' and first.find('table').get('name') == 'ProjectStamp'
    assert [o for _, _, o in bs.stamp_cells(first.find('table'))] == [f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS]
    assert not bs.SUBMISSION_FORBIDDEN.search(' '.join(t for _, t in bs.visible_text_elements(root)))
    out[f'report:{name}'] = data
    record[name] = {'source': f'pile_bpad/journal/{name}.xml', 'fragment_sha256': v['fragment_sha256'], 'definitions': sum(dynexps(root).values())}

# ----------------------------------------------------------------------------- PedBridge: the index
text = base.part('report:PedBridge').decode('utf-8')
nl = '\r\n' if '\r\n' in text else '\n'
P = ' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">'
H = ' ' * 8 + '<heading level="1" keepwithnext="True">'


def link_para(target, label):
    return P + nl + ' ' * 12 + f'<link address="#{target}">{label}</link>' + nl + ' ' * 8 + '</paragraph>'


start_marker = H + 'Loads and FBMP entry</heading>'
end_marker = H + 'Quantities, decisions and references</heading>'
once(text, start_marker, 'loads heading')
once(text, end_marker, 'quantities heading')
i, j = text.index(start_marker), text.index(end_marker)
old_block = text[i:j]
old_links = re.findall(r'<link address="#([^"]+)">([^<]*)</link>', old_block)
assert {t for t, _ in old_links} == {t for t, _ in BASIS_LINKS + CALC_LINKS} - {'CodeReferencesC001', 'CodeReferencesC002', 'CodeReferencesC003', 'CodeReferencesC004', 'BearingDesign'}, \
    sorted({t for t, _ in old_links} ^ ({t for t, _ in BASIS_LINKS + CALC_LINKS}))
new_block = nl.join([start_marker] + [link_para(t, l) for t, l in BASIS_LINKS] +
                    [H + 'Calculations C001 to C016</heading>'] + [link_para(t, l) for t, l in CALC_LINKS]) + nl
text = text[:i] + new_block + text[j:]
# the bearings link leaves the basis group (it is C016 in the calculations group now)
text = rep(text, link_para('BearingDesign', 'C016 - Bearings and Support Details') + nl + H + 'Loads and FBMP entry</heading>',
           H + 'Loads and FBMP entry</heading>', 'bearings link in the basis group')
anchor = P.rstrip() .replace(' ' * 8, '', 1)
anchor = ' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: 20 October 2026, submission formatting (T022):'
note = ' ' * 8 + f'<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
text = rep(text, anchor, note + nl + anchor, 'revision paragraph')
root = E.fromstring(text.encode('utf-8'))
old = base.elements['report:PedBridge']
assert dynexps(old) == dynexps(root) and cells(old) == cells(root)
links = [(l.get('address'), l.text) for l in root.iter('link')]
assert [x for x in links if x[0] in {'#' + t for t, _ in CALC_LINKS} and x[0] != '#MSEWallExclusion' or x[0] == '#MSEWallExclusion' and x[1].startswith('C015 - MSE Wall Exclusion - Both')] == [('#' + t, l) for t, l in CALC_LINKS], 'calculation links out of order'
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + index regroup', 'calculation_links': len(CALC_LINKS)}

# ----------------------------------------------------------------------------- DecisionLog
text = base.part('report:DecisionLog').decode('utf-8')
nl = '\r\n' if '\r\n' in text else '\n'
tail = ' ' * 8 + '</section>' + nl + ' ' * 4 + '</report>'
assert text.endswith(tail) and f'name="{DECISION_SECTION}"' not in text
entry = nl.join([' ' * 8 + f'<section name="{DECISION_SECTION}" capture="False" hide="false">',
                 ' ' * 12 + f'<heading level="1" keepwithnext="True">{DECISION_HEADING}</heading>',
                 ' ' * 12 + f'<paragraph fontfamily="{TNR}" fontsize="11" leftindent="0" spacingafter="7">{escape(DECISION)}</paragraph>',
                 ' ' * 8 + '</section>'])
text = text[:-len(' ' * 4 + '</report>') - len(nl)] + nl + entry + nl + ' ' * 4 + '</report>'
E.fromstring(text.encode('utf-8'))
out['report:DecisionLog'] = text.encode('utf-8')
record['DecisionLog'] = {'source': 'base.bpad + entry', 'section': DECISION_SECTION}

for key, blob in out.items():
    (TASK / 'components' / mapping[key]).write_bytes(blob)
(TASK / 'definitions.json').write_text(json.dumps({'edited_formulas': [], 'derived_cache_refreshes': {},
                                                   'added_definitions': {n: list(STAMP_DEFS.elements()) for n in PILES}}, indent=2) + '\n', encoding='utf-8')
(TASK / 'independent-checks.json').write_text(json.dumps({'task': 'T024', 'base_sha256': base.sha256, 'components': record,
                                                          'order': json.loads((TASK / 'component_order.json').read_text(encoding='utf-8'))}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T024', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)} for k, v in sorted(out.items())}}, indent=2))
