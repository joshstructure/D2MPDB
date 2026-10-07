"""Regression coverage for disappearing steel, current inventory and search errors."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from pier_cap.model import default_case,evaluate,set_inputs,upgrade_case
from pier_cap.transverse import suggested_detail,scheduled_bars
from pier_cap.visuals import section_figure,reinforcement_plan_figure,elevation_figure,configuration_html
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case as ready_case


class LiveCageControlsTests(unittest.TestCase):
    def test_new_defaults_preserve_saved_project_values(self):
        fresh=default_case()['inputs']
        self.assertEqual((fresh['Pile_embed'],fresh['C_pile']),(12,2))
        old=set_inputs(default_case(),Pile_embed=6,C_pile=1,Ready_pile=True)
        self.assertEqual(upgrade_case(old)['inputs'],old['inputs'])

    def test_2d_buttons_hide_physical_bars_and_restore_every_group(self):
        c=set_inputs(ready_case(),n_B1=2,Ready_pile=True,Pile_embed=12,C_pile=2)
        c['transverse_detail']=suggested_detail(evaluate(c));e=evaluate(c)
        for fig in (section_figure(e,'P'),section_figure(e,'B'),reinforcement_plan_figure(e),elevation_figure(e)):
            hoops=next(b for b in fig.layout.updatemenus[0].buttons if b.label=='Hoops + U-bars')
            mask=hoops.args[0]['visible']
            self.assertEqual(len(mask),len(fig.data))
            for t,v in zip(fig.data,mask):
                self.assertEqual(v,(t.meta or {}).get('part','cap') in {'cap','piles','transverse'})
            self.assertTrue(any(v and t.meta and t.meta['part']=='transverse' for t,v in zip(fig.data,mask)))
            self.assertTrue(all(fig.layout.updatemenus[0].buttons[0].args[0]['visible']))
            self.assertFalse(any(s.type=='circle' for s in fig.layout.shapes))
        section=section_figure(e,'B')
        bars=[t for t in section.data if t.name=='Bar outline']
        self.assertTrue(bars)
        self.assertTrue(all(t.fill=='toself' and t.legendgroup for t in bars))

    def test_one_3d_widget_survives_geometry_and_bar_count_changes(self):
        c=ready_case();c['transverse_detail']=suggested_detail(evaluate(c))
        app=CapNotebook(c)
        try:
            widget=app.cage_3d_widget;model_id=widget.model_id
            count=len(scheduled_bars(c));original=deepcopy(c['transverse_detail'])
            for width,depth,top in ((52,42,6),(44,36,4),(48,48,8)):
                for t in widget.data:t.visible=False
                widget.layout.updatemenus[0].active=3
                app.controls['b'].value=width
                app.controls['h'].value=depth
                app.controls['n_N1'].value=top
                self.assertEqual(app.cage_3d_widget.model_id,model_id)
                self.assertEqual(app.case['transverse_detail'],original)
                self.assertEqual(widget.layout.updatemenus[0].active,0)
                hoops=[t for t in widget.data if t.meta['part']=='transverse']
                self.assertEqual(len(hoops),count)
                self.assertTrue(all(t.visible is not False for t in hoops))
                self.assertTrue(all(max(t.z)<=depth for t in hoops))
                for button in widget.layout.updatemenus[0].buttons:
                    self.assertEqual(len(button.args[0]['visible']),len(widget.data))
                self.assertIn(f'{width} × {depth}',app.cage.children[0].value)
            self.assertTrue(any('Cross section' in f.layout.title.text for f in app.figures))
            self.assertTrue(any('PLAN VIEW' in f.layout.title.text for f in app.figures))
            self.assertTrue(any('SIDE ELEVATION' in f.layout.title.text for f in app.figures))
        finally:app.close()

    def test_readout_updates_counts_sizes_and_actual_runs(self):
        c=set_inputs(ready_case(),n_N1=5,Bar_N1=9,n_P1=4,n_B1=2,n_skin=3)
        text=configuration_html(evaluate(c))
        for value in ('5 × #9','4 × #8','2 × #8','3 × #5 per side','actual stations not set'):
            self.assertIn(value,text)
        c['transverse_detail']=suggested_detail(evaluate(c))
        text=configuration_html(evaluate(c))
        self.assertIn('Open-bottom U-bars',text);self.assertIn('R1:',text)

    def test_search_reason_beside_progress_and_retry_clears_error(self):
        app=CapNotebook(ready_case())
        try:
            with patch('pier_cap.widgets.search',side_effect=ValueError('Bad <pitch> input')):
                app._run_search(None)
            self.assertEqual(app.progress.bar_style,'danger')
            self.assertIn('Bad &lt;pitch&gt; input',app.search_status.value)
            row=next(w for w in app.search_panel.children if hasattr(w,'children') and app.progress in w.children)
            self.assertIn(app.search_status,row.children)
            self.assertFalse(app.run_button.disabled)
            app.case['transverse_detail']=suggested_detail(evaluate(app.case))
            app._run_search(None)
            self.assertIn('actual transverse',app.search_status.value.lower())
            self.assertNotIn('Bad',app.search_status.value)
            self.assertEqual(app.progress.bar_style,'danger')
            app.controls['h'].value+=1
            self.assertEqual(app.search_status.value,'')
            self.assertEqual(app.progress.bar_style,'')
        finally:app.close()
