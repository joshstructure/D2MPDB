"""Index native journal definitions and saved cells, without evaluating BPAD.

Discovery is confined to named, non-archive report/spreadsheet modules in the
registered journal. References are lexical source evidence, not proof that saved
results are current. Ambiguous definitions are never resolved by position.
"""
from collections import Counter, defaultdict
import math
import re
import xml.etree.ElementTree as ET

from design_atlas.journal import cell_text

IDENT = r'[^\W\d]\w*'
DEFINITION = re.compile(r'^\s*(' + IDENT + r')(?:\(([^()]*)\))?\s*=(?!=)\s*(.+)$', re.S)
TOKEN = re.compile(r'(?<![\w.])' + IDENT + r'(?:\.' + IDENT + r')*(?![\w.])')
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
UNIT = r'(?:in|ft|kip|lbf|lb|psi|ksi|psf|ksf|pcf|deg|rad|mm|cm|m|N|kN)(?:\^[+-]?\d+)?'
QUANTITY = re.compile(r'(' + NUMBER + r')(?:\s+(' + UNIT + r'(?:[*/]' + UNIT + r')*))?')
ENTRY_IDS = {'FBMPPier': 'JOURNAL-PIER-ENTRY', 'FBMPEndBent': 'JOURNAL-EB-ENTRY'}
COMPONENTS = {'CapDesignPier': 'Pier', 'CapDesignEndBentOne': 'End Bent 1',
              'CapDesignEndBentTwo': 'End Bent 2', 'PierWallFins': 'Pier',
              'PileDesignPier': 'Pier', 'PileDesignEndBentOne': 'End Bent 1', 'PileDesignEndBentTwo': 'End Bent 2',
              'EndBentBackwallDesign': 'End Bent 1'}
CALC_NUMBER = re.compile(r'^(C\d{3}) - ')          # the numbered calculation modules, e.g. "C011 - End Bent 1 Pile Design"


def literal(text):
    """Only an entire literal, never arithmetic, a lookup or a unit conversion."""
    text = text.strip()
    match = QUANTITY.fullmatch(text)
    if match and math.isfinite(float(match[1])):
        return float(match[1]), match[2] or ''
    if re.fullmatch(r'"[^"\r\n]*"', text):
        return text[1:-1], ''
    if text in ('True', 'False', 'true', 'false'):
        return text.lower() == 'true', ''
    return None


def saved_result(item, rhs, function=False):
    cached = item.find('expresult') if item.tag == 'dynexp' else None
    text = ' '.join(' '.join(cached.itertext()).split()) if cached is not None else cell_text(item)
    if text is not None:
        text = text.lstrip('=').strip()
        value, unit = literal(text) or (text, '')
        return value, unit, 'saved journal result', text
    # A literal assignment is source data even when BPAD omits its result cache.
    source_literal = None if function else literal(rhs)
    if source_literal is not None:
        return *source_literal, 'literal journal input', None
    return None, '', 'formula without saved result', None


def paths(element, path):
    """Unambiguous positional XPath, including repeated symbols and empty cells."""
    yield element, path
    counts = Counter()
    for child in element:
        counts[child.tag] += 1
        yield from paths(child, path + f'/{child.tag}[{counts[child.tag]}]')


