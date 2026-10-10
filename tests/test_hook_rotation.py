"""Trial hook yaw is real 3D geometry and never certifies anchorage."""
from copy import deepcopy
import json
import math
import tempfile
import unittest

from pier_cap.cage_3d import layout_3d
from pier_cap.io import export_bundle,load_case
from pier_cap.model import evaluate
from pier_cap.transverse import (HOOK_ROTATIONS,bar_shape,development_current,
    development_fingerprint,shape_issues,validate_detail)
from pier_cap.transverse_visuals import add_projection,schedule_html
from pier_cap.widgets import CapNotebook
from tests.test_transverse_detail import explicit_case


def rotated_case(left=60,right=60):
    case=explicit_case();case['transverse_detail']['version']=4
    run=next(r for r in case['transverse_detail']['runs'] if r['kind']=='pile_u')
    run['shape']=dict(zip(HOOK_ROTATIONS,(left,right)))
    return case,run


class HookRotationTests(unittest.TestCase):
    def test_independent_hooks_rotate_about_vertical_legs_without_changing_length(self):
        case,run=rotated_case(60,-30);e=evaluate(case)
        original=deepcopy(run);original['shape']={}
        before=bar_shape(e,original);after=bar_shape(e,run)
        self.assertAlmostEqual(after['length_in'],before['length_in'])
        n=after['hook_point_count']
        self.assertEqual(after['points_3d'][n:-n],before['points_3d'][n:-n])
        left=case['inputs']['C_s']+before['diameter']/2
        for index,theta,axis,sign in [(0,60,left,1),(-1,-30,case['inputs']['b']-left,-1)]:
            reach=sign*(before['points'][index][0]-axis)
            x,y,z=after['points_3d'][index]
            self.assertAlmostEqual(x,reach*math.sin(math.radians(theta)))
            self.assertAlmostEqual(y,axis+sign*reach*math.cos(math.radians(theta)))
            self.assertEqual(z,before['points'][index][1])
        self.assertEqual(after['points'],[(y,z) for _,y,z in after['points_3d']])

    def test_rotation_clears_pile_but_anchorage_stays_pending_even_if_recorded(self):
        case,run=rotated_case();e=evaluate(case)
        self.assertFalse(any('embedded pile' in s for s in shape_issues(e,run)))
        anchorage=next(c for c in e.checks if c.key=='Status_transverse_development_'+run['id'])
        self.assertEqual(anchorage.status,'PENDING')
        self.assertIn('Trial hook rotation',anchorage.basis)
        shear=[c for c in e.checks if c.key.startswith('Chk_actual_shear_') and run['id']+'-' in c.key]
        self.assertTrue(shear)
        self.assertTrue(all('Rotated-hook anchorage is PENDING' in c.basis for c in shear))
        run.update(development_confirmed=True,development_basis='Trial detail')
        run['development_fingerprint']=development_fingerprint(case,run)
        self.assertFalse(development_current(case,run))
        self.assertNotIn('Development recorded',schedule_html(e))
        run['shape']={}
        self.assertTrue(any('embedded pile' in s for s in shape_issues(evaluate(case),run)))

    def test_rotated_tail_can_reach_pile_outside_its_leg_station_and_cap_end(self):
        case,run=rotated_case(30,30);e=evaluate(case)
        center=e.value('E_CL')+case['inputs']['S_pile']*12
        inset=case['inputs']['D_pile']/2+e.value('Tol_pile')+case['inputs']['C_pile']+bar_shape(e,run)['diameter']/2
        run.update(first_in=center-inset-1,end_in=center-inset-1)
        case['transverse_detail']['runs']=[run]
        self.assertTrue(any('embedded pile' in s for s in shape_issues(evaluate(case),run)))
        run['shape']=dict.fromkeys(HOOK_ROTATIONS,-30.)
        self.assertFalse(any('embedded pile' in s for s in shape_issues(evaluate(case),run)))
        case,run=rotated_case(-90,-90)
        self.assertTrue(any('cap end cover' in s for s in shape_issues(evaluate(case),run)))

    def test_projected_hook_crossing_is_distinct_from_a_real_3d_crossing(self):
        case,run=rotated_case(30,30)
        run['shape']['tail_in']=30
        self.assertTrue(any('intersect in 3D' in s for s in shape_issues(evaluate(case),run)))
        run['shape'][HOOK_ROTATIONS[1]]=-30
        self.assertFalse(any('intersect in 3D' in s for s in shape_issues(evaluate(case),run)))

    def test_views_and_export_share_station_offsets_and_rotation_values(self):
        import plotly.graph_objects as go
        case,run=rotated_case();e=evaluate(case);shape=bar_shape(e,run)
        trace=next(t for t in layout_3d(e).data if t.legendgroup==run['id'])
        expected=[(run['first_in']+x,y,z) for x,y,z in shape['points_3d']]
        self.assertEqual(list(zip(trace.x,trace.y,trace.z)),expected)
        for view,dimension in [('plan',1),('elevation',2)]:
            fig=go.Figure();add_projection(fig,e,view)
            trace=next(t for t in fig.data if t.legendgroup==run['id'])
            self.assertEqual(list(trace.x),[p[0]/12 for p in expected])
            self.assertEqual(list(trace.y),[p[dimension] for p in expected])
        with tempfile.TemporaryDirectory() as root:
            folder=export_bundle(case,root)
            self.assertEqual(load_case(folder/'selected_case.json')['transverse_detail'],case['transverse_detail'])
            shapes=json.loads((folder/'transverse_shapes.json').read_text(encoding='utf-8'))
            saved=next(s for s in shapes if s['run']['id']==run['id'])
            self.assertEqual(saved['geometry']['points_3d'],[list(p) for p in shape['points_3d']])

    def test_validation_and_widgets_keep_rotation_explicit_and_backwards_safe(self):
        case,run=rotated_case()
        for invalid in (True,float('nan'),float('inf'),-91,91,'30'):
            run['shape'][HOOK_ROTATIONS[0]]=invalid
            with self.assertRaisesRegex(ValueError,'hook rotation'):validate_detail(case)
        run['shape'][HOOK_ROTATIONS[0]]=60
        case['transverse_detail']['version']=3
        with self.assertRaisesRegex(ValueError,'version 4'):validate_detail(case)
        case=explicit_case();app=CapNotebook(case)
        try:
            run=next(r for r in app.case['transverse_detail']['runs'] if r['kind']=='pile_u')
            controls=app.transverse_panel.zone_controls[run['id']]
            controls[HOOK_ROTATIONS[0]].value=60
            self.assertEqual(app.case['transverse_detail']['version'],4)
            self.assertTrue(controls['development_confirmed'].disabled)
            saved=deepcopy(app.case);app.load(explicit_case());app.load(saved)
            controls=app.transverse_panel.zone_controls[run['id']]
            self.assertEqual(controls[HOOK_ROTATIONS[0]].value,60)
            controls['end_angle'].value=0
            self.assertTrue(controls[HOOK_ROTATIONS[0]].disabled)
            controls['end_angle'].value=90
            self.assertFalse(controls[HOOK_ROTATIONS[0]].disabled)
            self.assertEqual(controls[HOOK_ROTATIONS[0]].value,60)
        finally:app.close()


if __name__=='__main__':unittest.main()
