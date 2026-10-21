"""Verify equation disclosures and both native formula dialects for edited cases."""
from copy import deepcopy
import json
import unittest
from lxml import etree, html
from ring_wall.model import analyze,default_case
from ring_wall.output import check_details,check_steps,native_sheets,render_report
from ring_wall.plots import checks_table
from ring_wall.calculation_report import families, check_type, Report
from ring_wall.notation import dependencies, expression, math, stem, TERMS


class RingWallEquationTests(unittest.TestCase):
    def test_all_check_endpoints_and_dependencies_are_in_ledger(self):
        r=analyze()
        for c in r['checks']:
            steps=check_steps(r,c);names={n['name']:n['value'] for n in steps}
            self.assertEqual(names[c['demand_node']],c['demand']);self.assertEqual(names[c['capacity_node']],c['capacity'])
            self.assertTrue(all(n['unit'] and n['expr'] for n in steps))
        self.assertIn('weld_radial',' '.join(x['name'] for x in check_steps(r,next(c for c in r['checks'] if c['id']=='R1-P2-WELD'))))

    def test_notebook_and_grouped_report_escape_text_without_mutation(self):
        r=analyze();r['case']['title']='<script>bad()</script>';r['checks'][0]['note']='<script>bad()</script>';original=deepcopy(r)
        report=render_report(r);notebook=checks_table(r)
        for c in r['checks']:
            detail=check_details(r,c);self.assertIn(detail,notebook)
        self.assertIn('&lt;script&gt;bad()&lt;/script&gt;',report)
        self.assertNotIn('<script>bad()</script>',report);self.assertEqual(r,original)
        self.assertIn('D/C is undefined',check_details(r,next(c for c in r['checks'] if c['id']=='RING-GRID')))

    def test_grouped_tables_cover_every_check_exactly_once_and_preserve_status(self):
        for p in [default_case(),default_case()|dict(pile_count=1,ring_count=1),default_case()|dict(imposed_rotation_rad=.002),
                  default_case()|dict(length_in=240.,thickness_in=44.,placement_tolerance_in=0.)]:
            r=analyze(p);doc=html.fromstring(render_report(r))
            rows=doc.xpath('//tr[@data-check-id]')
            self.assertEqual(len(rows),len(r['checks']))
            self.assertEqual({x.get('data-check-id') for x in rows},{c['id'] for c in r['checks']})
            for row in rows:
                c=next(c for c in r['checks'] if c['id']==row.get('data-check-id'))
                self.assertEqual(row.xpath('./td[last()]/span/text()'),[c['status']])
            self.assertEqual(len(doc.xpath('//article[@id="eq-weld-WELD"]')),1)
            self.assertEqual(len(doc.xpath('//details[@id="method-weld"]//tr[@data-check-id]')),len(r['rings']))

    def test_every_equation_has_real_math_schematic_and_current_operands(self):
        r=analyze(default_case()|dict(density_kcf=.18,ring_t_in=1.,weld_leg_in=.375))
        original=deepcopy(r);doc=html.fromstring(render_report(r));nodes={n['name']:n for n in r['nodes']}
        equations=doc.xpath('//article[@class="equation"]')
        self.assertGreater(len(equations),80)
        self.assertLess(len(equations),len(r['checks']))
        ids=[a.get('id') for a in equations];self.assertEqual(len(ids),len(set(ids)))
        for article in equations:
            self.assertTrue(article.xpath('./div[@class="equation-line"]/math'))
            detail=article.xpath('./details[@class="equation-working"]');self.assertEqual(len(detail),1)
            self.assertEqual(len(detail[0].xpath('.//svg[@role="img"]')),1)
            self.assertTrue(detail[0].xpath('.//svg/title/text()'))
            self.assertTrue(detail[0].xpath('.//table//td'))
            name=article.get('data-node');self.assertIn(name,nodes)
            # Parse every generated MathML/SVG as XML separately, not just tolerant HTML.
        for g in families(r):
            for name in g['names']:
                if name not in nodes:continue
                self.assertIn(stem(name),TERMS)
                for dep in dependencies(nodes[name]['expr']):self.assertIn(stem(dep),TERMS)
                etree.fromstring(math(expression(nodes[name]['expr'])).encode())
                etree.fromstring(math(expression(nodes[name]['expr'],{n:v['value'] for n,v in nodes.items()})).encode())
        self.assertEqual(r,original)

    def test_representatives_remain_trial_when_contact_fails_and_groups_fail_closed(self):
        r=analyze(default_case()|dict(imposed_rotation_rad=.002));g=next(g for g in families(r) if g['key']=='weld')
        self.assertEqual(g['representative']['status'],'PENDING')
        self.assertFalse(g['example']['contact_ok'])
        fragment=Report(r).family(g)
        self.assertIn('Full contact fails here',fragment)
        self.assertIn('cannot establish a pass',fragment)
        self.assertIn('pending',fragment)
        r['checks'][0]['id']='NEW-UNASSIGNED-CHECK'
        with self.assertRaises(ValueError):list(families(r))

    def test_notation_preserves_precedence_and_conditional_branches(self):
        markup=math(expression('a-(b+c)/(d**2)'))
        root=etree.fromstring(markup.encode());ns={'m':root.nsmap[None]}
        self.assertEqual(len(root.xpath('.//m:mfrac',namespaces=ns)),1)
        self.assertEqual(len(root.xpath('.//m:msup',namespaces=ns)),1)
        self.assertIn('<mo>(</mo>',expression('a-(b+c)'))
        branch=expression('IF(a>3,12,18)',{'a':4})
        self.assertIn('<mn>12</mn>',branch);self.assertIn('<mn>18</mn>',branch)

    def test_native_equation_and_status_parity_for_default_and_edited_cases(self):
        cases=[default_case(),default_case()|dict(length_in=240.,thickness_in=44.,placement_tolerance_in=0.),default_case()|dict(imposed_rotation_rad=.002),
               default_case()|dict(pile_count=1,ring_count=1,grid_bar=6,coating='epoxy',auto_grid_spacing=False,grid_spacing_in=8.,ring_t_in=1.,weld_leg_in=.375,density_kcf=.19)]
        for p in cases:
            with self.subTest(case=p):
                r=analyze(p);data=native_sheets(r);record=json.loads(data['ring_wall_sheet_verification.json'])
                self.assertEqual(record['numeric_values'],len(r['nodes']));self.assertEqual(record['check_statuses'],len(r['checks']))
                self.assertFalse(record['native_application_recalculation'])
                for name in ('ring_wall_design.xmcd','Ring Supported Wall Design.bpad'):etree.fromstring(data[name])
                root=etree.fromstring(data['Ring Supported Wall Design.bpad'])
                formulas=[e.get('formula') for e in root.iter('dynexp')]
                self.assertTrue(any('Sqrt' in f for f in formulas));self.assertTrue(any('PENDING' in f for f in formulas))


if __name__=='__main__':unittest.main()
