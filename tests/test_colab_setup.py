"""Exercise the notebook's actual setup against disposable local Git remotes."""
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


REPO = Path(__file__).resolve().parent.parent
NOTEBOOK = REPO / 'Pier_Cap_Design_Optimizer.ipynb'
LEGACY_API = '''class SearchConfig: pass
def search(): pass
def candidate_case(): pass
VERSION = "old"
'''
CURRENT_API = LEGACY_API + '''def filter_candidates(): pass
def candidate_dc(): pass
VERSION = "new"
'''


class ColabSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.remote = Path(self.temp.name) / 'remote'
        self.target = Path(self.temp.name) / 'D2MPDB'
        self.remote.mkdir()
        self.git(self.remote, 'init', '--initial-branch=main')
        self.git(self.remote, 'config', 'user.name', 'Setup test')
        self.git(self.remote, 'config', 'user.email', 'setup-test@example.invalid')
        package = self.remote / 'pier_cap'
        package.mkdir()
        (package / '__init__.py').write_text('', encoding='utf-8')
        (package / 'optimizer.py').write_text(LEGACY_API, encoding='utf-8')
        (self.remote / 'requirements-pier-cap-colab.txt').write_text('', encoding='utf-8')
        (self.remote / '.gitignore').write_text('exports/\n__pycache__/\n', encoding='utf-8')
        self.commit('old API')
        self.old_revision = self.git(self.remote, 'rev-parse', 'HEAD')
        notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
        self.source = ''.join(notebook['cells'][2]['source']).split('from IPython.display import display, HTML')[0]
        self.source = self.source.replace(
            'REPO_URL = "https://github.com/joshstructure/D2MPDB.git"',
            'REPO_URL = _test_url',
        ).replace('Path("/content/D2MPDB")', 'Path(_test_root)')

    @staticmethod
    def git(folder, *args):
        return subprocess.run(['git', '-C', str(folder), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, message):
        self.git(self.remote, 'add', '.')
        self.git(self.remote, 'commit', '-m', message)

    def publish_current_api(self):
        (self.remote / 'pier_cap' / 'optimizer.py').write_text(CURRENT_API, encoding='utf-8')
        self.commit('new filter API')
        return self.git(self.remote, 'rev-parse', 'HEAD')

    def clone(self):
        # Use file:// so --depth really creates a shallow checkout like Colab.
        subprocess.run(['git', 'clone', '--depth', '1', '--branch', 'main',
                        '--single-branch', self.remote.as_uri(), str(self.target)],
                       check=True, capture_output=True, text=True)

    @contextlib.contextmanager
    def colab(self):
        previous_cwd, previous_path = Path.cwd(), list(sys.path)
        real_run = subprocess.run
        pip_calls = []
        google = types.ModuleType('google')
        colab = types.ModuleType('google.colab')
        colab.output = types.SimpleNamespace(enable_custom_widget_manager=Mock())
        google.colab = colab

        def run(args, **kwargs):
            if args[:4] == [sys.executable, '-m', 'pip', 'install']:
                pip_calls.append(args)
                return subprocess.CompletedProcess(args, 0)
            return real_run(args, **kwargs)

        scope = {'_test_url': self.remote.as_uri(), '_test_root': str(self.target)}
        try:
            with patch.dict(sys.modules, {'google': google, 'google.colab': colab}), \
                 patch('subprocess.run', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
                yield scope, pip_calls
        finally:
            os.chdir(previous_cwd)
            sys.path[:] = previous_path
            importlib.invalidate_caches()

    def setup(self, scope):
        exec(compile(self.source, 'notebook-colab-setup', 'exec'), scope)

    def test_fresh_clone_and_repeat_setup(self):
        latest = self.publish_current_api()
        with self.colab() as (scope, pip_calls):
            self.setup(scope)
            self.assertTrue(scope['IN_COLAB'])
            self.assertEqual(Path.cwd(), self.target)
            self.assertEqual(scope['optimizer_module'].VERSION, 'new')
            self.setup(scope)
            self.assertEqual(self.git(self.target, 'rev-parse', 'HEAD'), latest)
            self.assertEqual(len(pip_calls), 2)
            self.assertEqual(scope['colab_output'].enable_custom_widget_manager.call_count, 2)

    def test_stale_shallow_checkout_and_cached_import_upgrade(self):
        self.clone()
        exports = self.target / 'exports' / 'selected_case.json'
        exports.parent.mkdir()
        exports.write_text('{"preserve": true}', encoding='utf-8')
        with self.colab() as (scope, _):
            with self.assertRaisesRegex(RuntimeError, 'different versions.*filter_candidates'):
                self.setup(scope)
            old_module = sys.modules['pier_cap.optimizer']
            self.assertEqual(old_module.VERSION, 'old')
            latest = self.publish_current_api()
            self.setup(scope)
            self.assertEqual(self.git(self.target, 'rev-parse', 'HEAD'), latest)
            self.assertIsNot(old_module, scope['optimizer_module'])
            self.assertEqual(scope['optimizer_module'].VERSION, 'new')
            self.assertEqual(exports.read_text(encoding='utf-8'), '{"preserve": true}')

    def test_edited_files_stop_refresh_without_overwrite(self):
        self.clone()
        edited = self.target / 'pier_cap' / 'optimizer.py'
        edited.write_text('# local work\n', encoding='utf-8')
        self.publish_current_api()
        with self.colab() as (scope, pip_calls):
            with self.assertRaisesRegex(RuntimeError, 'edited project files'):
                self.setup(scope)
            self.assertEqual(edited.read_text(encoding='utf-8'), '# local work\n')
            self.assertEqual(self.git(self.target, 'rev-parse', 'HEAD'), self.old_revision)
            self.assertEqual(pip_calls, [])

    def test_local_commits_stop_refresh_without_reset(self):
        self.clone()
        (self.target / 'local.txt').write_text('keep this work', encoding='utf-8')
        self.git(self.target, 'add', 'local.txt')
        self.git(self.target, '-c', 'user.name=Setup test', '-c',
                 'user.email=setup-test@example.invalid', 'commit', '-m', 'local work')
        local_revision = self.git(self.target, 'rev-parse', 'HEAD')
        with self.colab() as (scope, pip_calls):
            with self.assertRaisesRegex(RuntimeError, 'Could not refresh'):
                self.setup(scope)
            self.assertEqual(self.git(self.target, 'rev-parse', 'HEAD'), local_revision)
            self.assertEqual(pip_calls, [])

    def test_fetch_failure_stops_before_importing_stale_code(self):
        self.clone()
        self.git(self.target, 'remote', 'set-url', 'origin',
                 (Path(self.temp.name) / 'missing-remote').as_uri())
        with self.colab() as (scope, pip_calls):
            with self.assertRaisesRegex(RuntimeError, 'stale calculations'):
                self.setup(scope)
            self.assertNotIn('optimizer_module', scope)
            self.assertEqual(pip_calls, [])

    def test_wrong_branch_and_non_repository_are_preserved(self):
        self.clone()
        self.git(self.target, 'checkout', '-b', 'local-experiment')
        with self.colab() as (scope, _):
            with self.assertRaisesRegex(RuntimeError, 'must be on main'):
                self.setup(scope)
        ordinary_folder = Path(self.temp.name) / 'ordinary'
        ordinary_folder.mkdir()
        with self.colab() as (scope, _):
            scope['_test_root'] = str(ordinary_folder)
            with self.assertRaisesRegex(RuntimeError, 'not a Git checkout'):
                self.setup(scope)
        self.assertEqual(self.git(self.target, 'branch', '--show-current'), 'local-experiment')


if __name__ == '__main__':
    unittest.main()
