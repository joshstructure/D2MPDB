"""Behavioral tests for the lossless task integration boundary."""
import json
from pathlib import Path
import tempfile
import unittest

from tools import bpad_workflow as w


SAMPLE = b'''<?xml version="1.0" encoding="utf-8"?>
<document version="1.9">
  <!-- Preserve wrapper whitespace and comments. -->
  <stylerule name="style" condition="A &gt; B"/>
  <report name="Geometry"><paragraph><dynexp formula="h = 4 ft"/></paragraph></report>
  <report name="Loads"><paragraph><dynexp formula="F = Geometry.h * 1 kip/(1 ft)"/></paragraph></report>
  <report name="Notes"><paragraph>Original notes</paragraph></report>
  <resource name="R" type="image/png">YWJj</resource>
</document>'''


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "journal/References").mkdir(parents=True)
        (self.root / w.JOURNAL).write_bytes(SAMPLE)
        (self.root / "standards").mkdir()
        (self.root / "standards/rules.txt").write_text("Native math only")
        self.declarations({"Geometry": [], "Loads": ["Geometry"], "Notes": []})

    def declarations(self, records):
        modules = {"report:" + name: {"reads": deps, "complete": True, "reviewed_by": "test fixture",
                    "rationale": "Synthetic fixture has only the explicit formulas above."} for name, deps in records.items()}
        w.write_json(self.root / "workflow/dependencies.json", {"modules": modules})

    def prepare(self, task_id="T001", module="Notes"):
        return w.prepare(self.root, task_id, "Test bounded editing", [module])

    def edit(self, task_id, old, new):
        p = self.root / "tasks" / task_id / "working.bpad"
        p.write_bytes(p.read_bytes().replace(old, new))

    def edit_current(self, old, new):
        p = self.root / w.JOURNAL
        p.write_bytes(p.read_bytes().replace(old, new))

    def test_lossless_roundtrip_including_entities_empty_tags_and_comments(self):
        data = SAMPLE.replace(b"Original notes", 'A &#160; B &amp; C \u03c6'.encode())
        j = w.Journal(data)
        self.assertEqual(j.replace({k: j.part(k) for k in j.order}), data)
        w.roundtrip(self.root / w.JOURNAL, self.root / "roundtrip")
        self.assertEqual((self.root / "roundtrip/roundtrip.bpad").read_bytes(), SAMPLE)

    def test_unrelated_accepted_change_is_retained(self):
        self.prepare()
        self.edit("T001", b"Original notes", b"Revised notes")
        self.edit_current(b"h = 4 ft", b"h = 5 ft")
        candidate, report = w.check(self.root, "T001")
        self.assertIn(b"h = 5 ft", candidate.data)
        self.assertIn(b"Revised notes", candidate.data)
        self.assertEqual(report["changed_components"], ["report:Notes"])

    def test_two_independent_task_results_merge_without_lost_update(self):
        self.prepare("T001", "Notes")
        self.prepare("T002", "Geometry")
        self.edit("T001", b"Original notes", b"Revised notes")
        self.edit("T002", b"h = 4 ft", b"h = 5 ft")
        first, _ = w.check(self.root, "T001")
        (self.root / w.JOURNAL).write_bytes(first.data)
        second, _ = w.check(self.root, "T002")
        self.assertIn(b"Revised notes", second.data)
        self.assertIn(b"h = 5 ft", second.data)

    def test_stale_numeric_dependency_rejected(self):
        self.prepare(module="Loads")
        self.edit_current(b"h = 4 ft", b"h = 5 ft")
        with self.assertRaisesRegex(w.WorkflowError, "Stale upstream"):
            w.check(self.root, "T001")

    def test_unreviewed_dependency_coverage_defaults_to_every_component(self):
        self.declarations({})
        self.prepare()
        self.edit_current(b"h = 4 ft", b"h = 5 ft")
        with self.assertRaisesRegex(w.WorkflowError, "Stale upstream"):
            w.check(self.root, "T001")

    def test_same_component_conflict_rejected_and_work_preserved(self):
        self.prepare()
        self.edit("T001", b"Original notes", b"Task notes")
        self.edit_current(b"Original notes", b"Accepted notes")
        with self.assertRaisesRegex(w.WorkflowError, "Conflicting owned"):
            w.check(self.root, "T001")
        self.assertIn(b"Task notes", (self.root / "tasks/T001/working.bpad").read_bytes())

    def test_out_of_scope_edit_rejected(self):
        self.prepare()
        self.edit("T001", b"h = 4 ft", b"h = 5 ft")
        with self.assertRaisesRegex(w.WorkflowError, "Out-of-scope"):
            w.check(self.root, "T001")

    def test_tampered_task_order_rejected(self):
        self.prepare()
        p = self.root / "tasks/T001/order.json"
        order = w.read_json(p)
        order["writes"].append("report:Geometry")
        w.write_json(p, order)
        with self.assertRaisesRegex(w.WorkflowError, "order changed"):
            w.check(self.root, "T001")

    def test_modified_base_rejected(self):
        self.prepare()
        p = self.root / "tasks/T001/base.bpad"
        p.write_bytes(p.read_bytes().replace(b"Original notes", b"changed"))
        with self.assertRaisesRegex(w.WorkflowError, "base was modified"):
            w.check(self.root, "T001")

    def test_changed_standard_or_assumption_rejected(self):
        self.prepare()
        (self.root / "standards/rules.txt").write_text("New standard")
        with self.assertRaisesRegex(w.WorkflowError, "Standards, references"):
            w.check(self.root, "T001")

    def test_changed_external_results_rejected(self):
        self.prepare()
        w.write_json(self.root / "workflow/external/run.json", {"input_sha256": "new analysis"})
        with self.assertRaisesRegex(w.WorkflowError, "analysis records changed"):
            w.check(self.root, "T001")

    def test_external_resource_edit_rejected(self):
        (self.root / "journal/References/page.pdf").write_bytes(b"pdf")
        self.prepare()
        (self.root / "tasks/T001/References/page.pdf").write_bytes(b"changed")
        with self.assertRaisesRegex(w.WorkflowError, "reference resources changed"):
            w.check(self.root, "T001")

    def test_new_broken_link_rejected(self):
        self.prepare()
        self.edit("T001", b"Original notes", b'<link address="#Missing">broken</link>')
        with self.assertRaisesRegex(w.WorkflowError, "New structural issues"):
            w.check(self.root, "T001")

    def test_duplicate_id_rejected(self):
        self.prepare()
        self.edit("T001", b"Original notes", b'<span id="x"/><span id="x"/>')
        with self.assertRaisesRegex(w.WorkflowError, "duplicate id"):
            w.check(self.root, "T001")

    def test_removed_published_output_rejected(self):
        self.prepare(module="Geometry")
        self.edit("T001", b"h = 4 ft", b"height = 4 ft")
        with self.assertRaisesRegex(w.WorkflowError, "Removed published name"):
            w.check(self.root, "T001")

    def test_new_native_error_rejected(self):
        self.prepare()
        self.edit("T001", b"Original notes", b"<error>bad input</error>")
        with self.assertRaisesRegex(w.WorkflowError, "New stored native errors"):
            w.check(self.root, "T001")

    def test_new_dependency_requires_contract(self):
        self.prepare()
        self.edit("T001", b"Original notes", b'<dynexp formula="Geometry.h"/>')
        with self.assertRaisesRegex(w.WorkflowError, "New dependencies"):
            w.check(self.root, "T001")

    def test_wrapper_change_and_topology_change_rejected(self):
        self.prepare()
        self.edit("T001", b'version="1.9"', b'version="1.8"')
        with self.assertRaisesRegex(w.WorkflowError, "wrapper"):
            w.check(self.root, "T001")
        (self.root / "tasks/T001/working.bpad").write_bytes(SAMPLE.replace(b"</document>", b'<report name="New"/></document>'))
        with self.assertRaisesRegex(w.WorkflowError, "addition/removal"):
            w.check(self.root, "T001")

    def test_prerequisite_blocks_assembly(self):
        self.prepare("T001")
        w.prepare(self.root, "T002", "Dependent task", ["Loads"], ["T001"])
        with self.assertRaisesRegex(w.WorkflowError, "Prerequisite"):
            w.check(self.root, "T002")

    def test_assembly_does_not_change_current_and_requires_review(self):
        self.prepare()
        self.edit("T001", b"Original notes", b"Revised notes")
        folder = self.root / "generated/candidate"
        w.assemble(self.root, "T001", folder)
        self.assertEqual((self.root / w.JOURNAL).read_bytes(), SAMPLE)
        with self.assertRaisesRegex(w.WorkflowError, "explicitly completed"):
            w.promote(self.root, folder)
        self.assertEqual((self.root / w.JOURNAL).read_bytes(), SAMPLE)

    def reviewed_candidate(self):
        self.prepare()
        self.edit("T001", b"Original notes", b"Revised notes")
        folder = self.root / "generated/candidate"
        w.assemble(self.root, "T001", folder)
        review = w.read_json(folder / "review.json")
        review.update(reviewer="Synthetic test", native_recalculation=True, native_visual_review=True,
                      engineering_review=True, design_outcome="not_applicable",
                      external_analysis_disposition="No external analysis in fixture.", external_analysis_status="not_applicable",
                      inherited_issues_disposition="No inherited issues in fixture.")
        (folder / "evidence.txt").write_text("SYNTHETIC TEST ONLY")
        review["evidence_files"] = [{"path": "evidence.txt", "sha256": w.digest((folder / "evidence.txt").read_bytes())}]
        w.write_json(folder / "review.json", review)
        return folder

    def test_reviewed_exact_revision_promotes_with_backup(self):
        folder = self.reviewed_candidate()
        receipt = w.promote(self.root, folder)
        self.assertIn(b"Revised notes", (self.root / w.JOURNAL).read_bytes())
        self.assertEqual((self.root / receipt["history"] / "previous.bpad").read_bytes(), SAMPLE)
        self.assertTrue((self.root / "workflow/completed/T001.json").is_file())

    def test_modified_candidate_cannot_reuse_review(self):
        folder = self.reviewed_candidate()
        p = folder / "candidate.bpad"
        p.write_bytes(p.read_bytes().replace(b"Revised notes", b"Sneaked change"))
        with self.assertRaisesRegex(w.WorkflowError, "Candidate changed"):
            w.promote(self.root, folder)

    def test_promotion_rechecks_current_revision(self):
        folder = self.reviewed_candidate()
        self.edit_current(b"h = 4 ft", b"h = 5 ft")
        with self.assertRaisesRegex(w.WorkflowError, "changed after assembly"):
            w.promote(self.root, folder)

    def test_changed_evidence_blocks_promotion(self):
        folder = self.reviewed_candidate()
        (folder / "evidence.txt").write_text("changed")
        with self.assertRaisesRegex(w.WorkflowError, "changed review evidence"):
            w.promote(self.root, folder)

    def test_lock_prevents_second_integrator(self):
        with w.writer_lock(self.root):
            with self.assertRaisesRegex(w.WorkflowError, "locked"):
                self.prepare()

    def test_entities_and_path_escape_rejected(self):
        with self.assertRaisesRegex(w.WorkflowError, "DTD"):
            w.Journal(b'<!DOCTYPE document [<!ENTITY x SYSTEM "file:///secret">]><document>&x;</document>')
        with self.assertRaisesRegex(w.WorkflowError, "escapes"):
            w.within(self.root, "../outside")

    def test_reference_import_and_portable_candidate_preserve_pdf_and_formulas(self):
        source = self.root / "pdf-source"
        source.mkdir()
        (source / "code.pdf").write_bytes(b"%PDF-1.7\nfixture")
        baseline = SAMPLE.replace(b'<stylerule', b'<xref name="PDF" path="C:\\missing\\code.pdf"/><stylerule', 1)
        (self.root / w.JOURNAL).write_bytes(baseline)
        w.import_references(self.root, source)
        w.prepare(self.root, "T001", "Relocate paths only", ["xref:PDF"])
        w.relocate_references(self.root, "T001")
        folder = self.root / "generated/portable"
        w.assemble(self.root, "T001", folder)
        proposed = w.Journal.load(folder / "candidate.bpad")
        original = w.Journal(baseline)
        self.assertEqual(original.changes(proposed), ["xref:PDF"])
        self.assertEqual((folder / "References/code.pdf").read_bytes(), (source / "code.pdf").read_bytes())
        self.assertTrue(all(r["exists"] and not r["absolute"] for r in w.external_refs(proposed, folder)))

    def test_component_import_rejects_native_work_overwrite(self):
        self.prepare()
        p = self.root / "tasks/T001/components/000.xml"
        p.write_bytes(p.read_bytes().replace(b"Original notes", b"Fragment edit"))
        w.import_components(self.root, "T001")
        self.assertIn(b"Fragment edit", (self.root / "tasks/T001/working.bpad").read_bytes())
        with self.assertRaisesRegex(w.WorkflowError, "already edited"):
            w.import_components(self.root, "T001")

    def test_rejected_native_import_keeps_working_copy(self):
        self.prepare()
        saved = self.root / "native.bpad"
        saved.write_bytes(SAMPLE.replace(b"h = 4 ft", b"h = 8 ft"))
        with self.assertRaisesRegex(w.WorkflowError, "Out-of-scope"):
            w.import_native(self.root, "T001", saved)
        self.assertEqual((self.root / "tasks/T001/working.bpad").read_bytes(), SAMPLE)

    def test_plan_only_folder_is_retained_during_registration(self):
        folder = self.root / "tasks/T001"
        folder.mkdir(parents=True)
        (folder / "plan.md").write_text("Reviewed plan")
        self.prepare()
        self.assertEqual((folder / "plan.md").read_text(), "Reviewed plan")

    def test_actual_supplied_journal_roundtrips_without_serializing(self):
        path = w.ROOT / w.JOURNAL
        if not path.exists():
            self.skipTest("Project journal absent in isolated tool distribution")
        j = w.Journal.load(path)
        self.assertEqual(j.replace({k: j.part(k) for k in j.order}), j.data)
        self.assertEqual(len(j.order), len(j.root))

    def test_tracked_proposal_restores_ignored_working_copy(self):
        folder = self.reviewed_candidate()
        working = self.root / "tasks/T001/working.bpad"
        expected = working.read_bytes()
        working.unlink()
        (self.root / "tasks/T001/base.bpad").unlink()
        w.restore_task(self.root, "T001")
        self.assertEqual(working.read_bytes(), expected)
        candidate, _ = w.check(self.root, "T001")
        self.assertEqual(candidate.data, (folder / "candidate.bpad").read_bytes())

    def test_missing_pdf_blocks_promotion(self):
        self.edit_current(b'<stylerule', b'<xref name="Missing" path="References/missing.pdf"/><stylerule')
        folder = self.reviewed_candidate()
        with self.assertRaisesRegex(w.WorkflowError, "all reference files"):
            w.promote(self.root, folder)

    def test_unreviewed_external_analysis_blocks_promotion(self):
        folder = self.reviewed_candidate()
        review = w.read_json(folder / "review.json")
        review['external_analysis_status'] = 'unreviewed'
        w.write_json(folder / "review.json", review)
        with self.assertRaisesRegex(w.WorkflowError, "stale external results"):
            w.promote(self.root, folder)

    def test_registered_module_deletion_preserves_other_bytes_and_restores(self):
        w.prepare(self.root, "T001", "Remove unused notes", [], delete_names=["Notes"])
        base = w.Journal(SAMPLE)
        expected = base.replace({"report:Notes": b""})
        (self.root / "tasks/T001/working.bpad").write_bytes(expected)
        candidate, report = w.check(self.root, "T001")
        self.assertEqual(candidate.data, expected)
        self.assertEqual(report["deleted_components"], ["report:Notes"])
        self.assertEqual(candidate.shell, base.shell)
        for key in candidate.order:
            self.assertEqual(candidate.part(key), base.part(key))
        folder = self.root / "generated/delete-notes"
        w.assemble(self.root, "T001", folder)
        (self.root / "tasks/T001/working.bpad").unlink()
        w.restore_task(self.root, "T001")
        self.assertEqual((self.root / "tasks/T001/working.bpad").read_bytes(), expected)
        self.assertEqual(w.check(self.root, "T001")[0].data, expected)

    def test_unregistered_module_deletion_is_rejected(self):
        self.prepare()
        base = w.Journal(SAMPLE)
        (self.root / "tasks/T001/working.bpad").write_bytes(base.replace({"report:Notes": b""}))
        with self.assertRaisesRegex(w.WorkflowError, "registered deletion"):
            w.check(self.root, "T001")

    def test_deletion_rejects_surviving_numeric_consumers(self):
        w.prepare(self.root, "T001", "Remove geometry", [], delete_names=["Geometry"])
        base = w.Journal(SAMPLE)
        (self.root / "tasks/T001/working.bpad").write_bytes(base.replace({"report:Geometry": b""}))
        with self.assertRaisesRegex(w.WorkflowError, "Deleted module Geometry still referenced"):
            w.check(self.root, "T001")

    def test_deletion_rejects_surviving_native_links(self):
        self.edit_current(b"Original notes", b'<link address="#Geometry">geometry</link>')
        w.prepare(self.root, "T001", "Remove geometry and loads", [], delete_names=["Geometry", "Loads"])
        base = w.Journal.load(self.root / w.JOURNAL)
        (self.root / "tasks/T001/working.bpad").write_bytes(base.replace({"report:Geometry": b"", "report:Loads": b""}))
        with self.assertRaisesRegex(w.WorkflowError, "New structural issues"):
            w.check(self.root, "T001")

    def test_resource_deletion_cannot_be_registered(self):
        with self.assertRaisesRegex(w.WorkflowError, "resources and styles remain protected"):
            w.prepare(self.root, "T001", "Remove resource", [], delete_names=["resource:R"])

    def test_registered_deletion_does_not_allow_other_deletions_or_reordering(self):
        w.prepare(self.root, "T001", "Remove notes", [], delete_names=["Notes"])
        base = w.Journal(SAMPLE)
        working = self.root / "tasks/T001/working.bpad"
        working.write_bytes(base.replace({"report:Notes": b"", "report:Loads": b""}))
        with self.assertRaisesRegex(w.WorkflowError, "registered deletion"):
            w.check(self.root, "T001")
        working.write_bytes(base.replace({"report:Geometry": base.part("report:Loads"), "report:Loads": base.part("report:Geometry"), "report:Notes": b""}))
        with self.assertRaisesRegex(w.WorkflowError, "reordering"):
            w.check(self.root, "T001")

    def test_deletion_retains_review_gate_and_promotes_exact_bytes(self):
        w.prepare(self.root, "T001", "Remove notes", [], delete_names=["Notes"])
        expected = w.Journal(SAMPLE).replace({"report:Notes": b""})
        (self.root / "tasks/T001/working.bpad").write_bytes(expected)
        folder = self.root / "generated/deletion-review"
        w.assemble(self.root, "T001", folder)
        with self.assertRaisesRegex(w.WorkflowError, "explicitly completed"):
            w.promote(self.root, folder)
        review = w.read_json(folder / "review.json")
        review.update(reviewer="Synthetic test only", native_recalculation=True, native_visual_review=True,
                      engineering_review=True, design_outcome="not_applicable",
                      external_analysis_disposition="No analysis in test fixture.", external_analysis_status="not_applicable",
                      inherited_issues_disposition="No inherited test issues.")
        (folder / "evidence.txt").write_text("SYNTHETIC TEST ONLY")
        review["evidence_files"] = [{"path":"evidence.txt", "sha256":w.digest((folder / "evidence.txt").read_bytes())}]
        w.write_json(folder / "review.json", review)
        w.promote(self.root, folder)
        self.assertEqual((self.root / w.JOURNAL).read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
