"""Narrow adapter for the observed native mixed-cage v0.5.1 source structure."""
import math, runpy
from pathlib import Path
from .geometry import length,result,pair,box_cover
REFERENCE=Path(__file__).resolve().parent.parent/'tests/Rebar_Mixed_Cage_v051.reference.FCMacro'

def reference(tol):
    # Run definitions only: the copied macro main entry point is never invoked.
    scope=runpy.run_path(str(REFERENCE),run_name='cad_ai_reference')
    scope['inspect_geometry'].__globals__['TOL']=tol
    return scope

def resolve(doc,inputs):
    candidates=[o for o in doc.Objects if getattr(o,'TestIdentifier',None)=='Rebar_Mixed_Cage_Test_v05' and getattr(o,'Inputs',None)==inputs and hasattr(o,'Hairpins') and hasattr(o,'LongBars')]
    if len(candidates)!=1: raise ValueError('Unsupported or ambiguous mixed cage; expected one observed quantity-link object')
    q=candidates[0]
    for key in ('Concrete','Hairpins','LongBars','HairpinProfile','LongProfile','Plate'):
        o=getattr(q,key)
        if o is None or o.Document!=doc: raise ValueError('Missing or cross-document source link: '+key)
    for bar in (q.Hairpins,q.LongBars):
        if getattr(getattr(bar,'Proxy',None),'Type',None)!='Rebar': raise ValueError('Expected native Arch Rebar proxy')
    return q

def parse(inputs,parameters,tol):
    ref=reference(tol); schema={row[0]:row[1] for row in ref['INPUTS']}; parsed={}
    for name,value in parameters.items():
        if name not in schema or name.startswith('Minimum') or name=='SectionY':
            raise ValueError('Unsupported mutation parameter: '+name)
        if name.endswith('Count') or name.endswith('BarNumber'):
            lo,hi=(3,8) if name.endswith('BarNumber') else (1,12)
            if type(value)!=int or not lo<=value<=hi: raise ValueError(name+' requires integer '+str(lo)+'..'+str(hi))
            parsed[name]=value
        else: parsed[name]=length(value,positive=schema[name]=='App::PropertyLength')
    return parsed

def checks(q,names,tol):
    ref=reference(tol); output=[]
    p,hi,li,lines=ref['inspect_geometry'](q)
    output.append(result('geometry_quantities_placement',True,details=lines))
    if 'clearance' in names:
        bars=hi+li
        for i,a in enumerate(bars):
            for b in bars[i+1:]:
                output.append({**pair(a['shape'],b['shape'],p['MinimumBarClearance'],tol),'objects':[a['id'],b['id']]})
            output.append({**pair(a['shape'],q.Plate.Shape,p['MinimumPlateClearance'],tol),'objects':[a['id'],q.Plate.Name]})
    if 'cover' in names:
        output.extend({**box_cover(x['shape'],q.Concrete,p['MinimumTestCover'],tol),'object':x['id']} for x in hi+li)
    if 'section' in names:
        section=ref['inspect_transverse_section'](q,p,li)
        output.append(result('section',section['ok'],details=section['lines']) if section['supported'] else {'name':'section','status':'SKIPPED','reason':section['lines']})
    if 'drawing_links' in names:
        views=[o for o in q.Document.Objects if o.TypeId=='TechDraw::DrawViewPart']
        expected={q.Concrete.Name,q.Hairpins.Name,q.LongBars.Name,q.Plate.Name}
        if not views: output.append({'name':'drawing_links','status':'SKIPPED','reason':'No drawing views in this fixture'})
        else:
            linked=[v for v in views if {o.Name for o in v.Source}==expected]
            output.append(result('drawing_links',len(linked)>=2,views=[v.Name for v in linked]))
    for name in ('clearance','cover','section','drawing_links'):
        if name not in names: output.append({'name':name,'status':'NOT CONFIGURED'})
    return output
