"""Conservative, node-relative provenance roles. Absence of a link is not origin."""


def classify(value, case, same_report, receipt_ok, receipt_evidence=None, case_path='project_current/cap_design/pier/selected_case.json'):
    roles = {}
    key = value['key']
    notes = case['analysis']['notes']
    geometry = case['analysis']['geometry']
    governing = case['analysis']['xml_audit'].get('governing', {})

    def role(node, kind, basis, source=None, evidence=None):
        entry = {'kind': kind, 'basis': basis, 'evidence': evidence or []}
        if source:
            entry['from_node'] = source
        roles[node] = entry

    for node in value['node_ids']:
        proof = [s['evidence'] for s in value['steps'] if s['node'] == node]
        role(node, 'unknown', 'The value is recorded here, but its original authoring source is not established by the captured evidence.', evidence=proof)

    case_proof = [s['evidence'] for s in value['steps'] if s['node'] == 'PIER-CASE']
    note_proof = {'path': case_path,
                  'locator': '/analysis/notes', 'excerpt': notes, 'note': 'Saved import policy and retained settings.'}
    if 'PIER-CASE' in roles:
        if key == 'Vu_L':
            role('PIER-CASE', 'derived', 'Local import policy sets low-interval shear equal to global shear (Vu_G). It is not a separately imported low-shear result.', evidence=case_proof + [note_proof])
        elif key in governing:
            if value.get('audit_agrees'):
                role('PIER-CASE', 'received', 'Selected input agrees with the retained adopted demand. The matching raw XML has not been independently re-extracted.', 'PIER-AUDIT', case_proof + [value['steps'][0]['evidence']])
            else:
                role('PIER-CASE', 'unknown', 'A governing record exists, but agreement with an adopted demand is not established.', evidence=case_proof)
        elif key in {'N_pile', 'S_pile', 'D_pile', 'b', 'h'} and key in geometry and value['value'] == geometry[key]:
            role('PIER-CASE', 'received', 'Selected geometry agrees with the saved analysis geometry record; the raw-file handoff is not independently verified.', 'PIER-AUDIT', case_proof + [value['steps'][0]['evidence']])
        elif key in {'E_clear', 'E_detail', 'C_t', 'C_b', 'C_s'} or key in {'phi_f','phi_v','gamma_e','gamma_fat','beta_v','theta','alpha_v','Ao_factor'} or key.startswith(('Bar_', 'n_')) or key in {'s_G','s_L','s_row'}:
            role('PIER-CASE', 'defined', 'Retained local design setting. The saved import notes explicitly retain reinforcement, covers, design factors and end-clearance allowances. First-ever authorship is not recorded.', evidence=case_proof + [note_proof])
        elif value['id'].startswith('run.'):
            role('PIER-CASE', 'defined', 'A saved transverse-run setting, defined in this case. No earlier authoring history is captured.', evidence=case_proof)
        elif value['id'] in {'active_bar','active_pitch'}:
            role('PIER-CASE', 'derived', 'The atlas derives this summary from this node’s saved run settings: ' + value['transform'] + ' It is not an additional stored case input.', evidence=case_proof)

    if 'PIER-AUDIT' in roles:
        proof = [s['evidence'] for s in value['steps'] if s['node'] == 'PIER-AUDIT']
        if key in governing:
            role('PIER-AUDIT', 'derived', 'The retained audit records governing selection, sign/magnitude handling and adoption from the identified FBMP run. This is recorded derivation, not a fresh solver result.', 'REQUIRED-PIER-XML', proof)
        elif key in {'N_pile','S_pile','D_pile','b','h'}:
            role('PIER-AUDIT', 'received', 'Geometry retained from the identified analysis run. Original XML extraction is not independently verified.', 'REQUIRED-PIER-XML', proof)
        else:
            role('PIER-AUDIT', 'defined', 'Retained local clearance allowance, not imported geometry; see the saved analysis notes.', evidence=proof + [note_proof])

    if 'REQUIRED-PIER-XML' in roles:
        role('REQUIRED-PIER-XML', 'unknown', 'Only a retained audit identifies this run. The atlas does not assert an original value definition in the required XML.', evidence=[value['steps'][0]['evidence']])

    if 'PIER-REPORT' in roles:
        report_proof = [s['evidence'] for s in value['steps'] if s['node'] == 'PIER-REPORT']
        if same_report:
            role('PIER-REPORT', 'received', 'The report’s embedded case equals the selected saved case. This establishes matching recorded content, not the chronology of file creation.', 'PIER-CASE', report_proof + case_proof)

    if 'PIER-MATHCAD' in roles:
        proof = [s['evidence'] for s in value['steps'] if s['node'] == 'PIER-MATHCAD']
        proof += [s['mapping'] for s in value['steps'] if s.get('mapping')]
        if receipt_evidence and value.get('value_kind') != 'expression': proof.append(receipt_evidence)
        if value.get('value_kind') == 'expression':
            role('PIER-MATHCAD', 'derived', 'This worksheet region defines the formula shown. Its numerical result has not been evaluated by the atlas or confirmed by native Mathcad recalculation.', evidence=proof)
        elif receipt_ok and value['sheet_status'] == 'match':
            role('PIER-MATHCAD', 'received', 'Explicit input mapping, matching case/worksheet fingerprints and a literal value comparison establish this handoff.', 'PIER-CASE', proof)
        else:
            role('PIER-MATHCAD', 'unknown', 'A mapping may be declared, but the complete receipt and literal-value checks do not establish this transfer.', evidence=proof)
    return roles
