"""Build one native journal module; upstream reports remain byte-identical."""
from pathlib import Path
from lxml import etree as E
import json,sys,math,hashlib,re

ROOT=Path(__file__).resolve().parents[2]; TASK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.bpad_workflow import Journal

source=json.loads((ROOT/'mse_strap_check/layout_snapshot.json').read_text())
assert hashlib.sha256((ROOT/source['model_path']).read_bytes()).hexdigest()==source['model_sha256']
base=Journal.load(TASK/'base.bpad')
doc=E.Element('document',version='1.9',language='en-us')
for lib in ['Math','Logic','Text','Lookup','Scripts','Geometry']:
    E.SubElement(doc,'include',target='Library.'+lib)
r=E.SubElement(doc,'report',name='MSEWallExclusion',title='MSE Wall Exclusion - Both End Bents',unit='in',pagesize='816,1056',margin='48,48,48,48',bordermargin='0,0,0,0',collapsemargins='False')
E.SubElement(r,'include',target='Library.Geometry')
E.SubElement(r,'stylerule',type='AnyEquation',name='Required Input',texthighlight='#F7E6B9')
defs=[]; sketches=[]
def p(parent,text='',**kw):
    a={'fontfamily':'Times New Roman','fontsize':'11','spacingafter':'6'};a.update({k:str(v) for k,v in kw.items()})
    el=E.SubElement(parent,'paragraph',**a);el.text=text;return el
def head(text,page=False):
    return p(r,text,fontsize='14',fontweight='bold',textcolor='#1766A0',spacingbefore='8',keepwithnext='True',**({'pagebreakbefore':'break'} if page else {}))
def eq(parent,f,caption='',inp=False):
    el=E.SubElement(p(parent,spacingbefore='4',spacingafter='1',keepwithnext='True'),'dynexp',formula=f,mathlayout='on',showformula='True',showresult='True',showsteps='False',**({'style':'Required Input'} if inp else {}))
    E.SubElement(el,'expbody').text=f;defs.append(f)
    if caption:p(parent,caption,fontsize='10',spacingafter='5')
    return el
def ref(f):return (f,)
def table(name,headers,rows,widths):
    t=E.SubElement(E.SubElement(r,'embed',spacingbefore='5',spacingafter='8'),'table',name=name,capture='False',colwidths=', '.join(f'{i+1}:{v}' for i,v in enumerate(widths)))
    E.SubElement(t,'stylerule',range=f'A1:{chr(64+len(headers))}{len(rows)+1}',fontfamily='Times New Roman',fontsize='10',valueformat='RoundedNumber(3, 3, {PriorityUnits: []})',border='Border("AllSides", "Solid", 0.6, "#A7B9C6"); Border("BetweenRows", "Solid", 0.4, "#CBD5DD");')
    for i,row in enumerate([headers]+rows):
        rr=E.SubElement(t,'row')
        for j,v in enumerate(row):
            attrs={'capture':'False'}
            if i==0:attrs.update(background='#DCE7F3',fontweight='bold')
            elif not isinstance(v,tuple) or 'Status' not in v[0]:attrs['background']='#EFF7F1'
            if not isinstance(v,tuple) and len(str(v))>widths[j]/4.5:
                c=E.SubElement(rr,'textcell',name=f'{name}Note{i}_{j}',**attrs);p(c,str(v),fontsize='10',spacingafter='3')
            else:
                c=E.SubElement(rr,'c',**attrs)
                if isinstance(v,tuple):c.set('formula',v[0])
                else:E.SubElement(c,'textvalue').text=str(v)
    return t
def section(name):return E.SubElement(r,'section',name=name,capture='False',hide='true')
def ft(v):return f'{v:.15g} ft'

