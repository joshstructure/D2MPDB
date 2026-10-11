"""Read-only native saved BRep ramp PGL QC. Run with FreeCAD Python."""
import json, zipfile, hashlib, math, csv
from pathlib import Path
import xml.etree.ElementTree as ET
import FreeCAD as App
import Part
import numpy as np
from numpy.polynomial import Polynomial as P
from scipy.integrate import quad
ROOT=Path(__file__).resolve().parents[1]

def grade_data(poles):
    a=np.array(poles,float)
    co=[a[0],3*(a[1]-a[0]),3*(a[2]-2*a[1]+a[0]),a[3]-3*a[2]+3*a[1]-a[0]]
    xyz=[P([c[k] for c in co]) for k in range(3)]
    dx,dy,dz=[v.deriv() for v in xyz]
    speed2=dx*dx+dy*dy
    critical=dz.deriv()*speed2-dz*(dx*dx.deriv()+dy*dy.deriv())
    ts=[0.,1.]+[float(r.real) for r in critical.roots() if abs(r.imag)<1e-8 and 0<r.real<1]
    grade=lambda t: float(100*dz(t)/math.sqrt(speed2(t)))
    run=lambda t: quad(lambda u:math.sqrt(speed2(u)),0,t,epsabs=1e-8)[0]
    return xyz,grade,run,sorted(set(ts))

def analyze(source,output,tolerance='0.001 in'):
    source=Path(source); output=Path(output);output.mkdir(parents=True,exist_ok=True)
    before=hashlib.sha256(source.read_bytes()).hexdigest();tol=App.Units.Quantity(tolerance).Value
    z=zipfile.ZipFile(source);root=ET.fromstring(z.read('Document.xml'))
    obs={o.get('name'):{p.get('name'):p for p in o.find('Properties')} for o in root.find('ObjectData').findall('Object')}
    def shape(name):
        s=Part.Shape();s.importBrepFromString(z.read(obs[name]['Shape'].find('Part').get('file')).decode());return s
    mapping=[e.get('value') for e in obs['CompletePGLTrace']['SegmentSlabs'].find('StringList')]
    slabs={n:shape(n) for n in set(mapping)}
    tops={n:Part.makeCompound([f for f in s.Faces if f.normalAt(sum(f.ParameterRange[:2])/2,sum(f.ParameterRange[2:])/2).z>.5]) for n,s in slabs.items()}
    rows=[];nodes=[];samples=[];checks=[];offset=0
    for side in 'AB':
        sh=shape('Ramp'+side+'PGL');station=0.;prev=None
        checks.append({'check':side+' valid single open wire','pass':sh.isValid() and len(sh.Wires)==1 and not sh.isClosed()})
        for i,e in enumerate(sh.Edges):
            assert isinstance(e.Curve,Part.BezierCurve) and e.Curve.Degree==3 and not e.Curve.isRational()
            assert abs(e.FirstParameter)<1e-12 and abs(e.LastParameter-1)<1e-12
            xyz,g,run,ts=grade_data([[p.x,p.y,p.z] for p in e.Curve.getPoles()]);a=e.valueAt(0);b=e.valueAt(1)
            slab=mapping[offset+i];h=run(1);dz=b.z-a.z;sid=f'{side}-S{i+1:02d}'
            if prev is not None:checks.append({'check':sid+' continuity','pass':prev.distanceToPoint(a)<=tol,'gap_mm':prev.distanceToPoint(a)})
            if i==0:nodes.append({'id':f'{side}-P00','side':side,'station_ft':0.,'x_ft':a.x/304.8,'y_ft':a.y/304.8,'z_ft':a.z/304.8})
            errors=[];tangent_errors=[]
            for t in sorted(set(np.linspace(0,1,41).tolist()+ts)):
                p=e.valueAt(t);d=Part.Vertex(p).distToShape(tops[slab])[0];errors.append(d)
                v=e.tangentAt(t);tangent_errors.append(abs(g(t)-100*v.z/math.hypot(v.x,v.y)))
                samples.append({'segment':sid,'t':t,'station_ft':(station+run(t))/304.8,'z_ft':p.z/304.8,'grade_percent':g(t),'top_distance_in':d/25.4})
            lo=min(ts,key=g);hi=max(ts,key=g)
            row={'id':sid,'side':side,'edge':i+1,'slab':slab,'start':nodes[-1]['id'],'end':f'{side}-P{i+1:02d}','z_start_ft':a.z/304.8,'z_end_ft':b.z/304.8,'rise_ft':dz/304.8,'horizontal_run_ft':h/304.8,'average_percent':100*dz/h,'minimum_percent':g(lo),'maximum_percent':g(hi),'max_at_station_ft':(station+run(hi))/304.8,'max_at_z_ft':float(xyz[2](hi))/304.8,'max_t':hi,'top_error_in':max(errors)/25.4,'station_start_ft':station/304.8,'station_end_ft':(station+h)/304.8}
            rows.append(row)
            checks.extend([{'check':sid+' on physical slab upper faces (41 samples plus extrema)','pass':max(errors)<=tol,'max_error_in':max(errors)/25.4},{'check':sid+' analytic vs native tangent','pass':max(tangent_errors)<1e-7,'error_percent':max(tangent_errors)},{'check':sid+' straight horizontal projection','pass':abs(h-math.hypot(b.x-a.x,b.y-a.y))<tol}])
            station+=h;nodes.append({'id':row['end'],'side':side,'station_ft':station/304.8,'x_ft':b.x/304.8,'y_ft':b.y/304.8,'z_ft':b.z/304.8});prev=b
        offset+=len(sh.Edges)
    checks.append({'check':'all mapped edges audited','pass':offset==len(mapping)==27})
    checks.append({'check':'source byte-for-byte preserved','pass':hashlib.sha256(source.read_bytes()).hexdigest()==before})
    report={'source':str(source),'sha256':before,'date':'2026-10-05','units':'international model feet (304.8 mm/ft)','direction':'entrance toward bridge; positive = rising','tolerance':tolerance,'checks':checks,'segments':rows,'nodes':nodes,'samples':samples,'slab_bounds':{n:[s.BoundBox.XMin/304.8,s.BoundBox.YMin/304.8,s.BoundBox.XMax/304.8,s.BoundBox.YMax/304.8] for n,s in slabs.items()}}
    (output/'qc.json').write_text(json.dumps(report,indent=2))
    for key in ['segments','nodes','samples']:
        with (output/(key+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(report[key][0]));w.writeheader();w.writerows(report[key])
    print(json.dumps({'checks':len(checks),'failures':[c for c in checks if not c['pass']],'grades':[{k:r[k] for k in ['id','average_percent','minimum_percent','maximum_percent','top_error_in']} for r in rows]},indent=2))
    return report
if __name__=='__main__':
    analyze(ROOT/'Models/B4 Pedestrian Bridge and Ramps - Pond14D.FCStd',ROOT/'reports/pgl-slope-qc-20261005')
