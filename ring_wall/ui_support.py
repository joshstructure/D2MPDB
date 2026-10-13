"""Small notebook compatibility helpers, following the cap workbench controls."""
from copy import deepcopy
from html import escape

import ipywidgets as W
import plotly.graph_objects as go
from traitlets import Int, List, TraitError, Unicode, observe, validate


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


if 'titles' in W.Accordion.class_traits():
    Accordion = W.Accordion
else:
    class Accordion(_LegacyTitles, W.Accordion):
        titles = List(Unicode()).tag(sync=True)


class PanelTabs(W.VBox):
    """Button navigation that mounts one page, without Colab's TabView.

    Plain button clicks switch the VBox children in Python. This avoids the
    mixed widget-manager selection protocol and hidden Plotly page views.
    """
    selected_index = Int(0)

    def __init__(self, panels, titles):
        if not panels or len(panels) != len(titles):
            raise ValueError('Each panel needs a title.')
        self.panels = tuple(panels)
        self.titles = tuple(titles)
        self.buttons = tuple(W.Button(description=title, tooltip='Show '+title,
                                      layout=W.Layout(width='auto', min_width='110px', height='34px'))
                             for title in titles)
        self.page_title = W.HTML()
        self.content = W.VBox(layout=W.Layout(width='100%', min_width='0'))
        navigation = W.HBox(self.buttons, layout=W.Layout(flex_flow='row wrap', grid_gap='4px'))
        navigation.add_class('ring-panel-nav')
        for index, button in enumerate(self.buttons):
            button.on_click(lambda _, i=index: self.select(i))
        super().__init__([navigation, self.page_title, self.content],
                         layout=W.Layout(width='100%', min_width='0', flex='0 0 auto'))
        self.observe(self._selected, names='selected_index')
        self._show()

    @validate('selected_index')
    def _valid_selection(self, proposal):
        if not 0 <= proposal['value'] < len(self.panels):
            raise TraitError('Panel index out of bounds.')
        return proposal['value']

    def select(self, index):
        if index == self.selected_index:
            self._show()
        else:
            self.selected_index = index

    def _selected(self, _):
        self._show()

    def _show(self):
        panel = self.panels[self.selected_index]
        # Snapshot before the new view mounts, including Plotly 6/anywidget.
        def prepare(widget):
            if isinstance(widget, FigureWidget):
                widget.prepare_display()
            for child in getattr(widget, 'children', ()):
                prepare(child)
        prepare(panel)
        self.content.children = (panel,)
        self.page_title.value = '<h3 style="margin:8px 0 2px">'+escape(self.titles[self.selected_index])+'</h3>'
        for i, button in enumerate(self.buttons):
            button.button_style = 'info' if i == self.selected_index else ''


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