# Native sketches use parameter-linked PlotLines and live dimension labels.
def canvas(name,height,scale,ox,oy):
    c=E.SubElement(E.SubElement(r,'embed',spacingbefore='4',spacingafter='5'),'canvas',name=name,unit='in',size=f'6.5 in; {height} in; scaletofit')
    E.SubElement(c,'include',target='Library.Geometry')
    spec={'name':name,'height':height,'scale':scale,'ox':ox,'oy':oy,'lines':[],'labels':[]};sketches.append(spec)
    def coord(x,origin):return f'{origin}+({x})/(1 ft)*({scale})'
    def line(points,color='#435D66',width=1):
        xs=[coord(x,ox) for x,y in points];ys=[coord(y,oy) for x,y in points]
        el=E.SubElement(c,'plot',formula=f'PlotLines([{",".join(xs)}],[{",".join(ys)}])',linecolor=color,linethickness=str(width))
        spec['lines'].append({'points':points,'color':color,'width':width})
    def rect(xa,xb,ya,yb,col,width=1):line([(xa,ya),(xb,ya),(xb,yb),(xa,yb),(xa,ya)],col,width)
    def label(x,y,text=None,formula=None,color='#263F49',size=9):
        el=E.SubElement(c,'planecontainer',origin=f'{x},{y},0',dir='1,0,0',normal='0,0,1',fontfamily='Times New Roman',fontsize=str(size),textcolor=color)
        if formula:el.set('formula',formula)
        else:E.SubElement(el,'textvalue').text=text
        spec['labels'].append({'x':x,'y':y,'text':text,'formula':formula,'color':color,'size':size})
    return c,line,rect,label

p(r,'D2 I-95 PEDESTRIAN BRIDGE',fontsize='16',fontweight='bold')
p(r,'MSE WALL CLEARANCE — FRONT AND SIDES',fontsize='16',fontweight='bold')
p(r,'Both end bents | 13 October 2026 | Front strap check; specified side offsets')
p(r,'Evaluate a straight strap from the FRONT wall on the normal through a nominal pile center. Use the selected alpha in either skew direction. The SIDE walls use a separate specified 24-inch minimum; their strap routing is not evaluated.',background='#F1F5FA')
table('ResultSummary',['Geometry output','Live value'],[
 ['Front wall: calculated minimum pile-face clear',ref('MinClear to in')],
 ['Front wall: adopted clear, rounded UP',ref('LayoutClear to in')],
 ['Side walls: specified minimum pile-face clear',ref('SideClear to in')],
 ['Selected front strap skew',ref('α to deg')],
 ['Trial strap width',ref('Width to in')],
 ['Geometry input validity',ref('InputStatus')]], [370,160])
p(r,'Measure to the BACK OF FACING. Pile placement tolerance is excluded by the selected nominal-geometry basis. Reversing skew is permitted for this screen; actual pile locations and the complete strap route require separate coordination.',fontsize='10')

head('1. TYPICAL PILE — FRONT AND SIDE LIMITS')
c,line,rect,label=canvas('TypicalBox',3.3,'TypicalScale','3.1','2.1')
line([('-SideExtent','DrawTop'),('-SideExtent','-FrontExtent'),('SideExtent','-FrontExtent'),('SideExtent','DrawTop')],'#B44840',2)
rect('-Half','Half','-Half','Half','#246B7B',2)
for sign in [-1,1]:
    line([(f'{sign}*Half','0 ft'),(f'{sign}*SideExtent','0 ft')],'#1766A0',1)
    for tip in ['Half','SideExtent']:line([(f'{sign}*{tip}','-0.15 ft'),(f'{sign}*{tip}','0.15 ft')],'#1766A0',1)
line([('0 ft','-Half'),('0 ft','-FrontExtent')],'#1766A0',1)
for yy in ['-Half','-FrontExtent']:line([('-0.15 ft',yy),('0.15 ft',yy)],'#1766A0',1)
label(.15,3.06,'RED: MINIMUM BACK-OF-FACING LIMITS',color='#9F332B',size=10)
label(1.86,2.19,formula='SideClear to in',color='#1766A0')
label(3.63,2.19,formula='SideClear to in',color='#1766A0')
label(3.23,1.02,formula='LayoutClear to in',color='#1766A0')
label(2.87,2.06,'PILE',color='#246B7B')
label(1.92,2.79,'OPEN — no rear-wall criterion',size=9)
label(.15,.16,'FRONT: calculated | SIDES: specified | pile tolerance excluded',size=9)

