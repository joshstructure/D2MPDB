"""Offline station report using results from the notebook's resolved geometry model."""
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

def clean(value):
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (np.integer, np.floating)):
        return clean(value.item())
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value

def compact_polygon(xy):
    """Remove only redundant collinear vertices; preserve the notebook outline."""
    p = np.asarray(xy)
    u, v = p - np.roll(p, 1, axis=0), np.roll(p, -1, axis=0) - p
    cross = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
    return p[np.abs(cross) > 1e-10]

def serialize_components(section):
    return [dict(kind=c['kind'], beam=c['beam'], xy=compact_polygon(c['xy']))
            for c in section['components']]

def coefficients(samples):
    a, m, b = np.asarray(samples, dtype=float)
    quadratic = 2 * (b - 2*m + a)
    linear = b - a - quadratic
    return np.stack([a, linear, quadratic]).tolist()

def report_data(model, section_geometry, initial_station=None):
    keys = ('pgl', 'camber', 'bottom', 'top', 'deck', 'haunch')
    pieces = []
    for span_index in range(len(model.spans)):
        cuts = model.breakpoints(span_index)
        for start, end in zip(cuts[:-1], cuts[1:]):
            stations = [float(start), float((start+end)/2), float(end)]
            evaluation = model.evaluate(stations, span_index)
            sections = []
            for station in stations:
                section = serialize_components(section_geometry(model, station)[0])
                sections.append([c for c in section if c['kind'] in ('Deck','Beam','Haunch')])
            mid = sections[1]
            for group in sections:
                assert len(group) == len(mid)
                for c, reference in zip(group, mid):
                    assert (c['kind'], c['beam']) == (reference['kind'], reference['beam'])
                    np.testing.assert_allclose(c['xy'][:,0], reference['xy'][:,0], atol=1e-10)
            pieces.append(dict(start=start, end=end, span=int(model.spans.iloc[span_index]['id']),
                fields={k: coefficients(evaluation[k]) for k in keys},
                components=[dict(kind=c['kind'],beam=c['beam'],x=c['xy'][:,0],
                    y=coefficients([s[i]['xy'][:,1] for s in sections])) for i,c in enumerate(mid)]))
    supports = []
    for support in sorted(model.supports, key=lambda s:s['station']):
        sections = section_geometry(model,support['station'])
        assert len(sections) == 1, 'This report requires a separate view for unequal support faces.'
        supports.append(dict(name=support['name'], station=support['station'],
            components=serialize_components(sections[0]),
            width=support['width'], top=support['top'], depth=support['depth'],
            length=support['length'], center=support['center'], slope=support['slope'],
            seats=support['seats'].to_dict('records'), piles=support['pile_elevations'].to_dict('records')))
    data = dict(version=1, source='Bridge_Geometry_2 Beam_V2.ipynb',
        generated_utc=datetime.now(timezone.utc).isoformat(),
        model_id=model.model_id, profile=model.profile_mode, deck_mode=model.deck_mode,
        start=model.start,end=model.end,offsets=model.offsets,depth=model.depth,flange=model.flange,
        deck_width=model.deck_width,deck_thickness=model.deck_thickness,
        pieces=pieces, road=model.road, supports=supports, spans=model.spans.to_dict('records'),
        minimum_clearance=model.clearance_details(),minimum_haunch=dict(value=model.haunch_min*12,station=model.haunch_station),
        required_clearance=model.clearance_required,required_haunch=model.minimum_haunch*12)

    data['initial_station'] = float(initial_station if initial_station is not None else model.pier.get('station', model.start))
    if not model.start <= data['initial_station'] <= model.end:
        raise ValueError('Initial report station is outside the bridge.')
    return clean(data)


def render_report(model, section_geometry, initial_station=None, assets=None):
    if assets is None:
        folder=Path(__file__).resolve().parent
        assets={name:(folder/name).read_text(encoding='utf-8') for name in
            ('report.template.html','report-engine.js','report-ui.js','report-document.html','d3.min.js')}
    data=report_data(model,section_geometry,initial_station)
    # Escape script-end sequences when embedding JSON in the document.
    payload=json.dumps(data,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    fragment=assets['report.template.html'].replace('__BRIDGE_DATA__',payload)
    fragment=fragment.replace('/*__ENGINE__*/',assets['report-engine.js']).replace('/*__UI__*/',assets['report-ui.js'])
    external='<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>'
    fragment=fragment.replace(external,'<script>'+assets['d3.min.js']+'</script>')
    return assets['report-document.html'].replace('__FRAGMENT__',fragment)


def export_interactive_report(model=None, path=None, station=None):
    """Export current applied dashboard results; reject unapplied CONFIG edits."""
    if model is None:
        active=globals().get('dashboard')
        if active and isinstance(active,dict):
            model=active['state']['model']
            if station is None: station=active['station'].value
        else:
            model=globals().get('MODEL')
        if model is None:
            raise RuntimeError('Run the geometry model before exporting a report.')
        if configuration_id(CONFIG)!=model.model_id:
            raise ValueError('Inputs changed. Click Apply input changes, then export the report again.')
    target=Path(path or f'Bridge_Geometry_Interactive_Report_{model.model_id}.html')
    text=render_report(model,section_geometry,station,assets=globals().get('_BRIDGE_REPORT_ASSETS'))
    target.write_text(text,encoding='utf-8')
    return target


def show_interactive_report_export():
    """One button for local Jupyter and Colab, with a durable HTML download."""
    import ipywidgets as W
    from IPython.display import HTML, FileLink, display
    button=W.Button(description='Export interactive report',icon='download',button_style='primary',
                    layout=W.Layout(width='auto'))
    output=W.Output()
    def download(_):
        button.disabled=True
        with output:
            output.clear_output(wait=True)
            try:
                path=export_interactive_report()
                print(f'Exported {path.name}. Open the HTML file to move stations and inspect plots offline.')
                try:
                    from google.colab import files
                except ImportError:
                    display(FileLink(str(path)))
                else:
                    files.download(str(path))
            except Exception as error:
                print(f'Report not exported: {error}')
            finally:
                button.disabled=False
    button.on_click(download)
    display(W.VBox([button,output]))
    return dict(button=button,output=output)
