"""A retained live study must not call code from the previous package import."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import pier_cap.model as old_model
from pier_cap.widgets import CapNotebook
from pier_cap.section_widgets import SectionStudy, close_study
from tests.case_fixtures import default_case, import_fbmp_xml

ROOT=Path(__file__).resolve().parent.parent


class LiveUpgradeTests(unittest.TestCase):
    def test_actual_package_reimport_rebuilds_old_study_and_preserves_inputs(self):
        nb=json.loads((ROOT/'Pier_Cap_Design_Optimizer.ipynb').read_text(encoding='utf-8'))
        case=import_fbmp_xml(ROOT/'tests/fixtures/fbmp_610_cap.xml')
        app=CapNotebook(case)
        app.load(case,import_name='latest.xml')
        app.search_lists['top_counts'].value=(5,6)
        study=SectionStudy(app)
        study.bounds['depth'][0].value=36
        study.bounds['depth'][1].value=42
        study.target.value=.95
        study.rates[0].value=250
        study.rates[1].value=2
        study.use_cost.value=True
        study.library={'saved.json':deepcopy(case)}
        study.library_note.value='Saved analysis library'
        saved=deepcopy(app.case)
        unrelated=Mock()
        app.limit.observe(unrelated,names='value')
        context={'app':app,'section_app':study,'case':default_case(),'ROOT':ROOT}
        stale_validator=Mock(side_effect=ValueError('Expected case schema_version 1.'))
        try:
            # Match setup: remove modules, import new classes, retain live objects.
            # The old validator emulates the previous schema-1-only release.
            with patch.dict(sys.modules),patch.object(old_model,'validate_case',stale_validator):
                for name in list(sys.modules):
                    if name=='pier_cap' or name.startswith('pier_cap.'):
                        del sys.modules[name]
                importlib.invalidate_caches()
                current=importlib.import_module('pier_cap.section_widgets')
                self.assertIsNot(current.SectionStudy,SectionStudy)
                with patch('IPython.display.display'):
                    exec(''.join(next(c for c in nb['cells'] if c.get('id')=='7447e4cc')['source']),context)
                rebuilt=context['section_app']
                self.assertIsInstance(rebuilt,current.SectionStudy)
                self.assertIsNot(rebuilt,study)
                self.assertEqual(context['app'].case,saved)
                self.assertEqual(context['app'].search_lists['top_counts'].value,(5,6))
                self.assertIn('latest.xml',context['app'].import_notice.value)
                self.assertEqual(rebuilt.target.value,.95)
                self.assertEqual(rebuilt.rates[0].value,250)
                self.assertEqual(rebuilt.rates[1].value,2)
                self.assertTrue(rebuilt.use_cost.value)
                self.assertEqual(rebuilt.library,{'saved.json':case})
                self.assertEqual(rebuilt.library_note.value,'Saved analysis library')
                self.assertIn(unrelated,app.limit._trait_notifiers['value']['change'])
                self.assertFalse(any(getattr(h,'__self__',None) is study
                                     for h in app.limit._trait_notifiers['value']['change']))
                self.assertIsNone(rebuilt.study)
                self.assertIn('NEEDS A NEW RUN',rebuilt.notice.value)
                # A full Run all continues through the study cell and its buttons.
                with patch('IPython.display.display'):
                    exec(''.join(next(c for c in nb['cells'] if c.get('id')=='509fc7f9')['source']),context)
                active=context['section_app']
                self.assertEqual([w.value for w in active.bounds['depth']],[36,42,6])
                self.assertEqual(active.library,rebuilt.library)
                self.assertEqual(active.target.value,.95)
                choices={'main_bars':(8,),'top_counts':(8,),'pile_bars':(8,),
                         'pile_counts':(8,),'span_bars':(8,),'span_counts':(8,),
                         'hoop_bars':(5,),'hoop_spacings':(8,),
                         'skin_bars':(5,),'skin_counts':(6,)}
                for name,values in choices.items():
                    context['app'].search_lists[name].value=values
                active.bounds['width'][0].value=48
                active.bounds['width'][1].value=48
                active.run_button.click()
                self.assertIsNotNone(active.study,active.notice.value)
                self.assertIn('Study completed',active.notice.value)
                self.assertEqual(active.study.evaluated,2)
                stale_validator.assert_not_called()
                # Closing stale controls is also safe after a failed earlier rebind.
                current.close_study(study)
                active.close();context['app'].close()
        finally:
            close_study(study);app.close()
            if context.get('section_app') is not study:context['section_app'].close()
            if context.get('app') is not app:context['app'].close()

    def test_cleanup_does_not_evaluate_an_old_or_partially_rebound_case(self):
        app=CapNotebook(default_case());study=SectionStudy(app)
        try:
            with patch.object(study,'invalidate',side_effect=ValueError('Expected case schema_version 1.')) as invalid:
                close_study(study)
                close_study(study)
                invalid.assert_not_called()
            self.assertNotIn(study.invalidate,app.case_listeners)
        finally:app.close()
