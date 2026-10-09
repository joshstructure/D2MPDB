"""Shared, explicit load provenance for notebook and Blockpad review copies."""
from .output_labels import numbered_tables
import html
import math


STRENGTH_INPUTS = ('Mu_N', 'Mu_P', 'Mu_B', 'Vu_G', 'Tu')
FORCE_LABELS = {'Mu_N': 'M− magnitude (kip-ft)', 'Mu_P': 'M+ pile (kip-ft)',
                'Mu_B': 'M+ bearing/span (kip-ft)', 'Vu_G': '|V| global (kip)',
                'Tu': '|T| (kip-ft)', 'Vu_L': '|V| low interval (kip)'}


def state_label(state):
    return str(state).replace('STRENGTH-', 'Strength ').replace('SERVICE-', 'Service ')


def force_basis(case, key):
    """Never attribute an edited input to a retained import audit."""
    analysis = case['analysis']
    row = analysis.get('xml_audit', {}).get('governing', {}).get(key)
    if row is None:
        row = analysis.get('workbook_audit', {}).get(key)
    if not row:
        return 'No recorded governing combination; verify the load source.'
    adopted = row.get('adopted', abs(row['value']) if 'value' in row else None)
    source = f'{state_label(row["state"])} · combo {row["combination"]}'
    if adopted is None or not math.isclose(case['inputs'][key], adopted, rel_tol=0, abs_tol=1e-8):
        return f'Edited input; imported {adopted:g} from {source}.' if adopted is not None else 'Imported value unavailable.'
    if key == 'Vu_L' and row.get('basis'):
        source += ' · global shear adopted; low-shear zone not established'
    if 'element' in row:
        source += f' · member {row["element"]}, {row["side"]}, x = {row["x_in"]/12:.3f} ft'
    elif 'location' in row:
        source += f' · {row["location"]}'
    return source


def strength_audit(case):
    """Plain tables shared across output formats; historic values stay marked."""
    audit = case['analysis'].get('xml_audit', {})
    envelopes = audit.get('strength_envelopes', {})
    headers = ['Load basis'] + [FORCE_LABELS[k] for k in STRENGTH_INPUTS]
    rows = []
    for state, envelope in envelopes.items():
        rows.append([state_label(state)] + [
            f'{envelope["governing"][k]["adopted"]:.2f} · C{envelope["governing"][k]["combination"]}'
            for k in STRENGTH_INPUTS])
    if envelopes:
        rows.append(['Imported combined envelope'] + [f'{audit["governing"][k]["adopted"]:.2f}' for k in STRENGTH_INPUTS])
    rows.append(['Current calculator inputs'] + [f'{case["inputs"][k]:.2f}' for k in STRENGTH_INPUTS])
    notes = ['The calculation uses independent maxima across all imported strength combinations. '
             'These are envelopes, not a simultaneous force vector or separate combination-by-combination checks. '
             'C denotes the XML combination number.']
    if audit:
        combos = audit.get('combinations', {})
        notes.append('XML combinations: ' + '; '.join(f'{k}: {state_label(v)}' for k,v in combos.items()) + '.')
        if 'STRENGTH-I' not in combos.values():
            notes.append('Strength I is NOT present in this XML; it has not been checked as a separate supplied load state.')
        if not envelopes:
            notes.append('This saved case predates the per-limit-state audit. Reimport its XML to populate that breakdown; '
                         'the existing governing records are shown below.')
    else:
        notes.append('No XML limit-state breakdown is recorded for this case. Reimport XML to establish the included states.')
    provenance = [[FORCE_LABELS[k], f'{case["inputs"][k]:.2f}', force_basis(case, k)]
                  for k in (*STRENGTH_INPUTS, 'Vu_L')]
    return dict(headers=headers, rows=rows, notes=notes,
                provenance_headers=['Current input', 'Value', 'Governing source / edit status'], provenance=provenance)


@numbered_tables('strength_loads', 'strength_sources')
def strength_html(case):
    data = strength_audit(case)
    def table(headers, rows):
        def cells(tag, values):
            return ''.join(f'<{tag} style="padding:5px 9px;text-align:left;border-bottom:1px solid #cad5dd">'
                           f'{html.escape(str(value))}</{tag}>' for value in values)
        return ('<table class="cap-table"><tr>'+cells('th',headers)+'</tr>'
                + ''.join('<tr>'+cells('td',row)+'</tr>' for row in rows)+'</table>')
    return ('<h4 style="margin-bottom:6px">Strength load breakdown</h4>' + table(data['headers'],data['rows'])
            + '<p>'+ '<br>'.join(html.escape(n) for n in data['notes'])+'</p>'
            + '<details><summary>Governing combination for each current strength input</summary>'
            + table(data['provenance_headers'],data['provenance']) + '</details>')
