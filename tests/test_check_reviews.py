"""Review decisions survive saving without replacing their calculation evidence."""
from copy import deepcopy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from lxml import html

from pier_cap.model import evaluate, set_inputs, sectional_checks_pass
from pier_cap.check_reviews import record_review, review_history
from pier_cap.io import load_case, write_case, export_bundle
from pier_cap.calculation_report import calculation_report, Report
from pier_cap.visuals import checks_html
from tests.case_fixtures import default_case


def check(e, key):
    return next(c for c in e.checks if c.key == key)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.e = evaluate(default_case())

    def test_close_pending_keeps_original_and_roundtrips(self):
        before = deepcopy(self.e.case)
        case = record_review(self.e, 'Status_III', 'close_pending', ' Checked external service calculation. ', ' JS ')
        e = evaluate(case)
        self.assertEqual(self.e.case, before)
        c = check(e, 'Status_III')
        self.assertEqual(c.status, 'PASS · CLOSED')
        self.assertEqual(c.ratio, check(self.e, c.key).ratio)
        self.assertEqual(c.calculated_status, check(self.e, c.key).status)
        self.assertEqual(c.review['reason'], 'Checked external service calculation.')
        self.assertEqual(c.review['reviewed_by'], 'JS')
        self.assertEqual(e.max_dc, self.e.max_dc)
        self.assertEqual(e.eligible, self.e.eligible)
        self.assertIn('PASS · CLOSED', Report(e).result('Status_III'))
        with tempfile.TemporaryDirectory() as folder:
            path = write_case(case, Path(folder)/'selected_case.json')
            restored = load_case(path)
        self.assertEqual(restored['check_reviews'], case['check_reviews'])
        self.assertEqual(check(evaluate(restored), c.key).status, c.status)

    def test_failed_override_retains_ratio_and_search_failure(self):
        failed = evaluate(set_inputs(default_case(), Mu_N=10000))
        self.assertIn('FAIL', check(failed, 'Chk_flex_N').status)
        with self.assertRaises(ValueError):record_review(failed, 'Chk_flex_N', 'close_pending', 'checked')
        case = record_review(failed, 'Chk_flex_N', 'override', 'Exception accepted in separate calculation.')
        e = evaluate(case)
        c = check(e, 'Chk_flex_N')
        self.assertEqual(c.status, 'PASS · OVERRIDE')
        self.assertGreater(c.ratio, 1)
        self.assertIn('FAIL', c.calculated_status)
        self.assertFalse(sectional_checks_pass(e))
        self.assertFalse(e.eligible)
        self.assertEqual(e.value('Mn_N'), failed.value('Mn_N'))
        self.assertEqual(e.max_dc, failed.max_dc)

    def test_blank_reason_invalid_action_and_summary_are_rejected(self):
        for reason in ('', '  \n', None):
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                record_review(self.e, 'Status_III', 'close_pending', reason)
        for key, action in [('Status_overall', 'override'), ('missing', 'override'), ('Chk_flex_N', 'close_pending'), ('Status_III', 'invalid')]:
            with self.subTest(key=key, action=action), self.assertRaises(ValueError):record_review(self.e, key, action, 'note')

    def test_changed_inputs_source_and_result_require_new_review(self):
        case = record_review(self.e, 'Status_III', 'close_pending', 'Original service review')
        for change in (lambda c: c['inputs'].update(Mu_N=c['inputs']['Mu_N']+1),
                       lambda c: c['analysis'].update(id='New analysis'),
                       lambda c: c['screening'].update(aggregate_in=1)):
            changed = deepcopy(case);change(changed)
            e = evaluate(changed);c = check(e, 'Status_III')
            self.assertEqual(c.review_state, 'Needs review')
            self.assertEqual(c.status, c.calculated_status)
            self.assertIn('Original service review', checks_html(e))
        e = evaluate(case)
        check(e, 'Status_III').calculated_basis += ' Revised criterion.'
        self.assertEqual(review_history(e)[0]['state'], 'Needs review')
        # Cosmetic name changes and JSON number types do not retire a decision.
        renamed = deepcopy(case);renamed['name'] = 'Renamed';renamed['inputs']['n_N1'] = float(renamed['inputs']['n_N1'])
        self.assertEqual(check(evaluate(renamed), 'Status_III').review_state, 'Active')

    def test_reopen_and_replacement_preserve_history(self):
        e = evaluate(record_review(self.e, 'Status_III', 'close_pending', 'First review'))
        e = evaluate(record_review(e, 'Status_III', 'override', 'Updated basis'))
        self.assertEqual([r['state'] for r in review_history(e)], ['Superseded', 'Active'])
        e = evaluate(record_review(e, 'Status_III', 'reopen', 'Request another review'))
        self.assertEqual(check(e, 'Status_III').status, check(self.e, 'Status_III').status)
        self.assertEqual([r['reason'] for r in review_history(e)], ['First review', 'Updated basis', 'Request another review'])
        self.assertEqual(review_history(e)[-1]['state'], 'Reopened')

    def test_all_pending_reviews_update_aggregate(self):
        from pier_cap.check_reviews import is_pending
        e = self.e
        keys = [c.key for c in e.checks if c.key != 'Status_overall' and is_pending(c.status)]
        for key in keys:e = evaluate(record_review(e, key, 'close_pending', 'Reviewed '+key))
        self.assertEqual(check(e, 'Status_overall').status, 'PASS · WITH RECORDED REVIEWS')
        self.assertIn('CHECK REGISTER PASS', e.status)
        self.assertFalse([c for c in e.checks if is_pending(c.status)])

    def test_actual_cage_reviews_remain_individual_and_do_not_change_capacity(self):
        from pier_cap.transverse import suggested_detail
        case = default_case();case['transverse_detail'] = suggested_detail(self.e)
        original = evaluate(case)
        e = evaluate(record_review(original, 'Status_actual_review', 'close_pending', 'STM check attached'))
        self.assertEqual(check(e, 'Status_actual_review').status, 'PASS · CLOSED')
        self.assertEqual(e.lrfd, original.lrfd)
        self.assertEqual(e.max_dc, original.max_dc)
        self.assertFalse(e.eligible)

    def test_bundle_and_report_export_notes_status_originals_and_history_escaped(self):
        note = 'Drawing C-12 checked <script id="injected">x</script> & signed.\nSecond line.'
        case = record_review(self.e, 'Status_III', 'close_pending', note, 'A&B')
        e = evaluate(case)
        markup = calculation_report(evaluation=e)
        doc = html.fromstring(markup)
        self.assertFalse(doc.xpath('//script[@id="injected"]'))
        for line in note.splitlines():self.assertIn(line, doc.xpath('//main')[0].text_content())
        self.assertIn('PASS · CLOSED', doc.get_element_by_id('register').text_content())
        self.assertIn(check(self.e, 'Status_III').status, doc.text_content())
        self.assertIn('A&B', doc.text_content())
        with tempfile.TemporaryDirectory() as folder:
            bundle = export_bundle(case, folder)
            data = json.loads((bundle/'checks.json').read_text(encoding='utf-8'))
            exported = next(c for c in data['checks'] if c['key'] == 'Status_III')
            self.assertEqual(exported['status'], 'PASS · CLOSED')
            self.assertEqual(exported['review']['reason'], note)
            self.assertEqual(data['review_history'], review_history(e))
            self.assertEqual(load_case(bundle/'selected_case.json')['check_reviews'], case['check_reviews'])
            with (bundle/'checks.csv').open(encoding='utf-8-sig', newline='') as stream:
                row = next(r for r in csv.DictReader(stream) if r['Check key'] == 'Status_III')
            self.assertEqual(row['Reason / closure note'], note)
            self.assertEqual(row['Calculated status'], check(self.e, 'Status_III').status)
            self.assertIn('PASS · CLOSED', (bundle/'calculation_report.html').read_text(encoding='utf-8'))

    def test_malformed_import_cannot_silently_apply_or_drop_review(self):
        case = record_review(self.e, 'Status_III', 'close_pending', 'Basis')
        for key, value in [('reason', ' '), ('recorded_at', 'yesterday'), ('case_fingerprint', 'bad'), ('original_ratio', None)]:
            candidate = deepcopy(case);candidate['check_reviews']['records'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):load_case(json.dumps(candidate).encode())
        candidate = deepcopy(case);candidate['check_reviews']['version'] = 99
        with self.assertRaises(ValueError):load_case(json.dumps(candidate).encode())

    def test_disappeared_check_can_be_reopened_and_history_is_preserved(self):
        from pier_cap.transverse import suggested_detail
        case = default_case();case['transverse_detail'] = suggested_detail(self.e)
        e = evaluate(record_review(evaluate(case), 'Status_actual_review', 'close_pending', 'Local detail reviewed'))
        disabled = deepcopy(e.case);disabled['transverse_detail']['enabled'] = False
        e = evaluate(disabled)
        self.assertEqual(review_history(e)[-1]['state'], 'Check unavailable')
        self.assertIn('Local detail reviewed', checks_html(e))
        reopened = record_review(e, 'Status_actual_review', 'reopen', 'Schedule removed')
        self.assertEqual(review_history(evaluate(reopened))[-1]['state'], 'Reopened')


