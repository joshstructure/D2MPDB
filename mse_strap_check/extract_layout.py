"""Read-only extraction of the selected model's saved native properties."""
from pathlib import Path
import xml.etree.ElementTree as E
import zipfile, struct, json, math, hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
MODEL=next((ROOT/'project_current/geometry/freecad').glob('*.FCStd'))
z=zipfile.ZipFile(MODEL)
doc=E.fromstring(z.read('Document.xml'))
objects={o.get('name'):{p.get('name'):p[0] for p in o.find('Properties') if p.tag=='Property'} for o in doc.find('ObjectData')}
def scalar(obj,key): return float(objects[obj][key].get('value'))
def vec(obj,key):return [float(objects[obj][key].get('value'+k)) for k in 'XYZ']
def vectors(obj,key):
    b=z.read(objects[obj][key].get('file'));n=struct.unpack('<I',b[:4])[0]
    assert len(b)==4+n*24
    return [list(struct.unpack_from('<ddd',b,4+24*i)) for i in range(n)]
def ft(v):return [n/304.8 for n in v]

frame=objects['BridgePGL']['Frame']
a=float(frame.get('A'));c,s=math.cos(a),math.sin(a)
origin=[float(frame.get(k))/304.8 for k in ['Px','Py']]
def world(x,y): return [origin[0]+c*x-s*y,origin[1]+s*x+c*y]
geometry=json.loads((ROOT/'project_current/geometry/freecad/evidence/2026-10-12-cambers/notebook-geometry.json').read_text())
config=geometry['configuration']
result={'model_path':str(MODEL.relative_to(ROOT)),'model_sha256':hashlib.sha256(MODEL.read_bytes()).hexdigest(),
        'journal_sha256':hashlib.sha256((ROOT/'journal/D2_I95_Project_Journal.bpad').read_bytes()).hexdigest(),
        'coordinate_unit':'ft','frame_angle_deg':math.degrees(a),'frame_origin_ft':origin,
        'wall_thickness_ft':scalar('MSEInputs','WallThickness')/304.8,
        'pad_width_ft':scalar('MSEInputs','FootingWidth')/304.8,'walls':[], 'bents':[],
        'snapshot_note':'Saved model properties, not a live file link. Source model unchanged.'}
for name in objects:
    if name.startswith('Wall') and name.endswith('Profile'):
        start=ft(vec(name,'Start'));t=vec(name,'Tangent');n=vec(name,'Normal');bc=vectors(name,'BaseControls');top=vectors(name,'ComputedTop');length=max(p[0] for p in bc)/304.8
        result['walls'].append({'id':name[4:-7], 'start':start[:2],'end':[start[i]+t[i]*length for i in range(2)],'tangent':t[:2],'outward':n[:2], 'length':length,'base_controls':[[p[0]/304.8,p[2]/304.8] for p in bc],'top_controls':[[p[0]/304.8,p[2]/304.8] for p in top]})
for label,support_name in [('EB1','End Bent 1'),('EB2','End Bent 2')]:
    support=next(s for s in geometry['geometry']['supports'] if s['name']==support_name)
    station=support['station']
    x=station-config['profile']['start_sta_ft'];ctr=world(x,0)
    L=scalar('BridgePGL','EndCapLength')/304.8;W=scalar('BridgePGL','EndCapWidth')/304.8
    spacing=scalar('BridgePGL','EndPileSpacing')/304.8;size=scalar('BridgePGL','EndPileSize')/304.8
    cap=[world(x+dx,dy) for dx,dy in [(-W/2,-L/2),(W/2,-L/2),(W/2,L/2),(-W/2,L/2)]]
    piles=[{'id':f'P{i+1}', 'center':world(x,(i-1.5)*spacing),'size':size} for i in range(4)]
    nearby=[]
    for w in result['walls']:
        mid=[(w['start'][i]+w['end'][i])/2 for i in range(2)]
        u=sum((ctr[i]-w['start'][i])*w['tangent'][i] for i in range(2))
        d=sum((ctr[i]-w['start'][i])*-w['outward'][i] for i in range(2))
        if -L/2-2<u<w['length']+L/2+2 and -1<d<15: nearby.append(w['id'])
    cap_section=next(o for o in support['components'] if o['kind']=='Cap')
    cap_bottom=min(v[1] for v in cap_section['xy'])
    result['bents'].append({'id':label,'station':station,'center':ctr,'cap':cap,'cap_length':L,'cap_width':W,'cap_depth':scalar('BridgePGL','EndCapDepth')/304.8,'cap_bottom':cap_bottom,'pile_top':cap_bottom+scalar('BridgePGL','EndPileEmbedment')/304.8,'trial_pile_length':scalar('BridgePGL','TrialPileLength')/304.8,'piles':piles,'nearby_walls':nearby})
(HERE/'layout_snapshot.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'bents':result['bents'],'walls':[{k:w[k] for k in ['id','start','end','outward']} for w in result['walls']]},indent=2))
