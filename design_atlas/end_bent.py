"""Read the selected EB1 case/report without replacing other snapshot evidence."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from design_atlas.origins import classify
from tools.project_coherence import report_case


def extend_end_bent(data, root, labels, category):
    root = Path(root).resolve()
    nodes = {n['id']: n for n in data['nodes']}
    if not all(key in nodes for key in ('EB-CASE', 'EB-REPORT', 'EB-XML')):
        return
    paths = {key: nodes[key]['path'] for key in ('EB-CASE', 'EB-REPORT', 'EB-XML')}
    before = {}
    for path in paths.values():
        source = (root / path).resolve()
        if not source.is_relative_to(root):
            raise ValueError('End-bent source outside repository')
        digest = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
        if digest != data['documents'][path]['sha256']:
            raise RuntimeError('End-bent source changed since this snapshot: ' + path)
        before[path] = digest
    case = json.loads((root / paths['EB-CASE']).read_text(encoding='utf-8-sig'))
    embedded = report_case(root / paths['EB-REPORT'])
    audit = case['analysis']['xml_audit']
    same = case == embedded
    xml_match = bool(before[paths['EB-XML']]) and before[paths['EB-XML']] == audit['sha256']

    def proof(path, locator, value, note=''):
        return {'path': path, 'locator': locator, 'excerpt': json.dumps(value, ensure_ascii=False, indent=2), 'note': note}

    def step(title, node, locator, value, unit='', status='recorded', note=''):
        path = paths['EB-REPORT'] if node == 'EB-REPORT' else paths['EB-CASE']
        return {'title': title, 'node': node, 'value': value, 'unit': unit, 'status': status,
                'note': note, 'evidence': proof(path, locator, value, note)}

    identity = proof(paths['EB-CASE'], '/analysis/xml_audit/sha256', audit['sha256'])
    new_nodes = [
        {'id': 'REQUIRED-EB-XML', 'title': 'End Bent 1 report-matching FBMP run', 'short_title': 'End Bent 1 required run',
         'stage': 'Analysis', 'status': 'match' if xml_match else 'missing',
         'path': paths['EB-XML'] if xml_match else '', 'expected_sha256': audit['sha256'],
         'detail': 'Exact run identified by the saved end-bent case. A different registered XML is not substituted.', 'evidence': [identity]},
        {'id': 'EB-AUDIT', 'title': 'End Bent 1 retained analysis audit', 'short_title': 'End Bent 1 analysis audit',
         'stage': 'Analysis', 'status': 'recorded', 'path': paths['EB-CASE'],
         'detail': 'Governing records and geometry retained inside the selected end-bent case; not independently re-extracted from raw XML.',
         'evidence': [proof(paths['EB-CASE'], '/analysis/xml_audit', {k: v for k, v in audit.items() if k not in {'end_records', 'strength_envelopes', 'governing'}})]}
    ]
    for node in new_nodes:
        node['review'] = 'Engineering review not inferred'
        if node['path']:
            node['document'] = data['documents'][node['path']]
    data['nodes'] = [n for n in data['nodes'] if n['id'] not in {n['id'] for n in new_nodes}] + new_nodes
    data['edges'] = [e for e in data['edges'] if not e['id'].startswith('eb-extracted:')]

    def edge(source, target, status, label, basis, evidence):
        data['edges'].append({'id': 'eb-extracted:' + source + ':' + target, 'source': source, 'target': target,
                              'kind': 'flow', 'status': status, 'label': label, 'basis': basis, 'evidence': evidence})

    for e in data['edges']:
        if e['source'] == 'EB-CASE' and e['target'] == 'EB-REPORT':
            e.update(kind='flow', status='match' if same else 'mismatch',
                     label='Embedded case agrees' if same else 'Embedded case differs',
                     basis='The selected report embedded case was parsed and compared with the saved end-bent case.',
                     evidence=[proof(paths['EB-REPORT'], 'embedded case comparison', {'equals_saved_case': same})])
        if e['source'] == 'EB-XML' and e['target'] in {'EB-CASE', 'EB-REPORT'}:
            e.update(kind='flow', status='match' if xml_match else 'mismatch',
                     label='Source identity matches' if xml_match else 'Required source differs',
                     basis='Required SHA-256 ' + audit['sha256'] + '; registered XML SHA-256 ' + str(before[paths['EB-XML']]), evidence=[identity])
    edge('REQUIRED-EB-XML', 'EB-AUDIT', 'recorded' if xml_match else 'missing', 'Retained source record',
         'Saved case identifies this exact run. Raw demand values have not been independently re-extracted.', [identity])
    edge('EB-AUDIT', 'EB-CASE', 'recorded', 'Recorded analysis import', case['analysis']['notes'],
         [proof(paths['EB-CASE'], '/analysis/notes', case['analysis']['notes'])])
    journal_link = next((e for e in data['edges'] if e['source'] == 'JOURNAL-EB-ENTRY' and e['target'] == 'EB-XML'), None)
    if journal_link:
        edge('JOURNAL-EB-ENTRY', 'REQUIRED-EB-XML', 'recorded', 'Journal node-data handoff', journal_link['basis'], journal_link['evidence'])

    values = []
    for key, val in case['inputs'].items():
        unit = case.get('units', {}).get(key, 'unitless')
        v = {'id': 'EB.inputs.' + key, 'key': key, 'label': labels.get(key, key), 'value': val, 'unit': unit,
             'category': category(key), 'primary_node': 'EB-CASE', 'node_ids': ['EB-CASE'], 'steps': [],
             'source_status': 'saved end-bent case', 'sheet_status': 'not applicable'}
        if key in audit.get('governing', {}):
            gov = audit['governing'][key]
            v.update(governing=gov, audit_agrees=math.isclose(float(gov['adopted']), float(val), abs_tol=1e-9),
                     source_status='retained end-bent audit', transform='Adopted demand retained in the saved analysis audit; no new solver calculation.')
            v['node_ids'].insert(0, 'EB-AUDIT')
            v['steps'].append(step('Recorded governing source', 'EB-AUDIT', '/analysis/xml_audit/governing/' + key, gov,
                                   note='Retained audit, not a fresh extraction from raw XML.'))
            if journal_link:
                v['upstream_context'] = {'node_ids': ['JOURNAL', 'JOURNAL-EB-ENTRY', 'REQUIRED-EB-XML'],
                    'detail': 'The journal supplies end-bent node data to FBMP. This demand is an analysis result, not an identical journal input. The exact journal revision used by the run is unconfirmed.'}
        elif key in case['analysis'].get('geometry', {}):
            v['node_ids'].insert(0, 'EB-AUDIT')
            v['steps'].append(step('Recorded analysis geometry / allowance', 'EB-AUDIT', '/analysis/geometry/' + key, case['analysis']['geometry'][key], unit))
        v['steps'].append(step('Selected end-bent case input', 'EB-CASE', '/inputs/' + key, val, unit))
        if same:
            v['node_ids'].append('EB-REPORT')
            v['steps'].append(step('Report embedded input', 'EB-REPORT', 'embedded case /inputs/' + key, embedded['inputs'][key], unit, 'match'))
        if case.get('transverse_detail', {}).get('enabled') and key in {'Bar_v', 's_G', 's_L'}:
            v['note'] = 'Dormant scalar setting. Enabled transverse runs take precedence.'
        values.append(v)
    for i, run in enumerate(case.get('transverse_detail', {}).get('runs', [])):
        for key in ('bar', 'pitch_in', 'first_in', 'end_in', 'development_confirmed'):
            if key not in run:
                continue
            unit = 'in' if key.endswith('_in') else 'unitless'
            v = {'id': 'EB.run.' + run['id'] + '.' + key, 'key': run['id'] + '.' + key,
                 'label': run['id'] + ' · ' + key.replace('_', ' '), 'value': run[key], 'unit': unit,
                 'category': 'Run details', 'primary_node': 'EB-CASE', 'node_ids': ['EB-CASE'],
                 'source_status': 'enabled run' if case.get('transverse_detail', {}).get('enabled') else 'disabled run',
                 'sheet_status': 'not applicable', 'steps': [step('Saved transverse run', 'EB-CASE', f'/transverse_detail/runs/{i}/{key}', run[key], unit)]}
            if same:
                v['node_ids'].append('EB-REPORT')
                v['steps'].append(step('Report embedded transverse run', 'EB-REPORT', f'embedded case /transverse_detail/runs/{i}/{key}', run[key], unit, 'match'))
            values.append(v)
    # Reuse the same conservative origin rules, substituting component IDs and exact source paths.
    aliases = {'EB-CASE': 'PIER-CASE', 'EB-REPORT': 'PIER-REPORT', 'EB-AUDIT': 'PIER-AUDIT', 'REQUIRED-EB-XML': 'REQUIRED-PIER-XML'}
    reverse = {value: key for key, value in aliases.items()}
    for v in values:
        relative = copy.deepcopy(v)
        relative['id'] = relative['id'].removeprefix('EB.')
        relative['node_ids'] = [aliases[n] for n in v['node_ids']]
        for s in relative['steps']:
            s['node'] = aliases[s['node']]
        roles = classify(relative, case, same, False, case_path=paths['EB-CASE'])
        for role in roles.values():
            if role.get('from_node'):
                role['from_node'] = reverse[role['from_node']]
        v['origins'] = {reverse[n]: role for n, role in roles.items()}
    # When reports diverge, expose their actual embedded values separately, without a claimed handoff.
    if not same:
        for key, val in embedded.get('inputs', {}).items():
            unit = embedded.get('units', {}).get(key, 'unitless')
            s = step('Report embedded input', 'EB-REPORT', 'embedded case /inputs/' + key, val, unit, 'mismatch')
            values.append({'id': 'EB.report.inputs.' + key, 'key': key, 'label': labels.get(key, key), 'value': val, 'unit': unit,
                'category': category(key), 'primary_node': 'EB-REPORT', 'node_ids': ['EB-REPORT'], 'steps': [s],
                'source_status': 'report differs from selected saved case', 'sheet_status': 'not applicable',
                'origins': {'EB-REPORT': {'kind': 'unknown', 'basis': 'The report embedded case differs from the saved case. A received handoff is not established.', 'evidence': [s['evidence']]}}})
    data['values'] = [v for v in data['values'] if not v['id'].startswith('EB.')] + values
    for n in data['nodes']:
        n['value_count'] = sum(n['id'] in v['node_ids'] for v in data['values'])
    data['checks']['end_bent_report_case_equal'] = same
    data['checks']['end_bent_required_xml_present'] = xml_match
    data['coverage']['map'] = 'All registered sources plus explicitly identified pier and End Bent 1 source gaps.'
    coverage = 'End Bent 1 saved case, retained governing audit, embedded report inputs and transverse runs.'
    if coverage not in data['coverage']['values']:
        data['coverage']['values'] += ' ' + coverage
    if not xml_match:
        limit = 'The matching End Bent 1 raw XML is not linked; retained audit records are available.'
        if limit not in data['coverage']['limits']:
            data['coverage']['limits'].append(limit)
    for path, digest in before.items():
        source = root / path
        if (hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None) != digest:
            raise RuntimeError('End-bent source changed during extraction: ' + path)


if __name__ == '__main__':
    import argparse
    from design_atlas.build import LABELS, ROOT, category, validate, write_atlas
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text(encoding='utf-8'))
    extend_end_bent(data, ROOT, LABELS, category)
    validate(data)
    write_atlas(data, args.output)
    print('End Bent 1 values and trace added; other source evidence preserved.')