def column_name(index):
    result = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def extract_calculations(root, path, evidence, entry_modules):
    document = ET.parse(root / path).getroot()
    modules, records, symbols = [], [], defaultdict(list)
    module_nodes = {}
    module_counts = Counter()
    for module in document:
        module_counts[module.tag] += 1
        name, title = module.get('name'), module.get('title', module.get('name', ''))
        if module.tag not in ('report', 'spreadsheet') or not name or title.startswith('Archive -'):
            continue
        # Position among siblings of the same tag also works in ElementTree's
        # XPath subset; no fragile quoting of names or wildcard-position rules.
        module_path = f'/document/{module.tag}[{module_counts[module.tag]}]'
        locations = dict(paths(module, module_path))
        items = []
        if module.tag == 'report':
            for item in module.iter('dynexp'):
                match = DEFINITION.fullmatch(item.get('formula', ''))
                if match:
                    symbol, args, rhs = match.groups()
                    items.append((item, symbol, args, rhs, locations[item]))
        else:
            for row_index, row in enumerate(module.findall('row'), 1):
                for col, item in enumerate((c for c in row if c.tag in ('c', 'cell')), 1):
                    if item.get('formula') or item.find('num') is not None:
                        items.append((item, column_name(col) + str(row_index), None,
                                      item.get('formula', ''), locations[item]))
        if not items:
            continue
        node_id = ENTRY_IDS.get(name, 'JOURNAL-CALC-' + name)
        module_nodes[name] = node_id
        module_evidence = evidence(path, module_path, {'name': name, 'title': title, 'definitions': len(items)},
                                   'Native journal module. Literal inputs and saved results only; no native recalculation.')
        # The numbered calculations (C001 to C016, journal tasks T022 to T026) are the design calculations that will be
        # issued as separate review documents: every one of them is a Design-stage node carrying its number.
        calc_number = CALC_NUMBER.match(title)
        stage = ('Design' if calc_number or name.startswith('CapDesign') or name in {'BearingDesign', 'PierWallFins'}
                 else 'Basis' if name in {'Materials', 'BridgeGeometry_2Beam', 'ProjectInfo'} else 'Analysis')
        modules.append({'id': node_id, 'module': name, 'title': 'Journal · ' + title,
                        'short_title': title, 'stage': stage, 'calc_number': calc_number.group(1) if calc_number else None,
                        'component': COMPONENTS.get(name), 'evidence': module_evidence})
        occurrences = Counter()
        totals = Counter(s for _, s, _, _, _ in items)
        for item, symbol, args, rhs, locator in items:
            occurrences[symbol] += 1
            suffix = f'.definition{occurrences[symbol]}' if totals[symbol] > 1 else ''
            value_id = f'journal.{name}.{symbol}' + suffix
            formula = item.get('formula', '')
            value, unit, status, raw = saved_result(item, rhs, args is not None)
            note = 'Read directly from the registered journal. Saved results may be stale; the atlas does not run Blockpad or confirm engineering approval.'
            if totals[symbol] > 1:
                note += ' This symbol has multiple definitions; references to it remain unresolved.'
            proof = evidence(path, locator, ET.tostring(item, encoding='unicode').strip(), note)
            kind = 'defined' if (args is None and literal(rhs) is not None) or not formula else 'derived'
            role = {'kind': kind, 'basis': 'Literal value defined in this module.' if kind == 'defined' else 'Formula defined in this module. The displayed result is saved, not recalculated.', 'evidence': [proof]}
            val = {'id': value_id, 'key': name + '.' + symbol, 'label': symbol,
                   'value': value, 'unit': unit, 'category': 'Journal · ' + title,
                   'node_ids': [node_id, 'JOURNAL'], 'primary_node': node_id,
                   'source_status': status, 'sheet_status': 'not applicable',
                   'expression': formula, 'saved_value': raw, 'note': note,
                   'steps': [{'title': title + ' · ' + symbol, 'node': node_id, 'value': value,
                              'unit': unit, 'status': 'recorded', 'evidence': proof, 'note': note}],
                   'origins': {node_id: role, 'JOURNAL': role}, 'inputs': []}
            if value is None:
                val.update(value='Not evaluated', value_kind='expression')
            record = {'module': name, 'symbol': symbol, 'rhs': rhs, 'args': args,
                      'value': val, 'proof': proof, 'node': node_id}
            records.append(record)
            symbols[name, symbol].append(record)

    # Existing FBMP table IDs remain stable and can now point into their formulas.
    for module in entry_modules:
        for val in module['values']:
            records.append({'module': module['module'], 'symbol': None,
                            'rhs': val.get('expression', ''), 'args': None,
                            'value': val, 'proof': val['steps'][0]['evidence'], 'node': module['id']})

    connections = {}
    for record in records:
        val, name, rhs, node_id = record['value'], record['module'], record['rhs'], record['node']
        # Quoted strings are source values, not identifiers or instructions.
        unquoted = re.sub(r'"(?:[^"\\]|\\.)*"', ' ', rhs)
        unquoted = re.sub(r'\$(?=[A-Za-z0-9])', '', unquoted)
        ranges = re.findall(r'(?<![\w.])(?:\w+\.)?[A-Z]+\d+:(?:\w+\.)?[A-Z]+\d+', unquoted)
        for cell_range in ranges:
            unquoted = unquoted.replace(cell_range, ' ')
        arguments = set(re.findall(IDENT, record['args'] or ''))
        refs = list(dict.fromkeys(TOKEN.findall(unquoted)))
        inputs = [{'reference': ref, 'status': 'unresolved', 'note': 'Cell range preserved; its members are not expanded by this adapter.'} for ref in dict.fromkeys(ranges)]
        for ref in refs:
            parts = ref.split('.')
            if len(parts) == 1:
                if ref in arguments or (name, ref) not in symbols:
                    continue
                target_module, symbol = name, ref
            elif len(parts) == 2:
                target_module, symbol = parts
            else:
                inputs.append({'reference': ref, 'status': 'unresolved', 'note': 'Nested reference is not resolved by this adapter.'})
                continue
            candidates = symbols.get((target_module, symbol), [])
            target_node = module_nodes.get(target_module)
            inp = {'reference': ref, 'status': 'unresolved'}
            if target_node:
                inp['node'] = target_node
            if len(candidates) == 1:
                source = candidates[0]['value']
                inp.update(value_id=source['id'], value=source['value'], unit=source['unit'], status='resolved')
            else:
                inp['note'] = 'Multiple source definitions; no value selected.' if candidates else 'Source definition is not extracted; no value inferred.'
            inputs.append(inp)
            if target_node and target_node != node_id:
                connection = connections.setdefault((target_node, node_id), {'references': set(), 'evidence': []})
                connection['references'].add(ref)
                if len(connection['evidence']) < 3:
                    connection['evidence'].append(record['proof'])
        val['inputs'] = inputs
        # Only a direct, uniquely resolved reference (optionally with a native
        # unit-display conversion) is labeled received. Never compare stale caches
        # or evaluate conversions to assert a matching transfer.
        direct = re.fullmatch(r'\s*(' + IDENT + r'\.' + IDENT + r')(?:\s+to\s+[\w */^+-]+)?\s*', rhs)
        source_input = next((i for i in inputs if direct and i['reference'] == direct[1]), None)
        if source_input and source_input.get('node') != node_id and source_input['status'] == 'resolved':
            source_record = symbols[tuple(direct[1].split('.'))][0]
            role = {'kind': 'received', 'from_node': source_input['node'],
                    'basis': 'The native formula explicitly references ' + direct[1] + '. Any displayed conversion is preserved, not evaluated. Saved-result agreement is not asserted.',
                    'evidence': [record['proof'], source_record['proof']]}
            val['origins'] = {node_id: role, 'JOURNAL': role}
            val['steps'].insert(0, dict(source_record['value']['steps'][-1]))
    return modules, [r['value'] for r in records if r['symbol'] is not None], connections
