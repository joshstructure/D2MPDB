"""Full-cap drawings recover cropped live ranges without discarding detail zoom."""
import unittest
from copy import deepcopy
from pier_cap.widgets import CapNotebook
from pier_cap.model import evaluate
from pier_cap.visuals import elevation_figure,reinforcement_plan_figure
from tests.test_transverse_zones import zoned_case


class ProjectionViewportTests(unittest.TestCase):
    def test_full_length_live_views_recover_a_clipped_cap_top(self):
        app=CapNotebook(zoned_case());self.addCleanup(app.close)
        figures={key:app.views.plots[key] for key in ('plan','elevation')}
        for figure in figures.values():
            # The returned browser range no longer contains the cap top.
            figure.layout.yaxis.range=[-22,30]
        app.transverse_panel.zone_controls['R4']['pitch'].value=6
        for key,figure in figures.items():
            self.assertIs(app.views.plots[key],figure)
            fit=figure.layout.meta['cap_fit_ranges']
            self.assertLessEqual(figure.layout.yaxis.range[0],fit['y'][0])
            self.assertGreaterEqual(figure.layout.yaxis.range[1],fit['y'][1])

    def test_zoom_into_part_of_the_cap_survives_steel_edits(self):
        app=CapNotebook(zoned_case());self.addCleanup(app.close)
        for key in ('plan','elevation'):
            app.views.plots[key].layout.xaxis.range=[2,10]
            app.views.plots[key].layout.yaxis.range=[10,30]
        app.transverse_panel.zone_controls['R4']['pitch'].value=6
        for key in ('plan','elevation'):
            figure=app.views.plots[key]
            self.assertEqual(tuple(figure.layout.xaxis.range),(2,10))
            self.assertEqual(tuple(figure.layout.yaxis.range),(10,30))

    def test_fit_cap_uses_current_geometry_and_all_aligned_station_axes(self):
        app=CapNotebook(zoned_case());self.addCleanup(app.close)
        app.controls['h'].value=72;app.controls['b'].value=60
        for key,top in [('plan',60),('elevation',72)]:
            figure=app.views.plots[key]
            button=next(b for m in figure.layout.updatemenus for b in m.buttons if b.label=='Fit cap')
            reset=button.args[0]
            self.assertGreater(reset['yaxis.range'][1],top)
            for axis in ('xaxis2','xaxis3'):
                self.assertEqual(reset[axis+'.range'],reset['xaxis.range'])
            # Apply exactly the relayout payload used by the browser button.
            figure.layout.xaxis.range=[2,10];figure.layout.yaxis.range=[10,30]
            figure.update_layout(reset)
            self.assertGreater(figure.layout.yaxis.range[1],top)
            self.assertEqual(list(figure.layout.xaxis.range),list(figure.layout.xaxis3.range))

    def test_more_dimension_lanes_do_not_steal_drawing_height(self):
        case=zoned_case();crowded=deepcopy(case)
        for i in range(8):
            run=deepcopy(case['transverse_detail']['runs'][1]);run['id']='Extra'+str(i)
            crowded['transverse_detail']['runs'].append(run)
        for factory in (elevation_figure,reinforcement_plan_figure):
            baseline=factory(evaluate(case),zone_labels=False)
            drawing_height=baseline.layout.height-baseline.layout.margin.t-baseline.layout.margin.b
            for current in (case,crowded):
                figure=factory(evaluate(current))
                available=figure.layout.height-figure.layout.margin.t-figure.layout.margin.b
                domain=figure.layout.yaxis.domain
                self.assertAlmostEqual(available*(domain[1]-domain[0]),drawing_height)
                self.assertEqual(figure.layout.yaxis.range,baseline.layout.yaxis.range)


if __name__=='__main__':unittest.main()
