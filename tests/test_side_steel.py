"""Search coverage and explanations for side steel below the skin-depth trigger."""
from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from pier_cap.model import evaluate, set_inputs, side_reinforcement
from pier_cap.optimizer import SearchConfig, search, layout_grids, bounded_layouts, cage_complexity
from pier_cap.sections import SectionGrid, run_section_study
from pier_cap.section_widgets import SectionStudy
from pier_cap.visuals import side_steel_html
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case

ROOT=Path(__file__).resolve().parent.parent
SMALL=SearchConfig(main_bars=(8,),top_counts=(8,),bottom_counts=(8,),
                   hoop_bars=(5,),hoop_spacings=(8,),skin_bars=(4,5))


def shallow_case():
    case=set_inputs(default_case(),h=36)
    case['analysis']['geometry']['h']=36
    return case


class SideSteelTests(unittest.TestCase):
    def test_zero_side_geometry_is_evaluated_once_and_study_budget_agrees(self):
        grids=layout_grids(SMALL)
        self.assertEqual(SearchConfig().skin_counts,tuple(range(8)))
        self.assertEqual(math.prod(map(len,grids)),15)  # one zero + seven of each size
        layouts=list(bounded_layouts(grids,100))
        self.assertEqual(sum(side[1]==0 for *_,side,pb,bb,pc,bc in layouts),1)
        result=search(shallow_case(),SMALL)
        self.assertEqual(result.evaluated,15)
        self.assertTrue(result.exhaustive)
        study=run_section_study(shallow_case(),SectionGrid(widths=(48,),depths=(36,),
                               max_total_cases=15),SMALL)
        point=study.points[0]
        self.assertEqual(point.result.total,15)
        self.assertEqual(point.result.candidates,result.candidates)
        self.assertTrue(point.result.exhaustive)
        for config in (replace(SMALL,skin_bars=()),replace(SMALL,skin_counts=())):
            with self.assertRaises(ValueError):search(shallow_case(),config)

    def test_small_side_counts_can_outrank_the_old_minimum(self):
        result=search(shallow_case(),SMALL)
        old=search(shallow_case(),replace(SMALL,skin_counts=(5,6,7)))
        self.assertLess(result.candidates[0].weight_lb,old.candidates[0].weight_lb)
        self.assertEqual(result.candidates[0].changes['n_skin'],4)
        self.assertIn(3,[c.changes['n_skin'] for c in result.candidates])
        self.assertEqual([c.weight_lb for c in result.candidates],
                         sorted(c.weight_lb for c in result.candidates))
        # No synthetic pass: even at this shallow section zero fails shrinkage.
        self.assertNotIn(0,[c.changes['n_skin'] for c in result.candidates])
        self.assertGreater(result.rejection_counts['Shrinkage reinforcement area'],0)

    def test_depth_exemption_does_not_bypass_shrinkage_and_explanation_is_read_only(self):
        case=shallow_case();before=deepcopy(case)
        e=evaluate(case)
        info=side_reinforcement(e)
        self.assertFalse(info['depth_required'])
        self.assertEqual({c.key for c in info['zero_side_failures']},
                         {'Chk_shrink_area','Chk_shrink_space'})
        self.assertEqual(case,before)
        zero=evaluate(set_inputs(case,n_skin=0))
        self.assertFalse(zero.eligible)
        self.assertEqual(zero.value('Chk_skin_area'),'✓ PASS')
        self.assertEqual(zero.value('Ash_side','in^2/ft'),0)
        self.assertGreater(zero.value('Ash_req','in^2/ft'),0)
        self.assertAlmostEqual(zero.value('SP_skin','in'),27.75)
        self.assertAlmostEqual(zero.value('s_shrink_limit','in'),12)
        self.assertEqual(side_reinforcement(zero),info)
        self.assertTrue(side_reinforcement(evaluate(default_case()))['depth_required'])
        text=side_steel_html(e)
        for expected in ('not required','Shrinkage reinforcement area','Shrinkage reinforcement spacing',
                         'not included in flexural resistance'):
            self.assertIn(expected,text)

    def test_unused_side_size_has_no_weight_or_complexity_penalty(self):
        zero=set_inputs(shallow_case(),n_skin=0,Bar_skin=3)
        other=set_inputs(zero,Bar_skin=11)
        self.assertEqual(evaluate(zero).weight_lb,evaluate(other).weight_lb)
        self.assertEqual(cage_complexity(zero['inputs']),cage_complexity(other['inputs']))
        with_side=set_inputs(zero,n_skin=3,Bar_skin=5)
        a=evaluate(zero);b=evaluate(with_side)
        self.assertLess(a.weight_lb,b.weight_lb)
        self.assertLess(cage_complexity(zero['inputs']),cage_complexity(with_side['inputs']))
        for region in 'NPB':
            self.assertEqual(a.value('Mr_'+region),b.value('Mr_'+region))
            self.assertGreater(a.value('DC_long_'+region),b.value('DC_long_'+region))


class SideSteelWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app=CapNotebook(shallow_case())
        self.study=SectionStudy(self.app)

    def tearDown(self):
        self.study.close();self.app.close()

    def test_search_and_study_show_actual_side_steel_reason(self):
        self.assertEqual(self.app.search_lists['skin_counts'].value,tuple(range(8)))
        self.assertEqual(self.app.search_lists['skin_counts'].options,tuple(range(11)))
        self.assertIn('Shrinkage reinforcement area',self.app.cage.children[1].value)
        self.app.search_result=search(self.app.case,SMALL)
        self.app._render_candidates()
        self.assertIn('0 matching layouts without side bars',self.app.search_text.value)
        self.study.study=run_section_study(self.app.case,
                            SectionGrid(widths=(48,),depths=(36,)),SMALL)
        self.study.target.value=1
        self.study._render()
        self.assertIn('not required',self.study.selection_info.value)
        self.assertIn('Shrinkage reinforcement area',self.study.selection_info.value)
        self.app.controls['n_skin'].value=0
        self.assertIn('no side bars',self.app.cage.children[1].value)
        self.assertFalse(self.app.current.eligible)

    def test_old_default_search_is_upgraded_but_new_deliberate_choices_survive(self):
        notebook=json.loads((ROOT/'Pier_Cap_Design_Optimizer.ipynb').read_text(encoding='utf-8'))
        source=''.join(next(c for c in notebook['cells'] if c.get('id')=='7447e4cc')['source'])
        def rerun():
            context={'app':self.app,'section_app':self.study,'case':default_case(),'ROOT':ROOT}
            with patch.object(CapNotebook,'display'):
                exec(source,context)
            self.app=context['app']
        self.app.search_lists['skin_counts'].options=tuple(range(4,11))
        self.app.search_lists['skin_counts'].value=(5,6,7)
        before=deepcopy(self.app.case)
        rerun()
        self.assertEqual(self.app.case,before)
        self.assertEqual(self.app.search_lists['skin_counts'].value,tuple(range(8)))
        self.app.search_lists['skin_counts'].value=(2,4)
        rerun()
        self.assertEqual(self.app.search_lists['skin_counts'].value,(2,4))
        # An older custom range keeps its values and gains the zero choice.
        self.app.search_lists['skin_counts'].options=tuple(range(4,11))
        self.app.search_lists['skin_counts'].value=(4,8)
        rerun()
        self.assertEqual(self.app.search_lists['skin_counts'].value,(0,4,8))
