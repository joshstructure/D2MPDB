"""Read-only orthogonal sections of captured native BReps and original TINs.

All calculations use full precision; exports use US survey feet. Geometry remains
native in the source model. This engine never opens or saves a working document.
"""
import json,hashlib,math,re
from pathlib import Path
import numpy as np
import FreeCAD as App
import Part
from .terrain_exchange import US_FOOT_M
from .geometry import length
ROOT=Path(__file__).resolve().parents[1]

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def metres(value):
    match=re.fullmatch(r'([0-9]+(?:\.[0-9]+)?) us-ft',value)
    answer=float(match.group(1))*US_FOOT_M if match else length(value,True)/1000
    if answer<=0:raise ValueError('Positive unit-bearing distance required')
    return answer

def section_plan(manifest,spacing,tol):
    out=[];checks=[]
    for ramp in ['A','B']:
        for axis in [0,1]:
            keys=[]
            def add(v,reason):keys.append((float(v)/1000,reason))
            for s in manifest['slabs']:
                if s['name'].startswith(ramp+'_'):
                    for p in s['corners']:add(p[axis],s['name'].replace('Surface','')+' boundary')
            for w in manifest['walls']:
                if w['name'].startswith('Wall'+ramp):
                    if abs(w['tangent'][axis])>.9:
                        for p in w['base']+w['top']:add(w['start'][axis]+w['tangent'][axis]*p[0],w['name'].replace('Profile','')+' end/break')
                    else:add(w['start'][axis]+w['normal'][axis]*69.85,w['name'].replace('Profile','')+' center')
            for p in manifest['keypoints']:
                if p['id'].startswith(ramp+'-'):add(p['point'][axis],p['id'])
            stations=[]
            for v,reason in sorted(keys):
                if stations and v-stations[-1][0]<=tol:stations[-1][1].add(reason)
                else:stations.append([v,{reason}])
            added=[]
            for (a,_),(b,_) in zip(stations,stations[1:]):
                n=1
                while a+n*spacing<b-tol:
                    added.append([a+n*spacing,{'25 ft interval'}]);n+=1
            stations=sorted(stations+added)
            maxgap=max(b[0]-a[0] for a,b in zip(stations,stations[1:]))
            assert maxgap<=spacing+tol
            assert all(min(abs(v-s[0]) for s in stations)<=tol for v,_ in keys)
            checks.append({'ramp':ramp,'axis':axis,'cuts':len(stations),'max_spacing_us_ft':maxgap/US_FOOT_M,'key_station_coverage':'PASS'})
            for i,(v,reasons) in enumerate(stations,1):
                out.append({'id':ramp+('-T' if axis==0 else '-L')+f'{i:02d}','ramp':ramp,'axis':axis,'station_m':v,'reasons':sorted(reasons)})
    return out,checks

def tin_profile(tri,axis,station,lo,hi,tol=1e-7):
    """Intersect supplied triangles; preserve gaps, reject inconsistent overlaps."""
    h=1-axis
    selected=tri[(tri[:,:,axis].min(1)<=station+1e-10)&(tri[:,:,axis].max(1)>=station-1e-10)&(tri[:,:,h].max(1)>=lo)&(tri[:,:,h].min(1)<=hi)]
    segments=[]
    for t in selected:
        ab=t[1,:2]-t[0,:2];ac=t[2,:2]-t[0,:2]
        if abs(ab[0]*ac[1]-ab[1]*ac[0])<1e-14:raise ValueError('Degenerate TIN triangle intersects section')
        pts=[]
        for a,b in zip(t,np.roll(t,-1,axis=0)):
            da,db=a[axis]-station,b[axis]-station
            if abs(da)<1e-10:pts.append(a[[h,2]])
            if da*db<0:pts.append((a+(b-a)*(-da/(db-da)))[[h,2]])
        if len(pts)<2:continue
        pts=sorted(pts,key=lambda p:p[0]);a,b=pts[0],pts[-1]
        l,r=max(lo,a[0]),min(hi,b[0])
        if r-l<1e-10:continue
        z=lambda x:float(a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0]))
        segments.append(([float(l),z(l)],[float(r),z(r)]))
    segments.sort(key=lambda s:(s[0][0],s[1][0]))
    pieces=[]
    for a,b in segments:
        if not pieces or a[0]-pieces[-1][-1][0]>tol:pieces.append([a,b]);continue
        prev=pieces[-1];end=prev[-1]
        if a[0]<end[0]-tol:
            arr=np.array(prev);z=float(np.interp(a[0],arr[:,0],arr[:,1]))
            if abs(z-a[1])>tol:raise ValueError('Overlapping TIN segments have different elevations')
            at=min(b[0],end[0]);za=float(np.interp(at,arr[:,0],arr[:,1]));zb=a[1]+(b[1]-a[1])*(at-a[0])/(b[0]-a[0])
            if abs(za-zb)>tol:raise ValueError('Inconsistent shared terrain edge')
            if b[0]>end[0]+tol:prev.append(b)
        else:
            if abs(end[1]-a[1])>tol:raise ValueError('Discontinuous terrain at triangle seam')
            prev.append(b)
    return pieces, len(selected)

