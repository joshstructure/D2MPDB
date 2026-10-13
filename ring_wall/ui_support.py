"""Small notebook compatibility helpers, following the cap workbench controls."""
from copy import deepcopy

import ipywidgets as W
import plotly.graph_objects as go
from traitlets import List, Unicode, observe


class FigureWidget(go.FigureWidget):
    """Keep Plotly 5/6 snapshots and delayed browser acknowledgements safe."""

    def prepare_display(self):
        if '_widget_data' in self.traits():
            self._widget_data = deepcopy(self._data)
            self._widget_layout = deepcopy(self._layout_obj._props)

    @observe('_js2py_traceDeltas')
    def _handler_js2py_traceDeltas(self, change):
        message = change['new']
        if message and message['trace_edit_id'] == self._last_trace_edit_id:
            uids = {trace.uid for trace in self.data}
            current = [d for d in message['trace_deltas'] if d['uid'] in uids]
            if len(current) != len(message['trace_deltas']):
                change = dict(change, new=dict(message, trace_deltas=current))
        return super()._handler_js2py_traceDeltas(change)


class _LegacyTitles:
    def set_title(self, index, title):
        super().set_title(index, title)
        self.titles = [self.get_title(i) or '' for i in range(len(self.children))]


if 'titles' in W.Tab.class_traits():
    Tab, Accordion = W.Tab, W.Accordion
else:
    class Tab(_LegacyTitles, W.Tab):
        titles = List(Unicode()).tag(sync=True)

    class Accordion(_LegacyTitles, W.Accordion):
        titles = List(Unicode()).tag(sync=True)


def update_figure(widget, fresh):
    """Update fixed traces in place, retaining the canvas and the user's zoom."""
    if len(widget.data) != len(fresh.data):
        raise ValueError('Live figure trace count changed unexpectedly.')
    with widget.batch_update():
        for current, new in zip(widget.data, fresh.data):
            props = new.to_plotly_json()
            props.pop('type', None)
            current.update(props, overwrite=True)
        widget.update_layout(fresh.layout.to_plotly_json(), overwrite=True)
    widget.prepare_display()