class ReviewWidgetTests(unittest.TestCase):
    def test_applying_search_candidate_keeps_reviews_recorded_after_search(self):
        from pier_cap.widgets import CapNotebook
        from pier_cap.optimizer import search, SearchConfig
        app = CapNotebook(default_case());self.addCleanup(app.close)
        app.recalc_button.click()
        result = search(app.case, SearchConfig(main_bars=(8,), top_counts=(10,), bottom_counts=(8,),
            hoop_bars=(5,), hoop_spacings=(8,), skin_bars=(5,), skin_counts=(6,)))
        self.assertEqual(len(result.candidates), 1)
        app.check_reviews.check.value = 'Status_III';app.check_reviews.reason.value = 'Review after search'
        app.check_reviews.close_pending.click()
        app.search_result = result;app._render_candidates(reset_page=True);app._apply(None)
        self.assertEqual(app.case['check_reviews']['records'][0]['reason'], 'Review after search')
        app.recalc_button.click()
        self.assertEqual(check(app.current, 'Status_III').review_state, 'Needs review')

    def test_save_reopen_reload_and_stale_controls(self):
        from pier_cap.widgets import CapNotebook
        app = CapNotebook(default_case());self.addCleanup(app.close)
        panel = app.check_reviews
        self.assertTrue(panel.close_pending.disabled)
        app.recalc_button.click()
        panel.check.value = 'Status_III'
        self.assertTrue(panel.close_pending.disabled)
        panel.reason.value = 'Service review completed';panel.reviewer.value = 'JS'
        self.assertFalse(panel.close_pending.disabled)
        panel.close_pending.click()
        self.assertIn('Review recorded', panel.message.value)
        self.assertEqual(check(app.current, 'Status_III').status, 'PASS · CLOSED')
        saved = deepcopy(app.case)
        app.check_view.value = 'pending_only'
        register = html.fromstring(app.register.value)
        self.assertFalse(register.xpath('//details[@data-check="Status_III"]'))
        app.check_view.value = 'reviewed_only'
        self.assertIn('Service review completed', app.register.value)
        panel.reopen.click()
        self.assertIn('PENDING', check(app.current, 'Status_III').status)
        app.load(saved);app.recalc_button.click()
        self.assertEqual(check(app.current, 'Status_III').status, 'PASS · CLOSED')
        app.controls['Mu_N'].value += 1
        self.assertTrue(panel.close_pending.disabled);self.assertTrue(panel.override.disabled);self.assertTrue(panel.reopen.disabled)
        prior = deepcopy(app.case)
        panel._save('override')
        self.assertEqual(app.case, prior)
        app.recalc_button.click()
        self.assertEqual(check(app.current, 'Status_III').review_state, 'Needs review')
        panel.check.value = 'Status_III';panel.reason.value = 'Reviewed changed case'
        panel.close_pending.click()
        self.assertEqual(check(app.current, 'Status_III').status, 'PASS · CLOSED')
        self.assertEqual(len(app.case['check_reviews']['records']), 2)


if __name__ == '__main__':unittest.main()
