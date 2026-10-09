"""Pile parsing, mechanics and trial selection checked independently of the UI."""
from copy import deepcopy
from pathlib import Path
import json
import math
import unittest
from lxml import etree as E
from pier_cap.pile_review import (import_pile_xml, elastic_profile, pile_heads,
                                 governors, parse_trials, evaluate_trials, section_from_xml)

FIXTURES = Path(__file__).parent/'fixtures'
XML = FIXTURES/'fbmp_610_piles.xml'


class PileResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = import_pile_xml(XML)

    def test_every_force_and_displacement_matches_source(self):
        root = E.parse(str(XML))
        source = {}
        source_disp = {}
        for case in root.findall('.//LOAD_CASE_RESULTS/LOAD_CASE'):
            combo = case.get('combination')
            for pile in case.findall('TIME_STEP/PILE_INTERNAL_FORCES/PILE'):
                for element in pile.findall('ELEMENT'):
                    for side in ('I','J'):
                        end = element.find('PILE_ELEMENT_'+side+'_END')
                        source[combo,pile.get('number'),element.get('number'),side] = end
            for pile in case.findall('TIME_STEP/PILE_DISPLACEMENTS/PILE'):
                for node in pile.findall('NODE'):
                    source_disp[combo,pile.get('number'),node.get('node_number')] = node
        self.assertEqual(len(self.review['forces']),1088)
        self.assertEqual(len(self.review['displacements']),560)
        fields = {'axial':'AXIAL','v2':'SHEAR-2','v3':'SHEAR-3','m2':'MOMENT-2','m3':'MOMENT-3','torque':'TORQUE','model_dc':'FAILURE-RATIO'}
        for r in self.review['forces']:
            end = source[r['combination'],r['pile'],str(r['local_element']),r['side']]
            for field,tag in fields.items():
                self.assertEqual(r[field],float(end.findtext(tag)))
            expected = float(end.findtext('AXIAL')) * (1 if r['side']=='I' else -1)
            self.assertEqual(r['axial_tension_kip'],expected)
        for r in self.review['displacements']:
            node = source_disp[r['combination'],r['pile'],r['node']]
            for field in ('dx','dy','dz'):
                self.assertEqual(r[field],float(node.findtext(field.upper())))
        self.assertEqual(len(pile_heads(self.review)),16)
        self.assertTrue(all(math.isclose(p['length_ft'],75) for p in self.review['piles'].values()))

    def test_material_absence_is_not_zero_stress(self):
        self.assertEqual(len(self.review['reported_stresses']),8)
        self.assertTrue(all('casing' in r['description'] and r['pile']!='0' for r in self.review['reported_stresses']))

    def test_load_factors_survive_import_and_invalid_saved_factors_are_rejected(self):
        from pier_cap.pile_review import validate_saved_review
        self.assertEqual(self.review['combination_factors']['1']['WS1'],0)
        self.assertEqual(self.review['combination_factors']['2']['WS1'],1)
        self.assertEqual(self.review['combination_factors']['3']['WS2'],1)
        self.assertEqual(self.review['combination_factors']['4']['WS3'],1)
        for bad in (float('nan'),True,'1'):
            data=deepcopy(self.review);data['combination_factors']['2']['WS1']=bad
            with self.assertRaisesRegex(ValueError,'load factors'):validate_saved_review(data)

    def test_uplift_is_retained_and_head_is_not_any_depth(self):
        head = next(r for r in pile_heads(self.review) if r['combination']=='1' and r['pile']=='4')
        self.assertEqual(head['compression_kip'],0)
        self.assertEqual(head['uplift_kip'],3.87)
        summaries = {(r['state'],r['metric']):r for r in governors(self.review)}
        self.assertEqual(summaries['STRENGTH-I','Head compression (kip)']['value'],27.61)
        self.assertEqual(summaries['STRENGTH-I','Any-depth compression (kip)']['value'],246.92)
        for summary in summaries.values():
            self.assertTrue(summary['records'])
            self.assertTrue(all(r['state']==summary['state'] for r in summary['records']))

    def test_circular_biaxial_stress_independent_hand_calc(self):
        review = {'forces':[dict(axial_tension_kip=-100,m2=30,m3=40,v2=3,v3=4)]}
        section = dict(kind='steel',area_in2=20,s2_in3=100,s3_in3=100,fy_ksi=50,circular=True,issues=[])
        r = elastic_profile(review,section)[0]
        self.assertAlmostEqual(r['stress_max_ksi'],1)
        self.assertAlmostEqual(r['stress_min_ksi'],-11)
        self.assertAlmostEqual(r['elastic_yield_ratio'],.22)
        section['circular']=False
        r = elastic_profile(review,section)[0]
        self.assertAlmostEqual(r['stress_max_ksi'],3.4)
        self.assertAlmostEqual(r['stress_min_ksi'],-13.4)

    def test_symmetric_strand_rows_use_group_orientation_and_exported_prestress(self):
        root = E.parse(str(FIXTURES/'fbmp_end_bent_section.xml')).getroot()
        section = section_from_xml(root)
        self.assertEqual(section['issues'], [])
        points = [p for g in section['groups'] for p in g['points']]
        expected = {(x,y) for y in (-5.5,5.5) for x in (-5.5,-2.75,0,2.75,5.5)}
        expected |= {(x,y) for x in (-5.5,5.5) for y in (-2.75,0,2.75)}
        self.assertEqual(set(points), expected)
        self.assertEqual(len(points), 16)
        # XML prints .15 in² per strand; never silently replace it by .153.
        self.assertEqual(section['prestress_kip'], 16*.15*140)
        profile = elastic_profile({'forces':[dict(axial_tension_kip=-100,m2=30,m3=40,v2=0,v3=0)]}, section)[0]
        self.assertAlmostEqual(profile['stress_max_ksi'], (-100-336)/324 + 12*70/972)
        # A genuinely eccentric or uninterpretable arrangement still needs review.
        root.find('STEEL_GROUPS/BAR_GROUP/PRESTRESS').text = '100'
        self.assertIn('Eccentric', ';'.join(section_from_xml(root)['issues']))
        root.find('STEEL_GROUPS/BAR_GROUP/ORIENTATION').text = '99'
        self.assertIn('Unknown prestressing', ';'.join(section_from_xml(root)['issues']))

    def test_sixty_concrete_stress_stations_match_workbook(self):
        fixture=json.loads((FIXTURES/'pile_workbook_reference.json').read_text())
        result=elastic_profile(fixture)
        self.assertEqual(len(result),60)
        for r in result:
            self.assertAlmostEqual(r['stress_min_ksi'],r['expected_min'],places=10,msg=str(r['source_row']))
            self.assertAlmostEqual(r['stress_max_ksi'],r['expected_max'],places=10,msg=str(r['source_row']))

    def test_bad_units_missing_results_and_duplicates_rejected(self):
        mutations = [lambda r:r.find('.//PILE_INTERNAL_FORCES/PILE/ELEMENT/PILE_ELEMENT_I_END/AXIAL').set('units','N'),
            lambda r:r.find('.//PILE_INTERNAL_FORCES/PILE').remove(r.find('.//PILE_INTERNAL_FORCES/PILE/ELEMENT')),
            lambda r:r.find('.//PILE_DISPLACEMENTS/PILE/NODE').set('node_number','invalid'),
            lambda r:r.find('.//LOAD_CASE_RESULTS').remove(r.find('.//LOAD_CASE_RESULTS/LOAD_CASE')),
            lambda r:r.find('.//PILE_COORDINATES/PILE/POINT/X').__setattr__('text','nan'),
            lambda r:r.find('.//PILE_COORDINATES/PILE/POINT').set('number','2')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                root=E.parse(str(XML)).getroot(); mutate(root)
                with self.assertRaises(ValueError):import_pile_xml(E.tostring(root))

    def test_missing_dc_is_unavailable_and_entities_are_rejected(self):
        root=E.parse(str(XML)).getroot()
        for n in root.findall('.//PILE_INTERNAL_FORCES/PILE/ELEMENT/PILE_ELEMENT_I_END/FAILURE-RATIO'):
            n.getparent().remove(n)
        data=import_pile_xml(E.tostring(root))
        self.assertIsNone(data['forces'][0]['model_dc'])
        with self.assertRaises(ValueError):
            import_pile_xml(b'<!DOCTYPE x [<!ENTITY y "test">]><FB-MULTIPIER_MODEL_DATA/>')


class TrialTests(unittest.TestCase):
    def rows(self, pairs, **extra):
        return [dict(series='A',trial=str(i),combination='1',pile='1',embedment_ft=e,displacement_in=d,dc=None,
                     converged=None,**extra) for i,(e,d) in enumerate(pairs,1)]

    def test_reference_and_row_order(self):
        rows=parse_trials((FIXTURES/'pile_minimum_tip_reference.csv').read_text())
        result=evaluate_trials(rows,reference_elevation=24.5)
        self.assertAlmostEqual(result['proposed_embedment_ft'],32.74)
        self.assertAlmostEqual(result['required_embedment_ft'],37.74)
        self.assertAlmostEqual(result['tip_elevation_ft'],-13.24)
        self.assertEqual(result['critical_embedment_ft'],32.74)
        self.assertEqual(result['selection_mode'],'automatic')
        self.assertEqual(result,evaluate_trials(list(reversed(rows)),reference_elevation=24.5))

    def test_driven_pile_default_adds_five_even_below_twenty_five(self):
        rows = self.rows([(20,1),(15,1.05)])
        result = evaluate_trials(rows)
        self.assertEqual(result['critical_embedment_ft'], 20)
        self.assertEqual(result['extension_mode'], 'fixed')
        self.assertEqual(result['extension_ft'], 5)
        self.assertEqual(result['required_embedment_ft'], 25)
        self.assertIsNone(result['tip_elevation_ft'])
        self.assertEqual(evaluate_trials(rows,reference_elevation=21.5)['tip_elevation_ft'], -3.5)
        self.assertEqual(evaluate_trials(rows,mode='lesser')['required_embedment_ft'], 24)

    def test_shallowest_qualifying_pair_matches_spreadsheet_min_formula(self):
        result=evaluate_trials(self.rows([(50,1),(40,1.05),(30,2),(20,2.01)]))
        self.assertEqual(result['critical_embedment_ft'],30)
        self.assertIsNone(result['tip_elevation_ft'])

    def test_each_series_needs_a_qualifying_pair(self):
        a=self.rows([(50,1),(40,1.01)])
        b=[dict(r,series='B') for r in self.rows([(60,1),(50,2)])]
        r=evaluate_trials(a+b)
        self.assertIsNone(r['proposed_embedment_ft'])
        self.assertIsNone(r['accepted_embedment_ft'])
        self.assertIsNone(r['required_embedment_ft'])

    def test_negative_tip_floor_and_distinct_ground_cutoff(self):
        r=evaluate_trials(self.rows([(30,1),(20,1.01)]),accepted_embedment=32.74,
            reference_elevation=24.5,cutoff_elevation=40,round_feet=True)
        self.assertEqual(r['tip_elevation_ft'],-14)
        self.assertEqual(r['total_length_ft'],54)
        r=evaluate_trials(self.rows([(30,1),(20,1.01)]),accepted_embedment=32.74,
            reference_elevation=24.5,cutoff_elevation=40.5,round_feet=True)
        self.assertEqual(r['tip_elevation_ft'],-14)
        self.assertEqual(r['total_length_ft'],55)
        r=evaluate_trials(self.rows([(20,1),(10,1.01)]),accepted_embedment=10,
            reference_elevation=20,mode='lesser')
        self.assertEqual(r['extension_ft'],2)

    def test_dc_and_convergence_remain_separate_from_spreadsheet_delta_formula(self):
        for update in [dict(converged=False),dict(dc=1.1)]:
            rows=self.rows([(50,1),(40,1.01)])
            rows[1].update(update)
            result = evaluate_trials(rows)
            self.assertEqual(result['critical_embedment_ft'],50)
            self.assertFalse(result['rows'][0]['analysis_ok'])

    def test_inclusive_point_one_and_no_qualifying_pair(self):
        r=evaluate_trials(self.rows([(30,1),(20,1.1),(10,2)]),reference_elevation=100)
        self.assertEqual(r['critical_embedment_ft'],30)
        self.assertEqual(r['tip_elevation_ft'],65)
        self.assertEqual(r['rows'][0]['next_embedment_ft'],20)
        self.assertEqual(r['rows'][0]['next_displacement_in'],1.1)
        for rows in [self.rows([(30,1),(20,1.100001)]),self.rows([(30,1)])]:
            r=evaluate_trials(rows,reference_elevation=100)
            self.assertIsNone(r['critical_embedment_ft'])
            self.assertIsNone(r['tip_elevation_ft'])

    def test_extension_methods_and_governing_series_are_automatic(self):
        rows=self.rows([(20,1),(10,1.01)])
        for mode, added in [('lesser',4),('fixed',5),('fraction',4)]:
            r=evaluate_trials(rows,mode=mode,reference_elevation=24.5)
            self.assertEqual(r['extension_ft'],added)
            self.assertEqual(r['tip_elevation_ft'],24.5-20-added)
        deep=self.rows([(50,1),(40,1.01)])
        self.assertEqual(evaluate_trials(deep,mode='fraction')['extension_ft'],10)
        self.assertEqual(evaluate_trials(self.rows([(25,1),(20,1.01)]))['extension_ft'],5)
        r=evaluate_trials(rows+[dict(v,series='B') for v in deep])
        self.assertEqual(r['critical_embedment_ft'],50)

    def test_duplicate_or_missing_rows_are_not_silent(self):
        with self.assertRaises(ValueError):evaluate_trials(self.rows([(10,1),(10,2)]))
        for text in ['1,2,3,4','1,2,3,nan,1','1,2,3,0,1','1,2,3,10,-1', 'trial,combination,pile,embedment_ft,displacement_in\n']:
            with self.subTest(text=text),self.assertRaises(ValueError):parse_trials(text)
        rows=parse_trials('1\t2\t4\t50\t1.2\n2\t3\t1\t40\t1.21')
        self.assertEqual(len(rows),2)
        self.assertEqual(evaluate_trials(rows)['proposed_embedment_ft'],50)


if __name__=='__main__':unittest.main()
