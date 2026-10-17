"""Regression tests for the generated information-lineage graph (lineage/).

Rebuild after any register, decision, tracker, saved-case or Mathcad-export change:
    .venv\\Scripts\\python.exe scripts\\build_lineage_graph.py
"""
import datetime
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REBUILD = r'Rebuild with: .venv\Scripts\python.exe scripts\build_lineage_graph.py'
MARKER = '/*__LINEAGE_DATA__*/'
ISSUE_STATUSES = {'Open', 'Closed', 'Deferred', 'Awaiting source'}
GEOMETRY_CHECK_NAMES = ['b', 'h', 'N_pile', 'D_pile', 'S_pile', 'Pile_embed', 'length']
LINK_KINDS = {'governing', 'mapping', 'formula', 'check', 'source', 'embedded'}
LINK_VALUE_KEYS = ('source_name', 'source_value', 'target_name', 'target_value')
# Printed check text, e.g. "Notebook 48; saved case 48.0. Units: in." or "...; source audit 230 in. Comparison ..."
CHECK_TEXT = re.compile(r'^Notebook (.+?); (?:saved case|source audit) (.+?)\.(?: |$)')


def load_generator():
    """`scripts` is not a package, so load the generator by path."""
    path = ROOT / 'scripts' / 'build_lineage_graph.py'
    spec = importlib.util.spec_from_file_location('build_lineage_graph', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


def leading_number(text):
    """The number a printed value starts with, or None ("369.55" -> 369.55, "235 in + ..." -> 235.0)."""
    m = re.match(r'^\s*(-?\d+(?:\.\d+)?)', str(text or ''))
    return float(m.group(1)) if m else None


class LineageGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = load_generator()
        cls.graph = cls.gen.build()
        cls.written = cls.gen.read_json(cls.gen.OUT_JSON)
        cls.nodes = {n['id']: n for n in cls.graph['nodes']}
        cls.edges = {e['id']: e for e in cls.graph['edges']}
        cls.register = cls.gen.read_csv(cls.gen.REGISTER)
        cls.checks = cls.gen.read_json(cls.gen.CHECKS)['checks']

    def edge(self, edge_id):
        self.assertIn(edge_id, self.edges, f'edge {edge_id} is missing. {REBUILD}')
        return self.edges[edge_id]

    def node(self, node_id):
        self.assertIn(node_id, self.nodes, f'node {node_id} is missing. {REBUILD}')
        return self.nodes[node_id]

    # ------------------------------------------------------------ currency
    def test_outputs_are_current(self):
        ok, why = self.gen.current_outputs_match(self.graph)
        self.assertEqual((ok, why), (True, 'current'), REBUILD)

    # ----------------------------------------------------- nodes and edges
    def test_every_register_source_is_a_node(self):
        ids = [n['id'] for n in self.graph['nodes']]
        self.assertEqual(len(ids), len(set(ids)), 'node ids are not unique. ' + REBUILD)
        for row in self.register:
            with self.subTest(source_id=row['source_id']):
                node = self.node(row['source_id'])
                self.assertIs(node['registered'], True)

    def test_edges_reference_existing_nodes(self):
        edge_ids = [e['id'] for e in self.graph['edges']]
        self.assertEqual(len(edge_ids), len(set(edge_ids)), 'edge ids are not unique. ' + REBUILD)
        for e in self.graph['edges']:
            with self.subTest(edge=e['id']):
                self.assertIn(e['source'], self.nodes)
                self.assertIn(e['target'], self.nodes)
                self.assertNotEqual(e['source'], e['target'], 'self-loop')
                self.assertEqual(e['id'], f"{e['source']}->{e['target']}")

    def test_register_dependencies_become_edges(self):
        checked = 0
        for row in self.register:
            deps = [d.strip() for d in (row['depends_on'] or '').split(';') if d.strip()]
            for dep in deps:
                if dep not in self.nodes:
                    continue
                with self.subTest(dependency=dep, dependent=row['source_id']):
                    e = self.edge(f"{dep}->{row['source_id']}")
                    self.assertEqual(e['kind'], 'depends_on')
                    checked += 1
        self.assertGreater(checked, 0, 'the register declares no dependencies that are nodes')

    # ------------------------------------------------------------- health
    def test_health_follows_machine_checks(self):
        source_checks = {}
        for chk in self.checks:
            if chk['check_id'].startswith('SOURCE:'):
                source_checks[chk['check_id'].split(':', 1)[1]] = chk['status']
        self.assertTrue(source_checks, 'machine_checks.json has no SOURCE checks')
        for sid, status in source_checks.items():
            with self.subTest(source_id=sid):
                self.assertEqual(self.node(sid)['health'], status, REBUILD)
        for nid, node in self.nodes.items():
            if nid in source_checks:
                continue
            with self.subTest(unchecked=nid):
                self.assertIn(node['health'], {'NONE', 'EMULATED'})

    # ---------------------------------------------------- analysis identity
    def test_analysis_identity_flags(self):
        pier = self.edge('PIER-XML->PIER-CASE')
        self.assertIn('identity-mismatch', pier['flags'])
        self.assertIs(pier['analysis_identity']['match'], False)

        eb2 = self.edge('EB2-XML->EB2-CASE')
        self.assertIs(eb2['analysis_identity']['match'], True)
        self.assertIs(eb2['analysis_identity']['file_present'], False)

        eb = self.edge('EB-XML->EB-CASE')
        self.assertIn('identity-mismatch', eb['flags'])

    # ------------------------------------------------------------- Mathcad
    def test_mathcad_mapping_edges(self):
        if not self.gen.MATHCAD_EXPORT.exists():
            self.skipTest(f'{rel(self.gen.MATHCAD_EXPORT)} is not present')
        for nid in ('MCAD-CAP-EB1', 'MCAD-CAP-EB2', 'MCAD-CAP-PIER'):
            with self.subTest(node=nid):
                node = self.node(nid)
                self.assertEqual(node['health'], 'EMULATED')
                self.assertIs(node['registered'], False)
        for case_id, nid in (('EB-CASE', 'MCAD-CAP-EB1'), ('EB2-CASE', 'MCAD-CAP-EB2'),
                             ('PIER-CASE', 'MCAD-CAP-PIER')):
            with self.subTest(edge=f'{case_id}->{nid}'):
                e = self.edge(f'{case_id}->{nid}')
                self.assertEqual(e['kind'], 'mapping')
                self.assertEqual(len(e['parameters']), 58)
                self.assertIs(e['case_identity']['match'], True)
                case_names = {p['name'] for p in self.node(case_id)['parameters']}
                from_case = [p for p in e['parameters'] if p['basis'].startswith('Selected case inputs.')]
                self.assertTrue(from_case, 'no mapping parameter is taken from the selected case')
                for p in from_case:
                    self.assertIn(p['name'], case_names, f"mapping parameter {p['name']} is not a case input")

    # ------------------------------------------------------------ backwall
    def test_backwall_parameter_provenance(self):
        node = self.node('BACKWALL-CASE')
        self.assertTrue(node['parameters'], 'BACKWALL-CASE has no parameters')
        for p in node['parameters']:
            with self.subTest(parameter=p['name']):
                self.assertIn('source_text', p)
        eb = self.edge('EB-CASE->BACKWALL-CASE')
        self.assertEqual(eb['kind'], 'parameter')
        self.assertGreaterEqual(len(eb['parameters']), 1)
        cad = self.edge('CAD-MODEL->BACKWALL-CASE')
        self.assertGreaterEqual(len(cad['parameters']), 1)

    # ------------------------------------------------------------ geometry
    def test_geometry_check_edges(self):
        for edge_id in ('GEOMETRY->PIER-CASE', 'GEOMETRY->EB-CASE'):
            with self.subTest(edge=edge_id):
                e = self.edge(edge_id)
                self.assertEqual(e['kind'], 'check')
                names = {p['name'] for p in e['parameters']}
                for name in GEOMETRY_CHECK_NAMES:
                    self.assertIn(name, names)

    # ------------------------------------------------------- FBMP envelopes
    def present_xml_nodes(self):
        return [n for n in self.graph['nodes'] if n['kind'] == 'analysis' and n['path'] and (ROOT / n['path']).exists()]

    def test_fbmp_envelope_parameters(self):
        if not self.gen.ENVELOPE_NOTEBOOK.exists():
            self.skipTest(f'{rel(self.gen.ENVELOPE_NOTEBOOK)} is not present')
        present = self.present_xml_nodes()
        if not present:
            self.skipTest('no registered FBMP XML is present')
        self.assertIn(rel(self.gen.ENVELOPE_NOTEBOOK), {i['path'] for i in self.graph['inputs']},
                      'the envelope notebook is an input of the graph')
        for node in present:
            with self.subTest(node=node['id']):
                src = node['envelope_source']
                self.assertIs(src['available'], True, src.get('reason', ''))
                digest = self.gen.sha256_file(ROOT / node['path'])
                self.assertEqual(src['sha256'], digest, REBUILD)
                self.assertEqual(src['register_match'], digest == node['sha256'])
                identity = node['parameters'][0]
                self.assertEqual(identity['role'], 'identity')
                self.assertEqual(identity['value'], digest)
                for p in node['parameters']:
                    self.assertEqual(p['xml_sha256'], digest, f"{p['name']} does not carry the XML hash")
                rows = [p for p in node['parameters'] if p['role'] == 'envelope']
                self.assertGreater(len(rows), 0)
                self.assertEqual(len(rows), src['envelope_rows'])
                self.assertEqual({r['component'] for r in rows}, {'M2', 'M3', 'V2', 'V3', 'T'})
                self.assertLessEqual({'Strength', 'Service'}, {r['family'] for r in rows})
                self.assertIn('PIER_CAP', {r['member'] for r in rows})
                for r in rows:
                    self.assertLessEqual(r['min'], r['max'])
                    self.assertEqual(r['abs_max'], max(abs(r['min']), abs(r['max'])))
                    for key in ('min_load_case', 'min_combination', 'max_load_case', 'max_combination',
                                'abs_max_load_case', 'abs_max_combination', 'limit_state', 'unit'):
                        self.assertTrue(r[key], f"{r['name']} lacks {key}")
                self.assertGreater(len([p for p in node['parameters'] if p['role'] == 'summary']), 0)

    def test_xml_identity_row_agrees_with_case_edge(self):
        present = self.present_xml_nodes()
        if not present:
            self.skipTest('no registered FBMP XML is present')
        for node in present:
            case_id = self.gen.CASE_OF_XML.get(node['id'])
            src = node['envelope_source']
            status = node['parameters'][0]['status']
            with self.subTest(node=node['id'], case=case_id):
                if not case_id or f"{node['id']}->{case_id}" not in self.edges:
                    self.assertIsNone(src['case_match'])
                    self.assertTrue(status.startswith('VARIANT'))
                    continue
                e = self.edge(f"{node['id']}->{case_id}")
                required = e['analysis_identity']['case_requires_sha256']
                self.assertEqual(src['case_requires_sha256'], required)
                self.assertEqual(src['case_match'], src['sha256'] == required)
                # The node-level row must say what the edge flag says: a mismatch stays visible.
                self.assertEqual(status.startswith('MISMATCH'), 'identity-mismatch' in e['flags'])
                self.assertEqual(status.startswith('MATCH'), e['analysis_identity']['match'])
                self.assertIn(required, node['parameters'][0]['detail'])

    # ---------------------------------------------------- cap formula trace
    def test_cap_formula_trace_parameters(self):
        if not self.graph['cap_trace']['available']:
            self.skipTest('pier_cap is not importable here: ' + self.graph['cap_trace']['reason'])
        cases = [(cid, p) for cid, p in self.gen.CASE_FILES.items() if p.exists()]
        if not cases:
            self.skipTest('no registered saved cap case is present')
        derived = {d['id']: d for d in self.graph['derived']}
        for case_id, _ in cases:
            with self.subTest(case=case_id):
                node = self.node(case_id)
                ft = node['formula_trace']
                if not ft['available']:
                    # The generator records why rather than guessing; the README must list it.
                    self.assertTrue(ft['reason'])
                    self.assertNotIn(f'JOURNAL->{case_id}', self.edges)
                    continue
                rows = [p for p in node['parameters'] if p.get('role') == 'formula']
                self.assertGreater(len(rows), 0)
                self.assertEqual(len(rows), ft['entries'])
                names = [r['name'] for r in rows]
                self.assertEqual(len(names), len(set(names)), 'trace names are not unique')
                for r in rows:
                    self.assertIn('formula', r)
                    self.assertIn('note', r)
                inputs = {p['name'] for p in node['parameters'] if p.get('role') == 'input'}
                self.assertLessEqual({'b', 'h'}, set(names) & inputs, 'cap width and depth are traced inputs')
                journal = [r for r in rows if self.gen.JOURNAL_REF.search(r['formula'])]
                self.assertEqual(len(journal), ft['journal_references'])
                self.assertGreater(len(journal), 0, 'no cap formula names a journal module')
                e = self.edge(f'JOURNAL->{case_id}')
                self.assertEqual(e['kind'], 'parameter')
                self.assertEqual([p['name'] for p in e['parameters']], [r['name'] for r in journal])
                for p in e['parameters']:
                    self.assertIn(f"{p['module']}.{p['variable']}", p['formula'])
                    self.assertEqual(p['value'], next(r['value'] for r in rows if r['name'] == p['name']))
                self.assertEqual(derived[f'formula-trace:{case_id}']['sha256'], ft['sha256'])
                self.assertEqual(ft['package_sha256'], self.graph['cap_package']['sha256'])
        self.assertIn('derived:', '\n'.join(['derived:'] if self.graph['derived'] else []),
                      'traces are part of the fingerprint')

    # ------------------------------------------------------- parameter links
    def links_on(self, edge_id):
        self.edge(edge_id)
        return [l for l in self.graph['links'] if l['edge'] == edge_id]

    def links_into(self, node_id, name):
        return [l for l in self.graph['links'] if l['target'] == node_id and l['target_name'] == name]

    def links_out_of(self, node_id, name):
        return [l for l in self.graph['links'] if l['source'] == node_id and l['source_name'] == name]

    def upstream(self, node_id, name):
        """Every (node, name) a quantity comes from, found only by matching (node, name) through links."""
        seen, todo = set(), [(node_id, name)]
        while todo:
            for l in self.links_into(*todo.pop()):
                here = (l['source'], l['source_name'])
                if l['source_name'] and here not in seen:
                    seen.add(here)
                    todo.append(here)
        return seen

    def downstream(self, node_id, name):
        """Every (node, name) a quantity is carried into, found only by matching (node, name) through links."""
        seen, todo = set(), [(node_id, name)]
        while todo:
            for l in self.links_out_of(*todo.pop()):
                here = (l['target'], l['target_name'])
                if here not in seen:
                    seen.add(here)
                    todo.append(here)
        return seen

    def case_inputs(self, node_id):
        return {p['name']: p for p in self.node(node_id)['parameters'] if p.get('role') == 'input'}

    def xml_has_envelope(self, node_id):
        return any(p.get('role') == 'envelope' for p in self.node(node_id)['parameters'])

    def test_links_reference_edge_parameters(self):
        links = self.graph['links']
        self.assertTrue(links, 'the graph has no parameter links. ' + REBUILD)
        for l in links:
            with self.subTest(edge=l['edge'], index=l['index']):
                e = self.edge(l['edge'])
                self.assertEqual((l['source'], l['target']), (e['source'], e['target']), REBUILD)
                self.assertIn(l['kind'], LINK_KINDS)
                self.assertIsInstance(l['index'], int)
                self.assertTrue(0 <= l['index'] < len(e['parameters']),
                                f"index {l['index']} is outside the {len(e['parameters'])} parameters of {l['edge']}")
                self.assertTrue(l['target_name'], 'a link is always named on its target side')
                p = e['parameters'][l['index']]
                for key in LINK_VALUE_KEYS:
                    self.assertIn(key, p, f"{l['edge']}[{l['index']}] does not carry {key}. {REBUILD}")
                    self.assertEqual(p[key], l[key], f"{key} differs between link and edge parameter. {REBUILD}")

    def test_governing_links(self):
        if not self.xml_has_envelope('PIER-XML'):
            self.skipTest('PIER-XML has no envelope rows here (XML or envelope notebook not present)')
        for edge_id in ('PIER-XML->PIER-CASE', 'EB-XML->EB-CASE', 'EB2-XML->EB2-CASE'):
            with self.subTest(edge=edge_id):
                e = self.edge(edge_id)
                links = self.links_on(edge_id)
                self.assertEqual(len(links), len(e['parameters']), REBUILD)
                for l in links:
                    with self.subTest(edge=edge_id, name=l['target_name']):
                        p = e['parameters'][l['index']]
                        self.assertEqual(l['kind'], 'governing')
                        self.assertEqual(l['target_name'], p['name'])
                        self.assertEqual(l['target_value'], p['value'])
                        if l['source_value']:
                            a, b = leading_number(l['source_value']), leading_number(l['target_value'])
                            self.assertIsNotNone(a, f"source value {l['source_value']!r} is not a number")
                            self.assertIsNotNone(b, f"target value {l['target_value']!r} is not a number")
                            same = abs(abs(a) - abs(b)) <= 0.011
                            self.assertEqual(l['status'], 'MATCH' if same else 'DIFFERS', REBUILD)
                        else:
                            self.assertEqual(l['status'], '', 'a link with nothing to compare has no status')
        with self.subTest(edge='PIER-XML->PIER-CASE', check='registered XML is a prior export'):
            links = {l['target_name']: l for l in self.links_on('PIER-XML->PIER-CASE')}
            self.assertEqual(len(links), 9, REBUILD)
            mu_b = links['Mu_B']
            self.assertEqual((mu_b['source_name'], mu_b['source_value'], mu_b['target_value'], mu_b['status']),
                             ('PIER_CAP: M3 STRENGTH-I', '369.55', '366.16', 'DIFFERS'), REBUILD)
            self.assertEqual(mu_b['target_value'], self.case_inputs('PIER-CASE')['Mu_B']['value'])
            for name in ('Mu_P', 'MI_P'):
                with self.subTest(name=name):
                    l = links[name]
                    self.assertTrue(l['source_name'], 'the envelope row is still named')
                    self.assertEqual((l['source_value'], l['status']), ('', ''), REBUILD)
                    self.assertIn('interior extremum', l['detail'])
        with self.subTest(edge='EB2-XML->EB2-CASE', check='XML missing'):
            if (ROOT / self.node('EB2-XML')['path']).exists():
                self.skipTest('EB2-XML is present here')
            for l in self.links_on('EB2-XML->EB2-CASE'):
                self.assertEqual((l['source_name'], l['source_value'], l['status']), ('', '', ''), REBUILD)
                self.assertIn('not present', l['detail'])

    def test_mapping_links(self):
        if not self.gen.MATHCAD_EXPORT.exists():
            self.skipTest(f'{rel(self.gen.MATHCAD_EXPORT)} is not present')
        for case_id, nid in (('EB-CASE', 'MCAD-CAP-EB1'), ('EB2-CASE', 'MCAD-CAP-EB2'), ('PIER-CASE', 'MCAD-CAP-PIER')):
            edge_id = f'{case_id}->{nid}'
            with self.subTest(edge=edge_id):
                e = self.edge(edge_id)
                links = self.links_on(edge_id)
                self.assertEqual(len(links), 58, REBUILD)
                self.assertEqual(len(links), len(e['parameters']))
                inputs = self.case_inputs(case_id)
                from_case = 0
                for l in links:
                    p = e['parameters'][l['index']]
                    with self.subTest(edge=edge_id, parameter=p['name'], region=p['region']):
                        self.assertEqual(l['kind'], 'mapping')
                        lhs, sep, rhs = p['after'].partition(':=')
                        self.assertEqual(sep, ':=', 'a Mathcad mapping row is a definition')
                        self.assertEqual(l['target_name'], lhs.strip())
                        self.assertEqual(l['target_value'], rhs.strip())
                        self.assertEqual(l['status'], 'CHANGED' if p['changed'] else 'UNCHANGED')
                        if p['basis'].startswith('Selected case inputs.'):
                            from_case += 1
                            self.assertEqual(l['source_name'], p['name'])
                            self.assertIn(p['name'], inputs, f"mapping parameter {p['name']} is not a case input")
                            self.assertEqual(l['source_value'], inputs[p['name']]['value'], REBUILD)
                        else:
                            self.assertEqual(l['source_name'], '', 'a derived region cannot name its source')
                            self.assertEqual(l['source_value'], '')
                            self.assertIn(p['basis'], l['detail'])
                self.assertGreater(from_case, 0, 'no mapping link is taken from the selected case')

    def test_formula_links(self):
        if not self.graph['cap_trace']['available']:
            self.skipTest('pier_cap is not importable here: ' + self.graph['cap_trace']['reason'])
        checked = 0
        for case_id in ('PIER-CASE', 'EB-CASE', 'EB2-CASE'):
            edge_id = f'JOURNAL->{case_id}'
            if edge_id not in self.edges:
                continue  # the generator records why on the case's formula_trace
            checked += 1
            with self.subTest(edge=edge_id):
                e = self.edge(edge_id)
                links = self.links_on(edge_id)
                self.assertEqual(len(links), 5, REBUILD)
                self.assertEqual(len(links), len(e['parameters']))
                for l in links:
                    p = e['parameters'][l['index']]
                    with self.subTest(edge=edge_id, parameter=p['name']):
                        self.assertEqual(l['kind'], 'formula')
                        self.assertEqual(l['source_name'], f"{p['module']}.{p['variable']}")
                        self.assertEqual(l['target_name'], p['name'])
                        self.assertEqual(l['target_value'], p['value'])
                        self.assertEqual(l['source_value'], '', 'the graph does not read the journal value')
                        self.assertIn(l['source_name'], l['detail'])
        self.assertGreater(checked, 0, 'no journal-to-case edge exists although the cap trace is available')

    def test_check_links(self):
        expected_b = {'GEOMETRY->PIER-CASE': ('48', '48.0'), 'GEOMETRY->EB-CASE': ('42', '42.0')}
        for edge_id, (notebook_b, case_b) in expected_b.items():
            with self.subTest(edge=edge_id):
                e = self.edge(edge_id)
                links = self.links_on(edge_id)
                self.assertEqual(len(links), 7, REBUILD)
                self.assertEqual(len(links), len(e['parameters']))
                self.assertEqual({l['kind'] for l in links}, {'check'})
                self.assertEqual([l['source_name'] for l in links], [p['name'] for p in e['parameters']])
                self.assertEqual({l['source_name'] for l in links}, set(GEOMETRY_CHECK_NAMES))
                for l in links:
                    self.assertEqual(l['target_name'], l['source_name'], 'the notebook and the case use one name')
                with self.subTest(edge=edge_id, name='b'):
                    b = next(l for l in links if l['source_name'] == 'b')
                    self.assertEqual((b['source_value'], b['target_value'], b['status']), (notebook_b, case_b, 'MATCH'), REBUILD)
                for l in links:
                    with self.subTest(edge=edge_id, printed_values=l['source_name']):
                        p = e['parameters'][l['index']]
                        self.assertEqual(l['status'], p['status'])
                        m = CHECK_TEXT.match(p['detail'])
                        self.assertIsNotNone(m, f"cannot read the printed values from {p['detail']!r}")
                        # The whole printed value, not a prefix of it: "4.5" must not become "4".
                        self.assertEqual((l['source_value'], l['target_value']), m.groups(), REBUILD)

    def test_source_links(self):
        edge_id = 'EB-CASE->BACKWALL-CASE'
        e = self.edge(edge_id)
        links = self.links_on(edge_id)
        inputs = self.case_inputs('EB-CASE')
        self.assertEqual(len(links), len(e['parameters']))
        by_target = {l['target_name']: l for l in links}
        b_cap = by_target['b_cap']
        self.assertEqual((b_cap['kind'], b_cap['source_name'], b_cap['source_value']), ('source', 'b', '42'), REBUILD)
        self.assertEqual(b_cap['source_value'], inputs['b']['value'])
        for l in links:
            with self.subTest(edge=edge_id, name=l['target_name']):
                self.assertEqual(l['kind'], 'source')
                if l['source_name']:
                    self.assertIn(l['source_name'], inputs, 'a named source is an input of the saved case')
                    self.assertEqual(l['source_value'], inputs[l['source_name']]['value'], REBUILD)
        cad_id = 'CAD-MODEL->BACKWALL-CASE'
        cad = self.edge(cad_id)
        cad_links = self.links_on(cad_id)
        self.assertEqual(len(cad_links), len(cad['parameters']))
        self.assertGreaterEqual(len(cad_links), 1)
        for l in cad_links:
            with self.subTest(edge=cad_id, name=l['target_name']):
                self.assertEqual(l['kind'], 'source')
                self.assertEqual((l['source_name'], l['source_value']), ('', ''), 'the CAD model is described in prose')
                self.assertTrue(l['detail'], 'a link that cannot name its source says why')
        for l in self.graph['links']:
            if l['kind'] == 'source':
                with self.subTest(edge=l['edge'], name=l['target_name']):
                    p = self.edge(l['edge'])['parameters'][l['index']]
                    self.assertEqual(l['target_value'], p.get('value', ''))
                    self.assertEqual(l['status'], p.get('status', ''))
                    if not l['source_name']:
                        self.assertEqual(l['source_value'], '')

    def test_embedded_links(self):
        # A report carries every input of the case it embeds, under the same name and value, so a
        # report's Inputs are never empty and a trail through a report reaches the case.
        checks = {c['check_id']: c for c in self.checks}
        for case_id, (report_id, check_id) in self.gen.REPORT_OF_CASE.items():
            edge_id = f'{case_id}->{report_id}'
            if case_id not in self.nodes or report_id not in self.nodes:
                continue
            with self.subTest(edge=edge_id):
                links = [l for l in self.links_on(edge_id) if l['kind'] == 'embedded']
                inputs = self.case_inputs(case_id)
                self.assertEqual({l['target_name'] for l in links}, set(inputs), REBUILD)
                for l in links:
                    self.assertEqual(l['source_name'], l['target_name'])
                    self.assertEqual(l['source_value'], l['target_value'])
                    self.assertEqual(l['target_value'], inputs[l['target_name']]['value'])
                    self.assertTrue(l['detail'], 'an embedded link says how the report and case were compared')
                statuses = {l['status'] for l in links}
                if check_id in checks:
                    self.assertEqual(statuses, {checks[check_id]['status']}, REBUILD)
                else:
                    self.assertEqual(statuses, {'NOT COMPARED'}, REBUILD)
        with self.subTest(chain='BACKWALL-REPORT b_cap <- BACKWALL-CASE b_cap <- EB-CASE b'):
            self.assertLessEqual({('BACKWALL-CASE', 'b_cap'), ('EB-CASE', 'b')}, self.upstream('BACKWALL-REPORT', 'b_cap'), REBUILD)

    def test_trail_continuity(self):
        # Each hop is found by matching (node, name) alone: the name a link writes on its target side
        # is the name the next link reads on its source side.
        with self.subTest(chain='BACKWALL-CASE b_cap <- EB-CASE b'):
            into_cap = self.links_into('BACKWALL-CASE', 'b_cap')
            self.assertIn(('EB-CASE', 'b'), [(l['source'], l['source_name']) for l in into_cap], REBUILD)
            feeds_b = {(l['source'], l['kind'], l['source_name']) for l in self.links_into('EB-CASE', 'b')}
            want = {('GEOMETRY', 'check', 'b')}
            if 'JOURNAL->EB-CASE' in self.edges:
                want.add(('JOURNAL', 'formula', 'BridgeGeometry_2Beam.PierCap_width'))
            self.assertLessEqual(want, feeds_b, REBUILD)
            reached = self.upstream('BACKWALL-CASE', 'b_cap')
            self.assertLessEqual({('EB-CASE', 'b'), ('GEOMETRY', 'b')}, reached, REBUILD)
        with self.subTest(chain='PIER-CASE Mu_B <- PIER-XML envelope row'):
            into = self.links_into('PIER-CASE', 'Mu_B')
            self.assertEqual({(l['source'], l['kind']) for l in into}, {('PIER-XML', 'governing')}, REBUILD)
            if self.xml_has_envelope('PIER-XML'):
                self.assertEqual({l['source_name'] for l in into}, {'PIER_CAP: M3 STRENGTH-I'}, REBUILD)
        if not self.gen.MATHCAD_EXPORT.exists():
            self.skipTest(f'{rel(self.gen.MATHCAD_EXPORT)} is not present')
        with self.subTest(chain='PIER-XML -> PIER-CASE Mu_B -> MCAD-CAP-PIER'):
            out = {(l['target'], l['target_name'], l['kind']) for l in self.links_out_of('PIER-CASE', 'Mu_B')}
            # The case input reaches the Mathcad sheet (renamed) and the report (embedded, same name).
            self.assertLessEqual({('MCAD-CAP-PIER', 'indexer(Mu, 2)', 'mapping'), ('PIER-REPORT', 'Mu_B', 'embedded')}, out, REBUILD)
            self.assertIn(('MCAD-CAP-PIER', 'indexer(Mu, 2)'), self.downstream('PIER-CASE', 'Mu_B'))
            reached = self.upstream('MCAD-CAP-PIER', 'indexer(Mu, 2)')
            self.assertIn(('PIER-CASE', 'Mu_B'), reached, REBUILD)
            if self.xml_has_envelope('PIER-XML'):
                self.assertIn(('PIER-XML', 'PIER_CAP: M3 STRENGTH-I'), reached, REBUILD)

    def test_links_sorted_and_counted(self):
        links = self.graph['links']
        keys = [(l['edge'], l['index']) for l in links]
        self.assertEqual(keys, sorted(keys), 'links are not sorted by (edge, index). ' + REBUILD)
        self.assertEqual(len(keys), len(set(keys)), 'an edge parameter has more than one link')
        expected_kinds = set(LINK_KINDS)
        if not self.gen.MATHCAD_EXPORT.exists():
            expected_kinds.discard('mapping')
        if not self.graph['cap_trace']['available']:
            expected_kinds.discard('formula')
        self.assertEqual({l['kind'] for l in links}, expected_kinds, REBUILD)
        keyed = 0
        for e in self.graph['edges']:
            for i, p in enumerate(e['parameters']):
                present = [key in p for key in LINK_VALUE_KEYS]
                with self.subTest(edge=e['id'], index=i):
                    self.assertIn(sum(present), (0, len(LINK_VALUE_KEYS)), 'an edge parameter carries only some link keys')
                keyed += any(present)
        self.assertEqual(len(links), keyed, 'links and name-carrying edge parameters differ. ' + REBUILD)

    # ------------------------------------------------- decisions and issues
    def test_decisions_parsed(self):
        decisions = self.graph['decisions']
        self.assertGreaterEqual(len(decisions), 40)
        self.assertEqual([d['id'] for d in decisions],
                         [f'D-{i:03d}' for i in range(1, len(decisions) + 1)],
                         'decision ids are not consecutive from D-001')
        for d in decisions:
            with self.subTest(decision=d['id']):
                self.assertRegex(d['date'], r'^\d{4}-\d{2}-\d{2}$')
                datetime.date.fromisoformat(d['date'])
                for sid in d['refs']['sources']:
                    self.assertIn(sid, self.nodes)
                for sid in d['refs']['inferred']:
                    self.assertIn(sid, d['refs']['sources'], 'inferred sources are merged into refs.sources')

    def test_decisions_attach_to_nodes(self):
        # D-001 only names project_current itself; every other decision governs a node.
        unlinked = [d['id'] for d in self.graph['decisions'] if not d['refs']['sources'] and d['id'] != 'D-001']
        self.assertEqual(unlinked, [], f'decisions without a node: {unlinked}. Add them to DECISION_SOURCES. {REBUILD}')
        linked_back = {d['id'] for d in self.graph['decisions'] if d['refs']['sources']}
        on_nodes = {did for n in self.graph['nodes'] for did in n['decisions']}
        self.assertEqual(linked_back, on_nodes & linked_back, 'nodes do not list every decision that references them')

    def test_issues_parsed(self):
        issues = self.graph['issues']
        self.assertTrue(issues, 'no issues parsed from items_snapshot.csv')
        self.assertEqual([i['id'] for i in issues],
                         [f'COH-{n:03d}' for n in range(1, len(issues) + 1)],
                         'issue ids are not consecutive from COH-001')
        status_of = {i['id']: i['status'] for i in issues}
        for i in issues:
            with self.subTest(issue=i['id']):
                self.assertIn(i['status'], ISSUE_STATUSES)
                for sid in i['refs']['sources']:
                    self.assertIn(sid, self.nodes)
                if i['checks']:
                    # TRACKER checks flag closed items that lack evidence.
                    self.assertEqual(i['status'], 'Closed')
        for nid, node in self.nodes.items():
            with self.subTest(node=nid):
                self.assertLessEqual(set(node['open_issues']), set(node['issues']))
                for iid in node['open_issues']:
                    self.assertNotEqual(status_of[iid], 'Closed')

    # ---------------------------------------------------------- supplements
    def test_supplement_nodes_are_tagged(self):
        for nid in ('RFQ', 'FBMP-TOOL'):
            with self.subTest(node=nid):
                node = self.node(nid)
                self.assertIs(node['registered'], False)
                self.assertEqual(node['health'], 'NONE')
        for e in self.graph['edges']:
            touches_unregistered = not (self.nodes[e['source']]['registered'] and self.nodes[e['target']]['registered'])
            if touches_unregistered and e['kind'] == 'supplement':
                with self.subTest(edge=e['id']):
                    self.assertIn('unregistered', e['flags'])

    def test_stages_cover_all_nodes(self):
        stage_ids = [s['id'] for s in self.graph['stages']]
        self.assertEqual(stage_ids, [sid for sid, _ in self.gen.STAGES], 'stages are not in STAGES order')
        for nid, node in self.nodes.items():
            with self.subTest(node=nid):
                self.assertIn(node['stage'], stage_ids)

    # --------------------------------------------------- fingerprint, inputs
    def test_fingerprint_and_inputs(self):
        self.assertRegex(self.graph['fingerprint'], r'^[0-9a-f]{64}$')
        self.assertTrue(self.graph['inputs'], 'the graph records no inputs')
        recorded = set()
        for rec in self.graph['inputs']:
            with self.subTest(path=rec['path']):
                path = ROOT / rec['path']
                self.assertTrue(path.exists(), f"input {rec['path']} does not exist")
                self.assertEqual(rec['sha256'], self.gen.sha256_file(path), REBUILD)
                recorded.add(rec['path'])
        for path in (self.gen.REGISTER, self.gen.DECISIONS, self.gen.ITEMS, self.gen.CHECKS):
            with self.subTest(required=rel(path)):
                self.assertIn(rel(path), recorded)

    # ------------------------------------------------------------ index.html
    def test_index_html_embeds_graph(self):
        template = self.gen.TEMPLATE.read_text(encoding='utf-8')
        self.assertEqual(template.count(MARKER), 1, f'viewer.html must contain {MARKER} exactly once')
        self.assertIn('id="lineage-data"', template)
        html = self.gen.OUT_HTML.read_text(encoding='utf-8')
        self.assertEqual(html, self.gen.render_html(self.written), REBUILD)
        self.assertNotIn(MARKER, html)

    # ------------------------------------------------------------ sign-offs
    @staticmethod
    def write_sidecar(path, entries, schema=None):
        doc = {'schema': 'd2mpdb.lineage-signoff' if schema is None else schema, 'schema_version': 1, 'signoffs': entries}
        path.write_text(json.dumps(doc, indent=2), encoding='utf-8')

    def signed_items(self, graph):
        return {x['id']: x['signoff'] for x in graph['nodes'] + graph['edges'] if 'signoff' in x}

    def test_signoff_sidecar_is_valid_and_merged(self):
        self.assertTrue(self.gen.SIGNOFF.exists(), f'{rel(self.gen.SIGNOFF)} is missing')
        sidecar = self.gen.load_signoffs(self.gen.SIGNOFF)
        summary = self.graph['signoff']
        self.assertEqual(summary['schema'], self.gen.SIGNOFF_SCHEMA)
        self.assertIs(summary['present'], True)
        self.assertEqual(summary['path'], rel(self.gen.SIGNOFF))
        self.assertIn(rel(self.gen.SIGNOFF), {r['path'] for r in self.graph['inputs']},
                      'the sidecar must be a fingerprint input so editing it makes the outputs stale')
        self.assertEqual(summary['entries'], sidecar['entries'])
        self.assertEqual(summary['orphans'], [], f"sign-offs name ids that are not in the graph: {summary['orphans']}")
        signed = self.signed_items(self.graph)
        self.assertEqual(set(signed), {e['id'] for e in sidecar['entries']})
        self.assertEqual(summary['signed_nodes'], sum(1 for i in signed if '->' not in i))
        self.assertEqual(summary['signed_edges'], sum(1 for i in signed if '->' in i))
        for sid, so in signed.items():
            with self.subTest(id=sid):
                for key in ('by', 'on', 'basis', 'hashes', 'current', 'stale', 'stale_detail', 'pinned', 'previous'):
                    self.assertIn(key, so)
                self.assertEqual(set(so['hashes']), set(so['current']))
                self.assertIs(so['stale'], any(so['hashes'][k] != so['current'][k] for k in so['current']))
        self.assertEqual(summary['stale'], sum(1 for so in signed.values() if so['stale']))

    def test_signoff_schema_rejects_malformed_entries(self):
        good = {'id': 'EB-CASE', 'by': 'Q. Checker', 'on': '2026-10-17', 'basis': 'test entry', 'hashes': {'node': '0' * 64}}
        bad = [
            ('empty by', {**good, 'by': ' '}),
            ('empty basis', {**good, 'basis': ''}),
            ('non-ISO date', {**good, 'on': '17/10/2026'}),
            ('impossible date', {**good, 'on': '2026-13-40'}),
            ('unknown key', {**good, 'extra': 1}),
            ('node with edge hashes', {**good, 'hashes': {'source': '0' * 64, 'target': '0' * 64}}),
            ('edge with node hashes', {**good, 'id': 'EB-XML->EB-CASE'}),
            ('hash not hex', {**good, 'hashes': {'node': 'not-a-hash'}}),
            ('hashes not an object', {**good, 'hashes': ['0' * 64]}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'signoff.json'
            for label, entry in bad:
                with self.subTest(case=label):
                    self.write_sidecar(path, [entry])
                    with self.assertRaises(SystemExit):
                        self.gen.load_signoffs(path)
            with self.subTest(case='wrong schema'):
                self.write_sidecar(path, [], schema='something-else')
                with self.assertRaises(SystemExit):
                    self.gen.load_signoffs(path)
            with self.subTest(case='valid entry'):
                self.write_sidecar(path, [good])
                self.assertEqual(self.gen.load_signoffs(path)['entries'], [good])
            with self.subTest(case='absent file'):
                self.assertEqual(self.gen.load_signoffs(Path(tmp) / 'absent.json'), {'present': False, 'note': '', 'entries': []})

    def test_stale_signoff_detected_in_temp_copy(self):
        eb_case, eb_xml = self.node('EB-CASE'), self.node('EB-XML')
        self.assertTrue(eb_case['sha256'] and eb_xml['sha256'])
        entries = [
            {'id': 'EB-CASE', 'by': 'Q. Checker', 'on': '2026-10-17', 'basis': 'current hash', 'hashes': {'node': eb_case['sha256']}},
            {'id': 'EB-XML->EB-CASE', 'by': 'P. Earlier', 'on': '2026-10-01', 'basis': 'superseded entry',
             'hashes': {'source': eb_xml['sha256'], 'target': eb_case['sha256']}},
            {'id': 'EB-XML->EB-CASE', 'by': 'Q. Checker', 'on': '2026-10-17', 'basis': 'fabricated stale source hash',
             'hashes': {'source': 'f' * 64, 'target': eb_case['sha256']}},
            {'id': 'RFQ', 'by': 'Q. Checker', 'on': '2026-10-17', 'basis': 'unregistered node, no hash', 'hashes': {'node': ''}},
            {'id': 'NOT-A-NODE', 'by': 'Q. Checker', 'on': '2026-10-17', 'basis': 'orphan', 'hashes': {'node': ''}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'signoff.json'
            self.write_sidecar(path, entries)
            graph = self.gen.build(signoff_path=path)
        signed = self.signed_items(graph)
        self.assertEqual(set(signed), {'EB-CASE', 'EB-XML->EB-CASE', 'RFQ'})
        self.assertIs(signed['EB-CASE']['stale'], False)
        self.assertIs(signed['EB-CASE']['pinned'], True)
        stale = signed['EB-XML->EB-CASE']
        self.assertIs(stale['stale'], True)
        self.assertEqual(stale['by'], 'Q. Checker', 'the latest entry for an id is the effective one')
        self.assertIn('source hash changed', stale['stale_detail'])
        self.assertEqual(stale['current'], {'source': eb_xml['sha256'], 'target': eb_case['sha256']})
        self.assertEqual([p['by'] for p in stale['previous']], ['P. Earlier'])
        self.assertIs(signed['RFQ']['stale'], False)
        self.assertIs(signed['RFQ']['pinned'], False, 'an empty register hash cannot pin a sign-off')
        summary = graph['signoff']
        self.assertEqual((summary['signed_nodes'], summary['signed_edges'], summary['stale']), (2, 1, 1))
        self.assertEqual(summary['orphans'], ['NOT-A-NODE'])
        self.assertEqual(len(summary['entries']), len(entries))
        self.assertNotIn(path.as_posix(), {r['path'] for r in graph['inputs']}, 'a sidecar outside the repo is not a fingerprint input')

    def test_empty_sidecar_leaves_graph_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / 'signoff.json'
            self.write_sidecar(empty, [])
            with_empty = self.gen.build(signoff_path=empty)
            without = self.gen.build(signoff_path=Path(tmp) / 'absent.json')
        for key in ('stages', 'nodes', 'edges', 'decisions', 'issues', 'inputs', 'fingerprint'):
            with self.subTest(key=key):
                self.assertEqual(with_empty[key], without[key])
        self.assertEqual(self.signed_items(with_empty), {})
        self.assertEqual((with_empty['signoff']['present'], without['signoff']['present']), (True, False))
        self.assertEqual(with_empty['signoff']['entries'], [])
        self.assertEqual((with_empty['signoff']['signed_nodes'], with_empty['signoff']['signed_edges'], with_empty['signoff']['stale']), (0, 0, 0))


if __name__ == '__main__':
    unittest.main()
