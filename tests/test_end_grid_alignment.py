from copy import deepcopy
import math
import unittest
from unittest.mock import patch
import numpy as np
from pier_cap import evaluate
from pier_cap.model import geometry_evaluation,bar_positions,BAR_DIAMETER
from pier_cap.end_grid import geometry,collision_review,settings,validate,minimum_bend
from pier_cap.end_grid_alignment import bounds
from pier_cap.detailing import required_clear
from tests.test_end_grid import case


class EndGridAlignmentTests(unittest.TestCase):
    def test_standard_hooks_update_with_size_and_ignore_custom_lengths(self):
        for size in (3,5,8,9,11):
            c=case();c['end_face_grid']['horizontal'].update(hook_mode='standard',bar=size,return_in=99,bend_diameter_in=99)
            b=geometry(geometry_evaluation(c))[0]
            self.assertEqual(b['return_in'],12*BAR_DIAMETER[size])
            self.assertEqual(b['inside_diameter_in'],minimum_bend(size))
            self.assertAlmostEqual(math.dist(b['points'][0],b['points'][1]),b['return_in'])

    def test_legacy_grid_preserves_geometry_and_new_standards_are_guarded(self):
        c=case();s=c['end_face_grid'];s['version']=1;s.pop('placement_mode')
        for direction in ('horizontal','vertical'):s[direction].pop('hook_mode')
        validate(c);old=geometry(geometry_evaluation(c))
        upgraded=deepcopy(c);upgraded['end_face_grid']=settings(c);upgraded['end_face_grid']['version']=2
        self.assertEqual(old,geometry(geometry_evaluation(upgraded)))
        c['end_face_grid']['horizontal']['hook_mode']='standard'
        with self.assertRaises(ValueError):validate(c)

    def test_aligned_surfaces_stagger_clearance_mirroring_and_no_main_bar_changes(self):
        c=case();c['inputs'].update(n_N1=4,n_P1=4,Bar_N1=6,Bar_P=9)
        before=bar_positions(geometry_evaluation(c),'P')
        s=c['end_face_grid'];s['placement_mode']='aligned'
        for direction in ('horizontal','vertical'):s[direction]['hook_mode']='standard'
        e=geometry_evaluation(c);bars=geometry(e);length=e.value('L_cap')
        self.assertEqual(before,bar_positions(e,'P'))
        self.assertTrue(all(b['placement_ok'] for b in bars))
        self.assertTrue(any(abs(b['shift_in'])>.01 for b in bars))
        for left,right in zip(bars[:7],bars[7:]):
            for u,v in zip(left['points'],right['points']):self.assertAlmostEqual(u[0]+v[0],length)
        for bar in bars:
            x0,x1,y0,y1=bounds(e,bar['diameter'])
            ends=(bar['points'][0],bar['points'][-1])
            self.assertEqual(tuple(v[1 if bar['direction']=='horizontal' else 2] for v in ends),
                             (x0,x1) if bar['direction']=='horizontal' else (y0,y1))
            for _,x,y in ends:
                for main in before:
                    clear=math.hypot(x-main['x'],y-main['y'])-(bar['diameter']+main['diameter'])/2
                    self.assertGreaterEqual(clear+1e-7,0.)
        self.assertTrue(any(abs(r['clear_in'])<1e-7 and r['longitudinal_contact'] for r in collision_review(e)))

    def test_impossible_stagger_retains_requested_bars_and_withholds_fit(self):
        c=case();c['end_face_grid']['placement_mode']='aligned';c['end_face_grid']['horizontal']['count']=40
        bars=geometry(geometry_evaluation(c));horizontal=[b for b in bars if b['direction']=='horizontal']
        self.assertEqual(len(horizontal),80)
        self.assertTrue(all(not b['fit'] for b in horizontal))
        self.assertTrue(all('cannot fit' in b['placement_note'] for b in horizontal))

    def test_dense_main_row_is_not_moved_to_make_grid_fit(self):
        c=case();before=bar_positions(geometry_evaluation(c),'P')
        c['end_face_grid']['placement_mode']='aligned';e=geometry_evaluation(c)
        self.assertEqual(before,bar_positions(e,'P'))
        vertical=[b for b in geometry(e) if b['direction']=='vertical']
        self.assertTrue(all(b['placement_ok'] for b in vertical))

    def test_equal_spacing_keeps_clear_nominal_bars_and_bumps_only_conflicts(self):
        c=case();c['inputs'].update(n_N1=4,n_P1=4,Bar_N1=6,Bar_P=9)
        s=c['end_face_grid'];s['placement_mode']='aligned'
        # This retained manual value must not defeat automatic equal spacing.
        for direction in ('horizontal','vertical'):s[direction].update(hook_mode='standard',spacing_in=1.)
        e=geometry_evaluation(c);bars=geometry(e);main=bar_positions(e,'P')
        fixed=moved=0
        for bar in bars:
            x0,x1,y0,y1=bounds(e,bar['diameter'])
            horizontal=bar['direction']=='horizontal'
            a,b=(y0,y1) if horizontal else (x0,x1)
            lo,hi=(x0,x1) if horizontal else (y0,y1)
            count=s[bar['direction']]['count'];i=int(bar['id'].split('-')[-1][1:])
            self.assertAlmostEqual(bar['nominal_coordinate_in'],a+i*(b-a)/(count+1))
            def main_clear(at):
                return min(math.hypot(max(lo-q['x' if horizontal else 'y'],q['x' if horizontal else 'y']-hi,0.),
                    at-q['y' if horizontal else 'x'])-(bar['diameter']+q['diameter'])/2 for q in main)
            if abs(bar['shift_in'])<1e-8:
                fixed+=1;self.assertGreaterEqual(main_clear(bar['coordinate_in']),-1e-8)
            else:
                moved+=1
                self.assertLess(main_clear(bar['nominal_coordinate_in']),0.)
                self.assertAlmostEqual(main_clear(bar['coordinate_in']),0.,places=7)
        self.assertGreater(fixed,0);self.assertGreater(moved,0)

    def test_longitudinal_lap_contact_passes_and_small_physical_overlap_fails(self):
        c=case();e=geometry_evaluation(c)
        e._end_grid_geometry=[dict(id='End-left-H1',diameter=.625,points=[(4.,10.,10.),(12.,10.,10.)])]
        for gap in (0.,.001,-.001,-.1):
            if hasattr(e,'_end_grid_collisions'):del e._end_grid_collisions
            main=[dict(kind='Bottom row 1',x=10.+(.625+1.)/2+gap,y=10.,diameter=1.)]
            with patch('pier_cap.model.bar_positions',return_value=main), \
                 patch('pier_cap.transverse.scheduled_bars',return_value=[]), \
                 patch('pier_cap.detailing.hook_paths',return_value=[]):
                row=collision_review(e)[0]
            self.assertAlmostEqual(row['clear_in'],gap)
            self.assertEqual(row['required_in'],0.)
            self.assertEqual(row['screen_margin_in']>=0,gap>=0)

    def test_parallel_end_grid_returns_still_require_clearance(self):
        e=geometry_evaluation(case())
        e._end_grid_geometry=[dict(id='End-left-'+str(i),diameter=.625,
            points=[(4.,10.+i,10.),(12.,10.+i,10.)]) for i in range(2)]
        with patch('pier_cap.model.bar_positions',return_value=[]), \
             patch('pier_cap.transverse.scheduled_bars',return_value=[]), \
             patch('pier_cap.detailing.hook_paths',return_value=[]):
            row=collision_review(e)[0]
        self.assertGreater(row['required_in'],0.)
        self.assertLess(row['screen_margin_in'],0.)

    def test_broad_phase_matches_unpruned_collision_screen(self):
        c=case();c['end_face_grid']['placement_mode']='aligned'
        e=geometry_evaluation(c);fast=collision_review(e);del e._end_grid_collisions
        with patch('numpy.flatnonzero',side_effect=lambda mask:np.arange(mask.size)):
            full=collision_review(e)
        for a,b in zip(fast,full):
            self.assertEqual(a['bar'],b['bar']);self.assertAlmostEqual(a['margin_in'],b['margin_in'],places=9)

    def test_preview_and_final_geometry_match(self):
        c=case();c['end_face_grid']['placement_mode']='aligned'
        preview=geometry_evaluation(c);final=evaluate(c)
        self.assertTrue(preview.calculating);self.assertFalse(preview.eligible);self.assertFalse(preview.checks)
        self.assertEqual(geometry(preview),geometry(final));self.assertEqual(bar_positions(preview),bar_positions(final))
        self.assertFalse(final.calculating)

    def test_grid_edit_reuses_sectional_work_but_refreshes_face_checks(self):
        from pier_cap import lrfd_checks
        lrfd_checks._CALCULATION_CACHE.clear()
        c=case()
        with patch.object(lrfd_checks,'actual_calculations',wraps=lrfd_checks.actual_calculations) as calculate:
            original=evaluate(c)
            c['end_face_grid']['horizontal']['count']=4;changed=evaluate(c)
            self.assertEqual(calculate.call_count,1)
            before=next(r for r in original.lrfd['faces'] if r['face']=='End left' and r['direction']=='Horizontal')
            after=next(r for r in changed.lrfd['faces'] if r['face']=='End left' and r['direction']=='Horizontal')
            self.assertEqual(after['end_grid_count'],4);self.assertGreater(after['provided_in2_ft'],before['provided_in2_ft'])
            self.assertEqual(original.lrfd['intervals'],changed.lrfd['intervals'])
            c['inputs']['n_N1']+=1;evaluate(c)
            self.assertEqual(calculate.call_count,2)
