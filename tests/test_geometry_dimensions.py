"""Dimension traces, tables and live updates share the current cap geometry."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from pier_cap.fbmp import import_fbmp_xml
from pier_cap.model import evaluate,set_inputs
from pier_cap.geometry_dimensions import geometry_dimensions,dimensions_figure,dimensions_html
from pier_cap.widgets import CapNotebook
from pier_cap.io import export_bundle
from tests.test_fbmp import FIXTURE


class GeometryDimensionTests(unittest.TestCase):
    def setUp(self):
        self.case=import_fbmp_xml(FIXTURE)

    def test_exact_dimensions_and_stations_match_geometry(self):
        e=evaluate(self.case);before=deepcopy(e.case)
        data=geometry_dimensions(e);values=data['values']
        self.assertAlmostEqual(values['length']['feet'],19.24)
        self.assertAlmostEqual(values['left_center']['inches'],25.44)
        self.assertAlmostEqual(values['right_center']['inches'],25.44)
        self.assertAlmostEqual(values['left_clear']['inches'],15.44)
        self.assertAlmostEqual(values['right_clear']['inches'],15.44)
        self.assertEqual(values['center_spacing']['inches'],60)
        self.assertEqual(values['clear_spacing']['inches'],40)
        self.assertEqual(values['width']['inches'],48)
        self.assertEqual(values['depth']['inches'],36)
        figure=dimensions_figure(e)
        traces={t.meta['dimension']:t for t in figure.data if t.meta}
        for key in ('length','left_clear','right_clear','pile_width','embedment'):
            self.assertAlmostEqual(traces[key].meta['inches'],values[key]['inches'])
            self.assertIn('ft = ',traces[key].customdata[0])
            self.assertIn('hovertemplate',traces[key].to_plotly_json())
        self.assertIn('15.44',dimensions_html(e))
        self.assertEqual(e.case,before)

    def test_live_dimensions_and_resistances_update_from_current_controls(self):
        app=CapNotebook(self.case)
        self.addCleanup(app.close)
        self.assertEqual(app.plot_tabs.get_title(5),'Dimensions')
        app.force_diagrams.show_resistance.value=True
        fig=app.force_diagrams.figure
        old=next(t.y for t in fig.data if (t.meta or {}).get('capacity')=='Mr_N')
        app.controls['Bar_N1'].value=11
        self.assertNotEqual(next(t.y for t in fig.data if (t.meta or {}).get('capacity')=='Mr_N'),old)
        app.controls['S_pile'].value=6
        app.controls['h'].value=42
        figure=app.dimensions.children[0]
        length=next(t for t in figure.data if (t.meta or {}).get('dimension')=='length')
        self.assertAlmostEqual(length.meta['feet'],22.24)
        self.assertIn('22.24',app.dimensions.children[1].value)
        self.assertIn('differ from analyzed',app.dimensions.children[1].value)
        self.assertIn('UNAVAILABLE',app.force_diagrams.resistance_notice.value)
        app.controls['b'].value=0
        self.assertEqual(app.dimensions.children,())

    def test_exports_include_current_dimensions_and_resistance_basis(self):
        case=set_inputs(self.case,n_B1=2,Bar_N1=9)
        with tempfile.TemporaryDirectory() as folder:
            path=export_bundle(case,folder)
            dimensions=(path/'geometry_dimensions.html').read_text(encoding='utf-8')
            self.assertIn('Current cap dimensions',dimensions)
            self.assertIn('15.44',dimensions)
            forces=(path/'force_diagrams.html').read_text(encoding='utf-8')
            self.assertIn('resistance',forces)
            self.assertIn('not a torsional resistance',forces)
            report=(path/'calculation_report.html').read_text(encoding='utf-8')
            self.assertIn('Current cap dimensions',report)
            self.assertIn('Strength overlays are hidden for service',report)
