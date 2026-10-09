"""Stable widget mounting, current data and view-state retention during edits."""
from copy import deepcopy
import unittest
from unittest.mock import patch,Mock
import plotly.graph_objects as go
from pier_cap.live_views import update_figure
from pier_cap.plotly_compat import FigureWidget
from pier_cap.widgets import CapNotebook
from tests.test_transverse_zones import zoned_case
from tests.case_fixtures import import_fbmp_xml


class FigurePatchTests(unittest.TestCase):
    def test_nested_display_snapshot_matches_edits_made_before_display(self):
        figure=FigureWidget(go.Figure([go.Scatter(x=[0]),go.Bar(x=[1])]))
        self.addCleanup(figure.close)
        update_figure(figure,go.Figure([go.Bar(x=[2]),go.Scatter(x=[3]),go.Scatter(x=[4])]))
        figure.prepare_display()
        if '_widget_data' in figure.traits():
            self.assertEqual(figure._widget_data,figure.to_plotly_json()['data'])
            self.assertEqual(figure._widget_layout,figure.to_plotly_json()['layout'])

    def test_ordinary_edit_batches_changed_data_without_removing_traces(self):
        figure=FigureWidget(go.Figure(go.Scatter(x=[0,1],y=[1,2],line=dict(color='blue',dash='dash'))))
        self.addCleanup(figure.close);uid=figure.data[0].uid
        fresh=go.Figure(go.Scatter(x=[0,1],y=[2,3],line=dict(color='red')))
        with patch.object(figure,'_send_deleteTraces_msg') as delete,patch.object(figure,'_send_addTraces_msg') as add,patch.object(figure,'_send_update_msg',wraps=figure._send_update_msg) as update:
            update_figure(figure,fresh)
            delete.assert_not_called();add.assert_not_called();update.assert_called_once()
        self.assertEqual(figure.data[0].uid,uid);self.assertEqual(tuple(figure.data[0].y),(2,3))
        self.assertIsNone(figure.data[0].line.dash)

    def test_mixed_trace_types_and_shorter_layout_remove_obsolete_properties(self):
        figure=FigureWidget(go.Figure([go.Scatter(x=[1]),go.Bar(x=[2]),go.Scatter(x=[3])],layout=dict(annotations=[dict(text='one'),dict(text='two')])))
        self.addCleanup(figure.close);uid=figure.data[0].uid
        fresh=go.Figure([go.Scatter(x=[4]),go.Scatter(x=[5])],layout=dict(annotations=[dict(text='new')]))
        update_figure(figure,fresh)
        self.assertEqual([t.type for t in figure.data],['scatter','scatter'])
        self.assertEqual([tuple(t.x) for t in figure.data],[(4,),(5,)])
        self.assertEqual(figure.data[0].uid,uid);self.assertEqual(len(figure.layout.annotations),1)


class LiveViewTests(unittest.TestCase):
    def setUp(self):
        self.app=CapNotebook(zoned_case());self.addCleanup(self.app.close)

    def test_size_pitch_and_location_edits_keep_mounted_views_cards_and_camera(self):
        app=self.app;panel=app.transverse_panel
        cards=dict(panel._cards);children=tuple(app.cage.children);models={k:w.model_id for k,w in app.views.plots.items()}
        changes=Mock();app.cage.observe(changes,names='children');panel.zone_grid.observe(changes,names='children')
        camera=dict(eye=dict(x=2,y=-1,z=.7));app.cage_3d_widget.layout.scene.camera=camera
        elevation=app.views.plots['elevation'];elevation.layout.xaxis.range=[2,10]
        elevation.layout.updatemenus[0].active=2;app.cage_3d_widget.layout.updatemenus[0].active=2
        card=panel.zone_controls['R4'];card['details'].selected_index=0
        for key,value in [('bar',6),('pitch',6),('first_in',card['first_in'].value+.25)]:
            card[key].value=value
            self.assertNotIn('Not applied',panel.status.value)
            self.assertEqual(app.cage.children,children);self.assertEqual({k:w.model_id for k,w in app.views.plots.items()},models)
            self.assertTrue(all(panel._cards[k] is v for k,v in cards.items()))
            self.assertEqual(app.cage_3d_widget.layout.scene.camera.to_plotly_json(),camera)
            self.assertEqual(tuple(elevation.layout.xaxis.range),(2,10))
            for figure in (elevation,app.cage_3d_widget):
                self.assertEqual(figure.layout.updatemenus[0].active,2)
                for trace,visible in zip(figure.data,figure.layout.updatemenus[0].buttons[2].args[0]['visible']):
                    self.assertEqual(trace.visible,visible)
            self.assertEqual(card['details'].selected_index,0)
        changes.assert_not_called()

    def test_select_run_updates_only_sections_without_recalculating_case(self):
        app=self.app;before=deepcopy(app.case);cage=app.cage_3d_widget.to_plotly_json()
        with patch('pier_cap.widgets.evaluate',side_effect=AssertionError('Unneeded recalculation')):
            app.transverse_panel.zone_controls['R4']['view'].click()
        self.assertEqual(app.case,before);self.assertEqual(app.cage_3d_widget.to_plotly_json(),cage)
        self.assertEqual(app.transverse_panel.selected_run_id,'R4')
        self.assertTrue(any(t.legendgroup=='R4' for t in app.views.plots['sectionP'].data))

    def test_hidden_tabs_render_latest_case_on_entry_and_remain_mounted(self):
        app=self.app;self.assertNotIn('results',app.views.plots);self.assertNotIn('dimensions',app.views.plots)
        app.plot_tabs.selected_index=1;results=app.results.children;old=app.views.plots['results'].to_plotly_json()
        app.plot_tabs.selected_index=0;app.controls['Mu_N'].value+=100
        self.assertEqual(app.views.plots['results'].to_plotly_json(),old)
        app.plot_tabs.selected_index=1
        self.assertEqual(app.results.children,results);self.assertNotEqual(app.views.plots['results'].to_plotly_json(),old)
        app.controls['h'].value=42;app.plot_tabs.selected_index=5
        depth=next(t for t in app.views.plots['dimensions'].data if (t.meta or {}).get('dimension')=='section_depth')
        self.assertEqual(depth.meta['inches'],42)
        app.plot_tabs.selected_index=0;app.controls['Pile_embed'].value=8;app.plot_tabs.selected_index=5
        embed=next(t for t in app.views.plots['dimensions'].data if (t.meta or {}).get('dimension')=='embedment')
        self.assertEqual(embed.meta['inches'],8)

    def test_unchanged_force_and_resistance_inputs_do_not_redraw_after_case_deepcopy(self):
        app=self.app;app.load(import_fbmp_xml('tests/fixtures/fbmp_610_cap.xml'))
        with patch('pier_cap.force_diagrams.cap_force_figure',side_effect=AssertionError('Unchanged force/resistance inputs')):
            app.force_diagrams.refresh(deepcopy(app.case),evaluation=app.current)

    def test_auxiliary_views_remount_after_invalid_input_restores_same_case(self):
        app=self.app
        for index,container in ((1,app.results),(5,app.dimensions)):
            app.plot_tabs.selected_index=index;children=container.children
            width=app.controls['b'].value
            app.controls['b'].value=0
            self.assertIsNone(app.current);self.assertFalse(container.children)
            app.controls['b'].value=width
            self.assertIsNotNone(app.current);self.assertEqual(container.children,children)


if __name__=='__main__':unittest.main()
