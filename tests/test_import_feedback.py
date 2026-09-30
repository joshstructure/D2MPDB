"""Imports must be visible and survive notebook-cell reruns in one runtime."""
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
from pier_cap.source_status import upload_entries,source_signature
from pier_cap.widgets import CapNotebook
from pier_cap.section_widgets import SectionStudy, rebind_study, close_study
from pier_cap.sections import run_section_study,SectionGrid
from pier_cap.optimizer import SearchConfig

from tests.case_fixtures import default_case, import_fbmp_xml

ROOT=Path(__file__).resolve().parent.parent
FIXTURE=ROOT/'tests/fixtures/fbmp_610_cap.xml'


def upload(name,content):
    return {'name':name,'content':memoryview(content),'type':'application/octet-stream',
            'size':len(content),'last_modified':datetime.now(timezone.utc)}


def receive_upload(widget,name,content):
    """Deliver the actual synchronized fields for either widget protocol."""
    if 'metadata' in widget.traits():
        widget.set_state({'metadata':[{'name':name,'type':'application/octet-stream',
                                      'size':len(content),'lastModified':0}],
                          'data':[memoryview(content)],'_counter':widget._counter+1})
    else:
        widget.set_state({'value':[upload(name,content) | {'last_modified':0}]})


class ImportFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.app=CapNotebook(default_case())
        self.study=SectionStudy(self.app)

    def tearDown(self):
        self.study.close()
        self.app.close()

    def test_xml_upload_preview_apply_receipt_and_study_invalidation(self):
        one=SearchConfig(main_bars=(8,),top_counts=(8,),bottom_counts=(8,),hoop_bars=(5,),
                         hoop_spacings=(8,),skin_bars=(5,),skin_counts=(6,))
        self.study.study=run_section_study(self.app.case,SectionGrid(widths=(48,),depths=(48,)),one)
        self.study._render()
        self.assertTrue(self.study.cage.options)
        before=deepcopy(self.app.case)
        panel=self.app.xml_import
        receive_upload(panel.upload,'Pier_MinTip.XML',FIXTURE.read_bytes())
        self.assertIn('PREVIEW READY',panel.status.value)
        self.assertIn('NOT APPLIED',panel.status.value)
        self.assertEqual(self.app.case,before)
        self.assertNotIn('SUCCESSFULLY',self.app.import_notice.value)
        panel.apply_button.click()
        self.assertIn('XML APPLIED',panel.status.value)
        self.assertIn('LOADS IMPORTED SUCCESSFULLY',self.app.import_notice.value)
        self.assertIn('Pier_MinTip.XML',self.app.import_notice.value)
        self.assertIn('UTC',self.app.import_notice.value)
        for expected in ('48 × 36','183.15','287.44','209.52','34.16','Pier_MinTip.XML'):
            self.assertIn(expected,self.app.source_label.value)
            self.assertIn(expected,self.study.source_status.value)
        self.assertIsNone(self.study.study)
        self.assertEqual(self.study.cage.options,())
        self.assertIn('NEEDS A NEW RUN',self.study.notice.value)
        self.app.controls['n_N1'].value=6
        self.assertIn('SUCCESSFULLY',self.app.import_notice.value)
        self.app.controls['Mu_B'].value=500
        self.assertIn('IMPORTED INPUTS HAVE CHANGED',self.app.import_notice.value)
        self.assertNotIn('XML APPLIED',panel.status.value)

    def test_json_receipt_and_visible_failures(self):
        case=import_fbmp_xml(FIXTURE)
        receive_upload(self.app.upload,'new_case.json',json.dumps(case).encode())
        self.assertEqual(self.app.case,case)
        self.assertIn('new_case.json',self.app.import_notice.value)
        self.assertIn('SUCCESSFULLY',self.app.import_notice.value)
        receive_upload(self.app.upload,'broken.json',b'{broken')
        self.assertIn('CASE IMPORT FAILED',self.app.import_notice.value)
        self.assertEqual(self.app.case,case)
        panel=self.app.xml_import
        receive_upload(panel.upload,'wrong.xml',b'<wrong/>')
        self.assertIn('XML IMPORT FAILED',panel.status.value)
        self.assertIsNone(panel.pending)
        self.assertTrue(panel.apply_button.disabled)
        # Errors in the upload envelope itself used to escape before stage().
        panel.upload=SimpleNamespace(value=[{'name':'missing_content.xml'}])
        panel._uploaded(None)
        self.assertIn('XML IMPORT FAILED',panel.status.value)

    def test_upload_library_is_explicitly_separate(self):
        before=deepcopy(self.app.case)
        case=import_fbmp_xml(FIXTURE)
        receive_upload(self.study.upload,'analysis.json',json.dumps(case).encode())
        self.assertEqual(self.app.case,before)
        self.assertIn('ADDED TO LIBRARY',self.study.library_note.value)
        self.assertIn('does not replace',self.study.library_note.value)
        self.assertIn('Library uploads do not replace',self.study.source_status.value)

    def test_workbench_rerun_preserves_case_and_rebinds_displayed_study(self):
        case=import_fbmp_xml(FIXTURE)
        self.app.load(case,import_name='Pier_MinTip.XML')
        self.app.search_lists['top_counts'].value=(5,6)
        self.app.dc_limit.value=.95
        before=deepcopy(self.app.case)
        old_app=self.app
        notebook=json.loads((ROOT/'Pier_Cap_Design_Optimizer.ipynb').read_text(encoding='utf-8'))
        context={'app':old_app,'section_app':self.study,'case':default_case(),'ROOT':ROOT,'CapNotebook':CapNotebook}
        with patch.object(CapNotebook,'display'):
            exec(''.join(next(c for c in notebook['cells'] if c.get('id') == '7447e4cc')['source']),context)
        self.app=context['app']
        self.assertIsNot(self.app,old_app)
        self.assertEqual(self.app.case,before)
        self.assertEqual(self.app.search_lists['top_counts'].value,(5,6))
        self.assertEqual(self.app.dc_limit.value,.95)
        self.assertIn('SUCCESSFULLY',self.app.import_notice.value)
        self.assertIs(self.study.app,self.app)
        self.assertNotIn(self.study.invalidate,old_app.case_listeners)
        self.assertIn(self.study.invalidate,self.app.case_listeners)
        self.app.controls['Mu_B'].value=400
        self.assertIn('400',self.study.source_status.value)
        self.assertIn('NEEDS A NEW RUN',self.study.notice.value)

    def test_notebook_upgrade_recovers_replaced_methods_and_partial_detachment(self):
        # Reproduce an old live instance after its methods were replaced. The
        # registered callbacks still contain the original function objects.
        class ReloadedStudy(SectionStudy):
            def _grid_changed(self, change):
                return super()._grid_changed(change)

            def invalidate(self):
                return super().invalidate()

        original_app = self.app
        first_control = next(iter(original_app.search_lists.values()))
        first_control.unobserve(self.study._grid_changed, names='value')
        unrelated = Mock()
        original_app.limit.observe(unrelated, names='value')
        original_app.case_listeners.append(unrelated)
        self.study.__class__ = ReloadedStudy
        # This is the exact failure in the previous notebook's rebind method.
        with self.assertRaises(ValueError):
            original_app.limit.unobserve(self.study._grid_changed, names='value')
        notebook=json.loads((ROOT/'Pier_Cap_Design_Optimizer.ipynb').read_text(encoding='utf-8'))
        context={'app':self.app,'section_app':self.study,'case':default_case(),'ROOT':ROOT}
        with patch.object(CapNotebook,'display'):
            exec(''.join(next(c for c in notebook['cells'] if c.get('id') == '7447e4cc')['source']),context)
        self.app=context['app']
        self.assertIs(self.study.app,self.app)
        for control in [*original_app.search_lists.values(),original_app.limit]:
            handlers=control._trait_notifiers.get('value',{}).get('change',())
            self.assertFalse(any(getattr(h,'__self__',None) is self.study for h in handlers))
        self.assertIn(unrelated,original_app.limit._trait_notifiers['value']['change'])
        # Running the study cell must also use current cleanup on an old object.
        with patch('IPython.display.display'):
            exec(''.join(next(c for c in notebook['cells'] if c.get('id') == '509fc7f9')['source']),context)
        old_study=self.study
        self.study=context['section_app']
        close_study(old_study)
        self.assertIs(self.study.app,self.app)
        self.assertIn(self.study.invalidate,self.app.case_listeners)

    def test_rebind_and_close_are_safe_when_repeated_and_preserve_other_listeners(self):
        unrelated=Mock()
        self.app.case_listeners.append(unrelated)
        rebind_study(self.study,self.app)
        rebind_study(self.study,self.app)
        self.assertEqual(self.app.case_listeners.count(self.study.invalidate),1)
        self.assertIn(unrelated,self.app.case_listeners)
        close_study(self.study)
        close_study(self.study)
        self.assertIn(unrelated,self.app.case_listeners)

    def test_upgrading_a_live_older_study_does_not_close_it_twice(self):
        notebook=json.loads((ROOT/'Pier_Cap_Design_Optimizer.ipynb').read_text(encoding='utf-8'))
        # Earlier notebook instances have close() but no rebind() method.
        old_study=self.study
        legacy=SimpleNamespace(close=old_study.close)
        context={'app':self.app,'section_app':legacy,'case':default_case(),'ROOT':ROOT,
                 'CapNotebook':CapNotebook,'SectionStudy':SectionStudy}
        with patch.object(CapNotebook,'display'),patch('builtins.print'):
            exec(''.join(next(c for c in notebook['cells'] if c.get('id') == '7447e4cc')['source']),context)
        self.app=context['app']
        self.assertIsNone(context['section_app'])
        with patch('IPython.display.display'):
            exec(''.join(next(c for c in notebook['cells'] if c.get('id') == '509fc7f9')['source']),context)
        self.study=context['section_app']
        self.assertIs(self.study.app,self.app)


