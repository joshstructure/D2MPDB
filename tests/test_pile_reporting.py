from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import csv
import io
import json
import unittest
import zipfile
from lxml import etree as E
from pier_cap.pile_review import import_pile_xml, section_from_xml, parse_trials, evaluate_trials
from pier_cap.pile_reporting import (elastic_stress_checks, reported_cracking_check,
                                     geotech_section_and_loads, selected_trial_handoff)
from pier_cap.pile_widgets import profile_figure, trial_figure
from pier_cap.widgets import CapNotebook

FIXTURES = Path(__file__).parent/'fixtures'


class PileReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = import_pile_xml(FIXTURES/'fbmp_610_piles.xml')
        cls.concrete = section_from_xml(E.parse(str(FIXTURES/'fbmp_end_bent_section.xml')).getroot())

    def test_model_peak_and_strain_import_preserve_source_pairing(self):
        self.assertEqual(self.concrete['tensile_peak_ksi'], .6)
        self.assertEqual(self.concrete['tensile_peak_strain'], .00013158)
        root = E.parse(str(FIXTURES/'fbmp_610_piles.xml')).getroot()
        xml_strains = root.findall('.//PILE_STRAINS/MAX_ITEM')
        for r in self.review['reported_stresses']:
            case = root.find('.//LOAD_CASE_RESULTS/LOAD_CASE[@combination="'+r['combination']+'"]')
            item = next(i for i in case.findall('TIME_STEP/PILE_STRAINS/MAX_ITEM')
                        if i.get('item') == r['description'].replace('stress', 'strain'))
            self.assertEqual(r['strain'], float(item.findtext('ITEM_VALUE')))
        pair = next(i for i in xml_strains if i.get('item') == 'max strain in steel (casing)')
        pair.find('PILE').text = '4'
        with self.assertRaisesRegex(ValueError, 'different locations'):
            import_pile_xml(E.tostring(root))

    def test_cracking_uses_strain_even_when_stress_has_softened(self):
        review = dict(section=self.concrete, reported_stresses=[dict(combination='1', pile='4', segment='1',
            description='max stress in concrete', strain=.0003, stress_ksi=.3)])
        result = reported_cracking_check(review, '1')[0]
        self.assertIn('reached / exceeded', result['result'])
        self.assertLess(result['stress_ksi'], self.concrete['tensile_peak_ksi'])
        for strain, expected in [(-.001, 'in compression'), (.0001, 'below model'), (.00013158, 'reached / exceeded')]:
            review['reported_stresses'][0]['strain'] = strain
            self.assertIn(expected, reported_cracking_check(review, '1')[0]['result'])
        review['reported_stresses'][0].pop('strain')
        self.assertIn('reload XML', reported_cracking_check(review, '1')[0]['result'])

    def test_elastic_cracking_screen_is_per_selected_pile_and_combo(self):
        s = dict(kind='concrete', area_in2=100, s2_in3=100, s3_in3=100,
                 circular=False, issues=[], prestress_kip=0, tensile_peak_ksi=.6)
        def row(pile, axial, moment, combo='4'):
            return dict(pile=pile, combination=combo, axial_tension_kip=axial, m2=moment, m3=0,
                        v2=0,v3=0,node='12',element='5',side='I')
        review = dict(section=s, forces=[row('1',-100,5),row('2',0,10),row('3',0,20),row('1',0,99,'1')])
        checks = elastic_stress_checks(review,'4',['1','2'])
        self.assertEqual([r['pile'] for r in checks], ['1','2'])
        self.assertAlmostEqual(checks[0]['stress_max_ksi'], -.4)
        self.assertEqual(checks[0]['ratio'], 0)
        self.assertIn('in compression',checks[0]['result'])
        self.assertAlmostEqual(checks[1]['ratio'],2)
        self.assertIn('above model cracking',checks[1]['result'])

    def test_limit_lines_are_labeled_and_axes_include_them(self):
        steel = profile_figure(self.review,'4',['1'])
        self.assertEqual({s.x0 for s in steel.layout.shapes if s.xref == 'x5'}, {-60,60})
        self.assertLess(steel.layout.xaxis5.range[0], -60)
        self.assertGreater(steel.layout.xaxis5.range[1], 60)
        self.assertTrue(any('D/C limit = 1' in a.text for a in steel.layout.annotations))
        concrete = profile_figure(self.review,'4',['1'],section=self.concrete)
        self.assertEqual({s.x0 for s in concrete.layout.shapes if s.xref == 'x5'}, {0,.6})
        self.assertGreater(concrete.layout.xaxis5.range[1], .6)
        self.assertTrue(any('Model cracking peak = 0.6 ksi' in a.text for a in concrete.layout.annotations))
        result = evaluate_trials(parse_trials('1,1,1,50,1\n2,1,1,40,1.01'))
        trials = trial_figure(result,.1)
        self.assertTrue(any('Δ limit = 0.1 in' in a.text for a in trials.layout.annotations))
        self.assertGreater(trials.layout.yaxis2.range[1], .1)
        self.assertGreater(trials.layout.yaxis3.range[1], 1)
        self.assertTrue(any('Lcrit = 50 ft' in a.text for a in trials.layout.annotations))
        self.assertEqual(len([s for s in trials.layout.shapes if s.x0 == 50 and s.x1 == 50]),3)

    def test_factored_head_loads_in_tons_exclude_service_and_retain_ties(self):
        review = deepcopy(self.review)
        for r in review['forces']:
            if r['local_element'] == 1 and r['side'] == 'I':
                r['axial_tension_kip'] = -10000 if r['state'] == 'SERVICE-I' else -100
        # Non-head force must not control; uplift from a separate combo stays separate.
        review['forces'][1]['axial_tension_kip'] = -99999
        review['forces'][0]['axial_tension_kip'] = 20
        section, loads = geotech_section_and_loads(review)
        self.assertEqual(loads[0]['short_tons'], 50)
        self.assertEqual(loads[1]['short_tons'], 10)
        self.assertNotIn('SERVICE',loads[0]['governing'])
        self.assertIn('Pile 2',loads[0]['governing'])
        self.assertIn('Pile 3',loads[0]['governing'])
        self.assertNotIn('Elastic modulus',str(section))
        for r in review['forces']:
            r['state'] = 'SERVICE-I'
        self.assertIsNone(geotech_section_and_loads(review)[1][0]['short_tons'])

    def test_handoff_uses_automatic_critical_and_never_interpolates(self):
        rows = parse_trials('1,2,4,50,1\n2,3,1,40,1.01')
        result = evaluate_trials(rows)
        self.assertEqual(selected_trial_handoff(self.review,result)['trials'][0]['embedment_ft'],50)
        with self.assertRaisesRegex(ValueError,'No critical embedment'):
            selected_trial_handoff(self.review,evaluate_trials(rows[:1]))
        result = evaluate_trials(rows, accepted_embedment=45)
        report = selected_trial_handoff(self.review,result,basis='Example')
        self.assertIsNone(report['trials'][0]['displacement_in'])
        self.assertIn('not interpolated',report['trials'][0]['status'])
        result = evaluate_trials(rows, accepted_embedment=50)
        report = selected_trial_handoff(self.review,result,basis='Example')
        self.assertEqual(report['trials'][0]['displacement_in'],1)
        self.assertIn('D/C not supplied',report['trials'][0]['status'])


class HandoffWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app = CapNotebook()
        self.panel = self.app.pile_review
        self.panel.set_review(import_pile_xml(FIXTURES/'fbmp_610_piles.xml'))

    def tearDown(self):
        self.app.close()

    def select_trials(self):
        self.panel.trial_text.value = (FIXTURES/'pile_minimum_tip_reference.csv').read_text()
        self.panel.reference.value = '24.5'
        self.panel.cutoff.value = '40'
        self.panel.trial_label.value = 'Separate workbook reference trials'

    def test_handoff_update_and_download_callbacks_make_short_report(self):
        self.select_trials()
        self.panel.handoff_refresh.click()
        self.assertIn('HANDOFF READY',self.panel.handoff_status.value)
        self.assertTrue(self.panel.accepted.disabled)
        self.assertEqual(self.panel.accepted.value,'32.740')
        self.assertEqual(self.panel.trial_basis.value,'')
        self.assertNotIn('engineering critical',self.panel.trial_summary.value)
        self.assertIn('-13.240 ft',self.panel.handoff.value)
        self.assertIn('Short tons',self.panel.handoff.value)
        self.assertNotIn('EA (kip)',self.panel.handoff.value)
        self.assertNotIn('modeled_weight',self.panel.handoff.value)
        with TemporaryDirectory() as folder:
            self.app.export_root = Path(folder)
            with patch.object(self.panel,'_download') as download:
                self.panel.handoff_export.click()
                download.assert_called_once()
                path = download.call_args.args[0]
            with zipfile.ZipFile(path) as z:
                self.assertEqual(len(z.namelist()),5)
                self.assertNotIn('pile_forces.csv',z.namelist())
                html = z.read('geotech_handoff.html').decode()
                self.assertIn('Minimum tip elevation: -13.240 ft',html)
                self.assertIn('Separate workbook reference trials',html)
                trials = list(csv.DictReader(io.StringIO(z.read('selected_trial_results.csv').decode('utf-8-sig'))))
                self.assertEqual(len(trials),1)
                self.assertEqual(float(trials[0]['embedment_ft']),32.74)
        self.panel.extension.value = 4
        self.assertNotIn('-13.240', self.panel.handoff.value)
        self.assertNotIn('HANDOFF READY', self.panel.handoff_status.value)

    def test_download_errors_are_visible_beside_handoff_button(self):
        with patch.object(self.panel,'_download') as download:
            self.panel.handoff_export.click()
            download.assert_not_called()
        self.assertIn('Paste trial rows first',self.panel.handoff_status.value)
        self.assertFalse(self.panel.handoff_export.disabled)
        self.select_trials()
        self.panel.reference.value = ''
        with TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError,'ground / scour'):
            self.panel.save_handoff(folder)
        self.panel.reference.value = '24.5'
        self.panel.trial_text.value = '1,2,3,not-a-number,1'
        self.panel.handoff_export.click()
        self.assertIn('Row 1: embedment_ft',self.panel.handoff_status.value)
        self.assertNotIn('-13.240', self.panel.handoff.value)

    def test_handoff_export_does_not_depend_on_manual_stress_properties(self):
        self.select_trials()
        self.panel.use_override.value = True
        self.panel.override['fy_ksi'].value = -1
        with TemporaryDirectory() as folder:
            self.panel.save_handoff(folder)
            self.assertTrue((Path(folder)/'geotech_handoff.html').exists())
        self.assertIn('PROFILE INPUT NEEDS REVIEW',self.panel.reported.value)

    def test_old_manual_depth_is_recomputed_and_new_state_has_no_depth_input(self):
        self.select_trials()
        state=self.panel.snapshot()
        self.assertEqual(state['schema_version'],3)
        self.assertNotIn('accepted',state['controls'])
        state['schema_version']=2
        state['controls']['accepted']='999'
        self.panel.restore(state)
        self.assertEqual(self.panel.accepted.value,'32.740')
        self.assertAlmostEqual(self.panel.trial_result['tip_elevation_ft'],-13.24)
        self.panel.extension_mode.value='fraction'
        self.assertEqual(self.panel.accepted.value,'32.740')
        self.assertAlmostEqual(self.panel.trial_result['extension_ft'],6.548)
        self.assertAlmostEqual(self.panel.trial_result['tip_elevation_ft'],-14.788)

    def test_saved_legacy_extension_is_preserved_and_labeled(self):
        self.select_trials()
        state = self.panel.snapshot()
        state['controls']['extension_mode'] = 'lesser'
        self.panel.restore(state)
        self.assertEqual(self.panel.extension_mode.value, 'lesser')
        self.assertIn('Lesser-of method selected (shaft/reference procedure)', self.panel.trial_summary.value)
        self.assertAlmostEqual(self.panel.trial_result['tip_elevation_ft'], -13.24)


if __name__ == '__main__':
    unittest.main()
