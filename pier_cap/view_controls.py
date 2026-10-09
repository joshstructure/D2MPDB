"""Steel visibility shared by drawings and the 3D cage."""

VIEWS = [('All steel', {'cap', 'piles', 'top', 'bottom', 'side', 'added', 'transverse', 'clearance'}),
         ('Longitudinal', {'cap', 'piles', 'top', 'bottom', 'side', 'added', 'clearance'}),
         ('Hoops + U-bars', {'cap', 'piles', 'transverse'}),
         ('Piles only', {'piles'})]


def bar_family(bar):
    return ('added' if bar.get('additional') else 'side' if bar['kind'] == 'Skin'
            else 'top' if bar['kind'].startswith('Top') else 'bottom')


def visibility_buttons(fig, *, drawing=False):
    """Build fresh, explicit masks; drawings also hide associated shapes/notes."""
    parts = [(t.meta or {}).get('part', 'cap') for t in fig.data]
    buttons = []
    for label, shown in VIEWS:
        traces = {'visible': [part in shown for part in parts]}
        if drawing:
            layout = {}
            for collection in ('shapes', 'annotations'):
                for i, item in enumerate(getattr(fig.layout, collection)):
                    part = item.name.removeprefix('part:') if item.name and item.name.startswith('part:') else 'cap'
                    layout[f'{collection}[{i}].visible'] = part in shown
            buttons.append(dict(label=label, method='update', args=[traces, layout, list(range(len(parts)))]))
        else:
            buttons.append(dict(label=label, method='restyle', args=[traces, list(range(len(parts)))]))
    return buttons


def drawing_controls(fig, *, zone_case=None, fit_cap=False):
    # Pixel offset keeps the controls clear of titles and engineering annotations
    # even in the narrow live-cage column. Finalize the margins BEFORE allocating
    # dimension bands, so their fractions describe the actual drawable height.
    old_top = fig.layout.margin.t or 0
    fig.layout.margin.t = max(old_top, 170)
    fig.layout.height += fig.layout.margin.t - old_top if fit_cap else 80
    if fit_cap:fig.layout.title.update(y=1, yanchor='top', pad=dict(t=12))
    else:fig.layout.title.update(y=.98, yanchor='top')
    if zone_case is not None:
        from .zone_visuals import add_zone_dimensions
        add_zone_dimensions(fig, zone_case)
    fig.update_layout(updatemenus=[dict(type='buttons', direction='right', active=0,
        x=0, y=1, xanchor='left', yanchor='bottom', pad=dict(b=76),
        buttons=visibility_buttons(fig, drawing=True), font=dict(size=10))],
        legend_groupclick='togglegroup')
    if fit_cap:
        # Keep a geometry-derived home view, independent of ranges returned by
        # the browser after a resize/zoom or a change in dimension-band height.
        ranges = dict(x=list(fig.layout.xaxis.range), y=list(fig.layout.yaxis.range))
        fig.update_layout(meta=dict(cap_fit_ranges=ranges))
        reset = {}
        for key in ('xaxis', 'xaxis2', 'xaxis3'):
            if key in fig.layout.to_plotly_json():
                reset[key+'.range'] = ranges['x']
                reset[key+'.autorange'] = False
        reset.update({'yaxis.range': ranges['y'], 'yaxis.autorange': False})
        fig.layout.updatemenus += (dict(type='buttons', showactive=False,
            x=1, y=1, xanchor='right', yanchor='bottom', pad=dict(b=76),
            buttons=[dict(label='Fit cap', method='relayout', args=[reset])],
            font=dict(size=10)),)
    return fig
