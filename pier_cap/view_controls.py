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


def drawing_controls(fig):
    # Pixel offset keeps the controls clear of titles and engineering annotations
    # even in the narrow live-cage column. Reserve room below the legend.
    fig.update_layout(updatemenus=[dict(type='buttons', direction='right', active=0,
        x=0, y=1, xanchor='left', yanchor='bottom', pad=dict(b=76),
        buttons=visibility_buttons(fig, drawing=True), font=dict(size=10))],
        legend_groupclick='togglegroup')
    fig.layout.margin.t = max(fig.layout.margin.t or 0, 170)
    fig.layout.height += 80
    fig.layout.title.update(y=.98, yanchor='top')
    return fig
