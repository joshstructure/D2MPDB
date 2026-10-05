"""Exact station schedules preserve the entered pitch and disclose overlap."""
from copy import deepcopy
import unittest
from pier_cap.transverse import empty_detail,validate_detail,scheduled_bars,run_summary,station_issues
from pier_cap.model import default_case,evaluate


def with_run(**changes):
    case=default_case()
    case['transverse_detail']={'version':1,'enabled':True,'runs':[
        dict(id='H1',kind='hoop',bar=6,zone='G',first_in=4,end_in=33,pitch_in=9,**changes)]}
    return case


class TransverseStationTests(unittest.TestCase):
    def test_exact_pitch_and_last_station_are_not_stretched(self):
        case=with_run()
        self.assertEqual([b['station_in'] for b in scheduled_bars(case)],[4,13,22,31])
        self.assertEqual(run_summary(case)[0]['actual_last_in'],31)
        self.assertEqual(run_summary(case)[0]['count'],4)

    def test_duplicate_runs_and_unbounded_counts_fail(self):
        case=with_run();case['transverse_detail']['runs']*=2
        with self.assertRaisesRegex(ValueError,'unique'):validate_detail(case)
        for key,value in [('pitch_in',0),('first_in',-1),('end_in',float('nan')),('bar',True),('pitch_in',.00001)]:
            case=with_run();case['transverse_detail']['runs'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate_detail(case)

    def test_coincident_bars_stay_in_schedule_and_are_reported(self):
        case=with_run();other=deepcopy(case['transverse_detail']['runs'][0]);other['id']='U1';other['kind']='pile_u'
        case['transverse_detail']['runs'].append(other)
        self.assertEqual(len(scheduled_bars(case)),8)
        self.assertTrue(any('overlap' in issue for issue in station_issues(evaluate(case))))

    def test_disabled_detail_preserves_input_but_draws_no_stations(self):
        case=with_run();case['transverse_detail']['enabled']=False
        self.assertEqual(scheduled_bars(case),[])
        self.assertEqual(len(case['transverse_detail']['runs']),1)
        self.assertEqual(empty_detail(),{'version':1,'enabled':False,'runs':[]})


if __name__=='__main__':unittest.main()
