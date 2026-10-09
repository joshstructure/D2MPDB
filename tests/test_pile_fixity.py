from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from pier_cap.pile_fixity import zero_crossings, displacement_fixity, compare_minimum_tip
from pier_cap.pile_review import evaluate_trials, parse_trials, import_pile_xml
from pier_cap.pile_fixity_visual import crossing_rows
from pier_cap.widgets import CapNotebook

FIXTURES = Path(__file__).parent/'fixtures'


def profile(values, *, pile='1', combo='1', spacing=10, batter=1):
    return [dict(combination=combo, pile=pile, node=str(i+1), state='STRENGTH-I',
        distance_ft=i*spacing*batter, vertical_ft=i*spacing, dx=x, dy=0.) for i,x in enumerate(values)]


def review(rows):
    return dict(displacements=rows, piles={r['pile']:{} for r in rows},
                combinations={r['combination']:r['state'] for r in rows},
                combination_factors={r['combination']:{'WS1':1.} for r in rows})


class CrossingTests(unittest.TestCase):
    def test_wind_factors_not_limit_state_names_determine_scope_and_governor(self):
        rows = profile([1,-1,1], combo='1', spacing=40)+profile([1,-1,1], combo='2', spacing=10)
        data = review(rows)
        data['combinations']={'1':'STRENGTH-III','2':'SERVICE-I'}
        data['combination_factors']={'1':{'DC':1.25,'WS1':0.,'WL1':0.},'2':{'DC':1.,'WL2':-.5}}
        f = displacement_fixity(data,cutoff=10,ground=0)
        self.assertEqual(f['wind_combinations'],['2'])
        self.assertEqual(f['excluded_combinations'],['1'])
        self.assertEqual(f['governors'][0]['second_vertical_ft'],15)
        self.assertTrue(f['complete'])
        self.assertFalse(f['profiles'][0]['crossings'])
        # Non-wind profiles without a crossing cannot make this incomplete.
        data['displacements'] = profile([1,1,1],combo='1')+profile([1,-1,1],combo='2')
        f = displacement_fixity(data)
        self.assertEqual(f['unresolved_count'],0)
        self.assertTrue(f['complete'])
        # A missing second crossing in the included wind profile still matters.
        data['displacements'] = profile([1,-1,1],combo='1')+profile([1,1,1],combo='2')
        f = displacement_fixity(data)
        self.assertEqual(f['unresolved_count'],1)
        self.assertFalse(f['complete'])

    def test_table_locations_follow_every_plotted_crossing_with_and_without_cutoff(self):
        from pier_cap.pile_widgets import profile_figure
        data = import_pile_xml(FIXTURES/'fbmp_610_piles.xml')
        for cutoff in (None, 0, 40.25):
            fixity = displacement_fixity(data, cutoff=cutoff, ground=24.5)
            rows = crossing_rows(fixity)
            self.assertEqual(len(rows), 32)
            for combo in data['combinations']:
                fig = profile_figure(data, combo, list(data['piles']), cutoff=cutoff, fixity=fixity)
                markers = [t for t in fig.data if t.meta and t.meta.get('part')=='fixity']
                expected = []
                for row in rows:
                    if row['combination'] != combo: continue
                    if not row['included_in_fixity']:
                        self.assertEqual(row['second_elevation_ft'],'Excluded — no wind')
                        continue
                    for index, name in enumerate(('first','second')):
                        self.assertIsInstance(row[name+'_vertical_ft'], float)
                        if cutoff is None:
                            self.assertEqual(row[name+'_elevation_ft'], 'Enter pile cutoff EL')
                            expected.append(row['crossings'][index]['distance_ft'])
                        else:
                            expected.append(row[name+'_elevation_ft'])
                            self.assertEqual(row[name+'_elevation_ft'], cutoff-row[name+'_vertical_ft'])
                self.assertEqual([t.y[0] for t in markers], expected)

    def test_interpolation_second_not_last_and_signed_components(self):
        rows = profile([2,-2,-1,3,-3])
        result = displacement_fixity(review(rows), cutoff=40, ground=30)
        p = result['governors'][0]
        self.assertEqual([c['vertical_ft'] for c in p['crossings']], [5,22.5,35])
        self.assertEqual(p['second_elevation_ft'],17.5)
        self.assertEqual(p['critical_embedment_ft'],12.5)
        self.assertEqual(p['component'],'DX'); self.assertTrue(result['complete'])
        self.assertEqual(p['crossings'][1]['upper_node'],'3')

    def test_zero_nodes_plateaus_touches_and_tails(self):
        for values, expected in [([0,1,0,-1,0,1,0],[2,4]), ([1,0,0,-1,0,1],[2,4]),
                                 ([1,0,1,-1,1],[2.5,3.5]), ([1,0,0],[]), ([0,0,0],[])]:
            with self.subTest(values=values):
                self.assertEqual([c['vertical_ft'] for c in zero_crossings(profile(values,spacing=1),'dx')],expected)
        self.assertEqual(zero_crossings(profile([1,0,0,-1],spacing=1),'dx')[0]['method'],
                         'Zero-band interval; deeper end used')

    def test_noise_missing_crossings_order_and_bad_stations(self):
        data = profile([1,-1,1e-8,-1e-8,0])
        result = displacement_fixity(review(data))
        self.assertEqual(result['unresolved_count'],1); self.assertFalse(result['complete'])
        self.assertFalse(result['governors'])
        self.assertEqual(zero_crossings(list(reversed(data)),'dx'),zero_crossings(data,'dx'))
        with self.assertRaisesRegex(ValueError,'without duplicates'):zero_crossings(data+[data[-1]],'dx')
        with self.assertRaisesRegex(ValueError,'Zero band'):zero_crossings(data,'dx',-1)

    def test_deepest_across_piles_combinations_and_directions_uses_vertical_depth(self):
        rows = profile([1,-1,1],pile='1',combo='1',spacing=10,batter=2)
        rows += profile([1,-1,1],pile='2',combo='2',spacing=20,batter=1.2)
        for r in rows:
            if r['pile']=='2':r['dy'],r['dx']=r['dx'],0
        # All expected pile/combination pairs exist, with other profiles inactive.
        rows += profile([0,0,0],pile='1',combo='2')+profile([0,0,0],pile='2',combo='1')
        result=displacement_fixity(review(rows),cutoff=10,ground=0)
        p=result['governors'][0]
        self.assertEqual((p['pile'],p['combination'],p['component']),('2','2','DY'))
        self.assertEqual(p['second_vertical_ft'],30); self.assertEqual(p['second_distance_ft'],36)
        self.assertEqual(p['second_elevation_ft'],-20)
        self.assertEqual(p['critical_embedment_ft'],20)


