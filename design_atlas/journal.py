"""Read saved FBMP entry cells from the native journal; never evaluate BPAD."""
import re
import xml.etree.ElementTree as ET


MODULES = [
    ('FBMPPier', 'JOURNAL-PIER-ENTRY', 'Journal · FBMP Entry — Pier', 'FE', [
        ('FEPositionMap', 'Pier node coordinates', 1, 5),
        ('PierSourceBearingMap', 'Recorded pier node mapping', 1, 5),
        ('FE_NodeEntry_DC_PL_W1_W3', 'Pier node loads', 2, 9),
    ]),
    ('FBMPEndBent', 'JOURNAL-EB-ENTRY', 'Journal · FBMP Entry — End Bent', 'EB', [
        ('EBNodeMap', 'End-bent node coordinates', 1, 5),
        ('EBNodeEntry', 'End-bent node loads', 2, 9),
    ]),
]


def cell_text(cell):
    # BPAD stores a saved result under num/textvalue. Do not mistake a formula
    # without a result, or a cached error, for a numerical value.
    cached = cell.find('num')
    if cached is None: cached = cell.find('textvalue')
    if cached is None: return None
    return ' '.join(' '.join(cached.itertext()).split())


def stored_value(text):
    if text is None: return None, ''
    match = re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?:\s+(ft|in|kip|kip\*ft|kip\*in))?', text)
    if match: return float(match[1]), match[2] or ''
    # Mixed feet/inches and node labels stay exactly as saved.
    return text, ''


def extract_journal(root, path, evidence):
    journal = ET.parse(root/path).getroot()
    result = []
    for name, node_id, title, prefix, tables in MODULES:
        module = next((n for n in journal if n.tag == 'report' and n.get('name') == name), None)
        if module is None: continue
        locator = '/document/report[@name="'+name+'"]'
        definitions = {}
        for item in module.iter('dynexp'):
            formula = item.get('formula', '')
            found = re.match(r'^\s*([\w]+)\s*=(?!=)', formula)
            if found: definitions.setdefault(found[1], []).append(item)

        def definition_proof(symbol):
            entries = definitions.get(symbol, [])
            # Ambiguous redefinitions are not silently resolved.
            return [evidence(path, locator+'//dynexp[@formula='+repr(item.get('formula'))+']',
                             ET.tostring(item, encoding='unicode'),
                             'Native definition and saved result. Not recalculated by the atlas.') for item in entries]

        def entry_unit(symbol):
            entries = definitions.get(symbol, [])
            if len(entries) != 1: return ''
            item = entries[0]
            cached = item.findtext('expresult', '').replace('\xa0', ' ').strip().lstrip('=').strip()
            if not cached:
                cached = item.get('formula', '').split('=', 1)[-1].strip()
            match = re.fullmatch(r'1\s+(kip(?:\*(?:ft|in))?)', cached)
            return match[1] if match else ''

        values = []
        summaries = []
        for table_name, category, start, stop in tables:
            table = next((t for t in module.iter('table') if t.get('name') == table_name), None)
            if table is None: continue
            rows = table.findall('row')
            if not rows: continue
            headers = [cell_text(c) or '' for c in rows[0].findall('c')]
            summaries.append({'table':table_name, 'rows':len(rows)-1, 'columns':headers})
            for row_number, row in enumerate(rows[1:], start=2):
                cells = row.findall('c')
                row_label = ' · '.join(cell_text(c) or '' for c in cells[:start])
                for column in range(start, min(stop, len(cells))):
                    cell = cells[column]
                    raw = cell_text(cell)
                    val, unit = stored_value(raw)
                    formula = cell.get('formula', '')
                    column_label = headers[column] if column < len(headers) else str(column+1)
                    if not unit and ('force' in column_label or 'moment' in column_label):
                        unit = entry_unit(prefix+('_U_M' if 'moment' in column_label else '_U_F'))
                        if not unit: unit = 'entry unit unconfirmed'
                    if table_name == 'PierSourceBearingMap' and column >= 3: unit = 'in'
                    cell_locator = locator+'//table[@name="'+table_name+'"]'+f'/row[{row_number}]/c[{column+1}]'
                    note = 'Saved journal cell; formulas and cached results are shown without native recalculation. Transfer into a particular FBMP run has not been compared cell by cell.'
                    if table_name == 'PierSourceBearingMap':
                        note += ' This is a recorded historical bearing-to-cap-node mapping; keep it distinct from the live journal entry coordinates.'
                    proof = evidence(path, cell_locator, ET.tostring(cell, encoding='unicode'), note)
                    references = []
                    for symbol in dict.fromkeys(re.findall(r'\b'+prefix+r'_\w+\b', formula)):
                        references.extend(definition_proof(symbol))
                    kind = 'derived' if formula and val is not None else 'defined' if val is not None else 'unknown'
                    basis = ('A formula-backed cell in '+name+'. The displayed value is its saved journal result; it has not been recalculated.' if formula else
                             'A recorded cell in '+name+'. Earlier authorship and exact-run transfer are not established.')
                    role = {'kind':kind, 'basis':basis, 'evidence':[proof]+references}
                    values.append({
                        'id':f'journal.{name}.{table_name}.r{row_number}.c{column+1}',
                        'key':f'{name}.{table_name}.{chr(65+column)}{row_number}',
                        'label':row_label+' · '+column_label, 'value':val, 'unit':unit,
                        'category':'Journal · '+category, 'node_ids':[node_id,'JOURNAL'],
                        'source_status':'saved journal result' if formula else 'recorded journal cell',
                        'sheet_status':'not applicable', 'expression':formula,
                        'note':note, 'saved_value':raw,
                        'steps':[{'title':'Journal cell · '+name,'node':node_id,'value':val,'unit':unit,
                                  'status':'recorded','evidence':proof,'note':note}],
                        'origins':{node_id:role,'JOURNAL':role},
                    })
        result.append({'id':node_id, 'title':title, 'module':name, 'values':values,
                       'evidence':evidence(path,locator,{'module':name,'tables':summaries},
                           'Tables inspected in the current journal snapshot; native calculations were not run.')})
    return result
