"""Audit native recalculation and import registered modules without serialization."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
from bpad_workflow import Journal, MODULE_TAGS, check, write_json

base = Journal.load(TASK / 'base.bpad')
native = Journal.load(TASK / 'native-recalculated.bpad')
order = json.loads((TASK / 'order.json').read_text())
assert base.sha256 == order['base_journal_sha256']
assert set(base.order) == set(native.order)

def authored(e):
    """Read-only comparison: exclude native display caches, keep all input data."""
    cache_tags = set()
    if e.tag == 'dynexp' and 'formula' in e.attrib:
        cache_tags = {'expbody', 'expresult', 'expstep', 'error'}
    elif 'formula' in e.attrib:
        cache_tags = {'num', 'textvalue', 'error'}
    text = (e.text or '').strip()
    if e.tag == 'paragraph':
        text = ' '.join(text.split())  # Native save collapses repeated prose spaces.
    return (e.tag, tuple(sorted(e.attrib.items())), text,
            tuple((authored(c), (c.tail or '').strip()) for c in e if c.tag not in cache_tags))

changed = []
for key in base.order:
    if base.elements[key].tag in MODULE_TAGS:
        assert authored(base.elements[key]) == authored(native.elements[key]), key
        if base.hashes[key] != native.hashes[key]:
            changed.append(key)
    else:
        assert base.part(key) == native.part(key), key
assert set(changed) <= set(order['writes'])
assert not list(native.root.iter('error'))

def values(e):
    return [(x.get('formula'), tuple((c.tag, ''.join(c.itertext()).strip()) for c in x
             if c.tag in {'expresult', 'expstep', 'num', 'textvalue', 'error'}))
            for x in e.iter() if 'formula' in x.attrib]

cache_changes = []
status_changes = []
for key in order['writes']:
    bv, nv = values(base.elements[key]), values(native.elements[key])
    assert len(bv) == len(nv)
    for index, ((formula, before), (nf, after)) in enumerate(zip(bv, nv)):
        assert formula == nf
        if before != after:
            cache_changes.append({'component': key, 'formula_index': index,
                                  'formula': formula, 'before': before, 'after': after})
        before_s = ' '.join(v for _, v in before)
        after_s = ' '.join(v for _, v in after)
        if ('PASS' in before_s and 'FAIL' in after_s) or ('FAIL' in before_s and 'PASS' in after_s):
            status_changes.append({'component': key, 'formula': formula,
                                   'before': before_s, 'after': after_s})

proposed = Journal(base.replace({k: native.part(k) for k in changed}))
assert proposed.shell == base.shell and proposed.order == base.order
assert all(proposed.part(k) == native.part(k) for k in order['writes'])
assert sum('formula' in e.attrib for e in proposed.root.iter()) == 8901
write_json(TASK / 'cache-changes.json', cache_changes)
evidence = {
    'base_sha256': base.sha256, 'native_sha256': native.sha256,
    'candidate_sha256': proposed.sha256, 'formula_count': 8901,
    'native_calculation_action': 'Blockpad Formulas > Update All (F5), followed by Ctrl+S on tasks/T018/working.bpad on 19 October 2026',
    'native_saved_copy': 'native-recalculated.bpad',
    'stored_errors': 0, 'authored_input_expression_style_and_structure_comparison': 'passed',
    'comparison_exclusions': 'Only formula-owned expbody/expresult/expstep and formula-owned cell num/textvalue/error caches; XML whitespace and native collapse of repeated prose spaces',
    'all_40_modules_exactly_match_native_save': True,
    'unassigned_components_preserved_byte_exact': len(base.order) - len(order['writes']),
    'document_shell_and_component_order_preserved_byte_exact': True,
    'changed_components': changed, 'changed_formula_cache_records': len(cache_changes),
    'pass_fail_transitions': status_changes,
    'engineering_review': 'not performed; failed checks retained',
    'external_analysis': 'FB-MultiPier was not rerun; its journal entry tables now show current native calculations, including two newly exposed consistency failures',
}
write_json(TASK / 'native-verification.json', evidence)
submission = {
    'summary': 'Full native Blockpad recalculation of the T017 source journal; import the exact native module bytes while preserving the source wrapper, component order and non-module resources.',
    'published_outputs': ['All 40 journal modules match the native recalculated save; existing output names, units, signs and cases retained'],
    'assumptions_and_conventions': ['All 8,901 formulas and authored inputs, expressions and styles preserved; native display/result caches and XML whitespace may differ'],
    'downstream_impact': ['Journal bearing, wind, gravity, uplift, FBMP entry, fin and quantity results refreshed; registered calculation modules saved by Blockpad'],
    'external_analysis': evidence['external_analysis'],
    'checks_performed': ['Native Update All and save', 'Zero stored native errors', 'Authored structure/input/expression comparison', 'Exact native module bytes and protected source bytes verified', 'Scope/dependency/reference checks'],
    'open_items': ['FBMPPier.NB_checkUplift changed PASS to FAIL', 'FBMPEndBent.EB_CheckGravity changed PASS to FAIL', 'Existing cap and other engineering failures retained; no engineering acceptance', 'Full native pagination/appearance review not performed'],
}
write_json(TASK / 'submission.json', submission)
_, report = check(ROOT, 'T018', proposed.data)
(TASK / 'working.bpad').write_bytes(proposed.data)
write_json(TASK / 'check.json', report)
print(json.dumps(evidence, indent=2, ensure_ascii=False))