class TipComparisonTests(unittest.TestCase):
    def setUp(self):
        self.fixity=displacement_fixity(review(profile([1,-1,1],spacing=20)),cutoff=10,ground=0)

    def compare(self, depth, **kwargs):
        trials=evaluate_trials(parse_trials(f'1,1,1,{depth},1\n2,1,1,{depth-5},1.01'),reference_elevation=0,cutoff_elevation=10)
        return compare_minimum_tip(trials,self.fixity,ground=0,cutoff=10,**kwargs)

    def test_either_criterion_can_control_and_ties_are_named(self):
        for depth,label,tip in [(10,'Second zero crossing',-25),(30,'Displacement-change trials',-35),
                                (20,'Displacement-change trials + Second zero crossing (tie)',-25)]:
            result=self.compare(depth)
            self.assertEqual(result['controlling_criterion'],label)
            self.assertEqual(result['tip_elevation_ft'],tip); self.assertTrue(result['comparison_complete'])
        self.assertEqual(self.compare(10,add_fixity_allowance=False)['tip_elevation_ft'],-20)

    def test_missing_data_never_becomes_zero_or_complete(self):
        f=displacement_fixity(review(profile([1,-1,0])),cutoff=10,ground=0)
        result=compare_minimum_tip(None,f,ground=0,cutoff=10)
        self.assertIsNone(result['tip_elevation_ft']);self.assertFalse(result['comparison_complete'])
        result=compare_minimum_tip(None,self.fixity,ground=0,cutoff=10)
        self.assertEqual(result['tip_elevation_ft'],-25);self.assertFalse(result['comparison_complete'])
        f=displacement_fixity(review(profile([1,-1,1],spacing=20)),ground=0)
        self.assertIsNone(compare_minimum_tip(None,f,ground=0)['tip_elevation_ft'])

    def test_incomplete_reasons_distinguish_found_crossings_from_other_profiles(self):
        rows = profile([1,-1,1],pile='1',spacing=20)+profile([1,-1,-1],pile='2',spacing=20)
        f = displacement_fixity(review(rows),cutoff=10,ground=0)
        trials = evaluate_trials(parse_trials('1,1,1,10,1\n2,1,1,5,1.01'),reference_elevation=0)
        result = compare_minimum_tip(trials,f,ground=0,cutoff=10)
        self.assertEqual(result['tip_elevation_ft'],-25)
        self.assertFalse(result['comparison_complete'])
        self.assertIn('Crossing available',result['candidates'][1]['status'])
        self.assertEqual(len(result['comparison_issues']),1)
        issues = [p for p in f['profiles'] if p['review_reason']]
        self.assertEqual([(p['pile'],p['component']) for p in issues],[('2','DX')])
        display = crossing_rows(f)
        self.assertEqual(display[2]['first_elevation_ft'],0)
        self.assertEqual(display[2]['second_elevation_ft'],'No second crossing found')
        self.assertEqual(display[1]['second_elevation_ft'],'Not applicable — within zero band')

    def test_missing_cutoff_keeps_crossing_depths_and_names_only_missing_input(self):
        f = displacement_fixity(review(profile([1,-1,1],spacing=20)),ground=0)
        trials = evaluate_trials(parse_trials('1,1,1,10,1\n2,1,1,5,1.01'),reference_elevation=0)
        result = compare_minimum_tip(trials,f,ground=0)
        self.assertEqual(len(result['comparison_issues']),1)
        self.assertIn('Pile cutoff EL',result['comparison_issues'][0])
        row = crossing_rows(f)[0]
        self.assertEqual((row['first_vertical_ft'],row['second_vertical_ft']),(10,30))
        self.assertEqual(row['second_elevation_ft'],'Enter pile cutoff EL')

    def test_fraction_and_rounding_use_same_datum(self):
        f=displacement_fixity(review(profile([1,-1,1],spacing=20)),cutoff=10.25,ground=-.5)
        result=compare_minimum_tip(None,f,ground=-.5,cutoff=10.25,mode='fraction',fraction=.2,round_feet=True)
        self.assertAlmostEqual(result['required_embedment_ft'],19.25*1.2)
        self.assertEqual(result['tip_elevation_ft'],-24);self.assertEqual(result['total_length_ft'],35)

    def test_no_wind_is_not_applicable_but_missing_factors_need_review(self):
        data = review(profile([1,-1,1]))
        data['combination_factors']={'1':{'DC':1.25,'WS1':0.}}
        trials=evaluate_trials(parse_trials('1,1,1,10,1\n2,1,1,5,1.01'),reference_elevation=0)
        result=compare_minimum_tip(trials,displacement_fixity(data,ground=0),ground=0)
        self.assertTrue(result['comparison_complete'])
        self.assertEqual(result['candidates'][1]['status'],'Not applicable — no wind combinations')
        self.assertEqual(result['comparison_issues'],[])
        self.assertEqual(result['tip_elevation_ft'],-15)
        del data['combination_factors']
        result=compare_minimum_tip(trials,displacement_fixity(data,cutoff=10,ground=0),ground=0,cutoff=10)
        self.assertFalse(result['comparison_complete'])
        self.assertEqual(result['fixity']['unknown_combinations'],['1'])
        self.assertTrue(any('Reload the original XML' in s for s in result['comparison_issues']))


class FixityWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app=CapNotebook();self.panel=self.app.pile_review
        data=import_pile_xml(FIXTURES/'fbmp_610_piles.xml')
        for r in data['displacements']:
            r['dx']=r['dy']=r['lateral_in']=0.
            if r['pile']=='3' and r['combination']=='2':
                z=r['vertical_ft'];r['dy']=5-z if z<=25 else z-45
                r['lateral_in']=abs(r['dy'])
        self.panel.set_review(data)
        self.panel.cutoff.value='40';self.panel.reference.value='30'
        self.panel.trial_text.value='1,2,3,20,1\n2,2,3,15,1.01';self.panel.run_trials.click()

    def tearDown(self):self.app.close()

    def test_plot_selection_does_not_change_governor_and_edits_update_every_view(self):
        p=self.panel;r=p.minimum_tip_result
        self.assertEqual(r['tip_elevation_ft'],-10);self.assertTrue(r['comparison_complete'])
        self.assertIn('Second zero crossing',p.minimum_tip_summary.value)
        self.assertIn('Pile 3',p.fixity_summary.value)
        p.combo.value='2';p.piles.value=('3',)
        markers=[t for t in p.figures['profiles'].data if t.meta and t.meta.get('part')=='fixity']
        self.assertEqual([t.y[0] for t in markers],[35,-5])
        self.assertTrue(any(s.y0==-10 for s in p.figures['profiles'].layout.shapes if s.yref=='y'))
        p.piles.value=('1',)
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-10)
        p.fixity_allowance.value=False
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-5)
        self.assertIn('-5.000 ft',p.handoff.value)
        p.cutoff.value='41'
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-4)
        self.assertIn('Figure 2',p.figures['profiles'].layout.title.text)
        self.assertIn('Table 8',p.minimum_tip_summary.value)
        self.assertIn('Table 6',p.minimum_tip_summary.value)
        self.assertNotIn('Why the comparison is incomplete',p.trial_status.value)

    def test_saved_review_and_exports_keep_criterion_and_coordinates(self):
        p=self.panel;p.fixity_allowance.value=False
        state=p.snapshot();p.restore(state)
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-5)
        with TemporaryDirectory() as folder:
            p.save_bundle(folder);folder=Path(folder)
            result=json.loads((folder/'minimum_tip_result.json').read_text())
            self.assertEqual(result['controlling_criterion'],'Second zero crossing')
            self.assertEqual(result['tip_elevation_ft'],-5)
            self.assertIn('Second zero crossing',(folder/'geotech_handoff.html').read_text(encoding='utf-8'))
            self.assertTrue((folder/'pile_zero_crossings.csv').exists())
            self.assertTrue((folder/'minimum_tip_criteria.csv').exists())

    def test_profile_only_and_invalid_inputs_clear_stale_result(self):
        p=self.panel;p.zero_band.value=-1
        self.assertIsNone(p.minimum_tip_result)
        self.assertIn('MINIMUM TIP INPUT NEEDS REVIEW',p.trial_status.value)
        p.zero_band.value=1e-6
        self.assertTrue(p.minimum_tip_result['comparison_complete'])
        p.trial_text.value='';p.run_trials.click()
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-10)
        self.assertFalse(p.minimum_tip_result['comparison_complete'])
        p.zero_band.value=-1
        self.assertIsNone(p.minimum_tip_result)
        self.assertIn('Zero band',p.minimum_tip_summary.value)
        self.assertNotIn('-10.000 ft',p.handoff.value)

    def test_invalid_saved_zero_band_does_not_replace_active_review(self):
        p=self.panel;before=p.snapshot();state=deepcopy(before)
        state['controls']['zero_band']=-1
        with self.assertRaisesRegex(ValueError,'Zero band'):p.restore(state)
        self.assertEqual(p.snapshot(),before)

    def test_legacy_save_recovers_wind_factors_on_same_xml_upload_without_losing_inputs(self):
        p=self.panel;p.set_review(import_pile_xml(FIXTURES/'fbmp_610_piles.xml'))
        p.cutoff.value='40';p.reference.value='30'
        p.trial_text.value='1,2,3,20,1\n2,2,3,15,1.01';p.run_trials.click()
        state=p.snapshot();state['review'].pop('combination_factors')
        p.restore(state)
        self.assertFalse(p.minimum_tip_result['comparison_complete'])
        self.assertIn('Reload the original XML',p.trial_status.value)
        self.app.xml_import.stage((FIXTURES/'fbmp_610_piles.xml').read_bytes(),'fbmp_610_piles.xml')
        self.assertFalse(p.minimum_tip_result['comparison_complete'])
        p._import((FIXTURES/'fbmp_610_piles.xml').read_bytes(),'fbmp_610_piles.xml')
        self.assertTrue(p.minimum_tip_result['comparison_complete'])
        self.assertEqual(p.cutoff.value,'40');self.assertEqual(p.reference.value,'30')
        self.assertEqual(p.trial_text.value,state['controls']['trial_text'])
        self.assertEqual(p.fixity_result['wind_combinations'],['2','3','4'])
        saved=p.snapshot();p.restore(saved)
        self.assertEqual(p.fixity_result['wind_combinations'],['2','3','4'])
        self.assertEqual(p.review['combination_factors'],saved['review']['combination_factors'])
        p.restore(state)
        p._import((FIXTURES/'fbmp_610_piles.xml').read_bytes(),'fbmp_610_piles.xml')
        self.assertTrue(p.minimum_tip_result['comparison_complete'])
        self.assertEqual(p.cutoff.value,'40');self.assertEqual(p.reference.value,'30')

    def test_new_xml_reset_and_calculate_never_flash_green_for_incomplete_comparison(self):
        from pier_cap.source_status import notice_html
        p = self.panel
        p.set_review(import_pile_xml(FIXTURES/'fbmp_610_piles.xml'))
        self.assertIn('MINIMUM-TIP INPUTS RESET',p.trial_status.value)
        self.assertEqual((p.cutoff.value,p.reference.value,p.trial_text.value),('','',''))
        p.reference.value='24.5'
        p.trial_text.value=(FIXTURES/'pile_minimum_tip_reference.csv').read_text()
        statuses=[]
        p.trial_status.observe(lambda change: statuses.append(change['new']), names='value')
        p.run_trials.click()
        self.assertFalse(p.minimum_tip_result['comparison_complete'])
        success_style=notice_html('','', 'success').split('>')[0]
        self.assertFalse(any(s.startswith(success_style) for s in statuses))
        self.assertIn('Enter Pile cutoff EL',p.trial_status.value)
        self.assertEqual(p.fixity_result['unresolved_count'],0)
        p.cutoff.value='40'
        self.assertTrue(p.minimum_tip_result['comparison_complete'])
        self.assertTrue(p.trial_status.value.startswith(success_style))
        self.assertNotIn('Enter Pile cutoff EL',p.trial_status.value)

    def test_crossing_table_follows_plot_selection_without_changing_criterion(self):
        from lxml import html
        p = self.panel
        original_tip = p.minimum_tip_result['tip_elevation_ft']
        p.combo.value='2';p.piles.value=('3',)
        doc = html.fromstring(p.minimum_tip_summary.value)
        selected = doc.xpath('//table[caption[@data-reference="crossings"]]/tr[position()>1]')
        self.assertEqual(len(selected),2)
        self.assertTrue(all(row.xpath('./td')[0].text=='3' and row.xpath('./td')[1].text=='2' for row in selected))
        self.assertIn('-5.000',' '.join(r.text_content() for r in selected))
        self.assertIn('STRENGTH-III',p.minimum_tip_summary.value)
        self.assertEqual(len(doc.xpath('//table[caption[@data-reference="other_crossings"]]/tr[position()>1]')),30)
        p.combo.value='1'
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],original_tip)
        doc = html.fromstring(p.minimum_tip_summary.value)
        selected = doc.xpath('//table[caption[@data-reference="crossings"]]/tr[position()>1]')
        self.assertTrue(all(row.xpath('./td')[1].text=='1' for row in selected))
        self.assertTrue(all('Excluded — no wind' in row.text_content() for row in selected))

    def test_handoff_separates_live_xml_crossing_allowance_and_trial_control(self):
        p=self.panel
        def crossing():return p.minimum_tip_result['candidates'][1]
        self.assertEqual(crossing()['critical_elevation_ft'],-5)
        self.assertIn('EL -5.000 ft',p.handoff.value)
        self.assertIn('= -5.000 − 5.000 allowance = <b>-10.000 ft</b>',p.handoff.value)
        self.assertIn('Loaded displacement XML: <b>fbmp_610_piles.xml</b>',p.handoff.value)
        p.extension.value=3
        self.assertEqual(crossing()['critical_elevation_ft'],-5)
        self.assertEqual(crossing()['raw_tip_elevation_ft'],-8)
        self.assertIn('= -5.000 − 3.000 allowance = <b>-8.000 ft</b>',p.handoff.value)
        # A new pasted trial changes the governing tip, not the loaded XML.
        p.trial_text.value='1,2,3,60,1\n2,2,3,55,1.01';p.run_trials.click()
        self.assertEqual(p.minimum_tip_result['controlling_criterion'],'Displacement-change trials')
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-33)
        self.assertEqual(crossing()['critical_elevation_ft'],-5)
        # A replacement displacement source changes the crossing and its label.
        data=deepcopy(p.review);data['filename']='new-analysis.xml'
        for r in data['displacements']:
            if r['pile']=='3' and r['combination']=='2' and r['vertical_ft']>25:
                r['dy']=r['vertical_ft']-47;r['lateral_in']=abs(r['dy'])
        p.set_review(data);p.cutoff.value='40.25';p.reference.value='30';p.rounding.value=True
        self.assertEqual(crossing()['critical_elevation_ft'],-6.75)
        self.assertEqual(crossing()['raw_tip_elevation_ft'],-9.75)
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-10)
        self.assertIn('new-analysis.xml',p.handoff.value)
        self.assertNotIn('fbmp_610_piles.xml',p.handoff.value)
        self.assertIn('= -6.750 − 3.000 allowance = <b>-9.750 ft</b>',p.handoff.value)


if __name__=='__main__':unittest.main()
