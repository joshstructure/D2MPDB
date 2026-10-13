"""Independent equations, geometric boundary checks, and native cache comparison."""
from pathlib import Path
from lxml import etree as E
import sys,json,math,re,random,hashlib,argparse
ROOT=Path(__file__).resolve().parents[2];TASK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'mse_strap_check'))
from expression_check import Engine,Q,parse

needed={'EndBentCap_width','EndBent_pileCount','EndBent_pileWidth','EndBent_pileSpacing','EndBent_edgeClear','EndBent_pileTolerance','EndBent_endDetail','EndBent_endFace','EndBent_endCenter','EndBentCap_length'}
upstream=[]
geo=E.parse(str(TASK/'base.bpad')).find("report[@name='BridgeGeometry_2Beam']")
for el in geo.findall('.//dynexp'):
    f=el.get('formula',''); lhs=f.split(' = ')[0]
    if lhs in needed:
        rhs=f.split(' = ',1)[1]
        rhs=re.sub(r'(?<![\w.])([A-Za-z_][A-Za-z_0-9]*)(?![\w.])',lambda m:'BridgeGeometry_2Beam.'+m[1] if m[1] in needed else m[1],rhs)
        upstream.append({'formula':'BridgeGeometry_2Beam.'+lhs+' = '+rhs})
assert len(upstream)==len(needed)
definitions=json.loads((TASK/'definitions.json').read_text(encoding='utf-8'))
engine=Engine(upstream+definitions);values=engine.all()
def evaluate(f):
    f=f.replace('MSEWallExclusion.','')
    f=re.sub(r'\s+to\s+[A-Za-z0-9^*/ ]+$','',f)
    return engine.eval(parse(f),{})
def number(f,unit='in'):
    return evaluate(f).v/evaluate('1 '+unit).v
def display(f):
    val=evaluate(f)
    if isinstance(val,bool):return str(val).lower()
    if not isinstance(val,Q):return val
    target=f.split(' to ')[-1] if ' to ' in f else ('in' if val.d==(1,0,0) else 'deg' if val.d==(0,0,1) else None)
    if target=='ft in':target='in'
    return engine.text(val,target,3)

def checks():
    rng=random.Random(9009)
    for i in range(200):
        h,w,c,a=[rng.uniform(*r) for r in [(6,18),(0,4),(0,2),(3,40)]]
        alpha=math.radians(a)
        setback=(h*math.cos(alpha)+w/2+c)/math.sin(alpha)
        for sign in [-1,1]:
            corner=(sign*h,setback)
            distance=abs(corner[1]*math.sin(sign*alpha)-corner[0]*math.cos(sign*alpha))
            assert math.isclose(distance,w/2+c,abs_tol=1e-10)
            assert (setback-.01)*math.sin(alpha)-h*math.cos(alpha)<w/2+c
    h=number('Half'); w=number('Width'); c=number('Clear'); a=math.radians(number(chr(945),'deg'))
    s=number('MinClear');lay=number('LayoutClear');side=number('SideClear');inc=number('RoundStep')
    assert math.isclose(s*math.sin(a)-h*math.cos(a),w/2+c,abs_tol=1e-10)
    assert lay>=s and lay-s<inc and math.isclose(lay/inc,round(lay/inc),abs_tol=1e-9)
    assert side==24 and math.isclose(h,number('PileSize')/2)
    assert math.isclose(number('FrontExtent'),h+lay) and math.isclose(number('SideExtent'),h+side)
    scenarios=[]
    for name,overrides in [('one-inch-strap',{'Width':Q(1,(1,0,0))}),('one-inch-gap',{'Clear':Q(1,(1,0,0))}),('ten-degree-skew',{chr(945):Q(math.radians(10),(0,0,1))}),('twenty-seven-degree-skew',{chr(945):Q(math.radians(27),(0,0,1))}),('large-placement-tolerance',{'BridgeGeometry_2Beam.EndBent_pileTolerance':Q(12,(1,0,0))})]:
        e=Engine(upstream+definitions,overrides=overrides)
        sv=e.get('MinClear').v
        assert e.get('SideClear').v==24
        if name in ['one-inch-gap','ten-degree-skew']:assert sv>s
        elif name=='large-placement-tolerance':assert sv==s and e.get('LayoutClear').v==lay
        else:assert sv<s
        scenarios.append({'case':name,'front_minimum_in':sv,'side_minimum_in':24,'skew_basis':e.get('SkewStatus')})
    snap=json.loads((ROOT/'mse_strap_check/layout_snapshot.json').read_text())
    walls={w['id']:w for w in snap['walls']}; results=[]
    for bi,b in enumerate(snap['bents'],1):
        for j,pile in enumerate(b['piles'],1):
            for ax,i,sg in [('x',0,1),('y',1,1 if bi==1 else -1)]:
                assert abs(number(f'Bent{bi}P{j}{ax}','ft')-(pile['center'][i]-b['center'][i])*sg)<1e-9
        for wi,wid in enumerate(['A5','A6','A7'] if bi==1 else ['B1','B6','B7'],1):
            wall=walls[wid];required=lay if wi==1 else side
            gaps=[sum((p['center'][k]-wall['start'][k])*-wall['outward'][k] for k in [0,1])*12-h for p in b['piles']]
            gap=min(gaps);extra=max(0,required-gap)
            assert math.isclose(gap,number(f'Bent{bi}W{wi}Gap'),abs_tol=1e-8)
            assert math.isclose(extra,number(f'Bent{bi}W{wi}Extra'),abs_tol=1e-8)
            assert engine.get(f'Bent{bi}W{wi}Status')==('SHORTFALL' if extra>0 else 'MEETS CLEAR')
            results.append({'bent':bi,'wall':wid,'basis':'front strap' if wi==1 else 'specified side offset','required_in':required,'current_gap_in':gap,'extra_setback_in':extra})
    return {'front_minimum_in':s,'front_adopted_in':lay,'side_minimum_in':side,'alpha_deg':number(chr(945),'deg'),'pile_tolerance_included':False,'nominal_pile_width_in':number('PileSize'),'checks':['400 independent corner/ray boundaries for both skew directions; 0.01 inch less fails','Upward quarter-inch rounding','Side criteria independent of alpha/strap width','12-inch shared pile-tolerance sensitivity leaves front/side setbacks unchanged','All eight CAD centers and six independent wall-face gaps/shortfalls'], 'scenarios':scenarios,'walls':results}

