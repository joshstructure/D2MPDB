"""Exercise the notebook's actual guard against Colab's preloaded widgets."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class ColabStartupTests(unittest.TestCase):
    def run_widget_setup(self, loaded, installed, plot_loaded='5.24.1', plot_installed='5.24.1'):
        notebook = json.loads((Path(__file__).resolve().parent.parent /
                               'Pier_Cap_Design_Optimizer.ipynb').read_text(encoding='utf-8'))
        tree = ast.parse(''.join(notebook['cells'][2]['source']))
        colab = next(node for node in tree.body if isinstance(node, ast.If)
                     and isinstance(node.test, ast.Name) and node.test.id == 'IN_COLAB')
        start = next(i for i, node in enumerate(colab.body)
                     if isinstance(node, ast.Import) and node.names[0].name == 'ipywidgets')
        end = next(i for i, node in enumerate(colab.body) if isinstance(node, ast.Expr)
                   and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                   and node.value.func.attr == 'enable_custom_widget_manager')
        guard = ast.Module(body=colab.body[start:end + 1], type_ignores=[])
        calls = []
        kernel = object()
        context = {'colab_output': SimpleNamespace(enable_custom_widget_manager=lambda: calls.append('manager')),
                   'get_ipython': lambda: SimpleNamespace(kernel=kernel)}
        runtime = SimpleNamespace(__version__=loaded, register_comm_target=lambda k: calls.append(k))
        with patch.dict('sys.modules', {'ipywidgets': runtime, 'plotly': SimpleNamespace(__version__=plot_loaded)}), \
                patch('importlib.metadata.version', side_effect=lambda name: installed if name=='ipywidgets' else plot_installed):
            exec(compile(guard, '<notebook widget setup>', 'exec'), context)
        return ['handlers' if value is kernel else value for value in calls]

    def test_stale_eight_cannot_create_silent_dead_controls(self):
        with self.assertRaisesRegex(RuntimeError, 'Restart session'):
            self.run_widget_setup('8.1.9', '7.7.1')

    def test_loaded_version_must_match_the_installed_package(self):
        with self.assertRaisesRegex(RuntimeError, 'restart required'):
            self.run_widget_setup('7.7.1', '8.1.9')
        self.assertEqual(self.run_widget_setup('7.7.1', '7.7.1'), ['handlers', 'manager'])

    def test_an_unsupported_major_cannot_pass_even_if_versions_match(self):
        with self.assertRaises(RuntimeError):
            self.run_widget_setup('8.1.9', '8.1.9')

    def test_stale_or_unsupported_plotly_stops_before_controls(self):
        for loaded, installed in [('6.6.0','5.24.1'),('5.24.1','6.6.0'),('6.6.0','6.6.0')]:
            with self.subTest(loaded=loaded, installed=installed), self.assertRaisesRegex(RuntimeError,'Chart session restart'):
                self.run_widget_setup('7.7.1','7.7.1',loaded,installed)

