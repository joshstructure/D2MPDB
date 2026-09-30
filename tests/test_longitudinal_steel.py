"""Main longitudinal steel must retain its credit when side bars are removed."""
import csv
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lxml import etree as E
from pier_cap.engine import parse
from pier_cap.io import export_blockpad, export_bundle
from pier_cap.model import evaluate, set_inputs
from pier_cap.visuals import checks_html, ratios_figure
from tests.case_fixtures import default_case
from tests.test_blockpad_export import journal


def trial(count=4, side=0):
    return set_inputs(default_case(),n_N1=count,n_P1=count,n_B1=count,n_skin=side)


class LongitudinalSteelTests(unittest.TestCase):
    def test_main_only_can_pass_or_fail_with_numeric_ratio(self):
        for count, passes in ((4,False),(8,True)):
            for fast in (False,True):
                with self.subTest(count=count,fast=fast):
                    e=evaluate(trial(count),fast=fast);p=e.case['inputs']
                    # Independent equilibrium arithmetic; geometry and section
                    # properties are separately verified in test_calculation.
                    fvt=math.sqrt((p['Vu_G']/p['phi_v'])**2+
                        (.45*e.value('ph')*p['Tu']*12/(2*e.value('Ao')*p['phi_v']))**2)
                    fvt/=math.tan(math.radians(p['theta']))
                    for z in 'NPB':
                        c=next(c for c in e.checks if c.key=='Chk_long_'+z)
                        demand=p['Mu_'+z]*12/(p['phi_f']*e.value('dv'))+fvt
                        self.assertAlmostEqual(c.ratio,demand/(count*.79*p['fy']))
                        self.assertEqual('PASS' in c.status,passes)
                        self.assertEqual(c.ratio<=1,passes)
                        self.assertIn(f'credited main {count*.79:.3f} + side 0.000',c.basis)
                        self.assertIn('shortfall',c.basis)
                        self.assertNotIn('NO STEEL',c.basis)

    def test_side_credit_and_original_pass_boundary_are_preserved(self):
        for side in (0,1,6):
            case=set_inputs(trial(side=side),Vu_G=0,Vu_L=0,Tu=0)
            base=evaluate(case)
            for target in (.999999,1.000001):
                moments={f'Mu_{z}':target*(base.value('As_'+z)+base.value('As_skin_eff'))*
                         case['inputs']['fy']*case['inputs']['phi_f']*base.value('dv')/12 for z in 'NPB'}
                e=evaluate(set_inputs(case,**moments))
                for z in 'NPB':
                    with self.subTest(side=side,target=target,region=z):
                        c=next(c for c in e.checks if c.key=='Chk_long_'+z)
                        self.assertAlmostEqual(c.ratio,target)
                        self.assertEqual('PASS' in c.status,target<1)
                        self.assertEqual(e.value('As_add_'+z)<=e.value('As_skin_eff'),target<1)

    def test_failure_is_visible_in_plot_and_export_with_main_steel_credit(self):
        e=evaluate(trial());fig=ratios_figure(e)
        with TemporaryDirectory() as folder:
            out=export_bundle(e.case,folder)
            with (out/'checks.csv').open(encoding='utf-8-sig',newline='') as f:
                rows={r['Check']:r for r in csv.DictReader(f)}
        table=checks_html(e)
        for c in e.checks:
            if not c.key.startswith('Chk_long_'):continue
            self.assertAlmostEqual(float(rows[c.label]['D/C']),c.ratio)
            self.assertEqual(rows[c.label]['Basis'],c.basis)
            i=list(fig.data[0].y).index(c.label)
            self.assertAlmostEqual(fig.data[0].x[i],c.ratio)
            self.assertIn(f'{c.ratio:.3f}',table)
            self.assertIn('credited main 3.160 + side 0.000',table)

    def test_old_blockpad_register_is_refreshed_and_stays_live(self):
        root=E.fromstring(journal());report=root.find("report[@name='PierCapDesign']")
        table=E.SubElement(report,'table',name='ExistingChecks')
        for z in 'NPB':
            row=E.SubElement(table,'row')
            E.SubElement(row,'textcell').text='Longitudinal steel '+z
            E.SubElement(row,'c',formula='Chk_long_'+z)
            ratio=E.SubElement(row,'c',formula=f'If(As_skin_eff > 0 in^2,Max(DC_long_{z},As_add_{z}/As_skin_eff),"NO STEEL")')
            E.SubElement(ratio,'textvalue').text='NO STEEL'
            basis=E.SubElement(row,'textcell')
            E.SubElement(basis,'paragraph').text='Old supplemental-only basis'
        original=E.tostring(root)
        with TemporaryDirectory() as folder:
            out=export_blockpad(original,trial(),Path(folder)/'review.bpad')
            saved=E.parse(str(out))
        rows=saved.find("report[@name='PierCapDesign']/table[@name='ExistingChecks']").findall('row')
        for count in (4,8):
            e=evaluate(trial(count))
            for row,z in zip(rows,'NPB'):
                ratio=e.engine.eval(parse(row[2].get('formula')),{}).v
                self.assertAlmostEqual(ratio,e.value('DC_long_'+z))
                self.assertEqual(ratio<=1,count==8)
                self.assertIsNone(row[2].find('textvalue'))
                self.assertIn('main bars plus effective side steel',row[3].find('paragraph').text)
        self.assertEqual(E.tostring(root),original)
        self.assertEqual(saved.find("report[@name='Other']").text,'Keep this report.')


if __name__=='__main__':
    unittest.main()
