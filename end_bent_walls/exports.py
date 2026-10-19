"""Case, register, report and strap-handoff exports."""
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import zipfile
from .model import COMBINATIONS, STRENGTH, INPUTS, CONFIRMATIONS, strap_table, upgrade_case

PLAN_NOTE = ('The soil reinforcement attached to the backwall shall be designed by a Specialty Engineer for the service and '
             'factored loads as shown using the design criteria for permanent MSE walls. Cost of furnishing and installing the '
             'soil reinforcement is considered incidental to the cost of the end bent.')


def case_json(case):
    return json.dumps(case, indent=1, sort_keys=False)


def load_case(content):
    data = json.loads(bytes(content).decode('utf-8-sig'))
    return upgrade_case(data)


def checks_rows(e):
    for c in e.checks:
        yield dict(group=c.group, check=c.label, status=c.status, ratio='' if c.ratio is None else f'{c.ratio:.4f}',
                   demand=c.demand, capacity=c.capacity, basis=c.basis, note=c.note,
                   review='' if not c.review else f'{c.review["action"]}: {c.review["reason"]} ({c.review["utc"]})')


def checks_csv(e):
    buffer = io.StringIO()
    rows = list(checks_rows(e))
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    return buffer.getvalue()


def handoff_xlsx(e):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook()
    ws = wb.active; ws.title = 'Tie-back loads'
    bold = Font(bold=True); head = PatternFill('solid', fgColor='DCECE0'); inp = PatternFill('solid', fgColor='FFF8E9')
    gov = max(STRENGTH, key=lambda c: e.value('f_str_' + c['key']))
    rows = [
        ('D2 I-95 Pedestrian Bridge · End bent soil reinforcement attached to the backwall', None, None),
        ('Common end-bent design (D-004); FDOT SDM 12.3.F and SDG 3.13.2.N', None, None),
        (None, None, None),
        ('Item', 'Service', 'Factored'),
        ('Load per foot along the backwall (kip/ft)', round(e.value('f_str_s'), 3), round(e.value('f_str_u'), 3)),
        ('Total for the backwall (kip)', round(e.value('F_str_s'), 2), round(e.value('F_str_u'), 2)),
        ('Backwall length (ft)', round(e.value('L_bw', 'ft'), 3), None),
        ('Strap elevation above the cap top (ft)', round(e.value('z_strap', 'ft'), 3), None),
        ('Governing factored combination', gov['label'], None),
        (None, None, None),
        ('Plan note', PLAN_NOTE, None),
        (None, None, None),
        ('Basis', None, None),
        ('Backfill', f'φ = {e.value("phi_soil", "deg"):g}°, γ = {1000 * e.value("gamma_s", "kip/ft^3"):g} pcf, active Coulomb, δ = {e.value("delta_w", "deg"):g}°', None),
        ('Surcharges', f'Pedestrian {1000 * e.value("q_PL", "kip/ft^2"):g} psf (LS); landing slab {1000 * e.value("q_ES", "kip/ft^2"):.0f} psf (ES)', None),
        ('Pile placement tolerance', f'{e.value("tol_pile", "in"):g} in toward the fill (SDG 3.13.2.N.3)', None),
        ('Settlement prerequisite', 'Confirmed' if e.case['confirmations']['settlement'] else 'PENDING: geotechnical confirmation that settlement above the cap bottom ≤ 2 in', None),
    ]
    for r in rows:
        ws.append(list(r))
    ws['A1'].font = Font(bold=True, size=13)
    for cell in ws[4]:
        cell.font = bold; cell.fill = head
    for row in ws.iter_rows(min_row=5, max_row=9):
        for cell in row[1:]:
            cell.fill = inp
    ws.column_dimensions['A'].width = 46; ws.column_dimensions['B'].width = 70; ws.column_dimensions['C'].width = 20
    ws['B11'].alignment = Alignment(wrap_text=True)
    table = wb.create_sheet('Overturning')
    table.append(['Combination', 'Load', 'Direction', 'Force (kip)', 'Arm (ft)', 'γ', 'γ·M (kip-ft)', 'Factor basis'])
    for cell in table[1]:
        cell.font = bold; cell.fill = head
    for c in COMBINATIONS:
        for r in strap_table(e, c['key']):
            table.append([c['label'], r['label'], r['kind'], round(r['force_kip'], 3), round(r['arm_ft'], 4), r['factor'],
                          round(r['factored_moment'], 3), r['basis']])
        table.append([c['label'], 'TOTAL', '', round(e.value('H_' + c['key']), 3), round(e.value('e_' + c['key'], 'ft'), 4), '',
                      round(e.value('M_' + c['key']), 3), f'F = {e.value("F_str_" + c["key"]):.2f} kip; {e.value("f_str_" + c["key"]):.3f} klf'])
    for col, width in zip('ABCDEFGH', (22, 32, 10, 12, 10, 8, 14, 34)):
        table.column_dimensions[col].width = width
    inputs = wb.create_sheet('Inputs')
    inputs.append(['Input', 'Value', 'Unit', 'Meaning', 'Source', 'Status'])
    for cell in inputs[1]:
        cell.font = bold; cell.fill = head
    for name, spec in INPUTS.items():
        src = e.case['sources'].get(name, {})
        inputs.append([name, e.case['inputs'][name], spec['unit'] or '', spec['caption'], src.get('source', ''), src.get('status', '')])
    for col, width in zip('ABCDEF', (14, 10, 10, 50, 60, 22)):
        inputs.column_dimensions[col].width = width
    buffer = io.BytesIO(); wb.save(buffer)
    return buffer.getvalue()


