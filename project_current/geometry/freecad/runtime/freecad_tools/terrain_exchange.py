"""Read-only terrain/placement analysis. Coordinates are parsed in float64.

Use the pinned FreeCAD bundled Python for numpy/scipy; no model saves or edits.
LandXML triangle connectivity is retained, never reconstructed from point clouds.
"""
import hashlib, json, math, re, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
US_FOOT_M = 1200.0 / 3937.0

def rotation(angle):
    c,s=np.cos(angle),np.sin(angle)
    return np.array([[c,-s,0],[s,c,0],[0,0,1]],dtype=np.float64)

def register_vertices(source, target, tolerance_m):
    """Fit horizontal rigid placement; verify ALL source vertices afterwards.

    Robust ICP only initializes the fit; no outlier is excluded from acceptance.
    The scale stays exactly one, so a unit/size mismatch fails verification.
    """
    from scipy.spatial import cKDTree
    from scipy.optimize import least_squares
    origin=target.mean(0); t=target-origin; tree=cKDTree(t)
    def apply(p,x):return p@rotation(x[0]).T+x[1:]
    solutions=[]
    for degrees in range(0,360,15):
        a=np.deg2rad(degrees); x=np.r_[a,t.mean(0)-(source@rotation(a).T).mean(0)]
        for _ in range(40):
            d,idx=tree.query(apply(source,x)); keep=d<=np.quantile(d,.8)
            fit=least_squares(lambda y:(apply(source[keep],y)-t[idx[keep]]).ravel(),x,xtol=1e-12,ftol=1e-12,gtol=1e-12)
            change=np.linalg.norm(fit.x-x);x=fit.x
            if change<1e-10:break
        d,idx=tree.query(apply(source,x));solutions.append((float(np.quantile(d,.8)),x))
    solutions.sort(key=lambda v:v[0]);x=solutions[0][1]
    # Refit using every vertex once the global match has been found.
    for _ in range(3):
        _,idx=tree.query(apply(source,x))
        x=least_squares(lambda y:(apply(source,y)-t[idx]).ravel(),x,xtol=1e-12,ftol=1e-12,gtol=1e-12).x
    dist,idx=tree.query(apply(source,x))
    if max(dist)>tolerance_m:raise ValueError('Placement fails all-vertex check: '+str(max(dist))+' m')
    return {'yaw_degrees':float(np.degrees(x[0])%360),'translation_m':(x[1:]+origin).tolist(),
            'rotation':rotation(x[0]).tolist(),'scale':1.0,'source_vertices_checked':len(source),
            'max_vertex_error_m':float(max(dist)),'rms_vertex_error_m':float(np.sqrt(np.mean(dist**2)))}

