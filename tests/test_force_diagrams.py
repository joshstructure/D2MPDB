from copy import deepcopy
import unittest

from pier_cap.fbmp import import_fbmp_xml
from pier_cap.force_diagrams import cap_profiles, cap_force_figure, diagram_notice, ForceDiagramPanel
from pier_cap.model import default_case
from tests.test_fbmp import FIXTURE, changed


class ForceDiagramTests(unittest.TestCase):
    def setUp(self):
        self.case=import_fbmp_xml(FIXTURE)

    def test_profiles_reproduce_imported_signed_envelopes_and_station_origin(self):
        before=deepcopy(self.case)
        profiles=cap_profiles(self.case)
        expected={'1':(-182.10,287.44,209.52,4.75), '2':(-183.15,279.73,168.62,34.16),
                  '3':(-181.41,278.61,154.15,3.88), '4':(-166.54,254.81,156.73,19.46)}
        for combo,values in expected.items():
            rows=[r for r in profiles[combo] if r]
            actual=(min(r['moment'] for r in rows),max(r['moment'] for r in rows),
                    max(abs(r['shear']) for r in rows),max(r['torque'] for r in rows))
            for a,b in zip(actual,values):self.assertAlmostEqual(a,b)
            self.assertAlmostEqual(rows[0]['x'],0)
            self.assertAlmostEqual(rows[-1]['x'],19.24)
            self.assertEqual(profiles[combo].count(None),19)
        self.assertEqual(self.case,before)

    def test_shared_node_keeps_opposite_raw_moment_signs_and_shear_jump(self):
        rows=cap_profiles(self.case)['1']
        at_node=[r for r in rows if r and abs(r['x']-(38.5+25.44)/12)<1e-10]
        self.assertEqual(len(at_node),2)
        self.assertEqual([r['moment'] for r in at_node],[287.44,287.44])
        self.assertEqual([r['shear'] for r in at_node],[142.32,-204.44])
        self.assertIn('J-end · raw M3 -287.44',at_node[0]['station'])
        self.assertIn('I-end · raw M3 287.44',at_node[1]['station'])

    def test_interior_extremum_is_included_not_just_member_ends(self):
        def mutate(root):
            el=root.find('.//LOAD_CASE_RESULTS/LOAD_CASE/TIME_STEP/STRUCTURE_INTERNAL_FORCES/PIER_CAP/ELEMENT[@number="9"]')
            for end in el:
                end.find('MOMENT-3').text='0'
                end.find('SHEAR-2').text='-800'
            for item in root.findall('.//STRUCTURE_PIER_CAP_MAX/MAX_ITEM'):
                if item.get('item')=='max shear in 2 direction':item.find('ITEM_VALUE').text='800'
                if item.get('item')=='min shear in 2 direction':item.find('ITEM_VALUE').text='-800'
        case=import_fbmp_xml(changed(mutate))
        winner=max((r for r in cap_profiles(case)['1'] if r),key=lambda r:r['moment'])
        self.assertAlmostEqual(winner['moment'],1000/3)
        self.assertAlmostEqual(winner['x'],(70+25.44)/12)

    def test_source_geometry_and_forces_do_not_follow_trial_edits(self):
        before=cap_profiles(self.case)
        self.case['inputs'].update(h=60,S_pile=6,Mu_B=999)
        self.assertEqual(cap_profiles(self.case),before)
        notice=diagram_notice(self.case)
        self.assertIn('CURRENT INPUTS DIFFER',notice)
        self.assertIn('Mu_B',notice)
        figure=cap_force_figure(self.case)
        self.assertIn('48 × 36 in',figure.layout.title.text)
        piles=next(t for t in figure.data if t.name=='Pile centers')
        self.assertEqual(tuple(round(x,2) for x in piles.x),(2.12,7.12,12.12,17.12))

    def test_envelope_selection_colors_and_absent_xml(self):
        figure=cap_force_figure(self.case)
        self.assertEqual(len(figure.layout.updatemenus[0].buttons),8)
        visible=[t for t in figure.data if t.visible is not False]
        self.assertNotEqual(visible[0].line.color,visible[2].line.color)
        self.assertEqual(min(v for v in visible[1].y if v is not None),-183.15)
        self.assertEqual(max(v for v in visible[0].y if v is not None),287.44)
        with self.assertRaisesRegex(ValueError,'Scalar workbook envelopes'):
            cap_profiles(default_case())

    def test_panel_retains_selected_figure_on_reinforcement_or_manual_load_edits(self):
        panel=ForceDiagramPanel()
        try:
            panel.refresh(self.case)
            figure=panel.figure
            figure.layout.updatemenus[0].active=5
            self.case['inputs']['n_N1']=9
            panel.refresh(self.case)
            self.assertIs(panel.figure,figure)
            self.assertEqual(panel.figure.layout.updatemenus[0].active,5)
            self.case['inputs']['Mu_B']=999
            panel.refresh(self.case)
            self.assertIn('CURRENT INPUTS DIFFER',panel.notice.value)
            panel.refresh(default_case())
            self.assertIsNone(panel.figure)
            self.assertIn('Upload and apply',panel.notice.value)
        finally:panel.close()

    def test_incomplete_saved_member_data_is_rejected(self):
        self.case['analysis']['xml_audit']['end_records'].pop(0)
        with self.assertRaisesRegex(ValueError,'Incomplete member-end'):
            cap_profiles(self.case)


if __name__=='__main__':unittest.main()
