"""Pending explanations follow every prerequisite, not just the largest D/C."""
import unittest
from unittest.mock import patch

from pier_cap.lrfd_checks import _aggregate, transverse_development
from pier_cap.model import evaluate, set_inputs
from pier_cap.visuals import checks_html
from tests.test_lrfd_actual import actual_case


class ShearPendingReasonTests(unittest.TestCase):
    def test_actual_shear_explains_anchorage_and_splices_in_ratio_basis(self):
        case=actual_case(True)
        result=evaluate(case)
        checks=[c for c in result.checks if c.key.startswith('Chk_actual_shear_') and c.status=='PENDING']
        self.assertTrue(checks)
        for check in checks:
            self.assertTrue(check.basis.startswith('Pending because:\n'))
            self.assertIn('Continuous-bar splices are unconfirmed',check.basis)
            self.assertIn('anchorage / closure',check.basis)
            self.assertIn('Vc=',check.basis)
        self.assertIn('Pending because:<br>',checks_html(result))
        case['lrfd_checks']['continuous_splices']='none'
        result=evaluate(case)
        for check in result.checks:
            if check.key.startswith('Chk_actual_shear_'):
                self.assertNotIn('Continuous-bar splices are unconfirmed',check.basis)

    def test_reasons_name_unverified_window_run_outside_adjacent_endpoints(self):
        case=actual_case(True)
        case['lrfd_checks']['continuous_splices']='none'
        development,checks=transverse_development(evaluate(case))
        for row in development:row.update(pending=False,ratio=.5)
        development[1].update(pending=True,notes='Test unresolved hook engagement')
        with patch('pier_cap.lrfd_checks.transverse_development',return_value=(development,checks)):
            result=evaluate(case)
        rows=[r for r in result.lrfd['intervals'] if r['anchored'] and r['pending']]
        self.assertTrue(rows)
        reason='Shear window includes reinforcement without verified anchorage: R2'
        self.assertTrue(any(reason in row['pending_reasons'] for row in rows))
        for row in rows:
            if reason in row['pending_reasons']:
                check=next(c for c in result.checks if c.label==row['id']+' shear')
                self.assertIn('R2: anchorage / closure is unconfirmed',check.basis)
                self.assertIn('Test unresolved hook engagement',check.basis)

    def test_lower_ratio_row_can_keep_aggregate_pending_and_failure_stays_fail(self):
        rows=[dict(id='high',ratio=.8,pending=False,pending_reasons=[]),
              dict(id='low',ratio=.2,pending=True,pending_reasons=['R2: hook engagement unconfirmed'])]
        check=_aggregate('Chk_shear_G','Actual shear',rows,'ratio','Calculation basis.')
        self.assertEqual((check.status,check.ratio),('PENDING',.8))
        self.assertIn('R2: hook engagement unconfirmed',check.basis)
        rows[0]['ratio']=1.2
        check=_aggregate('Chk_shear_G','Actual shear',rows,'ratio','Calculation basis.')
        self.assertEqual((check.status,check.ratio),('FAIL',1.2))
        self.assertTrue(check.basis.startswith('Unresolved prerequisites:'))

    def test_source_mismatch_and_unsupported_precompression_are_explained(self):
        case=set_inputs(actual_case(True),Mu_B=999,fpc=1)
        result=evaluate(case)
        checks=[c for c in result.checks if c.key.startswith('Chk_actual_shear_')]
        self.assertTrue(checks)
        for check in checks:
            self.assertIn('fpc = 1 ksi',check.basis)
            self.assertIn(result.lrfd['source_notice'],check.basis)


if __name__=='__main__':unittest.main()
