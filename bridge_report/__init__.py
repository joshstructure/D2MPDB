"""Offline station report using results from the notebook's resolved geometry model."""
import base64
import hashlib
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
    if not getattr(model,'physical',False) or getattr(model,'geometry_version',None)!='physical-station-cuts-2':
        raise ValueError('The applied model has older station-only support geometry. Reopen the updated notebook and Run all before exporting.')
    keys = ('pgl', 'camber', 'bottom', 'top', 'deck', 'haunch')
    pieces = []
    for span_index in range(len(model.spans)):
        cuts = model.breakpoints(span_index)
        for start, end in zip(cuts[:-1], cuts[1:]):
            stations = [float(start), float((start+end)/2), float(end)]
            evaluation = model.evaluate(stations, span_index)
            sections = []
            for station in stations:
                section = serialize_components(section_geometry(model, station, span_index=span_index,
                    include_supports=False, include_absent=True)[0]) if model.physical else serialize_components(section_geometry(model,station)[0])
                sections.append([c for c in section if c['kind'] in (('Deck','Haunch') if model.physical else ('Deck','Beam','Haunch'))])
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
        if not model.physical:
            assert len(sections)==1, 'The legacy report requires a separate view for unequal support faces.'
        supports.append(dict(name=support['name'], station=support['station'],
            components=serialize_components(sections[0]),
            width=support['width'], top=support['top'], depth=support['depth'],
            length=support['length'], center=support['center'], slope=support['slope'],
            seats=support['seats'].to_dict('records'), piles=support['pile_elevations'].to_dict('records'),
            datum_station=support.get('datum_station',support['station']),
            solid_geometry=support.get('solid_geometry')))
    data = dict(version=2, geometry_version=model.geometry_version, source='Bridge_Geometry_2 Beam_V2.ipynb',
        generated_utc=datetime.now(timezone.utc).isoformat(),
        geometry_source={k:model.cfg.get('physical_geometry',{}).get(k) for k in ('source_file','source_sha256')},
        model_id=model.model_id, profile=model.profile_mode, deck_mode=model.deck_mode,
        authority='Notebook CONFIG and geometry equations; CAD consumes the exported results.',
        camber_basis=model.cfg.get('camber_basis',[]),
        start=model.start,end=model.end,offsets=model.offsets,depth=model.depth,flange=model.flange,
        physical=model.physical,inspection_start=model.inspection_start,inspection_end=model.inspection_end,
        beam_limits=model.beam_limits,deck_limits=model.deck_limits,bearing_limits=model.bearing_limits,
        beam_outline=model.beam_outline(0,0) if model.physical else None,
        deck_width=model.deck_width,deck_thickness=model.deck_thickness,
        pieces=pieces, road=model.road, supports=supports, spans=model.spans.to_dict('records'),
        minimum_clearance=model.clearance_details(),minimum_haunch=dict(value=model.haunch_min*12,station=model.haunch_station),
        required_clearance=model.clearance_required,required_haunch=model.minimum_haunch*12)

    data['initial_station'] = float(initial_station if initial_station is not None else model.pier.get('station', model.start))
    if not model.inspection_start <= data['initial_station'] <= model.inspection_end:
        raise ValueError('Initial report station is outside the bridge.')
    return clean(data)


