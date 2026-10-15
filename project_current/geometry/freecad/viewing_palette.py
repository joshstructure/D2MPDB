"""Apply the bridge viewing palette in FreeCAD without saving or recomputing."""
from collections import Counter
import re

# Cap steel colors match vendor_cap_20261010/pier_cap/cage_3d.py.
PALETTE = {
    'copings': '#D8B36A', 'barriers': '#98A6CF',
    'slabs': '#D5DFE5', 'mse_walls': '#A8BEA1',
    'top': '#1F5B91', 'bottom': '#448BC1', 'side': '#167B75',
    'added': '#D88822', 'hoop': '#7952A3', 'pile_u': '#BD407D',
    'end_horizontal': '#167B75', 'end_vertical': '#1F5B91',
    'wall_vertical': '#24734B', 'wall_horizontal': '#B46A29',
    'pedestal': '#757129', 'wwr': '#00A6A6',
}


def category(name, family='', is_bar=False):
    if is_bar:
        f = family.lower()
        if name.startswith('WWRCheek'):
            return 'wwr'
        if name.startswith('PedSteel'):
            return 'pedestal'
        if name.startswith('SteelBridge'):
            return 'wall_vertical' if 'vertical' in f else 'wall_horizontal' if 'horizontal' in f else None
        if name.startswith('Cage'):
            for token, key in [('pile_u','pile_u'), ('hoop','hoop'), ('top','top'),
                               ('bottom','bottom'), ('skin','side'), ('added','added')]:
                if token in f:
                    return key
            if f.startswith('end '):
                return 'end_vertical' if 'vertical' in f else 'end_horizontal'
        return None
    if any(x in name for x in ('Path', 'Profile', 'Tools', 'Source')):
        return None
    if name.startswith(('Coping', 'PlinthReturn')):
        return 'copings'
    if name.startswith('Barrier'):
        return 'barriers'
    if re.match(r'^Wall[AB]\d+(?:Finished|Mitred)?$', name):
        return 'mse_walls'
    if name.startswith('BridgeDeckS') or re.match(r'^[AB]_\w+Slab(?:Finished|BentJoint)?$', name):
        return 'slabs'
    return None


def rgb(key):
    h = PALETTE[key].lstrip('#')
    return tuple(int(h[i:i+2], 16)/255.0 for i in (0, 2, 4))


def apply(doc):
    """Change only surface RGB; retain visibility, transparency and geometry."""
    if not all(doc.getObject(n) for n in ('BridgePGL', 'CageEB1Bars', 'CageEB2Bars')):
        raise ValueError('Select the B4 bridge document before applying its colors.')
    plan = []
    for obj in doc.Objects:
        if not hasattr(obj, 'Shape') or obj.Shape.isNull():
            continue
        is_bar = hasattr(obj, 'Diameter') and hasattr(obj, 'Base')
        family = getattr(getattr(obj, 'Base', None), 'Family', '') if is_bar else ''
        key = category(obj.Name, family, is_bar)
        if key:
            plan.append((obj, key))
    if not plan:
        raise ValueError('No supported bridge objects found.')
    before = [(o, tuple(o.ViewObject.ShapeColor), list(o.ViewObject.DiffuseColor),
               o.ViewObject.Visibility, o.ViewObject.Transparency) for o, _ in plan]
    try:
        for obj, key in plan:
            view = obj.ViewObject
            old_faces = list(view.DiffuseColor)
            transparency = view.Transparency
            color = rgb(key)
            view.ShapeColor = color
            if old_faces:
                view.DiffuseColor = [color + tuple(c[3:]) for c in old_faces]
            view.Transparency = transparency
        for obj, key in plan:
            assert max(abs(a-b) for a,b in zip(obj.ViewObject.ShapeColor[:3], rgb(key))) < 1e-6, obj.Name
        for obj, _, _, visible, transparency in before:
            assert obj.ViewObject.Visibility == visible, obj.Name
            assert obj.ViewObject.Transparency == transparency, obj.Name
    except Exception:
        for obj, color, faces, visible, transparency in before:
            obj.ViewObject.ShapeColor = color
            obj.ViewObject.DiffuseColor = faces
            obj.ViewObject.Transparency = transparency
            obj.ViewObject.Visibility = visible
        raise
    return {'document': doc.Name, 'objects': len(plan),
            'categories': dict(Counter(key for _, key in plan)),
            'saved': False, 'recomputed': False,
            'visibility_and_transparency_preserved': True}
