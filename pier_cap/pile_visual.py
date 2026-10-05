"""Persist pile appearance without changing the cap's force or clearance model."""
import math


def validate_pile_visual(case):
    value=case.get('pile_visual')
    if value is None:return
    if not isinstance(value,dict) or value.get('version')!=1 or value.get('shape') not in ('unknown','square','round','pipe'):
        raise ValueError('Pile appearance must specify square, round, pipe or unknown (version 1).')
    wall=value.get('wall_in')
    if wall is not None and (type(wall) not in (int,float) or not math.isfinite(wall) or wall<=0):
        raise ValueError('Pipe wall thickness must be positive inches, or left unspecified.')
    if value.get('shape')=='pipe' and wall is not None and 2*wall>=case['inputs']['D_pile']:
        raise ValueError('Pipe wall thickness must be less than half the pile outside diameter.')
    if value.get('filled') is not None and type(value['filled']) is not bool:
        raise ValueError('Pipe fill must be concrete, open or unspecified.')
    if not isinstance(value.get('source',''),str):raise ValueError('Pile appearance source must be text.')


def pile_appearance(case):
    validate_pile_visual(case)
    value=dict(version=1,shape='unknown',wall_in=None,filled=None,source='No pile shape has been saved for this case')
    value.update(case.get('pile_visual',{}));value['width_in']=case['inputs']['D_pile']
    if value['shape']=='pipe':
        label='Pipe pile'
        detail=f'OD {value["width_in"]:g} in'
        detail+=f'; wall {value["wall_in"]:g} in' if value['wall_in'] is not None else '; wall unspecified — outline only'
        detail+='; concrete filled' if value['filled'] is True else '; open' if value['filled'] is False else '; fill unspecified'
    elif value['shape']=='square':label='Square pile';detail=f'{value["width_in"]:g} × {value["width_in"]:g} in'
    elif value['shape']=='round':label='Round solid pile';detail=f'Diameter {value["width_in"]:g} in'
    else:label='Pile shape unspecified';detail='Dashed envelope only; set Geometry → Pile head → 3D pile shape'
    value.update(label=label,description=detail)
    return value


def appearance_from_xml(segment,source):
    dims=segment.find('DIMENSIONS')
    def optional(parent,path,unit):
        node=parent.find(path)
        if node is None:return None
        if node.get('units')!=unit:raise ValueError(f'{path}: expected {unit} for pile appearance.')
        v=float(node.text)
        if not math.isfinite(v):raise ValueError(f'{path}: nonfinite pile appearance dimension.')
        return v
    wall=optional(dims,'SHELL_THICK','in')
    if wall is not None and wall<0:raise ValueError('SHELL_THICK must be nonnegative.')
    fc=optional(segment,'MATERIAL_PROPS/FPC','ksi')
    shape='square' if dims.get('type')=='Rectangular' else 'pipe' if wall and wall>0 else 'round'
    return dict(version=1,shape=shape,wall_in=wall if shape=='pipe' else None,
                filled=(fc>0 if fc is not None else None) if shape=='pipe' else None,source=source)
