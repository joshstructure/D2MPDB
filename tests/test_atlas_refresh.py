"""Change detection, stable candidates, failure isolation and publication receipts."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from design_atlas import refresh as r


class RefreshTests(unittest.TestCase):
    def setUp(self):
        qa = r.build.ROOT / 'design_atlas/qa'
        qa.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=qa)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.put(r.build.REGISTRY, 'source_id,path\nTEST,source.json\nMISSING,later.xml\n')
        self.put('source.json', '{"value": 4}')
        self.put('design_atlas/site.json', '{"project_id":"atlas-test"}')
        self.put('design_atlas/adapter.py', '# adapter\n')
        for name in ('index.html', 'atlas.css', 'atlas.js', 'layouts.js'):
            self.put('design_atlas/web/' + name, (r.build.ASSETS / name).read_text(encoding='utf-8'))

    def put(self, relative, text):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')

    def fake_data(self, root):
        return {'schema_version': 1, 'generated_at': 'test capture', 'nodes': [], 'edges': [], 'values': [],
                'checks': {}, 'documents': {p: {'sha256': h} for p, h in r.inventory(root)['files'].items()}}

    def prepare(self):
        with patch.object(r.build, 'build_data', side_effect=self.fake_data), patch.object(r, 'check_browser_code'):
            return r.prepare(self.root)

    def test_unchanged_and_unrelated_changes_do_not_trigger(self):
        first = r.inventory(self.root)
        self.put('unrelated.txt', 'does not feed the atlas')
        self.put('design_atlas/.refresh/output.json', 'generated')
        self.put('design_atlas/publication.json', '{}')
        self.assertEqual(first, r.inventory(self.root))

    def test_content_changes_even_if_size_and_time_stay_same(self):
        import os
        first = r.inventory(self.root)
        stamp = (self.root / 'source.json').stat()
        self.put('source.json', '{"value": 5}')
        os.utime(self.root / 'source.json', ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertEqual(r.changed_paths(first, r.inventory(self.root)), ['source.json'])

    def test_missing_file_creation_deletion_and_register_reselection(self):
        before = r.inventory(self.root)
        self.put('later.xml', '<new/>')
        self.assertIn('later.xml', r.changed_paths(before, r.inventory(self.root)))
        (self.root / 'source.json').unlink()
        self.assertIn('source.json', r.changed_paths(before, r.inventory(self.root)))
        self.put(r.build.REGISTRY, 'source_id,path\nTEST,new-source.json\n')
        self.put('new-source.json', '{}')
        after = r.inventory(self.root)
        self.assertIn('new-source.json', after['files'])
        self.assertNotIn('source.json', after['files'])
        self.assertNotEqual(before['digest'], after['digest'])

    def test_assumptions_register_edits_trigger_refresh(self):
        before = r.inventory(self.root)
        self.assertIn(r.build.ASSUMPTIONS, before['files'])
        self.put(r.build.ASSUMPTIONS, '{"schema":"d2mpdb.assumptions-register","schema_version":1,"entries":[]}')
        self.assertEqual(r.changed_paths(before, r.inventory(self.root)), [r.build.ASSUMPTIONS])

    def test_inventory_refuses_external_or_traversal_paths(self):
        for path in ('../outside.json', 'C:/outside.json'):
            self.put(r.build.REGISTRY, 'source_id,path\nTEST,' + path + '\n')
            with self.assertRaises(ValueError): r.inventory(self.root)

    def test_same_input_reuses_exact_artifacts_without_rebuild(self):
        first = self.prepare()
        with patch.object(r.build, 'build_data', side_effect=AssertionError('must not rebuild')):
            second = r.prepare(self.root)
        self.assertEqual(first, second)
        self.assertFalse((self.root / 'design_atlas/publication.json').exists())

    def test_parser_failure_does_not_advance_last_publication(self):
        self.prepare()
        self.put('design_atlas/publication.json', '{"previous":"keep"}')
        pending = r.pending_path(self.root).read_bytes()
        self.put('source.json', 'new invalid source')
        with patch.object(r.build, 'build_data', side_effect=ValueError('malformed source')):
            with self.assertRaises(ValueError): r.prepare(self.root)
        self.assertEqual(pending, r.pending_path(self.root).read_bytes())
        self.assertEqual(r.read_json(self.root / 'design_atlas/publication.json'), {'previous': 'keep'})

    def test_compact_json_and_browser_exports_preserve_all_data(self):
        data = self.fake_data(self.root)
        data['note'] = 'Quoted "source" → <xml>\nnext line'
        output = self.root / 'export'
        r.build.write_atlas(data, output, self.root)
        raw = (output / 'atlas-data.json').read_text(encoding='utf-8')
        script = (output / 'dataset.js').read_text(encoding='utf-8')
        self.assertEqual(json.loads(raw), data)
        self.assertEqual(json.loads(script.removeprefix('window.ATLAS_DATA = ').removesuffix(';\n')), data)
        self.assertNotIn('<xml>', script)
        self.assertLess(len(raw), len(json.dumps(data, ensure_ascii=False, indent=2)))

    def test_asset_limit_accepts_boundary_and_rejects_larger_nested_file(self):
        folder = self.root / 'size-check'
        path = folder / 'downloads' / 'part.bin'
        path.parent.mkdir(parents=True)
        with path.open('wb') as handle:
            handle.truncate(r.MAX_ASSET_BYTES)
        r.check_asset_sizes(folder)
        with path.open('ab') as handle:
            handle.write(b'X')
        with self.assertRaisesRegex(RuntimeError, 'hosting limit: downloads/part.bin'):
            r.check_asset_sizes(folder)

    def test_oversized_export_keeps_previous_publication_and_candidate(self):
        self.prepare()
        self.put('design_atlas/publication.json', '{"previous":"keep"}')
        pending = r.pending_path(self.root).read_bytes()
        self.put('source.json', '{"value": 5}')
        write_atlas = r.build.write_atlas
        def oversized(data, output, root):
            write_atlas(data, output, root)
            with (output / 'atlas-data.json').open('ab') as handle:
                handle.truncate(r.MAX_ASSET_BYTES + 1)
        with patch.object(r.build, 'write_atlas', side_effect=oversized):
            with self.assertRaisesRegex(RuntimeError, 'hosting limit: atlas-data.json'):
                self.prepare()
        self.assertEqual(pending, r.pending_path(self.root).read_bytes())
        self.assertEqual(r.read_json(self.root / 'design_atlas/publication.json'), {'previous': 'keep'})

    def test_save_during_build_is_rejected(self):
        def changing(root):
            data = self.fake_data(root)
            self.put('source.json', 'concurrent save')
            return data
        with patch.object(r.build, 'build_data', side_effect=changing), patch.object(r, 'check_browser_code'):
            with self.assertRaisesRegex(RuntimeError, 'changed during'): r.prepare(self.root)
        self.assertFalse(r.pending_path(self.root).exists())

    def test_new_unwatched_adapter_read_is_rejected(self):
        def unwatched(root):
            data = self.fake_data(root)
            data['documents']['unwatched.file'] = {'sha256': '123'}
            return data
        with patch.object(r.build, 'build_data', side_effect=unwatched):
            with self.assertRaisesRegex(RuntimeError, 'Unwatched'): r.prepare(self.root)

    def test_candidate_tampering_and_stale_sources_block_stage(self):
        pending = self.prepare()
        self.put('source.json', 'edited')
        with self.assertRaisesRegex(RuntimeError, 'Sources changed'): r.verify_artifact(self.root, pending)
        self.put('source.json', '{"value": 4}')
        self.put(pending['output'] + '/dataset.js', 'tampered')
        with self.assertRaisesRegex(RuntimeError, 'modified'): r.verify_artifact(self.root, pending)

    def test_staging_requires_matching_site_and_exact_assets(self):
        pending = self.prepare()
        checkout = self.root / 'hosted'
        self.put('hosted/.openai/hosting.json', '{"project_id":"wrong","static":{"directory":"dist"}}')
        with self.assertRaises(ValueError): r.stage(self.root, checkout)
        self.put('hosted/.openai/hosting.json', '{"project_id":"atlas-test","static":{"directory":"dist"}}')
        self.assertEqual(r.stage(self.root, checkout)['status'], 'staged')
        self.assertIn('dist/** -text', (checkout / '.gitattributes').read_text())
        self.assertEqual(r.artifact_hashes(checkout / 'dist'), pending['artifacts'])
        self.put('source.json', 'another agent saved a newer source')
        self.assertEqual(r.prepare(self.root)['status'], 'publication_in_progress')
        self.assertEqual(r.read_json(r.pending_path(self.root))['inputs'], pending['inputs'])
        with self.assertRaisesRegex(RuntimeError, 'already in progress'): r.stage(self.root, checkout)
        result = {'project_id': 'atlas-test', 'id': 'deployment-test', 'version_id': 'version-test', 'status': 'pending'}
        def committed(args, **kwargs):
            if args[1] == 'rev-parse': return 'commit-test\n'
            return (checkout / args[2].split(':', 1)[1]).read_bytes()
        with patch.object(r.subprocess, 'check_output', side_effect=committed):
            with self.assertRaisesRegex(RuntimeError, 'Pushed source'):
                r.record_deployment(self.root, checkout, 'wrong-commit', result)
            self.assertEqual(r.record_deployment(self.root, checkout, 'commit-test', result)['status'], 'deployment_recorded')
        with self.assertRaisesRegex(RuntimeError, 'Reconcile'): r.stage(self.root, checkout)

    def saved_deployment(self):
        pending = self.prepare()
        result = {'project_id': 'atlas-test', 'id': 'deployment-test', 'version_id': 'version-test', 'status': 'pending', 'url': 'https://example.test'}
        pending.pop('status')
        pending.update(deployment=result, commit_sha='test-commit')
        r.write_json(r.pending_path(self.root), pending)
        return result

    def test_pending_blocks_new_build_and_nonterminal_cannot_finish(self):
        result = self.saved_deployment()
        self.put('source.json', 'changed while publishing')
        self.assertEqual(r.prepare(self.root)['status'], 'deployment_pending')
        with self.assertRaisesRegex(ValueError, 'not confirmed'): r.finish(self.root, result)

    def test_failed_publish_keeps_previous_receipt_and_allows_retry(self):
        result = self.saved_deployment()
        self.put('design_atlas/publication.json', '{"previous":"keep"}')
        result['status'] = 'failed'
        self.assertEqual(r.finish(self.root, result)['status'], 'publish_failed')
        self.assertEqual(r.read_json(self.root / 'design_atlas/publication.json'), {'previous': 'keep'})
        self.assertEqual(self.prepare()['status'], 'ready_to_publish')

    def test_only_matching_success_can_advance_receipt(self):
        result = self.saved_deployment()
        result['status'] = 'succeeded'
        wrong = {**result, 'id': 'another-deployment'}
        with self.assertRaises(ValueError): r.finish(self.root, wrong)
        self.assertEqual(r.finish(self.root, result)['status'], 'current')
        with patch.object(r.build, 'build_data', side_effect=AssertionError('no rebuild')):
            self.assertEqual(r.prepare(self.root)['status'], 'current')

    def test_changes_during_publication_remain_pending_for_next_refresh(self):
        result = self.saved_deployment()
        self.put('source.json', 'newer source')
        result['status'] = 'succeeded'
        self.assertEqual(r.finish(self.root, result)['status'], 'refresh_required')
        self.assertEqual(r.status(self.root)['changed_paths'], ['source.json'])


if __name__ == '__main__': unittest.main()
