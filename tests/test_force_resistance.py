"""Current sectional overlays must never silently replace the analyzed demand."""
from copy import deepcopy
import unittest
from pier_cap.fbmp import import_fbmp_xml
from pier_cap.model import evaluate,set_inputs
from pier_cap.force_diagrams import cap_force_figure,ForceDiagramPanel
from pier_cap.transverse import suggested_detail,shear_intervals
from pier_cap.detailing import hook_paths
from pier_cap.model import bar_positions
from pier_cap.force_trace import RESISTANCE,THRESHOLD,DEMAND,DEMAND_LOWER
from tests.test_fbmp import FIXTURE


def overlays(figure):
    return [t for t in figure.data if (t.meta or {}).get('role') in ('resistance','threshold')]


class ForceResistanceTests(unittest.TestCase):
    def setUp(self):
        self.case=import_fbmp_xml(FIXTURE)
        self.case['inputs']['n_B1']=2

    def test_signed_capacities_and_added_extents_use_current_calculation(self):
        e=evaluate(self.case);base=cap_force_figure(self.case)
        figure=cap_force_figure(self.case,show_resistance=True,evaluation=e)
        curves={t.meta['capacity']:t for t in overlays(figure)}
        self.assertEqual([v for v in curves['Mr_N'].y if v is not None],[-e.value('Mr_N','kip*ft')]*2)
        self.assertNotIn('Mr_P',curves)  # A single positive-resistance outline.
        paths=hook_paths(e,bar_positions(e,'B'))
        first=paths[0]
        positive=curves['Mr_B'];self.assertNotIn(None,positive.x)
        self.assertEqual(positive.x[0],0);self.assertAlmostEqual(positive.x[-1],19.24)
        self.assertEqual(positive.y[0],e.value('Mr_P','kip*ft'))
        self.assertEqual(positive.y[-1],e.value('Mr_P','kip*ft'))
        for start,end in [((p['left']+p['radius'])/12,(p['right']-p['radius'])/12) for p in paths]:
            at_start=[y for x,y in zip(positive.x,positive.y) if abs(x-start)<1e-9]
            at_end=[y for x,y in zip(positive.x,positive.y) if abs(x-end)<1e-9]
            self.assertEqual(at_start,[e.value('Mr_P','kip*ft'),e.value('Mr_B','kip*ft')])
            self.assertEqual(at_end,[e.value('Mr_B','kip*ft'),e.value('Mr_P','kip*ft')])
        self.assertIn('Continuous bottom steel only',positive.customdata[0])
        demands=[t for t in figure.data if not (t.meta or {}).get('role')]
        self.assertEqual(len(demands),len(base.data))
        for t,same in zip(base.data,demands):
            self.assertEqual(same.x,t.x)
            self.assertEqual(same.y,t.y)
            self.assertEqual(same.customdata,t.customdata)
        self.assertEqual(curves['T_threshold'].meta['role'],'threshold')
        self.assertIn('not resistance',curves['T_threshold'].name)
        self.assertAlmostEqual(curves['T_threshold'].y[0],e.value('T_threshold','kip*ft'))

    def test_solid_complementary_demand_and_resistance_styles(self):
        fig=cap_force_figure(self.case,show_resistance=True)
        for t in overlays(fig):
            self.assertEqual(t.line.dash,'solid')
            self.assertEqual(t.line.color,THRESHOLD if t.meta['role']=='threshold' else RESISTANCE)
            self.assertNotIn(t.line.color,(DEMAND,DEMAND_LOWER))
        self.assertNotIn('Dashed lines',fig.layout.meta['resistance_notice'])
        plain=deepcopy(self.case);plain['inputs']['n_B1']=0
        capacity=next(t for t in overlays(cap_force_figure(plain,show_resistance=True)) if t.meta['capacity']=='Mr_P')
        self.assertEqual(tuple(capacity.x),(0,19.24))

    def test_service_modes_hide_all_strength_overlays(self):
        fig=cap_force_figure(self.case,show_resistance=True)
        ids=[i for i,t in enumerate(fig.data) if (t.meta or {}).get('role')]
        for button in fig.layout.updatemenus[0].buttons:
            strength='strength' in button.label.lower()
            self.assertEqual([button.args[0]['visible'][i] for i in ids],[strength]*len(ids))
        self.assertTrue(ids)

    def test_actual_shear_matches_checks_and_has_no_uniform_fallback(self):
        self.case['transverse_detail']=suggested_detail(evaluate(self.case))
        e=evaluate(self.case);intervals=shear_intervals(e)
        fig=cap_force_figure(self.case,show_resistance=True,evaluation=e)
        curves=[t for t in overlays(fig) if t.meta['capacity']=='Vr_actual']
        self.assertEqual(len(curves),2)
        self.assertFalse(any(t.meta['capacity']=='Vr_uniform' for t in overlays(fig)))
        self.assertEqual(list(curves[0].y[::2]),[v['vr'] for v in intervals])
        self.assertEqual(list(curves[1].y[::2]),[-v['vr'] for v in intervals])
        self.assertEqual(list(curves[0].x[::2]),[v['a']['station_in']/12 for v in intervals])
        self.assertNotIn(None,curves[0].x)
        self.assertEqual(curves[0].x[0],intervals[0]['a']['station_in']/12)
        self.assertEqual(curves[0].x[-1],intervals[-1]['b']['station_in']/12)
        for i in range(1,len(curves[0].x)-1,2):self.assertEqual(curves[0].x[i],curves[0].x[i+1])
        checks=[c for c in e.checks if c.key.startswith('Chk_actual_shear_')]
        self.assertEqual([v['ratio'] for v in intervals],[c.ratio for c in checks])
        self.case['transverse_detail']['runs']=[]
        empty=cap_force_figure(self.case,show_resistance=True)
        self.assertFalse(any(t.meta['capacity'].startswith('Vr_') for t in overlays(empty)))
        self.assertIn('No valid adjacent',empty.layout.meta['resistance_notice'])

    def test_width_depth_trials_and_layout_mismatch_are_explicit(self):
        original=cap_force_figure(self.case,show_resistance=True)
        trial=cap_force_figure(set_inputs(self.case,h=48),show_resistance=True)
        self.assertIn('TRIAL SECTION',trial.layout.meta['resistance_notice'])
        self.assertIn('Analyzed cap 48 × 36',trial.layout.title.text)
        self.assertIn('Current resistance section 48 × 48',trial.layout.title.text)
        a=next(t for t in overlays(original) if t.meta['capacity']=='Mr_N')
        b=next(t for t in overlays(trial) if t.meta['capacity']=='Mr_N')
        self.assertNotEqual(a.y,b.y)
        mismatch=cap_force_figure(set_inputs(self.case,S_pile=7),show_resistance=True)
        self.assertFalse(overlays(mismatch))
        self.assertIn('OVERLAY UNAVAILABLE',mismatch.layout.meta['resistance_notice'])

    def test_toggle_updates_steel_keeps_selected_mode_and_removes_stale_capacity(self):
        panel=ForceDiagramPanel()
        self.addCleanup(panel.close)
        panel.refresh(self.case)
        figure=panel.figure
        panel.figure.layout.updatemenus[0].active=2
        panel.show_resistance.value=True
        self.assertIs(panel.figure,figure)
        self.assertEqual(panel.figure.layout.updatemenus[0].active,2)
        old=deepcopy(next(t.y for t in overlays(figure) if t.meta['capacity']=='Mr_N'))
        self.case['inputs']['Bar_N1']=11
        panel.refresh(self.case)
        self.assertNotEqual(next(t.y for t in overlays(figure) if t.meta['capacity']=='Mr_N'),old)
        self.assertEqual(panel.figure.layout.updatemenus[0].active,2)
        self.case['inputs']['b']=0
        panel.refresh(self.case)
        self.assertFalse(overlays(figure))
        self.assertIn('UNAVAILABLE',panel.resistance_notice.value)
        panel.show_resistance.value=False
        self.assertFalse(overlays(figure))
        self.assertEqual(panel.resistance_notice.value,'')
