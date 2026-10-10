"""Actual transverse envelopes must govern both coordinates and calculations."""
from copy import deepcopy
import csv
import json
import math
import tempfile
import unittest

from pier_cap.model import evaluate,bar_positions,set_inputs,BAR_AREA,formula_trace
from pier_cap.transverse import suggested_detail,bar_shape,_point_segment,development_fingerprint,development_current
from pier_cap.io import export_bundle
from pier_cap.visuals import configuration_html,section_figure
from pier_cap.cage_3d import layout_3d
from tests.case_fixtures import default_case


def actual_case(**inputs):
    case=set_inputs(default_case(),b=60,h=48,n_N1=6,n_N2=6,n_N3=0,Bar_N1=8,Bar_N2=8,
                    n_P1=4,n_P2=4,Bar_P=9,n_B1=2,n_B2=2,Bar_B=7,n_skin=4,
                    Pile_embed=12,C_pile=2,Ready_pile=True)
    case=set_inputs(case,**inputs)
    case['analysis']['geometry'].update({k:case['inputs'][k] for k in case['analysis']['geometry']})
    case['transverse_detail']=suggested_detail(evaluate(case))
    for run in case['transverse_detail']['runs']:
        run.update(bar=8 if run['kind']=='hoop' else 6,
                   shape=dict(inside_diameter_in=7,side_inset_in=1,end_angle=90,tail_in=4,end_raise_in=1))
    return case


