"""Exercise the real widget message path used by delayed browser trace deltas."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import Mock
import plotly.graph_objects as go

from pier_cap.plotly_compat import FigureWidget
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import import_fbmp_xml


def acknowledge(widget, deltas, edit_id=None):
    message = {'trace_deltas': deltas,
               'trace_edit_id': widget._last_trace_edit_id if edit_id is None else edit_id}
    before = deepcopy(message)
    widget.set_state({'_js2py_traceDeltas': message})
    return before, message


class TraceDeltaTests(unittest.TestCase):
    def setUp(self):
        self.figure = FigureWidget(go.Scatter(x=[0, 1], y=[1, 2]))
        self.addCleanup(self.figure.close)

    def replace(self):
        old_uid = self.figure.data[0].uid
        with self.figure.batch_update():
            self.figure.data = []
            self.figure.add_trace(go.Scatter(x=[0, 1], y=[3, 4]))
            self.figure.layout.title = 'Current data'
        return old_uid

    def test_removed_uid_with_latest_edit_id_is_discarded_and_acknowledged(self):
        old_uid = self.replace()
        widget = self.figure
        before = widget.to_plotly_json()
        completed = Mock()
        widget._layout_edit_in_process = False
        widget._trace_edit_in_process = True
        widget.on_edits_completed(completed)
        sent, received = acknowledge(widget, [{'uid': old_uid, 'y': [-999, -999]}])
        self.assertEqual(sent, received)
        self.assertEqual(widget.to_plotly_json(), before)
        self.assertIsNone(widget._js2py_traceDeltas)
        self.assertFalse(widget._trace_edit_in_process)
        completed.assert_called_once_with()

    def test_mixed_message_applies_current_defaults_and_callbacks_once(self):
        old_uid = self.replace()
        trace = self.figure.data[0]
        updated = Mock()
        trace.on_change(updated, 'marker.color')
        sent, received = acknowledge(self.figure, [
            {'uid': old_uid, 'marker': {'color': 'red'}},
            {'uid': trace.uid, 'marker': {'color': 'blue'}}])
        self.assertEqual(sent, received)
        self.assertEqual(trace._prop_defaults['marker']['color'], 'blue')
        self.assertEqual(tuple(trace.y), (3, 4))
        updated.assert_called_once()
        self.assertIsNone(self.figure._js2py_traceDeltas)

    def test_old_edit_remains_ignored_even_for_a_current_uid(self):
        self.replace()
        trace = self.figure.data[0]
        before = deepcopy(trace._prop_defaults)
        acknowledge(self.figure, [{'uid': trace.uid, 'marker': {'color': 'red'}}],
                    edit_id=self.figure._last_trace_edit_id-1)
        self.assertEqual(trace._prop_defaults, before)
        self.assertIsNone(self.figure._js2py_traceDeltas)

    def test_acknowledgement_during_empty_data_and_next_update_both_complete(self):
        widget = self.figure
        old_uid = widget.data[0].uid
        widget.data = []
        acknowledge(widget, [{'uid': old_uid, 'visible': False}])
        widget.add_trace(go.Scatter(x=[0], y=[8]))
        acknowledge(widget, [{'uid': widget.data[0].uid, 'marker': {'size': 7}}])
        self.assertEqual(widget.data[0]._prop_defaults['marker']['size'], 7)
        self.assertIsNone(widget._js2py_traceDeltas)

    def test_malformed_current_message_is_not_silenced(self):
        with self.assertRaises(KeyError):
            acknowledge(self.figure, [{'marker': {'size': 7}}])

    def test_normal_widget_protocol_is_preserved(self):
        plain = go.FigureWidget(go.Scatter(x=[0], y=[0]))
        self.addCleanup(plain.close)
        for name in ('_model_name', '_model_module', '_view_name', '_view_module'):
            self.assertEqual(getattr(self.figure, name), getattr(plain, name))
        handlers = self.figure._trait_notifiers['_js2py_traceDeltas']['change']
        self.assertEqual(len(handlers), 1)
        acknowledge(self.figure, [{'uid': self.figure.data[0].uid, 'marker': {'size': 9}}])
        self.assertEqual(self.figure.data[0]._prop_defaults['marker']['size'], 9)


class WorkbenchTraceDeltaTests(unittest.TestCase):
    def test_live_redraw_handles_delayed_3d_and_force_messages(self):
        root = Path(__file__).resolve().parents[1]
        app = CapNotebook(import_fbmp_xml(root/'tests/fixtures/fbmp_610_cap.xml'))
        self.addCleanup(app.close)
        cage, force = app.cage_3d_widget, app.force_diagrams.figure
        self.assertIsInstance(cage, FigureWidget)
        self.assertTrue(all(isinstance(f, FigureWidget) for f in app.figures))
        self.assertIsInstance(force, FigureWidget)
        force.layout.updatemenus[0].active = 2
        for size in (9, 10, 8):
            previous_cage = [t.uid for t in cage.data]
            previous_force = [t.uid for t in force.data]
            cage_edit=cage._last_trace_edit_id;force_edit=force._last_trace_edit_id
            app.controls['Bar_N1'].value = size
            expected_cage = cage.to_plotly_json()
            expected_force = force.to_plotly_json()
            # Reused traces keep their IDs. Their previous edit acknowledgements
            # are ignored by edit ID; removed IDs still use the stale-UID guard.
            acknowledge(cage, [{'uid': uid, 'visible': False} for uid in previous_cage],cage_edit)
            acknowledge(force, [{'uid': uid, 'visible': False} for uid in previous_force],force_edit)
            self.assertEqual(cage.to_plotly_json(), expected_cage)
            self.assertEqual(force.to_plotly_json(), expected_force)
            self.assertIs(app.cage_3d_widget, cage)
            self.assertIs(app.force_diagrams.figure, force)
            self.assertEqual(force.layout.updatemenus[0].active, 2)
            self.assertEqual(app.current.case['inputs']['Bar_N1'], size)
            self.assertIn(f'#{size}', app.cage.children[0].value)
        # A mismatch with the analyzed pile layout retires resistance traces.
        overlay_uids = [t.uid for t in force.data if (t.meta or {}).get('role')]
        app.controls['S_pile'].value += 1
        acknowledge(force, [{'uid': uid, 'visible': True} for uid in overlay_uids])
        self.assertFalse(any((t.meta or {}).get('role') for t in force.data))
