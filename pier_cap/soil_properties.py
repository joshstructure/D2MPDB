"""Retain all exported soil inputs without interpreting FBMP model codes."""
from collections import Counter
import math
import re


def soil_properties_from_xml(group):
    soil = group.find('SOIL_INPUT_DATA')
    rows = []
    if soil is None:
        return rows

    def scalar(text):
        text = (text or '').strip()
        try:
            value = float(text)
        except ValueError:
            return text
        if not math.isfinite(value):
            raise ValueError('Soil properties contain a nonfinite value.')
        return value

    def visit(node, category, soil_set='', layer='', position='', path=()):
        if not isinstance(node.tag, str):
            return
        consumed = {'units'}
        if node.tag == 'SOIL_SET':
            soil_set = node.get('number', soil_set)
            consumed.add('number')
        elif node.tag == 'LAYER':
            soil_set = node.get('soilset', soil_set)
            layer = node.get('number', layer)
            consumed.update(('number', 'soilset'))
        elif node.tag in ('TOP', 'BOTTOM'):
            position = node.tag
        context = dict(category=category, soil_set=soil_set, layer=layer, position=position)

        def add(name, value, units=''):
            rows.append(dict(context, property=name, value=scalar(value), units=units))

        for key, value in node.attrib.items():
            if key not in consumed:
                add('/'.join((*path, 'MODEL' if key == 'model' else '@'+key)), value)
        children = [c for c in node if isinstance(c.tag, str)]
        if not children:
            if (node.text or '').strip():
                add('/'.join(path) or node.tag, node.text, node.get('units', ''))
            return
        counts = Counter(c.tag for c in children)
        occurrences = Counter()
        for child in children:
            occurrences[child.tag] += 1
            structural = child.tag in ('SOIL_SET', 'LAYER', 'TOP', 'BOTTOM')
            label = child.tag + (f'[{occurrences[child.tag]}]' if counts[child.tag] > 1 and not structural else '')
            visit(child, category, soil_set, layer, position, path if structural else (*path, label))

    for category in soil:
        if isinstance(category.tag, str):
            visit(category, category.tag)
    return rows


def validate_soil_properties(rows):
    fields = ('category', 'soil_set', 'layer', 'position', 'property', 'units')
    if not isinstance(rows, list):
        raise ValueError('Invalid saved soil properties.')
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in fields):
            raise ValueError('Invalid saved soil property labels.')
        value = row.get('value')
        if not (isinstance(value, str) or type(value) in (int, float) and math.isfinite(value)):
            raise ValueError('Invalid saved soil property value.')


CATEGORIES = {
    'AXIAL': 'Axial', 'LATERAL': 'Lateral', 'TORSION': 'Torsion', 'TIP': 'Pile tip',
    'SOIL_MOVEMENT_OPTION': 'Soil movement', 'INITIAL_OFFSETS_XP_AND_YP': 'Lateral initial offsets',
    'INITIAL_OFFSETS_TZ': 'Axial initial offsets', 'INITIAL_OFFSETS_TTHETA': 'Torsional initial offsets',
    'INITIAL_OFFSETS_QZ': 'Tip initial offsets', 'P_SCALE_FACTORS': 'Lateral scale factors',
}
PROPERTIES = {
    'MODEL': 'Model code', 'ELEV': 'Layer elevation', 'ELEV_PIEZO': 'Piezometric elevation',
    'PHI': 'Friction angle (PHI)', 'RK': 'Subgrade parameter (RK)', 'GAMMA': 'Unit weight (GAMMA)',
    'G': 'Shear modulus (G)', 'POISSON': "Poisson's ratio", 'TAU_MAX': 'Limiting shear stress (TAU_MAX)',
    'CU': 'Undrained shear strength (CU)', 'QU': 'Compressive strength (QU)',
    'CAVG': 'Average strength parameter (CAVG)', 'E50': 'Strain parameter (E50)',
    'Q_ULT': 'Ultimate tip resistance (Q_ULT)', 'OPTION_FLAG': 'Movement option code',
    'OFFSET_XP': 'Initial XP offset', 'OFFSET_YP': 'Initial YP offset',
    'OFFSET_TZ': 'Initial axial offset (TZ)', 'OFFSET_TTHETA': 'Initial rotation (TTHETA)',
    'OFFSET_QZ': 'Initial tip offset (QZ)', 'PSCALE_FACTOR_XP': 'P scale factor, XP',
    'PSCALE_FACTOR_YP': 'P scale factor, YP',
}


def soil_report_rows(rows):
    """Pair top/bottom properties while retaining unrecognized fields and attributes."""
    grouped = {}
    categories = list(CATEGORIES)
    for r in sorted(rows, key=lambda r: categories.index(r['category']) if r['category'] in categories else len(categories)):
        r = dict(r)
        if not r['position'] and re.search(r'_(TOP|BOT)_', r['property']):
            r['position'] = 'TOP' if '_TOP_' in r['property'] else 'BOTTOM'
            r['property'] = re.sub(r'_(TOP|BOT)_', '_', r['property'])
        key = tuple(r[k] for k in ('category', 'soil_set', 'layer', 'property', 'units'))
        slot = {'TOP': 'top', 'BOTTOM': 'bottom'}.get(r['position'], 'value')
        # Repeated records must remain distinct, never silently overwrite a value.
        occurrence = 0
        while slot in grouped.get((*key, occurrence), {}):
            occurrence += 1
        row = grouped.setdefault((*key, occurrence), dict(
            category=CATEGORIES.get(r['category'], r['category'].replace('_', ' ').title()),
            soil_set=r['soil_set'], layer=r['layer'],
            property=PROPERTIES.get(r['property'], r['property']), units=r['units']))
        row[slot] = r['value']
    return list(grouped.values())