head('2. INPUTS AND FRONT-WALL MINIMUM',True)
p(r,'Shared pile size and spacing are live journal references. Use nominal pile width only, without a placement envelope. Wall positions remain the saved CAD snapshot.',background='#FFF8E9')
for f,cap,inp in [
 ('PileSize = BridgeGeometry_2Beam.EndBent_pileWidth','Nominal square pile width.',False),
 ('PileSpacing = BridgeGeometry_2Beam.EndBent_pileSpacing','Pile spacing along the row.',False),
 ('Width = 2 in','Trial front-wall strap width; use vendor dimension.',True),
 ('Clear = 0 in','Additional strap-edge gap; zero is tangency.',True),
 ('α = 15 deg','Selected front-wall plan skew, to either side of the wall normal.',True),
 ('SideClear = 24 in','Specified side pile-face to back-of-facing minimum; no side strap check.',False),
 ('RoundStep = 0.25 in','Round the computed front setback upward by this increment.',True),
 ('Half = PileSize/2','Nominal pile half-width; no placement allowance.',False),
 ('MinClear = (Half*Cos(α)+Width/2+Clear)/Sin(α) to in','Front wall: minimum clear from nominal pile face to back of facing.',False),
 ('LayoutClear = -Floor(-MinClear/Max(RoundStep,0.001 in),1)*Max(RoundStep,0.001 in) to in','Front wall: adopted clear rounded UP.',False),
 ('FrontExtent = Half+LayoutClear','Pile center to front-wall limit.',False),
 ('SideExtent = Half+SideClear','Pile center to either side-wall limit.',False)]:eq(r,f,cap,inp)
p(r,'DERIVATION: S sin alpha - h cos alpha = w/2 + c. Solve for S using h = nominal pile width / 2. The centered nominal geometry is symmetric for positive or negative skew. No pile placement term enters this expression.',fontsize='10',background='#F1F5FA')

calc=section('GeometryAndChecks')
for f in [
 f'FrameAngle = {source["frame_angle_deg"]:.15g} deg',
 'PileCount = BridgeGeometry_2Beam.EndBent_pileCount',
 'CapLength = BridgeGeometry_2Beam.EndBentCap_length',
 'CapWidth = BridgeGeometry_2Beam.EndBentCap_width',
 'CapX = (CapLength*Abs(Sin(FrameAngle))+CapWidth*Abs(Cos(FrameAngle)))/2',
 'CapY = (CapWidth*Abs(Sin(FrameAngle))+CapLength*Abs(Cos(FrameAngle)))/2',
 'InputsValid = And(PileSize > 0 in,PileSpacing > PileSize,PileCount == 4,Width >= 0 in,Clear >= 0 in,α > 0 deg,α < 90 deg,SideClear >= 24 in,RoundStep > 0 in)',
 'InputStatus = If(InputsValid,"VALID","INVALID - DO NOT USE")',
 'SkewStatus = If(And(α > 0 deg,α <= 15 deg),"Within ordinary 15 deg limit","Above ordinary 15 deg limit")',
 'DrawTop = Half+1 ft',
 'TypicalScale = 2.25/((DrawTop+FrontExtent)/(1 ft))',
 'PlotScale = Min(6/((3*PileSpacing+2*SideExtent)/(1 ft)),2.5/((FrontExtent+DrawTop+2 ft)/(1 ft)))',
 'PanelThickness = '+ft(source['wall_thickness_ft'])]:eq(calc,f)