def cache():
    tree=E.parse(str(TASK/'components/000.xml'))
    for el in tree.xpath('.//dynexp | .//c[@formula] | .//planecontainer[@formula]'):
        f=el.get('formula');val=engine.get(f.split(' = ')[0]) if ' = ' in f else evaluate(f)
        shown=display(f.split(' = ')[0]+(' to '+f.split(' to ')[-1] if ' to ' in f else '')) if ' = ' in f else display(f)
        for child in list(el):
            if child.tag in ['expresult','num','bool','textvalue','error']:el.remove(child)
        if el.tag=='dynexp':E.SubElement(el,'expresult').text=' = '+shown
        else:E.SubElement(el,'bool' if isinstance(val,bool) else 'num' if isinstance(val,Q) else 'textvalue').text=shown
    (TASK/'components/000.xml').write_bytes(E.tostring(tree.getroot(),encoding='utf-8',pretty_print=True).rstrip())

def native(path):
    tree=E.parse(str(path)); report=tree.find("report[@name='MSEWallExclusion']")
    assert report is not None
    assert not report.findall('.//error')
    assert not any('[Error]' in ''.join(el.itertext()) for el in report.findall('.//expresult'))
    built=E.parse(str(TASK/'components/000.xml')).getroot()
    assert [e.get('formula') for e in report.iter() if e.get('formula')]==[e.get('formula') for e in built.iter() if e.get('formula')]
    compared=0
    for el in report.xpath('.//c[@formula] | .//planecontainer[@formula]'):
        expected=evaluate(el.get('formula'))
        if isinstance(expected,Q):
            actual=evaluate(el.findtext('num'))
            assert actual.d==expected.d and math.isclose(actual.v,expected.v,rel_tol=1e-10,abs_tol=1e-8),(el.get('formula'),actual,expected)
        else:assert el.findtext('textvalue')==expected
        compared+=1
    return {'native_file':str(path),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'native_module_errors':0,'native_table_and_dimension_values_compared':compared}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--cache',action='store_true');ap.add_argument('--native',type=Path);args=ap.parse_args()
    record=checks()
    if args.cache:cache()
    if args.native:record['native']=native(args.native)
    (TASK/'independent-checks.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))
