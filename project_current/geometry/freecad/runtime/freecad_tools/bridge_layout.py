"""Physical bearing layout around the notebook's PGL and deck calculations."""
import copy
from . import bridge_notebook_engine as notebook

if not hasattr(notebook.np,'trapezoid'):
    notebook.np.trapezoid=notebook.np.trapz

class PhysicalBridgeModel(notebook.BridgeModel):
    """Keep notebook logic; anchor quadratic camber to physical bearing CLs.

    User confirmed profile end stations are front faces of backwalls. Journal
    beam-end clearance is 3 in, bearing setback 9 in and pier beam gap 3 in.
    The notebook's contiguous spans still partition the deck and PGL.
    """
    def __init__(self,config,beam_end_clear_ft=.25,bearing_setback_ft=.75,pier_gap_ft=.25):
        p=config['profile']; a=p['start_sta_ft']; b=p['end_sta_ft']; c=p['intersection_sta_ft']
        self.beam_limits=[(a+beam_end_clear_ft,c-pier_gap_ft/2),(c+pier_gap_ft/2,b-beam_end_clear_ft)]
        self.bearing_limits=[(s+bearing_setback_ft,e-bearing_setback_ft) for s,e in self.beam_limits]
        super().__init__(copy.deepcopy(config))

    def span_components(self,stations,span_index=None):
        # Retain notebook's station validation and unambiguous span selection.
        index,_,_=super().span_components(stations,span_index)
        s=notebook.np.atleast_1d(notebook.np.asarray(stations,dtype=float))
        a=notebook.np.array([self.bearing_limits[i][0] for i in index])
        b=notebook.np.array([self.bearing_limits[i][1] for i in index])
        t=(s-a)/(b-a)
        chord=self.pgl(a)+(self.pgl(b)-self.pgl(a))*t
        camber=4*self.spans.camber_in.to_numpy()[index]/12*t*(1-t)
        return index,chord,camber

    def breakpoints(self,span_index):
        points=super().breakpoints(span_index)
        a,b=self.bearing_limits[span_index]
        return notebook.np.unique(notebook.np.r_[points,a,(a+b)/2,b])

    def quantities(self):
        # Notebook Simpson integration is exact for these quadratic surfaces.
        # Its full-span shortcut assumes zero camber at deck limits, which is
        # no longer the physical bearing layout; visibly remove that shortcut.
        table=super().quantities()
        table['Analytical difference (ft3)']=notebook.np.nan
        return table
