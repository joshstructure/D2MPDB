"""Independent positive cages and physical pile-head interference.

The 12 in head and 1.5 in gap below are test dimensions, not project defaults.
"""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from lxml import etree as E
from pier_cap.model import (default_case, set_inputs, evaluate, bar_positions,
                            upgrade_case, BAR_AREA, BAR_DIAMETER, DEFINITIONS)
from pier_cap.optimizer import SearchConfig, search, candidate_case
from pier_cap.sections import SectionGrid, run_section_study
from pier_cap.io import load_case, export_bundle, export_blockpad, input_formula
from pier_cap.visuals import section_figure
from pier_cap.widgets import CapNotebook
from pier_cap.section_widgets import SectionStudy

ROOT=Path(__file__).resolve().parent.parent
NEW_INPUTS={'Bar_P','Bar_B','Ready_pile','Pile_embed','C_pile'}


def head_case(**changes):
    return set_inputs(default_case(),**(dict(Ready_pile=True,Pile_embed=12,
        C_pile=1.5,n_skin=7,n_P1=4)|changes))


def legacy_case():
    case=default_case();case['schema_version']=1
    for name in NEW_INPUTS:
        case['inputs'].pop(name);case['units'].pop(name)
    case['inputs']['Bar_pos']=7;case['units']['Bar_pos']='unitless'
    return case


