"""Keep delayed browser acknowledgements from targeting removed chart traces."""
import plotly.graph_objects as go
from traitlets import observe


class FigureWidget(go.FigureWidget):
    """Plotly widget that tolerates obsolete trace defaults after a redraw.

    A persistent widget can receive a browser delta containing a deleted UID,
    even with the latest edit ID, while delete/add/update messages are in
    flight. Plotly otherwise looks up that UID without checking membership.
    Only those removed traces are filtered; the parent still applies current
    defaults, dispatches callbacks and completes its edit acknowledgement.
    """

    @observe('_js2py_traceDeltas')
    def _handler_js2py_traceDeltas(self, change):
        message = change['new']
        if message and message['trace_edit_id'] == self._last_trace_edit_id:
            current_uids = {trace.uid for trace in self.data}
            deltas = message['trace_deltas']
            current = [delta for delta in deltas if delta['uid'] in current_uids]
            if len(current) != len(deltas):
                change = dict(change, new=dict(message, trace_deltas=current))
        return super()._handler_js2py_traceDeltas(change)
