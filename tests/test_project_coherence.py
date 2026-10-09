import ast
import hashlib
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.project_coherence import source_checks, safe_value, tracker_checks, HEADERS


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


if __name__=='__main__': unittest.main()