def interp_profiles(profiles,x,tol=1e-7):
    values=[]
    for p in profiles:
        a=np.array(p)
        if a[0,0]-tol<=x<=a[-1,0]+tol:values.append(float(np.interp(x,a[:,0],a[:,1])))
    if not values:return None
    if max(values)-min(values)>tol:raise ValueError('Ambiguous terrain elevation')
    return sum(values)/len(values)

def edge_polyline(edge,tol_mm):
    if isinstance(edge.Curve,Part.Line):pts=[edge.Vertexes[0].Point,edge.Vertexes[-1].Point]
    else:pts=edge.discretize(Deflection=tol_mm*.25)
    if len(pts)<2:raise ValueError('Empty section edge')
    # Independent distance samples of the exact curve against its export polyline.
    # Nearest midpoint candidates yield a conservative distance upper bound to
    # the whole polyline, without thousands of heavyweight OCC distance calls.
    from scipy.spatial import cKDTree
    pp=np.array([list(p) for p in pts]);a=pp[:-1];b=pp[1:];ab=b-a
    samples=np.array([list(edge.valueAt(float(t))) for t in np.linspace(edge.FirstParameter,edge.LastParameter,max(9,2*len(pts)))])
    tree=cKDTree((a+b)/2);_,idx=tree.query(samples,k=min(8,len(a)))
    if idx.ndim==1:idx=idx[:,None]
    aa=a[idx];vv=ab[idx];delta=samples[:,None,:]-aa
    denom=np.sum(vv*vv,axis=2)
    tt=np.divide(np.sum(delta*vv,axis=2),denom,out=np.zeros_like(denom),where=denom>0).clip(0,1)
    distances=np.min(np.linalg.norm(delta-tt[:,:,None]*vv,axis=2),axis=1)
    # Very uneven segment lengths can defeat midpoint candidate selection.
    # Resolve every nonpassing bound against ALL segments before accepting or
    # reporting failure; numerical tolerance and sample density are unchanged.
    bad=np.flatnonzero(distances>tol_mm)
    den=np.sum(ab*ab,axis=1)
    for start in range(0,len(bad),32):
        ids=bad[start:start+32];delta=samples[ids,None,:]-a[None,:,:]
        t=np.divide(np.sum(delta*ab[None,:,:],axis=2),den[None,:],out=np.zeros(delta.shape[:2]),where=den[None,:]>0).clip(0,1)
        distances[ids]=np.min(np.linalg.norm(delta-t[:,:,None]*ab[None,:,:],axis=2),axis=1)
    error=float(np.max(distances))
    if error>tol_mm:raise ValueError('Section curve approximation exceeds tolerance: '+str(error))
    return np.array([list(p) for p in pts]),error

def brep_section(shape,axis,station,lo,hi,tol_mm):
    h=1-axis;corners=[]
    for x,z in [(lo,-50),(hi,-50),(hi,40),(lo,40),(lo,-50)]:
        p=[0.,0.,z*1000];p[axis]=station*1000;p[h]=x*1000;corners.append(App.Vector(*p))
    plane=Part.Face(Part.makePolygon(corners));cut=shape.copy().section(plane)
    lines=[];maxerr=0
    for e in cut.Edges:
        p,err=edge_polyline(e,tol_mm);maxerr=max(maxerr,err)
        if np.max(np.abs(p[:,axis]-station*1000))>tol_mm:raise ValueError('Section edge outside plane')
        lines.append((p[:,[h,2]]/1000).tolist())
    return lines,maxerr

