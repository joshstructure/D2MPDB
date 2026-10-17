"""Regression tests for the generated information-lineage graph (lineage/).

Rebuild after any register, decision, tracker, saved-case or Mathcad-export change:
    .venv\\Scripts\\python.exe scripts\\build_lineage_graph.py
"""
import datetime
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REBUILD = r'Rebuild with: .venv\Scripts\python.exe scripts\build_lineage_graph.py'
MARKER = '/*__LINEAGE_DATA__*/'
ISSUE_STATUSES = {'Open', 'Closed', 'Deferred', 'Awaiting source'}
GEOMETRY_CHECK_NAMES = ['b', 'h', 'N_pile', 'D_pile', 'S_pile', 'Pile_embed', 'length']


def load_generator():
    """`scripts` is not a package, so load the generator by path."""
    path = ROOT / 'scripts' / 'build_lineage_graph.py'
    spec = importlib.util.spec_from_file_location('build_lineage_graph', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


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


if __name__ == '__main__':
    unittest.main()