class Terrain:
    """Exact interpolation on supplied triangles, with coverage checks."""
    def __init__(self, points, faces):
        self.points=points; self.faces=faces; self.tri=points[faces]
        self.lo=self.tri[:,:,:2].min(1); self.hi=self.tri[:,:,:2].max(1)
        self.base=self.tri[:,0,:2]
        ab=self.tri[:,1,:2]-self.base;ac=self.tri[:,2,:2]-self.base
        self.det=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]
        if np.any(abs(self.det)<1e-14):raise ValueError('Degenerate terrain triangle in analysis region')
        self.inv=np.stack([ac[:,1],-ac[:,0],-ab[:,1],ab[:,0]],axis=1).reshape(-1,2,2)/self.det[:,None,None]
    def bary(self,xy,ids):
        uv=np.einsum('nij,nj->ni',self.inv[ids],np.asarray(xy)-self.base[ids])
        return np.c_[1-uv.sum(1),uv]
    def heights(self,xy):
        out=[]
        for p in np.atleast_2d(xy):
            ids=np.flatnonzero(np.all(self.lo<=p+1e-9,axis=1)&np.all(self.hi>=p-1e-9,axis=1))
            b=self.bary(p,ids);valid=np.all(b>=-1e-9,axis=1); ids=ids[valid]; b=b[valid]
            if not len(ids):out.append(float('nan'));continue
            z=np.sum(b*self.tri[ids,:,2],1)
            if np.ptp(z)>1e-7:raise ValueError('Terrain is multivalued at a query point')
            out.append(float(z.mean()))
        return np.array(out)
    def line(self,a,b):
        """All triangle crossings, elevations and complete segment coverage."""
        a=np.asarray(a)[:2];b=np.asarray(b)[:2]
        ids=np.flatnonzero(np.all(self.lo<=np.maximum(a,b)+1e-9,axis=1)&np.all(self.hi>=np.minimum(a,b)-1e-9,axis=1))
        w0=self.bary(a,ids);w1=self.bary(b,ids);d=w1-w0
        low=np.zeros(len(ids));high=np.ones(len(ids));valid=np.ones(len(ids),dtype=bool)
        for j in range(3):
            up=d[:,j]>1e-14;down=d[:,j]<-1e-14;flat=~(up|down)
            low[up]=np.maximum(low[up],-w0[up,j]/d[up,j])
            high[down]=np.minimum(high[down],-w0[down,j]/d[down,j])
            valid &= ~(flat & (w0[:,j]<-1e-9))
        valid &= (high-low)>1e-10
        spans=sorted(zip(low[valid],high[valid])); reach=0.
        for lo,hi in spans:
            if lo>reach+1e-8:raise ValueError('Terrain coverage gap on wall trace')
            reach=max(reach,hi)
        if reach<1-1e-8:raise ValueError('Terrain ends before wall trace')
        ts=np.unique(np.clip(np.r_[0.,1.,low[valid],high[valid]],0.,1.))
        z=self.heights(a+ts[:,None]*(b-a))
        if not np.isfinite(z).all():raise ValueError('Uncovered terrain boundary')
        return ts,z
    def polygon_extrema(self,polygon):
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        lo=np.asarray(polygon.bounds[:2]);hi=np.asarray(polygon.bounds[2:])
        ids=np.flatnonzero(np.all(self.lo<=hi,axis=1)&np.all(self.hi>=lo,axis=1));pieces=[];xyz=[]
        for i in ids:
            q=polygon.intersection(Polygon(self.tri[i,:,:2]))
            if q.is_empty or q.area<1e-14:continue
            polys=[q] if q.geom_type=='Polygon' else [x for x in getattr(q,'geoms',[]) if x.geom_type=='Polygon']
            for poly in polys:
                pieces.append(poly)
                for x,y in poly.exterior.coords:
                    z=float(np.sum(self.bary([x,y],np.array([i]))[0]*self.tri[i,:,2]));xyz.append((x,y,z))
        if not xyz:raise ValueError('Footing outside terrain')
        covered=unary_union(pieces).area; gap=polygon.difference(unary_union(pieces)).area
        if gap>max(1e-10,polygon.area*1e-9):raise ValueError('Incomplete footprint terrain coverage')
        p=np.array(xyz)
        return {'min_point_m':p[p[:,2].argmin()].tolist(),'max_point_m':p[p[:,2].argmax()].tolist(),'coverage_area_m2':covered,'gap_area_m2':gap}

def lower_envelope(profiles):
    ts=np.unique(np.concatenate([v[0] for v in profiles])); values=[np.interp(ts,*p) for p in profiles]
    extra=[]
    for i in range(len(values)):
        for j in range(i):
            d=values[i]-values[j]
            for k in np.flatnonzero(d[:-1]*d[1:]<0):extra.append(ts[k]+(ts[k+1]-ts[k])*(-d[k])/(d[k+1]-d[k]))
    ts=np.unique(np.r_[ts,extra]);z=np.min([np.interp(ts,*p) for p in profiles],axis=0)
    return ts,z

