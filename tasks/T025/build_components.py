"""T025: the project stamp of the seven hand-authored calculations in multiline result-only cells (rerunnable, byte-surgical).

In each report the eight value cells `<c capture="False" background="#F1F5FA" formula="ProjectInfo.<Key>"><textvalue>text</textvalue></c>`
become `<textcell ...><paragraph ...><dynexp formula="Stamp_<Key> = ProjectInfo.<Key>" ... style="Result only"><expbody/><expresult>text</expresult>
</dynexp></paragraph></textcell>`, the form scripts/bpad_sheet.py writes for the generated editions. Nothing else changes.
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

REPORTS = ['C001WindLoadOnPedBridgeSuperstructure', 'FenceWind', 'BridgeMovement', 'SuperstructureUplift', 'PierWallFins',
           'MSEWallExclusion', 'BearingDesign']
TNR = 'Times New Roman'
CELL = re.compile(r'<c capture="False" background="#F1F5FA" formula="ProjectInfo\.(\w+)"><textvalue>([^<]*)</textvalue></c>')
STAMP_DEFS = Counter(f'{bs.STAMP_PREFIX}{k} = {bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS)
STAMP_CELLS = Counter(f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS)
DECISION_SECTION = 'SubmissionFormatting20261020c'
DECISION_HEADING = '2026-10-20 - Project stamp of the hand-authored calculations in multiline cells (T025)'
DECISION = ('Follow-up of T024 (user direction of 20 October 2026: every calculation carries the project information table). The '
            'stamp tables of C001, C002, C003, C004, C006, C015 and C016 held their values in value cells referencing ProjectInfo, '
            'which clip the project name natively; the eight value cells of each become multiline cells holding a result-only '
            'definition Stamp_<Key> = ProjectInfo.<Key> with the same cached text, the form of the generated calculations (T022). '
            'Eight definitions added per report, nothing removed, every other byte unchanged. Native recalculation, appearance and '
            'engineering reviews not performed; no engineering value changed.')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def new_cell(key, text):
    formula = f'{bs.STAMP_PREFIX}{key} = {bs.PROJECT_INFO}.{key}'
    return (f'<textcell capture="False" background="#F1F5FA"><paragraph fontfamily="{TNR}" fontsize="9" spacingafter="0">'
            f'<dynexp formula="{formula}" mathlayout="on" showformula="False" showresult="True" showsteps="False" style="Result only" '
            f'showidentifier="False"><expbody>{formula}</expbody><expresult>{text}</expresult></dynexp></paragraph></textcell>')


def iter_tags(el, tags):
    return (e for e in el.iter() if e.tag in tags)


def dynexps(el):
    return Counter(d.get('formula') for d in el.iter('dynexp'))


def cells(el):
    return Counter(e.get('formula') for e in iter_tags(el, ('c', 'planecontainer', 'lineardim', 'plot')) if e.get('formula'))


base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert {k.split(':', 1)[1] for k in mapping} == set(REPORTS) | {'DecisionLog'}, sorted(mapping)
out, record = {}, {}
for name in REPORTS:
    text = base.part(f'report:{name}').decode('utf-8')
    found = CELL.findall(text)
    assert [k for k, _ in found] == list(bs.STAMP_KEYS), (name, found)
    assert [t for _, t in found] == [escape(bs.PROJECT_STAMP[k]) for k in bs.STAMP_KEYS], (name, found)
    new = CELL.sub(lambda m: new_cell(m.group(1), m.group(2)), text)
    assert new != text and len(new) - len(text) > 0
    root, old = E.fromstring(new.encode('utf-8')), base.elements[f'report:{name}']
    assert dynexps(root) - dynexps(old) == STAMP_DEFS and not (dynexps(old) - dynexps(root)), name
    assert cells(old) - cells(root) == STAMP_CELLS and not (cells(root) - cells(old)), name
    table = next(t for t in root.iter('table') if t.get('name') == 'ProjectStamp')
    assert [o for _, _, o in bs.stamp_cells(table)] == [f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS]
    assert [t for _, t, _ in bs.stamp_cells(table)] == [bs.PROJECT_STAMP[k] for k in bs.STAMP_KEYS]
    assert all(c.tag == 'textcell' for row in table.findall('row') for c in row)
    # byte check: the report minus the eight cells is unchanged
    assert CELL.sub('', text) == re.sub(r'<textcell capture="False" background="#F1F5FA"><paragraph fontfamily="Times New Roman" fontsize="9" spacingafter="0"><dynexp formula="Stamp_\w+ = ProjectInfo\.\w+".*?</textcell>', '', new)
    out[f'report:{name}'] = new.encode('utf-8')
    record[name] = {'cells_converted': 8, 'definitions_added': list(STAMP_DEFS.elements()), 'sha256_before': base.hashes[f'report:{name}'], 'sha256_after': sha(out[f'report:{name}'])}

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
for key, blob in out.items():
    (TASK / 'components' / mapping[key]).write_bytes(blob)
(TASK / 'definitions.json').write_text(json.dumps({'edited_formulas': [], 'derived_cache_refreshes': {},
                                                   'added_definitions': {n: list(STAMP_DEFS.elements()) for n in REPORTS}}, indent=2) + '\n', encoding='utf-8')
(TASK / 'verification.json').write_text(json.dumps({'task': 'T025', 'base_sha256': base.sha256, 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T025', 'components': {k: {'file': mapping[k], 'sha256': sha(v)} for k, v in sorted(out.items())}}, indent=2))
