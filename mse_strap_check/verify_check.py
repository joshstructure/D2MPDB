"""Independent checks of native expression definitions; not native recalculation."""
from pathlib import Path
import sys,math,re,json,random
from lxml import etree as E
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from expression_check import Engine,Q,parse

class Extended(Engine):
    def get(self,name):
        if name=='null':return None
        return super().get(name)
    def eval(self,a,scope):
        if a[0]=='call' and a[1] in ['Atan','Asin']:
            q=self.eval(a[2][0],scope);assert q.d==(0,0,0)
            return Q((math.atan if a[1]=='Atan' else math.asin)(q.v),(0,0,1))
        return super().eval(a,scope)

source=json.loads((HERE/'formulas.json').read_text())
names={r:{x['formula'].split(' = ')[0].split('(')[0] for x in source if x['report']==r} for r in {x['report'] for x in source}}
definitions=[]
for item in source:
    r=item['report'];lhs,rhs=item['formula'].split(' = ',1)
    fargs=set(lhs.split('(',1)[1][:-1].split(',')) if '(' in lhs else set()
    # Only qualify identifiers, never words in string literals or existing qualified names.
    pieces=re.split(r'("[^"]*")',rhs)
    for j in range(0,len(pieces),2):
        pieces[j]=re.sub(r'(?<![\w.])([A-Za-z][A-Za-z0-9]*)(?![\w.])',lambda m:r+'.'+m[1] if m[1] in names[r] and m[1] not in fargs else m[1],pieces[j])
    definitions.append({'formula':r+'.'+lhs+' = '+''.join(pieces)})
engine=Extended(definitions)
values=engine.all()
def scalar(k,unit=1):return engine.get(k).v/unit

# Independent 2D segment-to-polygon calculation by orientation + segment endpoints.
def orient(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def onseg(p,a,b):return min(a[0],b[0])-1e-10<=p[0]<=max(a[0],b[0])+1e-10 and min(a[1],b[1])-1e-10<=p[1]<=max(a[1],b[1])+1e-10
def cross(a,b,c,d):
    u,v,w,x=orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)
    if u*v<0 and w*x<0:return True
    return any(abs(z)<1e-10 and onseg(p,q,r) for z,p,q,r in [(u,c,a,b),(v,d,a,b),(w,a,c,d),(x,b,c,d)])
def pointseg(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];n=dx*dx+dy*dy
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/n)) if n else 0
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
def dist(a,b,rect):
    x0,x1,y0,y1=rect;ps=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    if any(x0<=p[0]<=x1 and y0<=p[1]<=y1 for p in [a,b]):return 0
    if any(cross(a,b,c,d) for c,d in zip(ps,ps[1:]+ps[:1])):return 0
    return min([pointseg(p,a,b) for p in ps]+[pointseg(p,c,d) for p in [a,b] for c,d in zip(ps,ps[1:]+ps[:1])])

checks=[]
rng=random.Random(4823)
for i in range(120):
    vals=[rng.uniform(-8,8) for _ in range(4)];x,y=rng.uniform(-4,4),rng.uniform(-4,4)
    box=[x,x+rng.uniform(.1,4),y,y+rng.uniform(.1,4)]
    if i<4: vals=[[0,0,0,8],[0,0,8,0],[0,0,0,0],[-10,-10,10,10]][i]
    call=('call','RouteMath.Dist',[('bin','*',('num',v),('name','ft')) for v in vals+box])
    actual=engine.eval(call,{}).v/12;expected=dist(tuple(vals[:2]),tuple(vals[2:]),box)
    assert abs(actual-expected)<1e-8,(actual,expected,vals,box)