wallmap={w['id']:w for w in source['walls']}
for bi,b in enumerate(source['bents'],1):
    pre=f'Bent{bi}';flip=1 if bi==1 else -1
    for j in range(1,5):
        eq(calc,f'{pre}P{j}x = {j-2.5}*PileSpacing*Abs(Sin(FrameAngle))')
        eq(calc,f'{pre}P{j}y = {flip*(j-2.5)}*PileSpacing*Cos(FrameAngle)')
    for s,f in [('Left',f'{pre}P1x-SideExtent'),('Right',f'{pre}P4x+SideExtent'),('Bottom',f'Min({pre}P1y,{pre}P4y)-FrontExtent'),('Top',f'Max({pre}P1y,{pre}P4y)+DrawTop'),('TotalX',f'{pre}Right-{pre}Left')]:eq(calc,f'{pre}{s} = {f}')
    for wi,wid in enumerate(['A5','A6','A7'] if bi==1 else ['B1','B6','B7'],1):
        w=wallmap[wid];wp=f'{pre}W{wi}'
        for suffix,value,unit in [('x',w['start'][0]-b['center'][0],True),('y',(w['start'][1]-b['center'][1])*flip,True),('len',w['length'],True),('tx',w['tangent'][0],False),('ty',w['tangent'][1]*flip,False),('nx',-w['outward'][0],False),('ny',-w['outward'][1]*flip,False)]:eq(calc,f'{wp}{suffix} = {ft(value) if unit else value}')
        for ax in 'xy':eq(calc,f'{wp}{ax}end = {wp}{ax}+{wp}t{ax}*{wp}len')
        for j in range(1,5):
            cp=f'{pre}Wall{wi}Pile{j}'
            eq(calc,f'{cp}Face = ({pre}P{j}x-{wp}x)*{wp}nx+({pre}P{j}y-{wp}y)*{wp}ny-Half')
            eq(calc,f'{cp}Extra = Max(0 in,{"LayoutClear" if wi==1 else "SideClear"}-{cp}Face)')
        eq(calc,f'{wp}Gap = Min({pre}Wall{wi}Pile1Face,{pre}Wall{wi}Pile2Face,{pre}Wall{wi}Pile3Face,{pre}Wall{wi}Pile4Face)')
        eq(calc,f'{wp}Extra = Max(0 in,{"LayoutClear" if wi==1 else "SideClear"}-{wp}Gap)')
        eq(calc,f'{wp}Status = If(InputsValid,If({wp}Extra <= 0 in,"MEETS CLEAR","SHORTFALL"),"INVALID")')
    eq(calc,f'{pre}CapGap = -{pre}W1x*{pre}W1nx-{pre}W1y*{pre}W1ny-CapX*Abs({pre}W1nx)-CapY*Abs({pre}W1ny)')
    eq(calc,f'{pre}CapStatus = If({pre}CapGap >= 24 in,"✓ PASS","⊗ FAIL")')
    head(f'{bi+2}. END BENT {bi} — FRONT AND SIDE PLAN',True)
    p(r,'Red open boundary shows computed front and specified side offsets. There is no rear-wall criterion. Gray is the cap; black is the current back of facing. Local x runs across the piles and +y into the approach.',fontsize='10')
    c,line,rect,label=canvas(f'{pre}Plan',4.0,'PlotScale','3.25','2.23')
    line([(pre+'Left',pre+'Top'),(pre+'Left',pre+'Bottom'),(pre+'Right',pre+'Bottom'),(pre+'Right',pre+'Top')],'#B44840',2.2)
    for j in range(1,5):
        x=f'{pre}P{j}x';y=f'{pre}P{j}y'
        rect(x+'-Half',x+'+Half',y+'-Half',y+'+Half','#246B7B',1.7)
        lx=3.25+(j-2.5)*.95-.08
        label(lx,1.82,f'P{j}',size=9)
        line([(x,y+'-Half'),(f'({lx+.08}-3.25)/PlotScale*1 ft','(1.98-2.23)/PlotScale*1 ft')],'#246B7B',.65)
    rect('-CapX','CapX','-CapY','CapY','#87949C',1)
    for wi in range(1,4):
        wp=f'{pre}W{wi}';clamp=lambda s:f'Min({pre}Top+0.5 ft,Max({pre}Bottom-0.5 ft,{s}))'
        line([(wp+'x',clamp(wp+'y')),(wp+'xend',clamp(wp+'yend'))],'#263F49',1.7)
    yy=pre+'Bottom-0.8 ft'
    line([(pre+'Left',yy),(pre+'Right',yy)],'#1766A0',1)
    for xx in [pre+'Left',pre+'Right']:line([(xx,pre+'Bottom'),(xx,pre+'Bottom-1 ft')],'#1766A0',.7)
    line([(pre+'P1x-Half',pre+'P1y'),(pre+'Left',pre+'P1y')],'#1766A0',1)
    line([(pre+'P4x+Half',pre+'P4y'),(pre+'Right',pre+'P4y')],'#1766A0',1)
    line([(pre+'P2x',pre+'P2y-Half'),(pre+'P2x',pre+'P2y-FrontExtent')],'#1766A0',1)
    label(.12,3.69,'FRONT: STRAP CHECK | SIDES: SPECIFIED MINIMUM',color='#9F332B',size=10)
    label(.12,3.41,'Front clear:',size=9);label(1.04,3.41,formula='LayoutClear to in',color='#1766A0')
    label(3.4,3.41,'Side clear:',size=9);label(4.35,3.41,formula='SideClear to in',color='#1766A0')
    label(2.76,.39,formula=pre+'TotalX to in',color='#1766A0')
    label(1.97,1.23,formula='LayoutClear to in',color='#1766A0')
    label(.43,2.35,formula='SideClear to in',color='#1766A0')
    label(5.3,2.35,formula='SideClear to in',color='#1766A0')
    label(.13,.09,'No rear limit | current walls are not relocated | tolerance excluded',size=9)
    label(.22,2.95,'A6 / left' if bi==1 else 'B6 / left',size=8)
    label(4.87,2.95,'A7 / right' if bi==1 else 'B7 / right',size=8)
    label(2.72,.80,'A5 / front' if bi==1 else 'B1 / front',size=8)
    table(pre+'Offsets',['Pile','Front face gap','Front required','Front shortfall'],[
      [f'P{j}',ref(f'{pre}Wall1Pile{j}Face to in'),ref('LayoutClear to in'),ref(f'{pre}Wall1Pile{j}Extra to in')] for j in range(1,5)],[55,155,155,165])
    table(pre+'Walls',['Wall / basis','Required','Current gap','Extra setback','Result'],[
      ['Front / strap',ref('LayoutClear to in'),ref(pre+'W1Gap to in'),ref(pre+'W1Extra to in'),ref(pre+'W1Status')],
      ['Left / specified',ref('SideClear to in'),ref(pre+'W2Gap to in'),ref(pre+'W2Extra to in'),ref(pre+'W2Status')],
      ['Right / specified',ref('SideClear to in'),ref(pre+'W3Gap to in'),ref(pre+'W3Extra to in'),ref(pre+'W3Status')]], [130,85,100,100,115])
    p(r,'Positive extra setback is the outward parallel-move shortfall. Side rows compare only the specified 24-inch clearance; they are not strap feasibility results.',fontsize='10')

