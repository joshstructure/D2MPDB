"""End-grid steel must be physical, persistent and consistent in every view."""
from copy import deepcopy
import csv
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pier_cap import default_case,evaluate,set_inputs
from pier_cap.model import validate_case,bar_positions,steel_quantity_components
from pier_cap.end_grid import settings,geometry,collision_review,pile_conflicts,_distances
from pier_cap.transverse import suggested_detail,scheduled_bars
from pier_cap.lrfd_checks import surface_checks
from pier_cap.io import write_case,load_case,export_bundle
from pier_cap.visuals import section_figure,reinforcement_plan_figure,elevation_figure,checks_html
from pier_cap.cage_3d import layout_3d
from pier_cap.geometry_dimensions import dimensions_figure
from pier_cap.end_grid_views import end_figure


def case(actual=True):
    c=set_inputs(default_case(),h=36,n_skin=3)
    if actual:c['transverse_detail']=suggested_detail(evaluate(c))
    c['schema_version']=5;c['end_face_grid']=settings(c);c['end_face_grid']['enabled']=True
    # Preserve the original manually dimensioned example for legacy regressions.
    for direction in ('horizontal','vertical'):
        c['end_face_grid'][direction].update(hook_mode='custom',return_in=18.)
    return c


class EndGridTests(unittest.TestCase):
    def test_old_cases_have_no_new_steel_or_weight(self):
        c=case();c['end_face_grid']['enabled']=False
        plain=deepcopy(c);plain.pop('end_face_grid');plain['schema_version']=3
        a=evaluate(c);b=evaluate(plain)
        self.assertFalse(geometry(a));self.assertEqual(a.weight_lb,b.weight_lb)
        self.assertEqual([(x.key,x.status,x.ratio) for x in a.checks],[(x.key,x.status,x.ratio) for x in b.checks])

    def test_mirrored_paths_and_returns(self):
        e=evaluate(case());bars=geometry(e);self.assertEqual(len(bars),14)
        length=e.value('L_cap')
        for a,b in zip(bars[:7],bars[7:]):
            self.assertEqual(a['direction'],b['direction'])
            for u,v in zip(a['points'],b['points']):
                self.assertAlmostEqual(u[0]+v[0],length)
                self.assertEqual(u[1:],v[1:])
            self.assertAlmostEqual(abs(a['points'][0][0]-a['points'][1][0]),18.)
            self.assertAlmostEqual(abs(a['points'][-1][0]-a['points'][-2][0]),18.)
            self.assertEqual(a['inside_diameter_in'],3.75)
        h=bars[0];v=bars[3]
        self.assertAlmostEqual(v['plane_in']-h['plane_in']-(h['diameter']+v['diameter'])/2,2.)

    def test_one_end_and_entered_spacing_are_exact(self):
        c=case();s=c['end_face_grid'];s['right']=False
        s['horizontal'].update(count=4,spacing_in=5.,bar=6,return_in=9.)
        e=evaluate(c);bars=geometry(e)
        self.assertTrue(all(b['end']=='left' for b in bars))
        hs=[b for b in bars if b['direction']=='horizontal']
        self.assertEqual(len(hs),4)
        self.assertEqual([b['coordinate_in']-a['coordinate_in'] for a,b in zip(hs,hs[1:])],[5.]*3)
        self.assertAlmostEqual(sum(b['coordinate_in'] for b in hs)/4,18.)
        self.assertTrue(all(b['return_in']==9 for b in hs))

    def test_face_area_counts_one_crosspiece_and_no_strength_credit(self):
        c=case();e=evaluate(c);rows,_=surface_checks(e)
        end={r['direction']:r for r in rows if r['face']=='End left'}
        self.assertAlmostEqual(end['Vertical']['provided_in2_ft'],6*.31*12/48)
        self.assertAlmostEqual(end['Horizontal']['provided_in2_ft'],5*.31*12/36)
        self.assertEqual(end['Vertical']['end_grid_count'],4)
        self.assertTrue(end['Vertical']['pending'])
        original=deepcopy(c);original['end_face_grid']['enabled']=False;b=evaluate(original)
        self.assertEqual(bar_positions(e),bar_positions(b))
        self.assertEqual(scheduled_bars(e.case),scheduled_bars(b.case))
        self.assertEqual(e.lrfd['inventory'],b.lrfd['inventory'])
        for key in ('As_N','As_P','As_B','Mr_N','Mr_P','Mr_B'):self.assertEqual(e.value(key),b.value(key))

    def test_invalid_geometry_is_drawn_but_not_credited(self):
        c=case();c['end_face_grid']['vertical']['spacing_in']=80
        e=evaluate(c);rows,_=surface_checks(e)
        self.assertFalse(all(b['fit'] for b in geometry(e)))
        self.assertEqual(next(q for q in e.checks if q.key=='Chk_end_grid_fit').status,'FAIL')
        r=next(r for r in rows if r['face']=='End left' and r['direction']=='Vertical')
        self.assertEqual(r['end_grid_count'],0)
        self.assertAlmostEqual(r['provided_in2_ft'],.155)

    def test_bend_and_bar_size_checks(self):
        c=case();c['end_face_grid']['horizontal'].update(bar=3,bend_diameter_in=.25)
        e=evaluate(c);checks={r.key:r for r in e.checks}
        self.assertEqual(checks['Chk_end_grid_bend_horizontal'].status,'FAIL')
        self.assertEqual(checks['Chk_fdot_bar_end_horizontal'].status,'FAIL')
        self.assertEqual(checks['Status_end_grid_anchorage'].status,'PENDING')
        self.assertIn('End-face U grid',checks_html(e))

    def test_validation_and_schema_guard(self):
        for mutation in (lambda c:c.update(schema_version=4),lambda c:c['end_face_grid'].update(version=7),
                         lambda c:c['end_face_grid']['horizontal'].update(count=2.5),
                         lambda c:c['end_face_grid']['vertical'].update(return_in=float('nan')),
                         lambda c:c['end_face_grid']['horizontal'].update(spacing_in=-1)):
            c=case(False);mutation(c)
            with self.assertRaises(ValueError):validate_case(c)

    def test_segment_distance_cross_parallel_and_endpoints(self):
        import numpy as np
        a=np.array([0.,0.,0.]);b=np.array([10.,0.,0.])
        c=np.array([[5.,-1.,0.],[0.,2.,0.],[12.,0.,0.],[5.,-1.,3.]])
        d=np.array([[5.,1.,0.],[10.,2.,0.],[15.,0.,0.],[5.,1.,3.]])
        self.assertTrue(np.allclose(_distances(a,b,c,d),[0.,2.,2.,3.]))

    def test_pile_conflict_screen_and_missing_data(self):
        c=case();c['inputs'].update(Ready_pile=True,Pile_embed=20)
        e=evaluate(c);self.assertTrue(pile_conflicts(e))
        self.assertEqual(next(q for q in e.checks if q.key=='Chk_end_grid_piles').status,'FAIL')
        c['inputs']['Ready_pile']=False;e=evaluate(c)
        self.assertFalse(pile_conflicts(e))
        self.assertTrue(collision_review(e))

    def test_quantities_include_exact_bends_and_returns(self):
        e=evaluate(case());q=steel_quantity_components(e)
        self.assertAlmostEqual(q['end_grid_in3'],sum(b['length_in']*.31 for b in geometry(e)))
        self.assertAlmostEqual(e.weight_lb,sum(q[k] for k in ('continuous_in3','additional_in3','transverse_in3','end_grid_in3'))*490/1728)
        c=deepcopy(e.case);c['end_face_grid']['horizontal']['return_in']+=2
        changed=evaluate(c)
        self.assertAlmostEqual(changed.weight_lb-e.weight_lb,2*3*2*2*.31*490/1728)

    def test_plot_paths_are_shared_and_sections_label_projections(self):
        e=evaluate(case());bars=geometry(e)
        for draw in (layout_3d,reinforcement_plan_figure,elevation_figure,section_figure,dimensions_figure):
            fig=draw(e);traces=[t for t in fig.data if (t.meta or {}).get('part')=='end_grid']
            self.assertGreaterEqual(len(traces),len(bars))
        fig=layout_3d(e);traces=[t for t in fig.data if (t.meta or {}).get('part')=='end_grid']
        for t,b in zip(traces,bars):self.assertEqual(list(zip(t.x,t.y,t.z)),b['points'])
        self.assertTrue(all('projected from end' in t.name for t in section_figure(e).data if (t.meta or {}).get('part')=='end_grid'))
        for end in ('left','right'):
            traces=[t for t in end_figure(e,end).data if (t.meta or {}).get('part')=='end_grid']
            self.assertEqual(len(traces),7)
            self.assertTrue(all(t.meta['end']==end for t in traces))

    def test_roundtrip_bundle_and_report(self):
        c=case()
        with tempfile.TemporaryDirectory() as folder:
            p=write_case(c,Path(folder)/'case.json');self.assertEqual(load_case(p)['end_face_grid'],c['end_face_grid'])
            bundle=export_bundle(c,folder)
            self.assertEqual(load_case(bundle/'selected_case.json')['end_face_grid'],c['end_face_grid'])
            with (bundle/'end_grid_schedule.csv').open(encoding='utf-8-sig') as f:
                schedule=list(csv.DictReader(f))
            self.assertEqual(len(schedule),14)
            self.assertEqual(len(json.loads((bundle/'end_grid_geometry.json').read_text())),14)
            for name in ('reinforcement_detail.html','calculation_report.html'):
                self.assertTrue('end-face u grid' in (bundle/name).read_text(encoding='utf-8').lower(),name)
            self.assertTrue((bundle/'end_grid_left.html').exists())

    def test_static_snapshot_uses_grid_paths(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from pier_cap.visuals import snapshot
        e=evaluate(case());fig=snapshot(e)
        try:
            section=fig.axes[0];elevation=fig.axes[1];bars=geometry(e)
            self.assertEqual(len(elevation.lines),len(bars))
            self.assertTrue(any('end U · projection' in line.get_label() for line in section.lines))
            for line,bar in zip(elevation.lines,bars):
                self.assertEqual(list(line.get_xdata()),[p[0]/12 for p in bar['points']])
                self.assertEqual(list(line.get_ydata()),[p[2]/12 for p in bar['points']])
        finally:plt.close(fig)

    @patch('IPython.display.display')
    def test_live_controls_refresh_save_and_added_schema(self,_display):
        from pier_cap.widgets import CapNotebook
        app=CapNotebook(case())
        try:
            chart=app.views.plots['cage3d']
            app.end_grid.rows['horizontal']['count'].value=5
            self.assertEqual(app.case['end_face_grid']['horizontal']['count'],5)
            self.assertIs(app.views.plots['cage3d'],chart)
            self.assertEqual(len([t for t in chart.data if (t.meta or {}).get('part')=='end_grid']),18)
            app.added_steel.mode.value='spacing'
            self.assertEqual(app.case['schema_version'],5)
            app.load(case());self.assertEqual(app.end_grid.rows['horizontal']['count'].value,3)
            app.end_grid.controls['enabled'].value=False
            self.assertFalse([t for t in chart.data if (t.meta or {}).get('part')=='end_grid'])
            for end in ('left','right'):
                self.assertFalse([t for t in app.views.plots['end_grid_'+end].data if (t.meta or {}).get('part')=='end_grid'])
        finally:app.close()


if __name__=='__main__':unittest.main()
