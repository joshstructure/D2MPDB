import ast
import hashlib
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.project_coherence import (source_checks, safe_value, tracker_checks, HEADERS, read_assumptions,
                                     assumption_checks, assumption_state, assumption_summary, write_report, ASSUMPTION_SCHEMA)


class SourceChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/'input.dat').write_bytes(b'original')
        self.source=dict(source_id='A', path='input.dat', status='Current source',
                         sha256=hashlib.sha256(b'original').hexdigest(), depends_on='')

    def tearDown(self): self.temp.cleanup()

    def test_exact_bytes_match(self):
        self.assertEqual(source_checks(self.root,[self.source])[0]['status'],'MATCH')

    def test_changed_source_flags_consumer(self):
        (self.root/'input.dat').write_bytes(b'revised')
        consumer=dict(self.source,source_id='B',depends_on='A')
        result=source_checks(self.root,[self.source,consumer])
        self.assertEqual(result[0]['status'],'CHANGED')
        self.assertEqual(result[-1]['check_id'],'DEP:B:A')
        self.assertEqual(result[-1]['status'],'REVIEW')
        self.assertEqual(self.source['sha256'],hashlib.sha256(b'original').hexdigest())

    def test_missing_file_does_not_pass(self):
        self.source['path']='absent.dat'
        self.assertEqual(source_checks(self.root,[self.source])[0]['status'],'MISSING')

    def test_unadopted_matching_file_still_needs_review(self):
        self.source['status']='Missing'
        self.assertEqual(source_checks(self.root,[self.source])[0]['status'],'REVIEW')

    def test_path_escape_is_rejected(self):
        self.source['path']='../other.dat'
        self.assertEqual(source_checks(self.root,[self.source])[0]['status'],'ERROR')

    def test_unknown_dependency(self):
        self.source['depends_on']='UNKNOWN'
        self.assertEqual(source_checks(self.root,[self.source])[-1]['status'],'ERROR')

    def test_duplicate_source_id(self):
        self.assertTrue(all(r['status']=='ERROR' for r in source_checks(self.root,[self.source,self.source])))

    def test_notebook_line_endings_only_are_normalized(self):
        self.source.update(hash_basis='lf_text',sha256=hashlib.sha256(b'a\nb\n').hexdigest())
        (self.root/'input.dat').write_bytes(b'a\r\nb\r\n')
        self.assertEqual(source_checks(self.root,[self.source])[0]['status'],'MATCH')
        (self.root/'input.dat').write_bytes(b'a\r\nc\r\n')
        self.assertEqual(source_checks(self.root,[self.source])[0]['status'],'CHANGED')


class InputExtraction(unittest.TestCase):
    def test_arithmetic_and_numpy_literal_without_execution(self):
        node=ast.parse("{'spacing': 8+7/12, 'station': np.float64(1593.22)}",mode='eval').body
        self.assertAlmostEqual(safe_value(node)['spacing'],103/12)

    def test_arbitrary_code_is_not_executed(self):
        with self.assertRaises(ValueError): safe_value(ast.parse("__import__('os').system('test')",mode='eval').body)


class TrackerChecks(unittest.TestCase):
    def item(self,**updates):
        d={h:'recorded' for h in HEADERS}
        d.update({'Item ID':'COH-001','Status':'Open','Your response':'','Owner':'','Due date':'','Resolution / evidence':''})
        d.update(updates)
        return d

    def test_unassigned_owner_is_allowed(self):
        self.assertEqual(tracker_checks([self.item()]),[])

    def test_closure_requires_evidence(self):
        item=self.item(Status='Closed')
        self.assertIn('requires resolution evidence',tracker_checks([item])[0]['detail'])
        item['Resolution / evidence']='Resolved by reviewed revision abc, 2026-10-09'
        self.assertEqual(tracker_checks([item]),[])

    def test_duplicate_id_is_rejected(self):
        results=tracker_checks([self.item(),self.item()])
        self.assertEqual(len(results),2)
        self.assertTrue(all('Duplicate' in r['detail'] for r in results))

    def test_missing_status_is_not_treated_as_closed(self):
        self.assertIn('valid status',tracker_checks([self.item(Status='')])[0]['detail'])


