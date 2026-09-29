"""Force-sign, topology, station recovery and one-file UI regressions."""
from copy import deepcopy
from pathlib import Path
import unittest
from lxml import etree as E
from pier_cap.fbmp import import_fbmp_xml, _moment_at
from pier_cap.model import default_case, evaluate


FIXTURE = Path(__file__).parent/'fixtures'/'fbmp_610_cap.xml'


def changed(mutator):
    root = E.parse(str(FIXTURE)).getroot()
    mutator(root)
    return E.tostring(root)


class FBMPTests(unittest.TestCase):
    def test_known_run_values_signs_geometry_and_provenance(self):
        base = default_case()
        base['inputs']['n_N1'] = 7
        original = deepcopy(base)
        case = import_fbmp_xml(FIXTURE,base=base)
        self.assertEqual(base,original)
        p = case['inputs']
        expected = dict(b=48,h=36,N_pile=4,S_pile=5,D_pile=20,fc=6,fy=60,Es=29000,
                        Mu_N=183.15,Mu_P=90.45,Mu_B=287.44,MI_N=166.54,MI_P=60.62,MI_B=254.81,
                        Vu_G=209.52,Vu_L=209.52,Tu=34.16,n_N1=7)
        for key,value in expected.items():
            self.assertAlmostEqual(p[key],value,msg=key)
        self.assertAlmostEqual(p['E_detail'],3.44)
        result = evaluate(case)
        self.assertEqual(result.stale,[])
        self.assertAlmostEqual(result.value('L_cap')/12,19.24)
        audit = case['analysis']['xml_audit']
        self.assertEqual(audit['cap_element_count'],19)
        self.assertEqual(audit['excluded_elements_per_case'],[1]*4)
        self.assertEqual(len(audit['end_records']),19*2*4)
        self.assertEqual(audit['governing']['Mu_N']['side'],'J')
        self.assertEqual(audit['governing']['Mu_N']['raw_moment_3'],183.15)
        self.assertEqual(audit['governing']['Mu_N']['moment'],-183.15)
        self.assertEqual(audit['governing']['Mu_B']['raw_moment_3'],-287.44)
        self.assertEqual(audit['governing']['Mu_P']['x_in'],50)
        self.assertEqual(audit['governing']['MI_P']['x_in'],130)
        self.assertEqual(len(audit['sha256']),64)

    def test_service_three_is_not_service_one_and_pending_reset(self):
        def mutate(root):
            combo = deepcopy(root.find('MODEL_INFO/LOAD_COMBINATION'))
            combo.set('number','5');combo.set('limitstate','SERVICE-III')
            root.find('MODEL_INFO').append(combo)
            result = deepcopy(root.find('.//LOAD_CASE_RESULTS/LOAD_CASE'))
            result.set('combination','5');result.set('number','12');result.set('limitstate','SERVICE-III')
            root.find('.//LOAD_CASE_RESULTS').append(result)
        base = default_case()
        base['inputs'].update(Ready_III=True,Ready_fatigue=True,MIII_N=999,MDL_P=10,DMLL_B=88)
        base['section_study'] = {'old':'marker'}
        case = import_fbmp_xml(changed(mutate),base=base)
        self.assertEqual(case['inputs']['MI_B'],254.81)
        self.assertFalse(case['inputs']['Ready_III'])
        self.assertFalse(case['inputs']['Ready_fatigue'])
        self.assertEqual(case['inputs']['MIII_N'],0)
        self.assertEqual(case['inputs']['MDL_P'],0)
        self.assertEqual(case['inputs']['DMLL_B'],0)
        self.assertNotIn('section_study',case)

    def test_uniform_load_midspan_extrema_are_not_lost(self):
        # Simply supported 10-ft segment with w=2 kip/ft -> wL²/8 = 25.
        self.assertAlmostEqual(_moment_at(0,0,10,-10,10,.5),25)
        self.assertEqual(_moment_at(0,0,10,-10,10,0),0)
        self.assertEqual(_moment_at(0,0,10,-10,10,1),0)
        def mutate(root):
            el = root.find('.//LOAD_CASE_RESULTS/LOAD_CASE/TIME_STEP/STRUCTURE_INTERNAL_FORCES/PIER_CAP/ELEMENT[@number="9"]')
            for end in el:
                end.find('MOMENT-3').text='0'
                end.find('SHEAR-2').text='-800'
            for item in root.findall('.//STRUCTURE_PIER_CAP_MAX/MAX_ITEM'):
                if item.get('item') == 'max shear in 2 direction':item.find('ITEM_VALUE').text='800'
                if item.get('item') == 'min shear in 2 direction':item.find('ITEM_VALUE').text='-800'
        case = import_fbmp_xml(changed(mutate))
        self.assertEqual(case['inputs']['Mu_B'],333.34)
        self.assertEqual(case['analysis']['xml_audit']['governing']['Mu_B']['x_in'],70)

    def test_extra_members_are_not_cap_forces(self):
        def mutate(root):
            for el in root.findall('.//PIER_CAP/ELEMENT[@number="20"]'):
                for end in el:
                    for tag in ['MOMENT-3','SHEAR-2','TORQUE']:end.find(tag).text='999999'
        case = import_fbmp_xml(changed(mutate))
        self.assertEqual(case['inputs']['Mu_B'],287.44)
        self.assertEqual(case['inputs']['Vu_G'],209.52)
        self.assertEqual(case['inputs']['Tu'],34.16)

    def test_rejects_unverified_formats_units_and_geometry(self):
        mutations = [
            lambda r:setattr(r.find('PROJECT_INFO/VERSION_NUMBER'),'text','6.2.0'),
            lambda r:setattr(r.find('CONTROL_INFO/ANALYSIS'),'text','Dynamic'),
            lambda r:setattr(r.find('CONTROL_INFO/PIERS'),'text','2'),
            lambda r:r.find('.//PIER_CAP/ELEMENT/STRUCTURE_ELEMENT_I_END/MOMENT-3').set('units','kip-in'),
            lambda r:setattr(r.find('.//PILE_COORDINATES/PILE[@number="2"]/POINT/X'),'text','61'),
            lambda r:setattr(r.find('.//PIER_GEOMETRY/CROSS-SECTIONS/SEGMENT[@number="3"]/DIMENSIONS/DEPTH'),'text','48'),
            lambda r:r.find('.//PIER_CAP/ELEMENT/STRUCTURE_ELEMENT_I_END').set('node_i','20'),
            lambda r:setattr(r.find('.//PIER_GEOMETRY/NODAL_COORDINATES/NODE/COORDINATES/Y'),'text','2'),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                import_fbmp_xml(changed(mutation))

    def test_rejects_incomplete_results_and_force_mismatch(self):
        mutations = [
            lambda r:r.find('.//LOAD_CASE_RESULTS').remove(r.find('.//LOAD_CASE_RESULTS/LOAD_CASE')),
            lambda r:r.find('.//LOAD_CASE_RESULTS/LOAD_CASE').append(E.Element('TIME_STEP')),
            lambda r:setattr(r.find('.//PIER_CAP/ELEMENT/STRUCTURE_ELEMENT_I_END/MOMENT-3'),'text','100'),
            lambda r:setattr(r.find('.//STRUCTURE_PIER_CAP_MAX/MAX_ITEM[@item="max moment about 3 axis"]/ITEM_VALUE'),'text','999'),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                import_fbmp_xml(changed(mutation))

    def test_does_not_shorten_required_end_allowance(self):
        base = default_case();base['inputs']['E_clear']=15
        with self.assertRaisesRegex(ValueError,'shorter'):
            import_fbmp_xml(FIXTURE,base=base)

    def test_xml_entities_and_nonfinite_data_rejected(self):
        malicious = b'<!DOCTYPE x [<!ENTITY test SYSTEM "file:///do-not-read">]><FB-MULTIPIER_MODEL_DATA>&test;</FB-MULTIPIER_MODEL_DATA>'
        with self.assertRaisesRegex(ValueError,'DTD'):
            import_fbmp_xml(malicious)
        with self.assertRaises(ValueError):
            import_fbmp_xml(changed(lambda r:setattr(r.find('.//PIER_GEOMETRY/CROSS-SECTIONS/SEGMENT/DIMENSIONS/WIDTH'),'text','NaN')))


class ImportWidgetTests(unittest.TestCase):
    def test_preview_apply_invalid_upload_and_changed_inputs(self):
        from pier_cap.widgets import CapNotebook
        from pier_cap.section_widgets import SectionStudy
        app = CapNotebook()
        section_app = SectionStudy(app)
        try:
            panel = app.xml_import
            before = deepcopy(app.case)
            panel.stage(FIXTURE)
            self.assertEqual(app.case,before)
            self.assertFalse(panel.apply_button.disabled)
            app._notify_case_change()  # A frontend echo with no changed data is harmless.
            self.assertFalse(panel.apply_button.disabled)
            self.assertIn('15.44',panel.preview.value)
            self.assertIn('combo 2',panel.preview.value)
            self.assertIn('36',panel.preview.value)
            app.controls['n_N1'].value = 6
            self.assertTrue(panel.apply_button.disabled)
            self.assertIsNone(panel.pending)
            panel.refresh_button.click()
            self.assertFalse(panel.apply_button.disabled)
            panel.apply_button.click()
            self.assertEqual(app.case['inputs']['h'],36)
            self.assertEqual(app.controls['h'].value,36)
            self.assertEqual(app.case['inputs']['n_N1'],6)
            self.assertIsNone(app.search_result)
            self.assertIn('Applied',panel.status.value)
            self.assertAlmostEqual(app.current.value('L_cap')/12,19.24)
            applied = deepcopy(app.case)
            panel.stage(FIXTURE)
            panel.stage(b'<wrong/>','wrong.xml')
            self.assertTrue(panel.apply_button.disabled)
            self.assertIsNone(panel.pending)
            panel.apply()
            self.assertEqual(app.case,applied)
        finally:
            for fig in app.figures:fig.close()
            app.ui.close();section_app.ui.close()
