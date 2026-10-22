"""Journal edition of the pier-wall annular-ring calculation (journal module C017, report PierWallRings).

    .venv\\Scripts\\python.exe scripts\\build_ring_wall_bpad.py            # ring_wall/bpad/journal/PierWallRings.xml + verification.json
    .venv\\Scripts\\python.exe scripts\\build_ring_wall_bpad.py --check    # rebuild in memory and compare with the committed fragment

The ring_wall package (the engine of Pier_Wall_Design.ipynb) evaluates its starting case; every ledger value and every check
status becomes a native Blockpad definition in the order the ledger evaluates them, with the live project stamp
(Stamp_<Key> = ProjectInfo.<Key>), the hidden working notes and the visible-text rule of scripts/bpad_sheet.py, like the
pile, cap and backwall journal editions. Before anything is written each definition is read back from the XML, evaluated by
the independent Blockpad-syntax evaluator (BpEngine) and compared with the package to 1 part in 10^9; the ProjectInfo strings
of the current journal are compared with the stamp. The fragment is what a journal task copies (tasks/T028).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from lxml import etree as ET  # noqa: E402

import bpad_sheet as bs  # noqa: E402
import mathcad_sheet as ms  # noqa: E402
from ring_wall.calculation_report import GROUPS, check_type  # noqa: E402
from ring_wall.model import analyze, default_case  # noqa: E402
from ring_wall.notation import term  # noqa: E402
from ring_wall.output import case_hash, source_hash  # noqa: E402
from ring_wall.workbench import GROUPS as INPUT_GROUPS  # noqa: E402

REPORT = 'PierWallRings'
NUMBER = 'C017'
TITLE = f'{NUMBER} - Pier Wall, Annular Pile Rings'
JOURNAL = ROOT / 'journal' / 'D2_I95_Project_Journal.bpad'
OUT = ROOT / 'ring_wall' / 'bpad' / 'journal'
TOL = 1e-9
# The notebook's PENDING status (a ring that lost full contact) is a submission-forbidden word even inside a formula, so the
# journal edition names it NO CONTACT; the parity check compares the mapped statuses.
STATUS = {'PASS': 'PASS', 'FAIL': 'FAIL', 'PENDING': 'NO CONTACT'}
# visible prose must not carry working language (scripts/bpad_sheet.SUBMISSION_FORBIDDEN); captions come from the package
VISIBLE_RULES = [('ring moment basis (D-070)', 'ring moment basis'), ('(D-070)', '(former basis)'), ('D-070', 'the 21 October 2026 basis'),
                 ('fixed input in distilled sheets', 'fixed input here'),
                 ('regenerate native sheet after bar-size changes', 'regenerate after bar-size changes'),
                 ('revise/recalculate after selecting', 'recalculate after selecting'),
                 ('Compare with the kern limit', 'Compared with the kern limit')]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chk_name(check_id: str) -> str:
    return 'Chk_' + re.sub(r'[^A-Za-z0-9]+', '_', check_id)


def ring_of(name: str):
    m = re.match(r'ring_(\d+)_(\d+)_', name)
    return (int(m[1]), int(m[2])) if m else None


def row_of(name: str):
    m = re.match(r'row_(\d+)_', name)
    return int(m[1]) if m else None


def caption_of(node: dict, labels: dict) -> str:
    """The input label of the workbench, else the notation meaning, with the unit; the ledger label when it says more."""
    name = node['name']
    meaning = labels.get(name) or term(name)[1]
    unit = node['unit']
    text = meaning if unit in ('—', '') or (labels.get(name) and '(' in meaning) else f'{meaning} [{unit}]'
    label = node['label']
    if label and label != name.replace('_', ' ') and label not in text and not labels.get(name):
        text += f'. {label}'
    for old, new in VISIBLE_RULES:
        text = text.replace(old, new)
    return text


def formula_of(node: dict) -> str:
    expr = node['expr']
    if re.fullmatch(r'-?\d+(\.\d*)?([eE][+-]?\d+)?', expr):
        return f'{node["name"]} = {bs.bp_num(float(expr))}'
    return f'{node["name"]} = {bs.bp_formula(ms.parse(expr))}'


def build(r: dict) -> dict:
    """The journal-edition fragment of an analysis result, verified; returns dict(fragment, verification, document)."""
    p = r['case']
    nodes = r['nodes']
    by_name = {n['name']: n for n in nodes}
    labels = {key: label for sections in INPUT_GROUPS.values() for _, fields in sections for key, label in fields}
    doc = bs.new_document()
    rep = bs.new_report(doc, REPORT, TITLE)
    bs.project_stamp_table(rep, bs.PROJECT_STAMP, live=True)
    bs.para(rep, 'D2 I-95 PEDESTRIAN BRIDGE', fontsize='16', spacingafter='2', fontweight='bold')
    bs.para(rep, TITLE, fontsize='14', spacingafter='6', fontweight='bold')

    # ---- hidden working notes: provenance, status, open items (not part of the submitted text)
    notes = bs.working_notes(rep)
    failed = [c['id'] for c in r['checks'] if c['status'] == 'FAIL']
    pending = [c['id'] for c in r['checks'] if c['status'] == 'PENDING']
    bs.para(notes, f'Journal edition written by scripts/build_ring_wall_bpad.py from the Pier Wall Design notebook package (ring_wall, the engine of '
                   f'Pier_Wall_Design.ipynb), starting case "{p["title"]}", case SHA-256 {case_hash(r)}, package source SHA-256 {source_hash()}. '
                   f'Every definition below was read back from this XML, evaluated by the independent Blockpad-syntax evaluator and compared with the '
                   f'notebook ledger to 1 part in 10⁹ ({len(nodes)} values, {len(r["checks"])} check statuses) before the file was written. '
                   f'Native Blockpad recalculation, appearance review and engineering review were not performed; the equations are the notebook\'s and '
                   f'the ratios are not design acceptance.')
    bs.para(notes, f'Status: {r["overall"]}. Failed checks: {", ".join(failed) or "none"}. Pending (contact lost) checks: {len(pending)}; the '
                   f'notebook writes that status as PENDING, this edition as NO CONTACT (the word is reserved by the submission text rule).')
    bs.para(notes, 'Ring moment basis D-070 (21 October 2026): tributaries assign vertical force only; the radial placement tolerance is a rigid-body '
                   'pile-group redistribution; the ring moment is the pile-head compatibility moment shared equally by the ring rows. The former '
                   'R (|e_n| + Δ_p) moment is kept as M_s for comparison. Wall geometry D-075 (22 October 2026): the CAD pier wall, 219 × 36 in from '
                   'EL 24.5264 (1 ft below terrain) to the cap bottom EL 40.76494 (194.8625 in high), 19.5 in from each wall end to the outer pile; the '
                   'journal gravity sheet row 42 carries the same wall. Pile stiffness defaults come from the pier pile case (PILE-PIER-CASE): '
                   '20 in pipe, 92.4 in from the wall bottom to the equivalent fixity (110.7 in sand depth to fixity below the pile-case ground EL 26.05, '
                   'LRFD C10.7.3.13.4, less the 18.3 in of wall below that ground), 600 in axial spring length as an allowance because the tip elevation '
                   'is pending. The calculation is a tool edition of the notebook; the registered source is the project_current/pier_wall export.')
    for key, text in r['pending']:
        bs.para(notes, f'• {key}: {text}', fontsize='11', spacingafter='4')
    bs.note(notes, 'This calculation covers the welded annular-ring support concept, the concept of the CAD model (D-076, D-079). The fin-plate and '
                   'hairpin hanger concept (the former C006 Pier Wall, Hairpins and Fin Plates) was withdrawn from the project on 22 October 2026 '
                   '(D-082, task T040) and is kept under sequestered/pier_wall_fins/ for revival; calculation numbers are permanent, so C006 is not reused.', size=9)

    # ---- visible design basis
    bs.heading(rep, 'Design basis')
    bs.para(rep, f'Welded annular steel rings carry the self-weight of the {p["length_in"]:g} × {p["thickness_in"]:g} × {p["height_in"]:g} in concrete '
                 f'pier wall onto {p["pile_count"]} steel pipe piles of {p["pile_od_in"]:g} in diameter. Each pile carries {p["ring_count"]} rows of '
                 'annular plates welded with continuous fillets above and below; the wall concrete bears on the plates. This calculation checks full '
                 'annular compression contact, concrete bearing, plate bending and shear at the pipe face, both fillets and the adjacent ring and pipe '
                 'base metal, then the minimum shrinkage and temperature reinforcement, spacing, cover, laps and bar fit of the wall.')
    bs.para(rep, 'Load path. The gross wall prism is divided at midplanes between piles and between ring rows, clipped at the wall edges, and each '
                 'cell\'s factored weight is the vertical force on its ring. The continuous wall carries the offset of a cell centroid from its pile; '
                 'the ring moment is the compatibility moment of the pile head: the rigid wall rotates on the axial and rotational springs of the pile '
                 'heads when the pile group is displaced by the radial placement tolerance, every pile head carries k_θ·θ_w, the ring rows share it '
                 'equally, and the axial redistribution ΔR is added to each tributary reaction. The former basis, R·(|e_n| + Δ_p) at every ring, is '
                 'evaluated as M_s for comparison only.')
    bs.para(rep, 'AASHTO LRFD Bridge Design Specifications, 10th edition (2024): concrete bearing 5.6.5 with the resistance factor of 5.5.4.2 and no '
                 'supporting-area enhancement (m = 1); minimum shrinkage and temperature reinforcement 5.10.6; bar spacing 5.10.3.1.1 and 5.10.3.2; bend '
                 'diameter 5.10.2; development and Class B laps 5.10.8.2.1 and 5.10.8.4.3; fillet weld resistance, minimum and maximum size and length '
                 '6.13.3.2.4, 6.13.3.4 and 6.13.3.5; shear yielding and rupture of the adjacent ring and pipe metal 6.13.5.2 and 6.13.5.3; steel '
                 'resistance factors 6.5.4.2; depth to fixity for the pile free length C10.7.3.13.4. Project cover, grid pitch cap and exposure follow '
                 'the entered values and the FDOT Structures Manual.')
    bs.para(rep, 'Units are inches, kip and ksi; concrete density in kip/ft³; rotations in radians. Ring elevations locate the plate top above the wall '
                 'bottom. Bearing excludes the footprint of the upper fillet; the peak pressure is applied over the whole radial cantilever strip; the two '
                 'fillets form a couple over the plate thickness. Weld legs are specified in sixteenths of an inch. A check reads PASS when demand is '
                 'within capacity and FAIL otherwise or when the available clearance is not positive; a ring whose minimum pressure is negative loses '
                 'full contact and its bearing, plate, weld and base-metal checks read NO CONTACT: their values are trial values until contact is restored.')
    bs.para(rep, 'Outside this calculation: wall flexure, shear and lateral or seismic load paths; concrete splitting, breakout and the transfer below '
                 'the lowest ring; pipe-shell bending and ovalization; global pile interaction, ring-segment splices, fatigue, corrosion and WPS or '
                 'fabrication acceptance; confirmation of the pile stiffness lengths. The fin-plate and hairpin support concept (the former C006) was '
                 'withdrawn from the project on 22 October 2026 and is not evaluated here.')

    # ---- 1. inputs, in the workbench card order
    bs.heading(rep, '1. Inputs')
    written = set()
    for group, sections in INPUT_GROUPS.items():
        for title, fields in sections:
            keys = [k for k, _ in fields if k in by_name]
            if not keys:
                continue
            bs.subheading(rep, f'{group} · {title}')
            for key in keys:
                bs.equation(rep, formula_of(by_name[key]), caption_of(by_name[key], labels), inline=True)
                written.add(key)
    bs.subheading(rep, 'Constants and selections')
    for name in ('schema_version', 'pi_value', 'bar_diameter', 'bar_area', 'selected_pitch', 'coating_factor'):
        if name in by_name and name not in written:
            bs.equation(rep, formula_of(by_name[name]), caption_of(by_name[name], labels), inline=True)
            written.add(name)

    # ---- 2..: the global ledger in evaluation order, grouped by subject
    SUBJECTS = [('2. Minimum wall reinforcement and detailing', lambda n: n in ('steel_L', 'steel_H', 'steel_required', 'code_pitch', 'pitch_limit', 'steel_provided',
                                                                               'clear_required', 'clear_provided', 'ld_basic', 'cb_in', 'lambda_rc', 'ld_horizontal', 'ld_vertical',
                                                                               'lap_horizontal', 'lap_vertical', 'bend_envelope', 'u_width', 'u_leg_available',
                                                                               'vertical_available')),
                ('3. Ring geometry, bearing annulus and fillet weld detailing', lambda n: n in ('pipe_radius', 'inner_radius', 'outer_radius', 'root_gap', 'bearing_inner',
                                                                                              'bearing_area', 'bearing_inertia', 'bearing_limit', 'plate_capacity',
                                                                                              'plate_shear_capacity', 'weld_throat', 'weld_capacity', 'thicker_part',
                                                                                              'minimum_thick_weld', 'minimum_mid_weld', 'minimum_table_weld',
                                                                                              'weld_minimum', 'weld_min_gap', 'weld_maximum', 'weld_length',
                                                                                              'weld_length_min', 'ring_base_capacity', 'pipe_base_capacity',
                                                                                              'pipe_yield_capacity')),
                ('4. Ring cover and cage clearances', lambda n: n in ('end_offset', 'end_clear', 'face_clear', 'grid_gap', 'ring_grid_required', 'bottom_ring_cover',
                                                                      'top_ring_cover', 'between_rings')),
                ('5. Wall weight, pile-head compatibility moment and tolerance redistribution', lambda n: n in ('weight_density', 'factored_density', 'total_service',
                                                                                                                  'total_factored', 'pipe_inner_radius', 'pipe_area',
                                                                                                                  'pipe_inertia', 'pile_axial_stiffness',
                                                                                                                  'pile_rotational_stiffness', 'group_centroid',
                                                                                                                  'group_second_moment', 'tolerance_rotation',
                                                                                                                  'wall_rotation', 'pile_head_moment', 'ring_moment',
                                                                                                                  'kern_limit'))]
    for heading, member in SUBJECTS:
        bs.heading(rep, heading)
        for n in nodes:
            if n['name'] in written or ring_of(n['name']) or row_of(n['name']) or not member(n['name']):
                continue
            bs.equation(rep, formula_of(n), caption_of(n, labels), inline=True)
            written.add(n['name'])
    leftovers = [n['name'] for n in nodes if n['name'] not in written and not ring_of(n['name']) and not row_of(n['name'])]
    if leftovers:
        raise ValueError(f'global ledger values without a section: {leftovers}')

    # ---- 6. rows and rings: tributary actions, contact, plate, welds and trial sizes, in ledger order
    bs.heading(rep, '6. Ring rows and rings: tributary force, compatibility actions, contact pressure, plate, welds and trial sizes')
    bs.note(rep, 'Rows count from the wall bottom and piles from the left wall end. Each row carries its tributary band of the wall height and each ring the '
                 'cell between pile midplanes; the subjects follow the method order: tributary self-weight, superseded comparison moment, tolerance '
                 'redistribution and design reaction, annular contact pressures, plate bending and shear, fillet-weld demand and the trial plate and weld sizes.')
    current = None
    for n in nodes:
        rk, rg = row_of(n['name']), ring_of(n['name'])
        if rk is None and rg is None:
            continue
        key = ('row', rk) if rg is None else ('ring',) + rg
        if key != current:
            current = key
            if key[0] == 'row':
                z = next(a['z'] for a in r['rows'] if a['row'] == key[1])
                bs.subheading(rep, f'Row {key[1]} · plate top {z:g} in above the wall bottom')
            else:
                bs.subheading(rep, f'Ring R{key[1]} / P{key[2]}')
        bs.equation(rep, formula_of(n), caption_of(n, labels), inline=True)
        written.add(n['name'])

    # ---- 7. check register: each check as a native status definition
    bs.heading(rep, '7. Check register')
    bs.note(rep, 'Each check is a definition that reads PASS or FAIL from its demand and capacity; the ring checks that depend on full contact read '
                 'their contact status first. The comparison tolerance is 1e-9 in the check\'s own unit.')
    check_formulas = {}
    groups_done = set()
    wall_checks = [c for c in r['checks'] if not re.match(r'R\d+-P\d+-', c['id'])]
    ring_checks = [c for c in r['checks'] if re.match(r'R\d+-P\d+-', c['id'])]
    bs.subheading(rep, 'Wall reinforcement, detailing, ring cover and weld detailing checks')
    for c in wall_checks + ring_checks:
        m = re.match(r'R(\d+)-P(\d+)-', c['id'])
        if m and ('ring', int(m[1]), int(m[2])) not in groups_done:
            groups_done.add(('ring', int(m[1]), int(m[2])))
            bs.subheading(rep, f'Ring R{m[1]} / P{m[2]} checks')
        d, cap = c['demand_node'], c['capacity_node']
        name = chk_name(c['id'])
        raw = f'IF({cap}>0,IF({d}<={cap}+1e-9,"PASS","FAIL"),"FAIL")'
        status = raw
        if m and not c['id'].endswith('-CONTACT'):
            status = f'IF(ring_{m[1]}_{m[2]}_qmin>=-1e-10,{raw},"{STATUS["PENDING"]}")'
        formula = f'{name} = {bs.bp_formula(ms.parse(status))}'
        bs.equation(rep, formula, f'{c["id"]} · {c["title"]} · {c["ref"]}', inline=True)
        check_formulas[name] = c

    # ---- 8. summary tables (value cells read the definitions above)
    bs.heading(rep, '8. Summary')
    rows = []
    for a in r['rings']:
        pre = f'ring_{a["row"]}_{a["pile"]}_'
        rows.append([f'R{a["row"]} / P{a["pile"]}', ('formula', pre + 'force'), ('formula', pre + 'design_force'), ('formula', 'ring_moment'),
                     ('formula', pre + 'equivalent_e'), ('formula', pre + 'qmax'), ('formula', chk_name(f'R{a["row"]}-P{a["pile"]}-CONTACT')),
                     ('formula', chk_name(f'R{a["row"]}-P{a["pile"]}-WELD')), ('formula', pre + 'weld_required_16')])
    bs.table(rep, 'RingSummary', ['Ring', 'R (kip)', 'R_d (kip)', 'M (kip-in)', 'e_eq (in)', 'q_max (ksi)', 'Contact', 'Weld', 'Weld leg, next 1/16 (in)'],
             rows, [62, 58, 58, 64, 58, 62, 62, 62, 74], palette='output', font='9')
    bs.table(rep, 'WallChecks', ['Check', 'Status'], [[f'{c["id"]} · {c["title"]}', ('formula', chk_name(c['id']))] for c in wall_checks],
             [380, 100], palette='output', font='9')
    bs.note(rep, 'The summary tables repeat the definitions above; the status column of the check register controls.')

    bs.rewrite_visible_text(rep, VISIBLE_RULES)
    bs.check_submission_text(rep)

    # ---- the engine is built from the XML that will be written; the stamp reads the journal's ProjectInfo strings
    eng = bs.BpEngine(report=REPORT)
    for key, text in bs.PROJECT_STAMP.items():
        eng.add_external(f'{bs.PROJECT_INFO}.{key}', text)
    n_defs = 0
    for dyn in rep.iter('dynexp'):
        formula = dyn.get('formula')
        body = dyn.find('expbody')
        if body is None or body.text != formula:
            raise ValueError(f'expbody differs from the formula: {formula!r}')
        eng.add(formula)
        n_defs += 1
    if eng.unresolved_calls():
        raise ValueError(f'undefined functions: {eng.unresolved_calls()}')
    eng.all()
    for name in sorted(eng.defs):
        if re.fullmatch(r'[A-Za-z]{1,3}[0-9]+', name):
            raise ValueError(f'{name} looks like a spreadsheet cell address')
    for el in rep.iter('table', 'textcell', 'section'):
        if el.get('name') in eng.defs:
            raise ValueError(f'{el.tag} name {el.get("name")} is also a definition')
    compared = 0
    for n in nodes:
        got = eng.get(n['name'])
        got = got.v if isinstance(got, bs.Q) else got
        if not isinstance(got, (int, float)) or abs(got - n['value']) > TOL * max(1.0, abs(n['value'])):
            raise ValueError(f'Blockpad value differs from the package: {n["name"]}: {got!r} vs {n["value"]!r}')
        compared += 1
    for name, c in check_formulas.items():
        if eng.get(name) != STATUS[c['status']]:
            raise ValueError(f'Blockpad status differs from the package: {c["id"]}: {eng.get(name)!r} vs {STATUS[c["status"]]!r}')
        compared += 1
    n_cells = bs.write_caches(rep, eng, REPORT)
    tables = [t for t in rep.iter('table') if t.get('name') == 'ProjectStamp']
    cells = bs.stamp_cells(tables[0])
    if [v for _, v, _ in cells] != [bs.PROJECT_STAMP[k] for k in bs.STAMP_KEYS] or [o for _, _, o in cells] != [f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS]:
        raise ValueError('the ProjectStamp cells are not live ProjectInfo references with the expected text')
    for el in rep.iter():
        if not isinstance(el.tag, str):
            raise ValueError('XML comment in the report')
    fragment = bs.serialize(rep, declaration=False).rstrip()
    document = bs.serialize(doc)
    verification = {
        'report_name': REPORT, 'number': NUMBER, 'title': TITLE, 'journal_file': 'journal/D2_I95_Project_Journal.bpad',
        'case_sha256': case_hash(r), 'source_sha256': source_hash(), 'case_title': p['title'],
        'definitions': n_defs, 'ledger_values_compared': compared - len(check_formulas), 'check_statuses_compared': len(check_formulas),
        'cells_and_labels': n_cells, 'tolerance': TOL, 'status': r['overall'], 'failed_checks': failed, 'pending_checks': len(pending),
        'project_stamp': {'owner': bs.PROJECT_INFO, 'live': True}, 'journal_references': [], 'status_words': STATUS,
        'native_application_recalculation': False, 'fragment_sha256': sha(fragment), 'bpad_sha256': sha(document)}
    return dict(fragment=fragment, document=document, verification=verification)


def journal_stamp_gate() -> None:
    """The ProjectInfo strings of the current journal must equal the stamp this edition will show (the live references resolve there)."""
    root = ET.parse(str(JOURNAL)).getroot()
    links = bs.JournalLinks(root, source=str(JOURNAL))
    bad = []
    for key, text in bs.PROJECT_STAMP.items():
        value = links.value(f'{bs.PROJECT_INFO}.{key}')
        if value != text:
            bad.append(f'  {bs.PROJECT_INFO}.{key}: journal {value!r}, stamp {text!r}')
    if bad:
        raise ValueError('the journal ProjectInfo strings differ from the project stamp:\n' + '\n'.join(bad))


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    journal_stamp_gate()
    out = build(analyze(default_case()))
    v = out['verification']
    if '--check' in argv:
        committed = (OUT / f'{REPORT}.xml').read_bytes()
        committed = committed[:-2] if committed.endswith(b'\r\n') else committed[:-1] if committed.endswith(b'\n') else committed
        same = committed == out['fragment']
        print(f'{"current" if same else "STALE"}: ring_wall/bpad/journal/{REPORT}.xml vs a fresh build ({v["fragment_sha256"][:12]})')
        return 0 if same else 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{REPORT}.xml').write_bytes(out['fragment'] + b'\n')
    (OUT / 'verification.json').write_text(json.dumps([v], indent=1, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    (ROOT / 'ring_wall' / 'bpad' / f'{TITLE}.bpad').write_bytes(out['document'])
    print(f'Wrote ring_wall/bpad/journal/{REPORT}.xml: {v["definitions"]} definitions; {v["ledger_values_compared"]} values and '
          f'{v["check_statuses_compared"]} statuses match the package; {v["status"]}; fragment {v["fragment_sha256"][:12]}')
    print(f'Wrote ring_wall/bpad/{TITLE}.bpad (review copy: the stamp references resolve only inside the project journal)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