class AssumptionChecks(unittest.TestCase):
    digest_a=hashlib.sha256(b'a').hexdigest()
    digest_b=hashlib.sha256(b'b').hexdigest()

    def setUp(self):
        self.sources=[dict(source_id='A',path='a.dat',status='Current',sha256=self.digest_a,depends_on=''),
                      dict(source_id='B',path='b.dat',status='Current',sha256=self.digest_b,depends_on='')]
        self.items=[{h:'recorded' for h in HEADERS}|{'Item ID':'COH-001','Status':'Open'}]

    def entry(self,**updates):
        e=dict(id='A-001',kind='gap',statement='A small gap.',where='Model',nodes=['A'],
               magnitude=dict(value=0.4,unit='kip',sized_by='Compared with the journal value.'),
               disposition=dict(status='accepted-negligible',decision='D-062',on='2026-10-19'),
               owner='Project user',coherence_items=['COH-001'],basis={'A':self.digest_a},references=[])
        e.update(updates)
        return e

    def register(self,*entries):
        return dict(schema=ASSUMPTION_SCHEMA,schema_version=1,note='',entries=list(entries))

    def test_current_basis_matches(self):
        result=assumption_checks(self.register(self.entry()),self.sources,self.items)
        self.assertEqual([r['status'] for r in result],['MATCH'])
        self.assertEqual(result[0]['check_id'],'ASSUMPTION:A-001')

    def test_moved_register_hash_marks_entry_stale_without_rejudging(self):
        self.sources[0]['sha256']=self.digest_b
        state=assumption_state(self.entry(),self.sources)
        self.assertTrue(state['stale']); self.assertEqual(state['stale_sources'],['A'])
        self.assertEqual(state['current_basis'],{'A':self.digest_b})
        result=assumption_checks(self.register(self.entry()),self.sources,self.items)
        self.assertEqual(result[0]['status'],'REVIEW')
        self.assertIn('re-judge',result[0]['detail'])
        self.assertEqual(self.entry()['disposition']['status'],'accepted-negligible')

    def test_hash_comparison_ignores_case(self):
        self.assertFalse(assumption_state(self.entry(basis={'A':self.digest_a.upper()}),self.sources)['stale'])

    def test_unknown_source_tracker_item_and_duplicate_id_are_errors(self):
        for bad in (dict(basis={'Z':self.digest_a}),dict(coherence_items=['COH-999']),dict(kind='guess'),
                    dict(disposition=dict(status='closed',decision='',on='2026-10-19')),dict(nodes=[]),
                    dict(magnitude=dict(value='big',unit='kip',sized_by='x')),dict(disposition=dict(status='pending',decision='D-050',on='19 Oct'))):
            result=assumption_checks(self.register(self.entry(**bad)),self.sources,self.items)
            self.assertEqual(result[0]['status'],'ERROR',bad)
        result=assumption_checks(self.register(self.entry(),self.entry()),self.sources,self.items)
        self.assertTrue(all(r['status']=='ERROR' and 'Duplicate' in r['detail'] for r in result))

    def test_pending_entries_need_no_decision_but_are_open(self):
        pending=self.entry(id='A-002',disposition=dict(status='pending',decision='',on='2026-10-19'))
        self.assertEqual(assumption_checks(self.register(pending),self.sources,self.items)[0]['status'],'MATCH')
        self.sources[1]['sha256']=self.digest_a
        stale=self.entry(id='A-003',basis={'B':self.digest_b})
        summary=assumption_summary(self.register(self.entry(),pending,stale),self.sources)
        self.assertEqual([e['id'] for e in summary['entries']],['A-003','A-002','A-001'])
        self.assertEqual((summary['count'],summary['open'],summary['stale']),(3,1,1))

    def test_report_lists_open_and_stale_entries_only(self):
        self.sources[1]['sha256']=self.digest_a
        summary=assumption_summary(self.register(self.entry(),self.entry(id='A-002',disposition=dict(status='pending',decision='',on='2026-10-19')),
                                                 self.entry(id='A-003',basis={'B':self.digest_b})),self.sources)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            write_report(root,dict(checked_at_utc='now',outstanding_count=0,source_count=2,item_count=1,check_counts={'MATCH':1},
                                   checks=[],items=[],assumptions=summary))
            text=(root/'project_current/coherence/latest_review.md').read_text(encoding='utf-8')
        self.assertIn('## Assumptions and gaps',text)
        self.assertIn('| A-002 | gap | open |',text)
        self.assertIn('| A-003 | gap | stale: B |',text)
        self.assertNotIn('| A-001 |',text)
        self.assertIn('0.4 kip',text)

    def test_schema_is_checked_and_absent_register_is_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'assumptions.json'
            self.assertIsNone(read_assumptions(path))
            self.assertEqual(assumption_checks(None,self.sources,self.items),[])
            path.write_text('{"schema":"other","schema_version":1,"entries":[]}',encoding='utf-8')
            with self.assertRaises(ValueError): read_assumptions(path)
            path.write_text('{"schema":"'+ASSUMPTION_SCHEMA+'","schema_version":1,"entries":[]}',encoding='utf-8')
            self.assertEqual(read_assumptions(path)['entries'],[])


if __name__=='__main__': unittest.main()