checks.append('120 independent distance cases, including axis-parallel / zero-length / crossing segments')
results=[]
for r in ['EndBentOne','EndBentTwo']:
    for wi in range(1,4):
        for j in range(1,5):
            q=f'{r}.C{wi}{j}';a=(scalar(q+'x',12),scalar(q+'y',12));env=scalar(r+'.Envelope',12)
            d=scalar(q+'d',12);half=scalar(r+'.Half',12)
            # Independent tangent equation: line width capacity from corner normal distance.
            maxw=max(0,2*((d-half)*math.sin(math.pi/12)-half*math.cos(math.pi/12))*12)
            assert abs(maxw-scalar(q+'width'))<1e-8
            for sign in ['Plus','Minus']:
                b=(scalar(q+sign+'x',12),scalar(q+sign+'y',12))
                pd=min(dist(a,b,[scalar(r+f'.P{k}x',12)-env,scalar(r+f'.P{k}x',12)+env,scalar(r+f'.P{k}y',12)-env,scalar(r+f'.P{k}y',12)+env]) for k in range(1,5))*12-scalar('Basis.Width')/2
                assert abs(pd-scalar(q+sign+'Pile'))<1e-7
                wd=min(dist(a,b,[scalar(r+f'.W{k}xmin',12),scalar(r+f'.W{k}xmax',12),scalar(r+f'.W{k}ymin',12),scalar(r+f'.W{k}ymax',12)]) for k in range(1,6) if k!=wi)*12-scalar('Basis.Width')/2
                assert abs(wd-scalar(q+sign+'Wall'))<1e-7
            results.append({'bent':r,'wall':wi,'pile':j,'d_ft':d,'max_width_in':maxw,'required_angle_deg':scalar(q+'theta',math.pi/180),'plus':engine.get(q+'PlusStatus'),'minus':engine.get(q+'MinusStatus'),'plus_edge_gap_in':scalar(q+'PlusPile'),'minus_edge_gap_in':scalar(q+'MinusPile')})
checks.append('All 48 signed routes independently checked against every pile and five wall rectangles per bent')

# Expected failure / threshold / tolerance behavior.
scenarios=[]
for name,overrides in [
 ('zero-width',{'Basis.Width':Q(0,(1,0,0))}),
 ('one-inch-strip',{'Basis.Width':Q(1,(1,0,0))}),
 ('three-inch-tolerance',{'Basis.Tolerance':Q(3,(1,0,0))}),
 ('layer-above-wall',{'Basis.Layer':Q(42*12,(1,0,0))}),
 ('invalid-angle',{'Basis.TestAngle':Q(math.radians(16),(0,0,1))}),
 ('short-strap',{'EndBentOne.LengthOverride':Q(2*12,(1,0,0))})]:
    e=Extended(definitions,overrides=overrides);front=e.get('EndBentOne.C12PlusStatus');scenarios.append({'case':name,'EndBentOne_front_P2_plus':front})
    assert front==('PASS' if name in ['zero-width','one-inch-strip'] else 'FAIL'),(name,front)
for r in ['EndBentOne','EndBentTwo']:
    d=scalar(r+'.C12d');a=scalar(r+'.Envelope');rr=scalar('Basis.Width')/2
    theta=scalar(r+'.C12theta')
    assert abs((d-a)*math.sin(theta)-a*math.cos(theta)-rr)<1e-8
checks.append('Tangency identity and six meaningful width/tolerance/layer/angle/length scenarios')
tree=E.parse(str(HERE/'MSE Strap Clearance - Both End Bents.bpad'))
assert not tree.findall('.//error')
names_all=[el.get('name') for el in tree.getroot() if el.get('name')]
assert len(names_all)==len(set(names_all))
assert all(not re.fullmatch(r'[A-Za-z]+[1-9][0-9]*',name) for name in names_all), 'Report names must not be cell addresses'
assert not any(re.search(r'\b(?:ATan|ASin)\s*\(',el.get('formula','')) for el in tree.iter()), 'Native inverse-trig names are case-sensitive'
checks.append('Native function capitalization and report names avoid the observed Blockpad evaluation errors')
summary={r:{'front_line_gap_in':scalar(r+'.FrontGap'),'front_max_strip_width_in':scalar(r+'.FrontMaxWidth'),'front_cap_setback_in':scalar(r+'.CapSetback1'),'left_cap_setback_in':scalar(r+'.CapSetback2'),'right_cap_setback_in':scalar(r+'.CapSetback3'),'left_nearest_required_deg':scalar(r+'.C21theta',math.pi/180),'right_nearest_required_deg':scalar(r+'.C34theta',math.pi/180)} for r in ['EndBentOne','EndBentTwo']}
record={'native_recalculation':'not established by this script','definitions_evaluated':len(engine.defs),'checks':checks,'scenarios':scenarios,'summary':summary,'routes':results}
(HERE/'verification.json').write_text(json.dumps(record,indent=2))
serial={k:({'value':v.v,'dimensions':v.d} if isinstance(v,Q) else v) for k,v in values.items()}
(HERE/'evaluated_values.json').write_text(json.dumps(serial,indent=2))
print(json.dumps({'definitions':len(engine.defs),'summary':summary,'scenarios':scenarios},indent=2))
