"""Distilled Blockpad (.bpad) export of the cap notebook's current case (scripts/build_cap_bpad.py in memory)."""
import json

from .bpad_export import package_revision
from .io import export_bundle
from .model import evaluate

NOTEBOOK_PROVENANCE = ('Blockpad edition exported from the cap notebook (scripts/build_cap_bpad.py in memory) for this case; '
                       'every definition was evaluated independently and compared with the cap tool to 1 part in 10⁹.')
LABELS = {'end_bent_1': 'End Bent 1', 'end_bent_2': 'End Bent 2', 'pier': 'Pier Cap', 'notebook': 'Cap'}
GENERIC_NAMES = ('CapDesignNotebook', 'Cap Design - Distilled', 'Cap Design.bpad')


def cap_key(case):
    """'end_bent_1', 'end_bent_2', 'pier' or 'notebook', from the case name and the imported FBMP file name."""
    text = (str(case.get('name', '')) + str(case.get('analysis', {}).get('xml_audit', {}).get('filename', ''))).lower()
    for n in ('1', '2'):
        if f'end bent {n}' in text or f'end_bent_{n}' in text or f'end bent{n}' in text:
            return f'end_bent_{n}'
    if 'pier' in text:
        return 'pier'
    return 'notebook'


def readiness(case):
    """None when the case can be distilled, else a plain-text reason."""
    if not case.get('analysis', {}).get('xml_audit', {}).get('end_records'):
        return 'Import the FBMP XML analysis first: the distilled sheet needs the pile and bearing stations.'
    if not case.get('transverse_detail', {}).get('runs'):
        return 'Enter the actual transverse runs (hoops / pile U bars) first: the distilled sheet checks the actual cage.'
    return None


def distill_cap(case, root, *, search_result=None, search_filter=None, revision=None, mathcad_compare=False):
    """Export the case bundle under `root`, then build and verify the distilled sheet into <bundle>/blockpad/.

    Returns dict(folder, bpad, verification, entry, summary)."""
    from scripts import build_cap_bpad as bc
    from scripts import build_cap_mathcad as bm
    e = evaluate(case)
    folder = export_bundle(case, root, search_result, search_filter)
    report = bm.report_info(folder / 'calculation_report.html', e, name=f'{folder.name}/calculation_report.html')
    key = cap_key(e.case)
    cap = dict(key=key, label=LABELS[key], case=None, reports=None, output=None)
    names = bc.SIDE_BY_KEY.get(key, GENERIC_NAMES)
    revision = revision or package_revision(prefixes=('cap-pile-tool-',), notebooks=('Cap_and_Pile_Design.ipynb',))
    sheet, eng, meta, filename, ctx = bc.build_cap(cap, mathcad_compare, e=e, report=report, revision=revision, names=names,
                                                   extra_provenance=NOTEBOOK_PROVENANCE)
    out = folder / 'blockpad'
    entry = bc.write_outputs(sheet, eng, meta, filename, ctx, cap, out_dir=out)
    verification = out / 'verification.json'
    verification.write_text(json.dumps([entry], indent=1, ensure_ascii=False, sort_keys=True), encoding='utf-8', newline='\n')
    summary = (f'{entry["tool_comparisons"]} values match the cap tool ({entry["coverage_comparisons"]} of them from '
               f'{entry["coverage_rows_real"] + entry["coverage_rows_synthetic"]} branch-coverage rows); every branch reached; '
               f'status {entry["status"]}; report {entry["report_file"]}.')
    return dict(folder=folder, bpad=out / filename, verification=verification, entry=entry, summary=summary)