def cad_geometry_data(model, section_geometry):
    """Portable analytic curves and solid parameters for downstream CAD rebuilds."""
    geometry=report_data(model,section_geometry)
    # Reject an unsupported nonquadratic future model rather than silently sample it.
    for piece in geometry['pieces']:
        span=next(i for i,row in model.spans.iterrows() if row['id']==piece['span'])
        for t in (.2113248654,.7886751346):
            expected=model.evaluate([piece['start']+t*(piece['end']-piece['start'])],span)
            for key,c in piece['fields'].items():
                a,b,q=np.asarray(c)
                if not np.allclose(a+b*t+q*t*t,expected[key][0],rtol=0,atol=1e-9):
                    raise ValueError(f'CAD export cannot represent {key} as a quadratic on this interval.')
    payload=clean(dict(schema='d2mpdb.notebook-cad-geometry',schema_version=1,
        authority='Bridge_Geometry_2 Beam_V2.ipynb applied inputs and equations',
        model_id=model.model_id,configuration=model.cfg,
        coordinates=dict(length_unit='international foot',feet_to_mm=304.8,
            x='Absolute bridge station',y='Transverse offset from PGL',z='Absolute elevation',
            station_origin_ft=model.start,
            cad_local_mm='X=(station-station_origin_ft)*304.8; Y=offset*304.8; Z=elevation*304.8; apply site placement separately'),
        polynomial_contract=dict(parameter='t=(station-piece.start)/(piece.end-piece.start)',
            evaluation='value=c[0]+c[1]*t+c[2]*t*t',coefficient_axis=0,
            field_units='All curve fields are feet, including camber and haunch.',
            array_axes='bottom/top: beam; deck/haunch: beam then left flange edge, center, right flange edge',
            applicability='Use beam_limits/deck_limits for solid presence. Do not bridge open joints.',
            support_geometry='Cap plane from top/slope/center and cap_bounds; pedestals piecewise linear in station; bearing planes from top/slope/station; square/pipe piles from dimensions and cutoff.'),
        support_drop_ft=model.support_drop,camber_diagnostics=model.camber_summary().to_dict('records'),
        limitations=['FIB36 outline fillets are tessellated; longitudinal curves are polynomial.',
            'Pile bottom values use trial lengths, not final design tips. Provisional walls are omitted.',
            'This export does not automatically rebuild or certify an existing CAD model.'],
        geometry=geometry))
    canonical=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    payload['payload_sha256']=hashlib.sha256(canonical).hexdigest()
    return payload


def export_cad_geometry(model=None,path=None):
    """Export the applied notebook configuration, analytic curves and support geometry."""
    if model is None:
        active=globals().get('dashboard')
        model=active['state']['model'] if isinstance(active,dict) else globals().get('MODEL')
        if model is None:raise RuntimeError('Run the geometry model before exporting CAD geometry.')
        if configuration_id(CONFIG)!=model.model_id:
            raise ValueError('Inputs changed. Click Apply input changes, then export CAD geometry again.')
    payload=cad_geometry_data(model,section_geometry)
    target=Path(path or f'Bridge_Geometry_CAD_{model.model_id}.json')
    target.write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return target


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
    target=Path(path or f'Bridge_Geometry_Interactive_Report_physical_v2_{model.model_id}.html')
    text=render_report(model,section_geometry,station,assets=globals().get('_BRIDGE_REPORT_ASSETS'))
    target.write_text(text,encoding='utf-8')
    return target


def show_interactive_report_export():
    """Report and CAD handoff downloads from the same applied notebook model."""
    import ipywidgets as W
    from IPython.display import HTML, FileLink, display
    button=W.Button(description='Export interactive report',icon='download',button_style='primary',
                    layout=W.Layout(width='auto'))
    cad_button=W.Button(description='Export CAD geometry',icon='download',layout=W.Layout(width='auto'))
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
    def download_cad(_):
        cad_button.disabled=True
        with output:
            output.clear_output(wait=True)
            try:
                path=export_cad_geometry()
                print(f'Exported {path.name}: notebook equations, curves, support geometry and input provenance for CAD.')
                try:
                    from google.colab import files
                except ImportError:
                    display(FileLink(str(path)))
                else:
                    files.download(str(path))
            except Exception as error:
                print(f'CAD geometry not exported: {error}')
            finally:
                cad_button.disabled=False
    cad_button.on_click(download_cad)
    display(W.VBox([W.HBox([button,cad_button]),output]))
    return dict(button=button,cad_button=cad_button,output=output)