def _report(e):
    from .report import build_report
    return build_report(e).encode('utf-8')


DISTILLED_BPAD = 'End Bent Backwall Design.bpad'
BPAD_VERIFICATION = 'backwall_bpad_verification.json'
_distilled = []                      # [(evaluation, (bpad bytes, verification bytes))]: the last distillation, reused by the bundle


def distilled_bpad(e):
    """(Blockpad document bytes, verification JSON bytes) of the evaluated case, built and verified in memory.

    The sheet is the distilled Blockpad edition of this calculation (scripts/build_backwall_bpad.py): every definition
    is evaluated independently and compared with this model to 1 part in 10⁹ before the bytes are returned."""
    if _distilled and _distilled[0][0] is e:
        return _distilled[0][1]
    from pier_cap.bpad_export import package_revision
    from scripts.build_backwall_bpad import distill
    revision = package_revision(Path(__file__).resolve().parent, prefixes=('backwall-tool-',), notebooks=('End_Bent_Backwall_Design.ipynb',))
    result = distill(e, revision=revision)
    _distilled[:] = [(e, result)]
    return result


def bpad_summary(verification):
    """One sentence for the export notice, from the verification JSON bytes."""
    entry = json.loads(bytes(verification).decode('utf-8'))[0]
    return (f'{entry["tool_comparisons"]} values match the notebook to 1 part in 10⁹; distilled status {entry["status"]}; '
            f'case {entry["case_sha256"][:12]}; package {entry["package_revision"]}.')


WRITERS = {
    'backwall_case.json': lambda e: case_json(e.case).encode('utf-8'),
    'backwall_checks.csv': lambda e: checks_csv(e).encode('utf-8'),
    'backwall_calculation_report.html': _report,
    'backwall_strap_handoff.xlsx': handoff_xlsx,
    DISTILLED_BPAD: lambda e: distilled_bpad(e)[0],
    BPAD_VERIFICATION: lambda e: distilled_bpad(e)[1],
}


def _folder(root):
    folder = Path(root) / f'backwall-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def export_file(e, root, name):
    """Write one export (or the full bundle) to a new timestamped folder; originals are never overwritten."""
    if name == 'backwall_bundle.zip':
        return export_bundle(e, root)['backwall_bundle.zip']
    path = _folder(root) / name
    path.write_bytes(WRITERS[name](e))
    if name == DISTILLED_BPAD:                   # the verification record travels with the sheet
        (path.parent / BPAD_VERIFICATION).write_bytes(WRITERS[BPAD_VERIFICATION](e))
    return path


def export_bundle(e, root):
    folder = _folder(root)
    files = {name: writer(e) for name, writer in WRITERS.items()}
    for name, data in files.items():
        (folder / name).write_bytes(data)
    bundle = folder / 'backwall_bundle.zip'
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return {name: folder / name for name in files} | {'backwall_bundle.zip': bundle}
