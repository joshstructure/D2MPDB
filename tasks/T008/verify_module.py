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
    rng=random.Random(8008)
    # Independent geometric cross product: ray from wall anchor to +skew direction.
    for i in range(200):
        h,t,w,c,a=[rng.uniform(*limits) for limits in [(6,18),(0,4),(0,4),(0,2),(3,15)]]
        alpha=math.radians(a)
        setback=t+((h+t)*math.cos(alpha)+w/2+c)/math.sin(alpha)
        corner=(h+t,setback-t)
        cross=corner[1]*math.sin(alpha)-corner[0]*math.cos(alpha)
        assert abs(cross-w/2-c)<1e-10
        assert (corner[1]-.01)*math.sin(alpha)-corner[0]*math.cos(alpha)<w/2+c
    h=number('Half'); t=number('Tolerance'); w=number('Width'); c=number('Clear'); a=math.radians(number('α','deg'))
    s=number('MinClear'); lay=number('LayoutClear'); inc=number('RoundStep')
    assert abs((s-t)*math.sin(a)-(h+t)*math.cos(a)-w/2-c)<1e-10
    assert lay>=s and lay-s<inc and math.isclose(lay/inc,round(lay/inc),abs_tol=1e-9)
    assert abs(number('BoxSide')-2*(h+lay))<1e-10
    assert abs(number('MinClear')-number('NominalClear')-t*(1+1/math.tan(a)))<1e-10
    scenarios=[]
    for name,overrides in [('zero-tolerance',{'Tolerance':Q(0,(1,0,0))}),('one-inch-strap',{'Width':Q(1,(1,0,0))}),('one-inch-gap',{'Clear':Q(1,(1,0,0))}),('ten-degree-skew',{'α':Q(math.radians(10),(0,0,1))}),('zero-angle',{'α':Q(0,(0,0,1))}),('excess-skew',{'α':Q(math.radians(16),(0,0,1))})]:
        e=Engine(upstream+definitions,overrides=overrides)
        state=e.get('InputStatus');sv=e.get('MinClear').v
        if name in ['zero-angle','excess-skew']:assert state.startswith('INVALID')
        elif name in ['one-inch-gap','ten-degree-skew']:assert sv>s
        else:assert sv<s
        scenarios.append({'case':name,'minimum_face_clear_in':sv,'state':state})
    snap=json.loads((ROOT/'mse_strap_check/layout_snapshot.json').read_text())
    for bi,b in enumerate(snap['bents'],1):
        for j,pile in enumerate(b['piles'],1):
            for ax,i,sg in [('x',0,1),('y',1,1 if bi==1 else -1)]:
                assert abs(number(f'Bent{bi}P{j}{ax}','ft')-(pile['center'][i]-b['center'][i])*sg)<1e-9
        # Independent side coordinates, then finite axis-aligned line clipping.
        box=[number(f'Bent{bi}'+k,'ft') for k in ['Left','Right','Bottom','Top']]
        for wi in range(1,4):
            wp=f'Bent{bi}W{wi}'
            x1,y1,x2,y2=[number(wp+k,'ft') for k in ['x','y','xend','yend']]
            hit=(box[0]<x1<box[1] and max(y1,y2)>box[2] and min(y1,y2)<box[3]) if abs(x2-x1)<1e-10 else (box[2]<y1<box[3] and max(x1,x2)>box[0] and min(x1,x2)<box[1])
            assert engine.get(wp+'Hit')==hit
    return {'minimum_nominal_in':number('NominalClear'),'placement_allowance_in':t,'minimum_face_clear_in':s,'adopted_face_clear_in':lay,'box_side_in':number('BoxSide'),'row_box_width_in':number('Bent1TotalX'),'row_box_depth_in':number('Bent1TotalY'),'checks':['200 independently computed corner/ray boundaries; 0.01 inch less than each boundary fails','Quarter-inch upward rounding and box dimensions','Six width/gap/tolerance/skew scenarios','All eight centers match registered CAD snapshot; six finite wall/box intersections'], 'scenarios':scenarios}

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
