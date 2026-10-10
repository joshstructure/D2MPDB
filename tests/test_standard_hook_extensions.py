"""CRSI dimensions, live changes, legacy inputs and exported closure checks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from pier_cap.hooks import stirrup_hook_extension
from pier_cap.io import load_case,write_case
from pier_cap.lrfd_checks import settings,closure_extension,validate_settings
from pier_cap.lrfd_views import working_html
from pier_cap.model import evaluate,upgrade_case
from pier_cap.transverse import shape_parameters,bar_shape
from pier_cap.widgets import CapNotebook
from tests.test_transverse_detail import explicit_case


class StandardHookExtensionsTests(unittest.TestCase):
    def test_crsi_straight_extensions_including_three_inch_minimum(self):
        expected={90:[3,3,3.75,9,10.5,12],135:[3,3,3.75,4.5,5.25,6],180:[2.5,2.5,2.5,3,3.5,4]}
        for angle,values in expected.items():
            for bar,value in zip(range(3,9),values):
                self.assertEqual(stirrup_hook_extension(bar,angle),value,(bar,angle))
        self.assertIsNone(stirrup_hook_extension(9,90))

    def test_legacy_zero_becomes_standard_but_explicit_custom_zero_and_lengths_survive(self):
        c=explicit_case()
        c['lrfd_checks']={'version':1,'hoop_closure':'hooks','closure_tail_in':0.}
        upgraded=upgrade_case(c)
        self.assertEqual(upgraded['lrfd_checks']['version'],2)
        self.assertEqual(closure_extension(settings(upgraded),5),3.75)
        c['lrfd_checks']['closure_tail_in']=7.5
        self.assertEqual(settings(c)['closure_extension_mode'],'custom')
        self.assertEqual(closure_extension(settings(c),5),7.5)
        c['lrfd_checks'].update(version=2,closure_extension_mode='custom',closure_tail_in=0.)
        self.assertEqual(closure_extension(settings(c),5),0.)
        for invalid in ('automatic',None):
            c['lrfd_checks']['closure_extension_mode']=invalid
            with self.assertRaises(ValueError):validate_settings(c)

    def test_mixed_closed_bar_sizes_and_hook_angle_recalculate_per_run(self):
        c=explicit_case();runs=c['transverse_detail']['runs']
        hoops=[r for r in runs if r['kind']=='hoop']
        for run,bar in zip(hoops,(3,5,6,8)):run['bar']=bar
        c['lrfd_checks'].update(hoop_closure='hooks',closure_engages_bars=True,closure_extension_mode='standard',closure_tail_in=0.)
        for angle in (90,135):
            c['lrfd_checks']['closure_angle']=angle;e=evaluate(c)
            rows={r['run']:r for r in e.lrfd['transverse_development']}
            for run in hoops:
                self.assertEqual(rows[run['id']]['tail_in'],stirrup_hook_extension(run['bar'],angle))
                self.assertLessEqual(rows[run['id']]['tail_ratio'],1.)
        self.assertIn('Closed-stirrup hook extension',working_html(e))
        self.assertIn('CRSI standard',working_html(e))
        with tempfile.TemporaryDirectory() as root:
            saved=load_case(write_case(c,Path(root)/'case.json'))
            self.assertEqual(evaluate(saved).lrfd['transverse_development'],e.lrfd['transverse_development'])

    def test_standard_u_geometry_updates_but_saved_custom_geometry_is_retained(self):
        c=explicit_case();run=next(r for r in c['transverse_detail']['runs'] if r['kind']=='pile_u')
        run['bar']=5;run['shape']={'end_angle':90}
        self.assertEqual(shape_parameters(run)['tail_in'],3.75)
        run['shape']['tail_in']=7.5
        self.assertEqual(shape_parameters(run)['extension_mode'],'custom')
        original=bar_shape(evaluate(c),run)
        run['shape']['extension_mode']='standard'
        new=bar_shape(evaluate(c),run)
        self.assertAlmostEqual(original['length_in']-new['length_in'],7.5)
        run['bar']=6
        self.assertEqual(shape_parameters(run)['tail_in'],9.)
        run['shape']['end_angle']=135
        self.assertEqual(shape_parameters(run)['tail_in'],4.5)

    def test_live_controls_update_defaults_and_preserve_review_requirements(self):
        c=explicit_case();c['lrfd_checks'].update(hoop_closure='hooks',closure_extension_mode='standard')
        app=CapNotebook(c)
        try:
            controls=app.lrfd_panel.controls
            self.assertEqual(controls['closure_extension_mode'].description,'Closed-stirrup hook extension')
            self.assertTrue(controls['closure_tail_in'].disabled)
            self.assertIn('CRSI standard',app.lrfd_panel.extension_summary.value)
            controls['closure_extension_mode'].value='custom'
            self.assertGreater(controls['closure_tail_in'].value,0)
            controls['closure_tail_in'].value=1.
            controls['closure_extension_mode'].value='standard'
            self.assertTrue(controls['closure_tail_in'].disabled)
            self.assertFalse(app.case['lrfd_checks']['closure_engages_bars'])
            run=next(r for r in app.case['transverse_detail']['runs'] if r['kind']=='pile_u')
            rc=app.transverse_panel.zone_controls[run['id']]
            rc['extension_mode'].value='standard';rc['bar'].value=5
            self.assertEqual(rc['tail_in'].value,3.75)
            self.assertTrue(rc['tail_in'].disabled)
            rc['bar'].value=6;self.assertEqual(rc['tail_in'].value,9.)
            rc['end_angle'].value=135;self.assertEqual(rc['tail_in'].value,4.5)
            rc['extension_mode'].value='custom';rc['tail_in'].value=7.5
            saved=deepcopy(app.case);app.load(saved)
            self.assertEqual(app.transverse_panel.zone_controls[run['id']]['tail_in'].value,7.5)
        finally:app.close()


if __name__=='__main__':unittest.main()