def upper_labels(lines):
    """Top boundary endpoints from actual section edges, including step levels."""
    candidates=[];curves=[]
    for p in lines:
        a=np.array(p)
        if abs(a[-1,0]-a[0,0])<1e-8:continue
        if a[0,0]>a[-1,0]:a=a[::-1]
        if np.any(np.diff(a[:,0])<-1e-9):raise ValueError('Non-monotone top edge needs an adapter')
        curves.append(a)
    breaks=sorted(set(float(v) for a in curves for v in [a[0,0],a[-1,0]]))
    for a in curves:
        cuts=[x for x in breaks if a[0,0]-1e-9<=x<=a[-1,0]+1e-9]
        for l,r in zip(cuts,cuts[1:]):
            if r-l<1e-8:continue
            x=(l+r)/2;z=float(np.interp(x,a[:,0],a[:,1]))
            zz=[float(np.interp(x,b[:,0],b[:,1])) for b in curves if b[0,0]-1e-9<=x<=b[-1,0]+1e-9]
            if z>=max(zz)-1e-7:
                candidates.extend([[l,float(np.interp(l,a[:,0],a[:,1]))],[r,float(np.interp(r,a[:,0],a[:,1]))]])
                if len(a)>2:candidates.append([x,z])
    return candidates

def generate(job):
    spacing=metres(job['spacing']);extent=metres(job['pond_extension'])
    context=metres(job['other_context']);tol=metres(job['tolerance'])
    if abs(spacing-25*US_FOOT_M)>1e-10:raise ValueError('This plan requires 25 US survey ft intervals')
    src=ROOT/job['snapshot'];out=ROOT/job['output_directory'];out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((src/'manifest.json').read_text());reg=json.loads((ROOT/job['placement']).read_text())
    R=np.array(reg['rotation']);T=np.array(reg['translation_m'])
    parts=[]
    for p in manifest['parts']:
        path=src/'brep'/(p['name']+'.brep')
        if digest(path)!=p['file_sha256']:raise ValueError('Captured BRep changed')
        shape=Part.Shape();shape.read(str(path))
        if not shape.isValid() or not shape.Solids:raise ValueError('Invalid source solid '+p['name'])
        if abs(shape.Volume-p['volume_mm3'])>max(1e-4,p['volume_mm3']*1e-10):raise ValueError('BRep volume mismatch')
        p=dict(p);p['shape']=shape
        p['ramp']=re.search(r'(?:Footing|Wall)([AB])',p['name']).group(1) if p['kind']!='Slab' else p['name'][0]
        parts.append(p)
    pond=np.load(ROOT/job['pond_cache']);pondtri=pond['points'][pond['faces']]
    eg=np.load(ROOT/job['existing_cache']);egp=(eg['points']*US_FOOT_M-T)@R
    # Broad phase only: no replacement triangulation or terrain smoothing.
    minxy=np.minimum(pondtri[:,:,:2].min((0,1)),np.min([p['bounds_mm'][0][:2] for p in parts],axis=0)/1000)-extent-context
    maxxy=np.maximum(pondtri[:,:,:2].max((0,1)),np.max([p['bounds_mm'][1][:2] for p in parts],axis=0)/1000)+extent+context
    f=eg['faces'];trixy=egp[f,:2];keep=np.all(trixy.max(1)>=minxy,axis=1)&np.all(trixy.min(1)<=maxxy,axis=1)
    egtri=egp[f[keep]];del trixy,egp,eg
    plan,planchecks=section_plan(manifest,spacing,tol);sections=[];maxerror=0.;used=set()
    for i,s in enumerate(plan):
        (out/'section-progress.json').write_text(json.dumps({'current':s['id'],'completed':i,'total':len(plan)}))
        axis=s['axis'];h=1-axis;station=s['station_m'];rp=[p for p in parts if p['ramp']==s['ramp']]
        crossing=[p for p in rp if p['bounds_mm'][0][axis]/1000-tol<=station<=p['bounds_mm'][1][axis]/1000+tol]
        concrete_lo=min(p['bounds_mm'][0][h] for p in crossing)/1000;concrete_hi=max(p['bounds_mm'][1][h] for p in crossing)/1000
        feet=[p for p in crossing if p['kind']=='Footing']
        edge_lo=min(p['bounds_mm'][0][h] for p in feet)/1000 if feet else concrete_lo
        edge_hi=max(p['bounds_mm'][1][h] for p in feet)/1000 if feet else concrete_hi
        pondside=-1 if pondtri[:,:,h].mean()<(edge_lo+edge_hi)/2 else 1
        lo=min(concrete_lo-context,edge_lo-(extent if pondside==-1 else context))
        hi=max(concrete_hi+context,edge_hi+(extent if pondside==1 else context))
        ps=pondtri[(pondtri[:,:,axis].min(1)<=station)&(pondtri[:,:,axis].max(1)>=station)]
        if s['ramp']=='B' and len(ps):
            lo=min(lo,float(ps[:,:,h].min())-5*US_FOOT_M);hi=max(hi,float(ps[:,:,h].max())+5*US_FOOT_M)
        surfaces={};counts={}
        for key,tris in [('EG',egtri),('POND',pondtri)]:surfaces[key],counts[key]=tin_profile(tris,axis,station,lo,hi)
        concrete=[];labels=[]
        def label(kind,x,z,source):
            for a in labels:
                if a['type']==kind and abs(a['h_m']-x)<=tol and abs(a['z_m']-z)<=tol:
                    if source not in a['sources']:a['sources'].append(source)
                    return
            labels.append({'type':kind,'h_m':float(x),'z_m':float(z),'sources':[source]})
        for p in crossing:
            lines,err=brep_section(p['shape'],axis,station,lo,hi,tol*1000);maxerror=max(maxerror,err)
            if not lines:continue
            used.add(p['name']);concrete.append({'name':p['name'],'kind':p['kind'],'lines_m':lines})
            for x,z in upper_labels(lines):
                kind={'Slab':'TOS','Wall':'TOW','Footing':'TOF'}[p['kind']];label(kind,x,z,p['name'])
                if p['kind']=='Wall':
                    for key in surfaces:
                        tz=interp_profiles(surfaces[key],x)
                        if tz is not None:label(key,x,tz,p['name']+' terrain at wall')
        if not concrete:raise ValueError('Section misses concrete: '+s['id'])
        for key,profiles in surfaces.items():
            for j,p in enumerate(profiles):
                a=np.array(p);inds={0,len(a)-1,int(a[:,1].argmin()),int(a[:,1].argmax())}
                for k in sorted(inds):label(key,*a[k],key+f' profile {j+1} end/extreme')
        labels.sort(key=lambda a:(a['h_m'],a['type'],a['z_m']))
        for k,a in enumerate(labels,1):
            a['id']=f'{k:02d}';a['offset_us_ft']=(a['h_m']-lo)/US_FOOT_M;a['elevation_us_ft']=(a['z_m']+T[2])/US_FOOT_M
        endpoints=[]
        for x in [lo,hi]:
            p=np.zeros(3);p[axis]=station;p[h]=x;endpoints.append(((p@R.T+T)/US_FOOT_M)[:2].tolist())
        gap=(edge_lo-lo if pondside==-1 else hi-edge_hi)/US_FOOT_M
        if gap+tol/US_FOOT_M<100:raise ValueError('Pond side extension short')
        span=sum(p[-1][0]-p[0][0] for p in surfaces['EG']);egcover=span/(hi-lo)
        ss=dict(s,range_m=[lo,hi],footing_edges_m=[edge_lo,edge_hi],pond_side=pondside,pond_extension_us_ft=gap,endpoints_EN_us_ft=endpoints,concrete=concrete,terrain_m=surfaces,terrain_triangles=counts,labels=labels,existing_coverage_fraction=egcover,pond_intersects=bool(surfaces['POND']))
        sections.append(ss)
        if (i+1)%10==0:print(f'Sections: {i+1}/{len(plan)}',flush=True)
    missing=sorted(set(p['name'] for p in parts)-used)
    if missing:raise ValueError('Unsectioned components: '+str(missing))
    checks={'status':'PASS','source_solids':len(parts),'all_components_sectioned':True,'section_plane_and_curve_tolerance_mm':tol*1000,'max_curve_error_mm':maxerror,'section_plan':planchecks,'min_pond_extension_us_ft':min(s['pond_extension_us_ft'] for s in sections),'existing_ground_coverage_gaps':[s['id'] for s in sections if s['existing_coverage_fraction']<1-1e-7], 'pond_intersection_count':sum(s['pond_intersects'] for s in sections),'soil_layers':'NOT CONFIGURED','water_level':'NOT CONFIGURED','structural_design':'NOT CONFIGURED','existing_bridge_MSE_clashes':{'status':'FAIL','pairs':12,'source':'previous unchanged whole-model audit'}}
    data={'title':'B4 ramp sections with Pond 14D','units':'US survey feet','source_snapshot':str(src),'placement':reg,'job':job,'checks':checks,'sections':sections,'plan_parts':[{k:p[k] for k in ['name','kind','ramp','bounds_mm']} for p in parts], 'pond_plan_triangles_m':pondtri[:,:,:2].tolist()}
    (out/'sections.json').write_text(json.dumps(data,indent=1,allow_nan=False))
    (out/'section-checks.json').write_text(json.dumps(checks,indent=2))
    return {'status':'PASS','sections':len(sections),'report':str(out/'section-checks.json'),'checks':checks}
