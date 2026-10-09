"""Persistent notebook views: patch changed properties without unmounting output."""
from copy import deepcopy
import ipywidgets as W
from .plotly_compat import FigureWidget


def _same(a,b):
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(_same(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
        return len(a)==len(b) and all(_same(x,y) for x,y in zip(a,b))
    try:
        result=a==b
        return bool(result.all()) if hasattr(result,'all') else bool(result)
    except (ValueError,TypeError):return False


def _changes(old,new,skip=()):
    return {k:new.get(k) for k in old.keys()|new.keys() if k not in skip and not _same(old.get(k),new.get(k))}


def update_figure(widget,fresh,*,preserve_view=True,preserve_filter=True):
    """Keep the canvas, trace IDs, zoom, camera and selected steel view.

    Ordinary edits send one batched restyle/relayout. If topology changes, only
    unmatched traces are removed/added; the output widget is never replaced.
    """
    if preserve_filter:
        for old,menu in zip(widget.layout.updatemenus,fresh.layout.updatemenus):
            active=old.active or 0
            if active<len(old.buttons):
                label=old.buttons[active].label
                match=next((i for i,b in enumerate(menu.buttons) if b.label==label),0)
                menu.active=match;button=menu.buttons[match]
                if button.method in ('update','restyle') and button.args:
                    for trace,visible in zip(fresh.data,button.args[0].get('visible',[])):trace.visible=visible
                    if button.method=='update' and len(button.args)>1:fresh.update_layout(button.args[1])
    # Preserve legend toggles by group; input changes can add/remove trace indices.
    if preserve_filter:
        hidden={t.legendgroup for t in widget.data if t.legendgroup and t.visible=='legendonly'}
        for trace in fresh.data:
            if trace.legendgroup in hidden:trace.visible='legendonly'
    new_layout=fresh.layout.to_plotly_json();old_layout=widget.layout.to_plotly_json()
    new_layout['uirevision']=old_layout.get('uirevision') or 'cap-live-view'
    if 'scene' in new_layout and old_layout.get('scene',{}).get('camera'):
        new_layout['scene']['camera']=deepcopy(old_layout['scene']['camera'])
    if preserve_view:
        for key,value in old_layout.items():
            if key.startswith(('xaxis','yaxis')) and isinstance(value,dict) and key in new_layout:
                for name in ('range','autorange'):
                    if name in value:new_layout[key][name]=deepcopy(value[name])
        fit = (new_layout.get('meta') or {}).get('cap_fit_ranges')
        if fit:
            x = new_layout['xaxis'].get('range') or fit['x']
            y = new_layout['yaxis'].get('range') or fit['y']
            # A full-length cap view must also contain its full depth. Do not
            # perpetuate a cropped vertical range from a previous live layout.
            # A user zoomed into part of the cap keeps that detailed view.
            full_length = x[0] <= fit['x'][0]+1e-8 and x[1] >= fit['x'][1]-1e-8
            if full_length and (y[0] > fit['y'][0]+1e-8 or y[1] < fit['y'][1]-1e-8):
                new_layout['yaxis'].update(range=[min(y[0],fit['y'][0]),max(y[1],fit['y'][1])],autorange=False)
    old=list(widget.data);new=list(fresh.data)
    # Complete topology changes before queuing indexed property updates. Moving
    # traces during a batch would leave its queued updates aimed at old indices.
    keep=[trace for i,trace in enumerate(old) if i<len(new) and trace.type==new[i].type]
    if len(keep)!=len(old):widget.data=keep
    ordered=[]
    for i,trace in enumerate(new):
        if i<len(old) and old[i].type==trace.type:current=old[i]
        else:widget.add_trace(trace);current=widget.data[-1]
        ordered.append(current)
    if len(ordered)!=len(widget.data) or any(a is not b for a,b in zip(ordered,widget.data)):widget.data=ordered
    with widget.batch_update():
        # Reuse a trace at its index when its Plotly type is unchanged. This also
        # keeps layout/trace acknowledgements tied to existing IDs during typing.
        for current,trace in zip(ordered,new):
            patch=_changes(current.to_plotly_json(),trace.to_plotly_json(),('uid','type'))
            if patch:current.update(patch,overwrite=True)
        for key,value in _changes(old_layout,new_layout).items():widget.layout[key]=value


class LiveViews:
    """Own view widgets and cache unchanged views independently of the case."""
    def __init__(self):self.plots={};self.texts={};self.bases={}

    def figure(self,key,factory,*,basis=None,preserve_view=True):
        if key in self.plots and basis is not None and self.bases.get(key)==basis:return self.plots[key]
        fresh=factory();fresh.layout.autosize=True
        if key not in self.plots:
            self.plots[key]=FigureWidget(fresh)
        else:update_figure(self.plots[key],fresh,preserve_view=preserve_view)
        self.bases[key]=basis
        return self.plots[key]

    def text(self,key,value):
        if key not in self.texts:self.texts[key]=W.HTML()
        self.texts[key].value=value
        return self.texts[key]

    @staticmethod
    def mount(container,children):
        children=tuple(children)
        if container.children!=children:container.children=children

    def close(self):
        for widget in [*self.plots.values(),*self.texts.values()]:widget.close()