class UploadDataTests(unittest.TestCase):
    def test_both_upload_formats_and_numeric_signature_equivalence(self):
        new=[{'name':'a.XML','content':b'xml'}]
        old={'a.XML':{'metadata':{'name':'a.XML'},'content':b'xml'}}
        for value in (new,old):
            self.assertEqual(upload_entries(value)[0]['name'],'a.XML')
            self.assertEqual(upload_entries(value)[0]['content'],b'xml')
        with self.assertRaises(ValueError):upload_entries([{'name':'a.XML'}])
        a=default_case();b=deepcopy(a)
        b['inputs']['N_pile']=int(b['inputs']['N_pile'])
        self.assertEqual(source_signature(a),source_signature(b))


class ColabNativeUploadTests(unittest.TestCase):
    def setUp(self):
        self.files=SimpleNamespace(upload=Mock())
        with patch.dict('sys.modules', {'google.colab':SimpleNamespace(files=self.files)}):
            self.app=CapNotebook(default_case())
        self.addCleanup(self.app.close)
        self.panel=self.app.xml_import

    def test_native_transfer_previews_then_applies_without_binary_widget_messages(self):
        before=deepcopy(self.app.case)
        self.files.upload.side_effect=lambda target_dir: {
            str(Path(target_dir)/'Pier_MinTip.XML'):FIXTURE.read_bytes()}
        self.panel.upload.click()
        self.assertEqual(self.app.case,before)
        self.assertIn('PREVIEW READY',self.panel.status.value)
        self.assertEqual(self.panel.pending['analysis']['xml_audit']['filename'],'Pier_MinTip.XML')
        self.assertFalse(self.panel.upload.disabled)
        self.assertEqual(self.panel.upload_output.layout.display,'none')
        self.panel.apply_button.click()
        self.assertEqual(self.app.case['inputs']['h'],36)
        self.assertIn('LOADS IMPORTED SUCCESSFULLY',self.app.import_notice.value)
        # Re-selecting the same file must still create a new preview.
        self.panel.upload.click()
        self.assertIsNotNone(self.panel.pending)
        self.assertIn('PREVIEW READY',self.panel.status.value)

    def test_cancel_or_failure_cannot_leave_an_earlier_preview_applicable(self):
        before=deepcopy(self.app.case)
        cases=[({},'UPLOAD CANCELLED'),
               ({'a.xml':b'bad','b.xml':b'bad'},'exactly one'),
               ({'a.txt':b'bad'},'.xml file'),
               ({'a.xml':b'<wrong/>'},'XML IMPORT FAILED')]
        for received,message in cases:
            with self.subTest(message=message):
                self.panel.stage(FIXTURE.read_bytes(),'old.xml')
                self.assertIsNotNone(self.panel.pending)
                self.files.upload.return_value=received
                self.panel.upload.click()
                self.assertIn(message,self.panel.status.value)
                self.assertIsNone(self.panel.pending)
                self.assertTrue(self.panel.apply_button.disabled)
                self.assertFalse(self.panel.upload.disabled)
                self.assertEqual(self.app.case,before)
        self.files.upload.side_effect=RuntimeError('Transfer disconnected')
        self.panel.upload.click()
        self.assertIn('Transfer disconnected',self.panel.status.value)
        self.assertFalse(self.panel.upload.disabled)
