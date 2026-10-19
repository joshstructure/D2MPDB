"""Verify equation disclosures and both native formula dialects for edited cases."""
from copy import deepcopy
import json
import unittest
from lxml import etree
from ring_wall.model import analyze,default_case
from ring_wall.output import check_details,check_steps,native_sheets,render_report
from ring_wall.plots import checks_table


class RingWallEquationTests(unittest.TestCase):
    def test_all_check_endpoints_and_dependencies_are_in_ledger(self):
        r=analyze()
        for c in r['checks']:
            steps=check_steps(r,c);names={n['name']:n['value'] for n in steps}
            self.assertEqual(names[c['demand_node']],c['demand']);self.assertEqual(names[c['capacity_node']],c['capacity'])
            self.assertTrue(all(n['unit'] and n['expr'] for n in steps))
        self.assertIn('weld_radial',' '.join(x['name'] for x in check_steps(r,next(c for c in r['checks'] if c['id']=='R1-P2-WELD'))))

    def test_notebook_and_report_use_same_disclosures_and_escape_text(self):
        r=analyze();r['case']['title']='<script>bad()</script>';r['checks'][0]['note']='<script>bad()</script>';original=deepcopy(r)
        report=render_report(r);notebook=checks_table(r)
        for c in r['checks']:
            detail=check_details(r,c);self.assertIn(detail,report);self.assertIn(detail,notebook)
        self.assertNotIn('<script>bad()</script>',report);self.assertEqual(r,original)
        self.assertIn('D/C is undefined',check_details(r,next(c for c in r['checks'] if c['id']=='RING-GRID')))

    def test_native_equation_and_status_parity_for_default_and_edited_cases(self):
        cases=[default_case(),default_case()|dict(length_in=240.,thickness_in=44.,placement_tolerance_in=0.),
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