def step_options(stations,ground,minimum_cover,increment,grid_origin=0.):
    """Highest grid-aligned horizontal benches under the exact ground envelope.

    Input and output use one explicit common length unit. No minimum tread is
    assumed. Threshold crossings are included, including short reversals.
    """
    s=np.asarray(stations);z=np.asarray(ground); cuts=list(s)
    for a,b,za,zb in zip(s[:-1],s[1:],z[:-1],z[1:]):
        if abs(zb-za)<1e-12:continue
        low,high=sorted(((za-minimum_cover-grid_origin)/increment,(zb-minimum_cover-grid_origin)/increment))
        for k in range(math.floor(low)+1,math.ceil(high)):
            elev=grid_origin+k*increment+minimum_cover
            cuts.append(a+(b-a)*(elev-za)/(zb-za))
    cuts=np.unique(cuts);segments=[]
    for a,b in zip(cuts[:-1],cuts[1:]):
        if b-a<1e-9:continue
        zm=float(np.interp((a+b)/2,s,z)); level=grid_origin+math.floor((zm-minimum_cover-grid_origin)/increment)*increment
        if segments and abs(segments[-1]['top']-level)<1e-10:segments[-1]['end']=float(b)
        else:segments.append({'start':float(a),'end':float(b),'top':float(level)})
    for seg in segments:
        mask=(s>seg['start'])&(s<seg['end']); ss=np.r_[seg['start'],s[mask],seg['end']]
        cover=np.interp(ss,s,z)-seg['top'];seg['length']=seg['end']-seg['start'];seg['min_cover']=float(min(cover));seg['max_cover']=float(max(cover))
        if seg['min_cover']<minimum_cover-1e-9:raise ValueError('Generated option violates minimum cover')
    return segments

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def read_obj(path):
    vertices=[]; groups={}; group='__ungrouped__'; material=''
    with Path(path).open(encoding='utf-8-sig') as f:
        for line in f:
            a=line.split()
            if not a: continue
            if a[0]=='v':
                vertices.append(tuple(map(float,a[1:4])))
            elif a[0]=='g': group=' '.join(a[1:])
            elif a[0]=='usemtl': material=' '.join(a[1:])
            elif a[0] in ('f','l','p'):
                ids=[]
                for v in a[1:]:
                    n=int(v.split('/')[0]); ids.append(n-1 if n>0 else len(vertices)+n)
                entry=groups.setdefault((group,material),{'f':[],'l':[],'p':[]})
                entry[a[0]].append(ids)
    v=np.asarray(vertices,dtype=np.float64)
    if not np.isfinite(v).all(): raise ValueError('Nonfinite OBJ coordinates')
    for g in groups.values():
        ids=[i for typ in g.values() for face in typ for i in face]
        if ids and (min(ids)<0 or max(ids)>=len(v)): raise ValueError('OBJ index out of range')
    return v,groups

def obj_inventory(path):
    v,groups=read_obj(path); rows=[]
    for (g,m),data in groups.items():
        ids=np.unique([i for typ in data.values() for face in typ for i in face])
        p=v[ids]
        rows.append({'group':g,'material':m,'vertices':len(p),
                     'faces':len(data['f']),'lines':len(data['l']),
                     'bounds':[p.min(axis=0).tolist(),p.max(axis=0).tolist()]})
    return {'vertices':len(v),'groups':rows}

def read_landxml(path, surface_name):
    points=[]; ids=[]; faces=[]; hidden=0; units=None; active=False; surfaces=[]
    for event,e in ET.iterparse(path,events=('start','end')):
        tag=e.tag.rsplit('}',1)[-1]
        if event=='start':
            if tag in ('Imperial','Metric'): units=e.attrib.get('linearUnit')
            if tag=='Surface':
                name=e.attrib.get('name'); surfaces.append(name); active=name==surface_name
            continue
        if active and tag=='P':
            p=list(map(float,e.text.split()))
            if len(p)!=3: raise ValueError('Expected N E Z point')
            ids.append(int(e.attrib['id'])); points.append((p[1],p[0],p[2]))
        elif active and tag=='F':
            f=list(map(int,e.text.split()))
            if len(f)!=3: raise ValueError('Expected triangular LandXML face')
            if e.attrib.get('i')=='1': hidden+=1
            else: faces.append(f)
        elif tag=='Surface': active=False
        e.clear()
    if surfaces.count(surface_name)!=1: raise ValueError('Terrain name missing or ambiguous')
    if units not in ('USSurveyFoot','foot','meter','millimeter'): raise ValueError('Unsupported terrain units '+str(units))
    if not points or not faces: raise ValueError('LandXML must contain vertices AND faces')
    if len(set(ids))!=len(ids): raise ValueError('Duplicate LandXML point IDs')
    index={x:i for i,x in enumerate(ids)}
    faces=np.asarray([[index[i] for i in f] for f in faces],dtype=np.int64)
    points=np.asarray(points,dtype=np.float64)
    if not np.isfinite(points).all(): raise ValueError('Nonfinite terrain coordinates')
    return points,faces,{'surface':surface_name,'units':units,'vertices':len(points),'triangles':len(faces),'hidden_triangles_excluded':hidden,'surfaces':surfaces}