class ActualPlacementTests(unittest.TestCase):
    def assert_geometry(self,e):
        self.assertTrue(e.longitudinal_layout['fitted'],e.longitudinal_layout['issues'])
        for run in e.case['transverse_detail']['runs']:
            shape=bar_shape(e,run)
            for b in bar_positions(e,'B'):
                gap=min(_point_segment((b['x'],b['y']),a,c) for a,c in zip(shape['points'],shape['points'][1:]))-(shape['diameter']+b['diameter'])/2
                self.assertGreaterEqual(gap,-1e-6,(run['id'],b,gap))
        self.assertEqual(bar_positions(e,'P'),[b for b in bar_positions(e,'B') if not b['additional']])

    def test_mixed_shapes_insets_bends_layers_and_skin_clear_real_surfaces(self):
        e=evaluate(actual_case());self.assert_geometry(e)
        self.assertFalse(any('Physical overlap' in s for s in e.issues))
        self.assertEqual(len(bar_positions(e,'B')),32)
        for family in ('Top','Bottom'):
            rows=[[b['x'] for b in bar_positions(e,'P') if b['layer']==f'{family} row {k}'] for k in (1,2)]
            self.assertEqual(rows[0],rows[1])

    def test_open_u_end_angles_and_raise_do_not_invent_bottom_closure(self):
        for angle in (0,90,135,180):
            with self.subTest(angle=angle):
                c=actual_case(n_skin=0,n_N2=0,n_P2=0,n_B2=0)
                for run in c['transverse_detail']['runs']:
                    if run['kind']=='pile_u':run['shape'].update(end_angle=angle,end_raise_in=2,tail_in=3)
                self.assert_geometry(evaluate(c))

    def test_actual_shape_controls_layout_independently_of_reference_bar(self):
        c=actual_case();e=evaluate(c)
        for size in (3,11):
            other=evaluate(set_inputs(c,Bar_v=size))
            self.assertEqual(bar_positions(e),bar_positions(other))
            for name in ('dc_N','dc_P','dc_B','SP_N','SP_P','SP_B','dv'):
                self.assertEqual(e.value(name),other.value(name))

    def test_centroids_depths_service_and_flexure_follow_drawn_coordinates(self):
        e=evaluate(actual_case())
        for z in 'NPB':
            bars=[b for b in bar_positions(e,'B' if z=='B' else 'P')
                  if b['kind'].startswith('Top' if z=='N' else ('Bottom','Added'))]
            area=sum(BAR_AREA[b['bar']] for b in bars)
            cover=sum(BAR_AREA[b['bar']]*(48-b['y'] if z=='N' else b['y']) for b in bars)/area
            d=48-cover
            self.assertAlmostEqual(e.value('As_'+z),area)
            self.assertAlmostEqual(e.value('dc_'+z),cover)
            self.assertAlmostEqual(e.value('d_'+z),d)
            self.assertAlmostEqual(e.value('Mn_'+z),area*e.case['inputs']['fy']*(d-e.value('a_'+z)/2))
            n=e.value('n_mod');cc=e.value('ccr_'+z)
            icr=e.case['inputs']['b']*cc**3/3+n*area*(d-cc)**2
            self.assertAlmostEqual(e.value('Icr_'+z),icr)
            self.assertAlmostEqual(e.value('Ss_'+z),icr/(d-cc))
        expected=max(.9*min(e.value('d_'+z) for z in 'NPB'),.72*48,
                     min(e.value('d_'+z)-e.value('a_'+z)/2 for z in 'NPB'))
        self.assertAlmostEqual(e.value('dv'),expected)
        trace={r['name']:r for r in formula_trace(e)}
        self.assertIn('actual longitudinal layout',trace['y_P1']['formula'])
        self.assertIn('fitted coordinates',configuration_html(e))

    def test_larger_actual_hoops_reduce_depth_and_update_downstream_results(self):
        c=actual_case(n_N2=0,n_P2=0,n_B2=0,n_skin=0)
        for r in c['transverse_detail']['runs']:r.update(bar=3,shape={'end_angle':0})
        small=evaluate(c)
        for r in c['transverse_detail']['runs']:r.update(bar=9,shape={'end_angle':0})
        large=evaluate(c);self.assert_geometry(large)
        for z in 'NPB':
            self.assertLess(large.value('d_'+z),small.value('d_'+z))
            self.assertLess(large.value('Mn_'+z),small.value('Mn_'+z))
            self.assertGreater(large.value('fs_I_'+z),small.value('fs_I_'+z))
            self.assertEqual(large.value('As_'+z),small.value('As_'+z))
        self.assertLess(large.value('dv'),small.value('dv'))

    def test_manual_pitch_preserved_and_calculated_pitch_measures_real_gap(self):
        c=actual_case(n_N2=0,n_P2=0,n_B1=0,n_B2=0,n_skin=0,Manual_spacing=True,
                      SP_detail_N=4.5,SP_detail_P=3.5)
        e=evaluate(c);self.assert_geometry(e)
        top=sorted(b['x'] for b in bar_positions(e) if b['kind']=='Top row 1')
        self.assertTrue(all(abs(b-a-4.5)<1e-8 for a,b in zip(top,top[1:])))
        bottom=sorted(b['x'] for b in bar_positions(e) if b['kind']=='Bottom row 1')
        self.assertAlmostEqual(bottom[1]-bottom[0],3.5)
        self.assertAlmostEqual(bottom[-1]-bottom[-2],3.5)
        self.assertAlmostEqual(e.value('SP_P'),3.5)
        self.assertGreater(max(b-a for a,b in zip(bottom,bottom[1:])),e.value('SP_P'))

    def test_impossible_shapes_fail_without_losing_bars_or_mutating_inputs(self):
        c=actual_case();before=deepcopy(c)
        c['transverse_detail']['runs'][0]['shape']['side_inset_in']=28
        e=evaluate(c)
        self.assertFalse(e.longitudinal_layout['fitted']);self.assertFalse(e.eligible)
        self.assertEqual(next(x.status for x in e.checks if x.key=='Chk_actual_longitudinal_fit'),'FAIL')
        self.assertTrue(any('cannot fit' in s for s in e.issues))
        self.assertEqual(len(bar_positions(e)),len(bar_positions(evaluate(before))))
        self.assertEqual(c['inputs'],before['inputs'])
        self.assertIn('FIT FAILED',configuration_html(e))

    def test_fast_and_unit_checked_engines_and_projections_use_identical_layout(self):
        c=actual_case();e=evaluate(c);fast=evaluate(c,fast=True)
        self.assertEqual(bar_positions(e),bar_positions(fast))
        for name in ('dc_N','dc_P','dc_B','dv','Mn_N','Mn_P','Mn_B','fs_I_N','fs_I_P','fs_I_B'):
            self.assertAlmostEqual(e.value(name),fast.value(name))
        fig=layout_3d(e)
        traces=[t for t in fig.data if t.meta.get('part') in ('top','bottom','side')]
        for trace,b in zip(traces,bar_positions(e,'P')):
            self.assertEqual(list(trace.y),[b['x']]*2);self.assertEqual(list(trace.z),[b['y']]*2)
        section=section_figure(e,'P')
        outlines=[t for t in section.data if t.name=='Bar outline']
        for trace,b in zip(outlines,bar_positions(e,'P')):
            self.assertAlmostEqual((max(trace.x)+min(trace.x))/2,b['x'])
            self.assertAlmostEqual((max(trace.y)+min(trace.y))/2,b['y'])
        from pier_cap.visuals import snapshot
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        static=snapshot(e)
        try:
            run=next(r for r in c['transverse_detail']['runs'] if r['kind']=='hoop')
            self.assertEqual(list(static.axes[0].lines[0].get_xdata()),[v[0] for v in bar_shape(e,run)['points']])
        finally:plt.close(static)

    def test_other_run_geometry_invalidates_development_record(self):
        c=actual_case();r=c['transverse_detail']['runs'][0]
        r.update(development_confirmed=True,development_basis='Checked detail')
        r['development_fingerprint']=development_fingerprint(c,r)
        self.assertTrue(development_current(c,r))
        c['transverse_detail']['runs'][1]['shape']['side_inset_in']+=1
        self.assertFalse(development_current(c,r))

    def test_live_shape_edit_moves_bars_and_can_record_current_confirmation(self):
        from pier_cap.widgets import CapNotebook
        app=CapNotebook(actual_case())
        try:
            panel=app.transverse_panel
            run=app.case['transverse_detail']['runs'][0]
            card=panel.zone_controls[run['id']]
            before=bar_positions(app.current)
            card['bar'].value=10
            card['development_basis'].value='Reviewed test detail';card['development_confirmed'].value=True
            current=next(r for r in app.case['transverse_detail']['runs'] if r['id']==run['id'])
            self.assertTrue(development_current(app.case,current))
            self.assertNotEqual(before,bar_positions(app.current))
            self.assertIn(f'{app.current.value("d_P"):.3f}',app.cage.children[0].value)
            traces=[t for t in app.cage_3d_widget.data if t.meta.get('part') in ('top','bottom','side')]
            self.assertEqual([t.z[0] for t in traces],[b['y'] for b in bar_positions(app.current,'P')])
        finally:app.close()

    def test_export_records_positions_and_calculation_geometry(self):
        c=actual_case();e=evaluate(c)
        with tempfile.TemporaryDirectory() as root:
            folder=export_bundle(c,root)
            geometry=json.loads((folder/'longitudinal_geometry.json').read_text())
            self.assertAlmostEqual(geometry['d_P'],e.value('d_P'));self.assertTrue(geometry['fitted'])
            with (folder/'longitudinal_bar_positions.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
            pbars=bar_positions(e,'P')
            self.assertEqual([float(r['Across cap (in)']) for r in rows[:len(pbars)]],[b['x'] for b in pbars])


if __name__=='__main__':unittest.main()