class PositiveRegionTests(unittest.TestCase):
    def test_independent_areas_centroids_and_flexural_resistance(self):
        case=head_case(Bar_P=9,n_P1=4,n_P2=2,Bar_B=7,n_B1=8,n_B2=1)
        e=evaluate(case);p=case['inputs']
        for region,size,n1,n2 in [('P',9,4,2),('B',7,8,1)]:
            with self.subTest(region=region):
                area=(n1+n2)*BAR_AREA[size]
                y1=p['C_b']+BAR_DIAMETER[p['Bar_v']]+BAR_DIAMETER[size]/2
                dc=(n1*y1+n2*(y1+p['s_row']))/(n1+n2)
                a=area*p['fy']/(.85*p['fc']*p['b'])
                self.assertAlmostEqual(e.value('As_'+region),area)
                self.assertAlmostEqual(e.value('dc_'+region),dc)
                self.assertAlmostEqual(e.value('Mr_'+region),p['phi_f']*area*p['fy']*(p['h']-dc-a/2))
        changed=evaluate(set_inputs(case,Bar_P=10,n_P1=6))
        for name in ('As_B','dc_B','Mr_B','SP_B','fs_I_B'):
            self.assertEqual(e.value(name),changed.value(name))
        self.assertNotEqual(e.value('Mr_P'),changed.value('Mr_P'))
        fast=evaluate(case,fast=True)
        for name in ('As_P','As_B','dc_P','dc_B','Mr_P','Mr_B','SP_P','SP_B'):
            self.assertAlmostEqual(e.value(name),fast.value(name))

    def test_side_rows_avoid_pile_and_central_gap_remains_checked(self):
        case=head_case(Bar_P=6,n_P1=4,n_P2=4,Bar_B=8)
        e=evaluate(case)
        bars=[b for b in bar_positions(e,'P') if b['kind'].startswith('Bottom')]
        self.assertEqual(len(bars),8)
        for b in bars:
            self.assertTrue(b['x']+b['diameter']/2<=e.value('Pile_left')-1.5+1e-9 or
                            b['x']-b['diameter']/2>=e.value('Pile_right')+1.5-1e-9)
        self.assertTrue(any(e.value('Pile_left')<b['x']<e.value('Pile_right')
                            for b in bar_positions(e,'B') if b['kind']=='Bottom row 1'))
        first=sorted(b['x'] for b in bars if b['kind']=='Bottom row 1')
        self.assertAlmostEqual(e.value('SP_P'),max(b-a for a,b in zip(first,first[1:])))
        self.assertAlmostEqual(e.value('s_shrink'),max(e.value(n) for n in ('SP_N','SP_B','SP_skin','s_G','s_L')))
        self.assertIn('PASS',e.value('Chk_shrink_space'))
        self.assertIn('FAIL',evaluate(set_inputs(case,MI_P=1500)).value('Chk_I_P'))
        manual=evaluate(set_inputs(case,Manual_spacing=True,SP_detail_P=3))
        self.assertGreater(manual.value('SP_P'),3)

    def test_second_row_above_head_is_full_width_and_bad_layouts_fail(self):
        e=evaluate(head_case(n_P1=4,n_P2=4,s_row=12))
        first=[b for b in bar_positions(e,'P') if b['kind']=='Bottom row 1']
        second=[b for b in bar_positions(e,'P') if b['kind']=='Bottom row 2']
        self.assertTrue(all(b['x']<e.value('Pile_left') or b['x']>e.value('Pile_right') for b in first))
        self.assertTrue(any(e.value('Pile_left')<b['x']<e.value('Pile_right') for b in second))
        self.assertTrue(all(b['y']-b['diameter']/2>=13.5 for b in second))
        crowded=evaluate(head_case(n_P1=12))
        self.assertTrue(any('clear spacing' in issue for issue in crowded.issues))
        clash=evaluate(head_case(n_P1=8,Manual_spacing=True,SP_detail_P=6))
        self.assertTrue(any('pile footprint' in issue for issue in clash.issues))
        tall=evaluate(head_case(Pile_embed=45))
        self.assertFalse(tall.eligible)
        with self.assertRaisesRegex(ValueError,'exceeds'):
            evaluate(head_case(Pile_embed=49))

    def test_pending_dimensions_and_migration_preserve_forces(self):
        old=legacy_case();original=deepcopy(old)
        case=load_case(json.dumps(old).encode())
        self.assertEqual(old,original)
        self.assertEqual(case['analysis'],old['analysis'])
        self.assertEqual(case['inputs']['Bar_P'],7)
        self.assertEqual(case['inputs']['Bar_B'],7)
        self.assertFalse(case['inputs']['Ready_pile'])
        self.assertEqual(case['inputs']['Mu_P'],old['inputs']['Mu_P'])
        self.assertIn('PENDING',evaluate(case).status)
        self.assertFalse(evaluate(case).eligible)
        for operation in (lambda:search(case),lambda:run_section_study(case)):
            with self.assertRaisesRegex(ValueError,'pile-head'):
                operation()
        with TemporaryDirectory() as folder:
            output=export_bundle(old,folder)
            self.assertEqual(load_case(output/'selected_case.json'),case)
            text=(output/'blockpad_inputs.txt').read_text()
            self.assertIn('Bar_P = 7',text);self.assertIn('Bar_B = 7',text)

    def test_search_and_section_study_vary_both_sizes_and_counts(self):
        config=SearchConfig(main_bars=(8,),top_counts=(8,),pile_bars=(8,9),
            span_bars=(7,8),pile_counts=(4,6),span_counts=(6,8),hoop_bars=(5,),
            hoop_spacings=(8,),skin_bars=(5,),skin_counts=(7,))
        result=search(head_case(),config)
        self.assertEqual(result.total,16);self.assertTrue(result.exhaustive)
        self.assertTrue(result.passed)
        self.assertTrue(any(c.changes['Bar_P']!=c.changes['Bar_B'] for c in result.candidates))
        self.assertTrue(any(c.changes['n_P1']!=c.changes['n_B1'] for c in result.candidates))
        for i,candidate in enumerate(result.candidates):
            e=evaluate(candidate_case(result,i));self.assertTrue(e.eligible)
            self.assertIn('pile',candidate.label);self.assertIn('between',candidate.label)
            self.assertFalse(e.issues)
        study=run_section_study(head_case(),SectionGrid(widths=(48,),depths=(48,)),config)
        self.assertEqual(study.total,16)
        self.assertEqual(study.points[0].result.candidates,result.candidates)

    def test_different_positive_sizes_have_no_free_steel_in_cost(self):
        e=evaluate(head_case(Bar_P=9,n_P1=6,Bar_B=8,n_B1=8))
        shared=evaluate(set_inputs(e.case,Bar_P=8))
        difference=(e.value('As_P')+e.value('As_B')-max(shared.value('As_P'),shared.value('As_B')))*e.value('L_cap')*490/1728
        self.assertAlmostEqual(e.weight_lb-shared.weight_lb,difference)

    def test_drawings_and_widgets_keep_regions_separate(self):
        app=CapNotebook(head_case());study=SectionStudy(app)
        try:
            before=app.current.value('As_B')
            app.controls['Bar_P'].value=9;app.controls['n_P1'].value=4
            self.assertEqual(app.current.value('As_B'),before)
            self.assertAlmostEqual(app.current.value('As_P'),4)
            self.assertIn('pile_bars',app.search_lists);self.assertIn('span_counts',app.search_lists)
            for name,values in dict(main_bars=(8,),top_counts=(8,),pile_bars=(9,),
                pile_counts=(4,),span_bars=(8,),span_counts=(8,),hoop_bars=(5,),
                hoop_spacings=(8,),skin_bars=(5,),skin_counts=(7,)).items():
                app.search_lists[name].value=values
            study.bounds['width'][0].value=study.bounds['width'][1].value=48
            study.bounds['depth'][0].value=study.bounds['depth'][1].value=48
            study.target.value=1
            study._run(None)
            self.assertIsNotNone(study.study)
            self.assertEqual(len(study.preview_figures),3)
            self.assertIn('at pile',study.preview_figures[0].layout.title.text)
            self.assertIn('between piles',study.preview_figures[1].layout.title.text)
            fig=section_figure(app.current,'P')
            self.assertTrue(any(s.type=='rect' and s.y1==12 for s in fig.layout.shapes))
            bottom=next(t for t in fig.data if t.name.startswith('Bottom row 1'))
            self.assertEqual(len(bottom.x),4)
        finally:
            study.close();app.close()

    def test_old_workbench_controls_and_case_upgrade_on_rerun(self):
        app=CapNotebook(head_case());old=app
        try:
            import ipywidgets as W
            for name in ('pile_bars','span_bars','pile_counts','span_counts'):
                app.search_lists.pop(name).close()
            app.search_lists['bottom_counts']=W.SelectMultiple(options=(4,6,8),value=(6,8))
            app.search_lists['main_bars'].value=(7,9)
            app.case=legacy_case()
            notebook=json.loads((ROOT/'Pier_Cap_Design_Optimizer.ipynb').read_text())
            context={'app':app,'ROOT':ROOT}
            with patch.object(CapNotebook,'display'):
                exec(''.join(next(c for c in notebook['cells'] if c['id']=='7447e4cc')['source']),context)
            app=context['app']
            self.assertEqual(app.case,upgrade_case(legacy_case()))
            for name in ('pile_counts','span_counts'):self.assertEqual(app.search_lists[name].value,(6,8))
            for name in ('pile_bars','span_bars'):self.assertEqual(app.search_lists[name].value,(7,9))
        finally:
            app.close()
            if app is not old:old.close()

    def test_legacy_blockpad_gets_current_equations_without_touching_other_reports(self):
        root=E.Element('blockpad');other=E.SubElement(root,'report',name='Geometry')
        other.text='Project inputs remain unchanged.'
        report=E.SubElement(root,'report',name='PierCapDesign')
        for d in DEFINITIONS:
            if d['name'] in NEW_INPUTS:continue
            formula=d['formula']
            if d['name']=='Bar_pos':formula='Bar_pos = 8'
            if d['name']=='As_P':formula='As_P = (n_P1+n_P2)*Ab(Bar_pos)+n_PU*Ab(Bar_U) to in^2'
            E.SubElement(report,'dynexp',formula=formula)
        table=E.SubElement(report,'table')
        for z in 'PB':
            row=E.SubElement(table,'row')
            node=next(d for d in report.findall('dynexp') if d.get('formula','').startswith(f'n_{z}1 ='))
            row.append(node)
            cell=E.SubElement(row,'c',formula='Bar_pos');E.SubElement(cell,'num').text='8'
            cell=E.SubElement(row,'c',formula=f'n_{z}1*Ab(Bar_pos) to in^2');E.SubElement(cell,'num').text='6.32 in^2'
        canvas=E.SubElement(report,'canvas',name='LiveReinforcementSections')
        E.SubElement(canvas,'plot',formula='PlotLines(PierCapDesign.GfxRowX(PierCapDesign.n_P1,0,1,.1),[1])')
        original=E.tostring(root);case=head_case(Bar_P=9,Bar_B=7)
        with TemporaryDirectory() as folder:
            out=export_blockpad(original,case,Path(folder)/'review.bpad')
            again=export_blockpad(out,case,Path(folder)/'second.bpad')
            first_plots=None
            for path in (out,again):
                tree=E.parse(str(path))
                self.assertEqual(E.tostring(tree.find("report[@name='Geometry']")),E.tostring(other))
                definitions=[node.get('formula') for node in tree.iter('dynexp')]
                for d in DEFINITIONS:
                    if d['name'] in ('Status_layout','Status_section'):continue
                    expected=input_formula(d['name'],case['inputs'][d['name']]) if d['input'] else d['formula']
                    self.assertEqual(definitions.count(expected),1,d['name'])
                refs=[node.get('formula') for node in tree.iter('c')]
                self.assertEqual(refs,['Bar_P','n_P1*Ab(Bar_P) to in^2','Bar_B','n_B1*Ab(Bar_B) to in^2'])
                self.assertFalse(list(tree.iter('num')))
                plots=[node.get('formula') for node in tree.iter('plot')]
                self.assertFalse(any('Bar_pos' in formula or 'y_pos' in formula for formula in plots))
                self.assertTrue(any('PierCapDesign.Pile_embed' in formula for formula in plots))
                self.assertTrue(any('PierCapDesign.P_side_span' in formula for formula in plots))
                self.assertTrue(any('PierCapDesign.SP_detail_P' in formula for formula in plots))
                if first_plots is None:first_plots=plots
                else:self.assertEqual(plots,first_plots)


if __name__=='__main__':
    unittest.main()
