"""Visible force provenance and import feedback shared by notebook panels."""
from datetime import datetime, timezone
import html
import json
from .model import GEOMETRY
from .force_audit import strength_html


IMPORTED_INPUTS = (*GEOMETRY, 'fc', 'fy', 'Es', 'Mu_N', 'Mu_P', 'Mu_B',
                   'MI_N', 'MI_P', 'MI_B', 'Vu_G', 'Vu_L', 'Tu')


def source_signature(case):
    return json.dumps({'id': case['analysis']['id'],
                       'geometry': {key: float(value) for key,value in case['analysis']['geometry'].items()},
                       'inputs': {key: float(case['inputs'][key]) for key in IMPORTED_INPUTS}}, sort_keys=True)


def upload_entries(value):
    """Normalize ipywidgets 8 sequence / legacy named-dict upload payloads."""
    if isinstance(value, dict):
        entries = []
        for name, item in value.items():
            metadata = item.get('metadata', {})
            entries.append({**metadata, **item, 'name': item.get('name', metadata.get('name', name))})
    else:
        entries = list(value or ())
    for entry in entries:
        if not entry.get('name') or 'content' not in entry:
            raise ValueError('The upload did not contain a file name and contents. Select the file again.')
    return entries


def notice_html(title, body, kind='info'):
    colors = {'info': ('#eaf1f6', '#245674'), 'success': ('#e5f5eb', '#17633b'),
              'pending': ('#fff3d6', '#805600'), 'error': ('#ffe9e7', '#9d302b')}
    background, foreground = colors[kind]
    return (f'<div role="status" aria-live="polite" style="padding:12px;margin:8px 0;'
            f'border-left:5px solid {foreground};background:{background};color:{foreground};border-radius:4px">'
            f'<b>{html.escape(title)}</b><br>{body}</div>')


def source_html(case, title='ACTIVE FORCE SOURCE', note=''):
    p, a = case['inputs'], case['analysis']
    g = a['geometry']
    body = (f'<b>{html.escape(a["id"])}</b><br>'
            f'Analyzed cap: <b>{g["b"]:g} × {g["h"]:g} in</b> · {g["N_pile"]:g} piles at {g["S_pile"]:g} ft centers<br>'
            + strength_html(case))
    if note:
        body += '<br>'+html.escape(note)
    return notice_html(title, body)


def import_receipt(case, filename):
    return {'filename': filename, 'loaded_utc': datetime.now(timezone.utc).strftime('%H:%M:%S UTC'),
            'signature': source_signature(case)}


def receipt_html(receipt, case):
    if not receipt:
        return ''
    same = receipt['signature'] == source_signature(case)
    body = (f'<b>{html.escape(receipt["filename"])}</b> · loaded {receipt["loaded_utc"]}<br>'
            + ('Geometry, materials and load inputs are active below. Search and study results are not restored from this file. '
               'Next: review the live cage and checks, then run a search or study as needed. No need to run all notebook cells again.' if same else
               'The source or imported inputs have changed since this import. Review the active force source below before searching.'))
    if case.get('retired_u_leg_inventory'):body+='<br><b>Converted saved steel:</b> '+html.escape(case['retired_u_leg_inventory']['note'])
    return notice_html('LOADS IMPORTED SUCCESSFULLY' if same else 'IMPORTED INPUTS HAVE CHANGED',
                       body, 'success' if same else 'pending')