head('5. SEPARATE REQUIREMENTS AND USE',True)
table('CapSetback',['Separate front-cap check','End Bent 1','End Bent 2'],[
 ['Front cap face to back of front facing',ref('Bent1CapGap to in'),ref('Bent2CapGap to in')],
 ['SDG 3.13.2.N.2.i: 24 in minimum',ref('Bent1CapStatus'),ref('Bent2CapStatus')]], [290,120,120])
table('SkewBasis',['Front skew basis','Live result'],[['SDG 3.13.2.K.8 ordinary plan skew',ref('SkewStatus')]], [290,240])
p(r,'Front strap clearance and cap-to-facing clearance are separate measurements. Keep the front face of the cap at least 24 inches from the back of facing. The cap is shown in plan for coordination; no elevation strap/cap clearance is solved here.')
p(r,'The side-wall 24-inch pile-face offset is the specified layout criterion for this task. SDG 3.13.2.N.2.i applies 24 inches to cap/front-facing clearance; N.2.ii applies it to battered pile/leveling-pad clearance. Those provisions are not a side-wall strap-clearance calculation.')
p(r,'Pile placement tolerance is excluded as requested. Skew may be reversed around the nominal pile, but this does not demonstrate clearance for all possible as-built positions or the full reinforcement route. Coordinate actual pile positions and adjacent obstructions separately.')
p(r,'Only the front wall is checked for nominal centered-strap geometry. Side reinforcement, rear walls, elevation routing, reinforcement length, connection/development and wall stability are outside this module. No side or overall wall-design pass is implied.')
p(r,'The plan assumes wall faces parallel to these axes. Nominal pile width defines the clearance; the tiny saved frame rotation is retained for pile centers and the cap outline. The open boundary has no rear edge or rear-wall requirement.')
p(r,'SOURCE AND PROVENANCE',fontweight='bold')
p(r,'Shared pile and cap dimensions: BridgeGeometry_2Beam. Current MSE wall back-face lines: saved FreeCAD model, '+source['model_path']+'. Facing thickness projects outward from the profile.',fontsize='10')
p(r,'Saved model SHA-256: '+source['model_sha256'],fontsize='9')
E.SubElement(p(r,fontsize='10'),'link',address='https://www.fdot.gov/Structures/StructuresManual/CurrentRelease').text='FDOT Structures Manual, January 2026 — SDG 3.13.2.K.8 and N.2.'

names={f.split(' = ')[0] for f in defs}
def qualify(f):
    return re.sub(r'(?<![\w.])([A-Za-z_α][A-Za-z_0-9α]*)(?![\w.])',lambda m:'MSEWallExclusion.'+m[1] if m[1] in names else m[1],f)
for c in r.findall('.//canvas'):
    for el in c.iter():
        if el.get('formula'):el.set('formula',qualify(el.get('formula')))
(TASK/'components/000.xml').write_bytes(E.tostring(r,encoding='utf-8',pretty_print=True).rstrip())
(TASK/'definitions.json').write_text(json.dumps([{'formula':f} for f in defs],indent=2,ensure_ascii=False),encoding='utf-8')
(TASK/'sketches.json').write_text(json.dumps(sketches,indent=2),encoding='utf-8')
print(json.dumps({'definitions':len(defs),'canvases':len(sketches),'module':'MSEWallExclusion'}))

