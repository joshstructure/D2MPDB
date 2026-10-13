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

p(r,'D2 I-95 PEDESTRIAN BRIDGE',fontsize='16',fontweight='bold')
p(r,'MSE WALL EXCLUSION BOXES',fontsize='16',fontweight='bold')
p(r,'Both end bents | 13 October 2026 | Minimum setback from pile faces')
p(r,'Solve the wall setback needed for a straight strap, starting on the wall normal through a pile center, to clear that pile within the allowed skew. The red boxes define the MSE back-face exclusion for this arrangement.',background='#F1F5FA')
table('ResultSummary',['Geometry output','Live value'],[
 ['Minimum face clear, nominal pile / zero tolerance',ref('NominalClear to in')],
 ['Minimum face clear, including journal pile tolerance',ref('MinClear to in')],
 ['Adopted clear from EACH nominal pile face (rounded UP)',ref('LayoutClear to in')],
 ['Individual square exclusion box, overall side',ref('BoxSide to in')],
 ['Trial strap width',ref('Width to in')],
 ['Input validity',ref('InputStatus')]], [370,160])
p(r,'Set the BACK OF FACING outside the red boundary. The rounded box includes the placement allowance; do not add that allowance again. All eight piles use the same live geometry and four-sided face setback. Zero added strap gap is a tangency screen.',fontsize='10')

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

head('1. TYPICAL PILE — FOUR-SIDED EXCLUSION')
c,line,rect,label=canvas('TypicalBox',3.3,'TypicalScale','3.1','1.6')
rect('-BoxHalf','BoxHalf','-BoxHalf','BoxHalf','#B44840',2)
rect('-Half','Half','-Half','Half','#246B7B',2)
# Four dimension lines from pile projected faces to the adopted wall boundary.
for sign in [-1,1]:
    line([(f'{sign}*Half','0 ft'),(f'{sign}*BoxHalf','0 ft')],'#1766A0',1)
    line([('0 ft',f'{sign}*Half'),('0 ft',f'{sign}*BoxHalf')],'#1766A0',1)
    for tip in ['Half','BoxHalf']:
        line([(f'{sign}*{tip}','-0.15 ft'),(f'{sign}*{tip}','0.15 ft')],'#1766A0',1)
        line([('-0.15 ft',f'{sign}*{tip}'),('0.15 ft',f'{sign}*{tip}')],'#1766A0',1)
label(.15,3.06,'RED: BACK OF FACING NOT ALLOWED INSIDE',color='#9F332B',size=10)
label(3.23,2.38,formula='LayoutClear to in',color='#1766A0')
label(3.23,.57,formula='LayoutClear to in',color='#1766A0')
label(1.86,1.7,formula='LayoutClear to in',color='#1766A0')
label(3.63,1.7,formula='LayoutClear to in',color='#1766A0')
label(2.9,1.45,'PILE',color='#246B7B')
label(.15,.16,'SCHEMATIC | from nominal projected pile faces | all four sides',size=9)
label(4.8,2.72,'Overall side:',size=9);label(4.8,2.48,formula='BoxSide to in',color='#1766A0')

head('2. INPUTS AND MINIMUM DISTANCE',True)
p(r,'The pile width, spacing, count and placement tolerance are live references to the journal geometry. The 3-inch coordinate allowance is applied conservatively in both plan directions. Wall coordinates are a dated CAD snapshot.',background='#FFF8E9')
for f,cap,inp in [
 ('PileSize = BridgeGeometry_2Beam.EndBent_pileWidth','Square pile size — shared journal geometry.',False),
 ('PileSpacing = BridgeGeometry_2Beam.EndBent_pileSpacing','Pile spacing along the row — shared journal geometry.',False),
 ('Tolerance = BridgeGeometry_2Beam.EndBent_pileTolerance','Placement allowance measured from nominal pile position in x and y.',False),
 ('Width = 2 in','Trial strap width; replace with vendor dimension.',True),
 ('Clear = 0 in','Required clear gap from strap edge to pile; zero is tangency.',True),
 ('α = 15 deg','Maximum selected skew; ordinary limit 15 deg (SDG 3.13.2.K.8).',True),
 ('RoundStep = 0.25 in','Upward rounding increment for the layout box; not added construction clearance.',True),
 ('Half = PileSize/2*(Abs(Sin(FrameAngle))+Abs(Cos(FrameAngle)))','Conservative pile half-width projected onto wall-aligned axes.',False),
 ('NominalClear = (Half*Cos(CalcAngle)+Width/2+Clear)/Sin(CalcAngle) to in','Zero-tolerance distance from nominal pile face to back of facing.',False),
 ('MinClear = Tolerance+((Half+Tolerance)*Cos(CalcAngle)+Width/2+Clear)/Sin(CalcAngle) to in','Minimum nominal-face setback including pile placement allowance.',False),
 ('LayoutClear = -Floor(-MinClear/Max(RoundStep,0.001 in),1)*Max(RoundStep,0.001 in) to in','Round UP to the chosen increment; normalize units before native Floor.',False),
 ('BoxHalf = Half+LayoutClear','Distance from pile center to each exclusion boundary.',False),
 ('BoxSide = 2*BoxHalf to in','Overall individual pile exclusion box side.',False)]:eq(r,f,cap,inp)
p(r,'DERIVATION: the limiting corner distance normal to the strap is (S − t) sin α − (h + t) cos α. Set this equal to w/2 + c and solve for S. Here h is projected nominal half-width and t is the coordinate allowance. This is derived geometry, not an FDOT prescribed setback.',fontsize='10',background='#F1F5FA')

calc=section('GeometryAndChecks')
for f in [
 f'FrameAngle = {source["frame_angle_deg"]:.15g} deg',
 'CalcAngle = If(And(α > 0 deg,α <= 15 deg),α,15 deg)',
 'PileCount = BridgeGeometry_2Beam.EndBent_pileCount',
 'CapLength = BridgeGeometry_2Beam.EndBentCap_length',
 'CapWidth = BridgeGeometry_2Beam.EndBentCap_width',
 'CapX = (CapLength*Abs(Sin(FrameAngle))+CapWidth*Abs(Cos(FrameAngle)))/2',
 'CapY = (CapWidth*Abs(Sin(FrameAngle))+CapLength*Abs(Cos(FrameAngle)))/2',
 'InputsValid = And(PileSize > 0 in,PileSpacing > PileSize,PileCount == 4,Width >= 0 in,Clear >= 0 in,Tolerance >= 0 in,α > 0 deg,α <= 15 deg,RoundStep > 0 in)',
 'InputStatus = If(InputsValid,"VALID","INVALID - DO NOT USE")',
 'TypicalScale = 2.5/(BoxSide/(1 ft))',
 'PlotScale = Min(6/((3*PileSpacing+BoxSide)/(1 ft)),2.5/((BoxSide+3 ft)/(1 ft)))',
 'PanelThickness = '+ft(source['wall_thickness_ft'])]:eq(calc,f)
wallmap={w['id']:w for w in source['walls']}
for bi,b in enumerate(source['bents'],1):
    pre=f'Bent{bi}';flip=1 if bi==1 else -1
    for j in range(1,5):
        eq(calc,f'{pre}P{j}x = {j-2.5}*PileSpacing*Abs(Sin(FrameAngle))')
        eq(calc,f'{pre}P{j}y = {flip*(j-2.5)}*PileSpacing*Cos(FrameAngle)')
    for s,f in [('Left',f'{pre}P1x-BoxHalf'),('Right',f'{pre}P4x+BoxHalf'),('Bottom',f'Min({pre}P1y,{pre}P4y)-BoxHalf'),('Top',f'Max({pre}P1y,{pre}P4y)+BoxHalf'),('TotalX',f'{pre}Right-{pre}Left'),('TotalY',f'{pre}Top-{pre}Bottom')]:eq(calc,f'{pre}{s} = {f}')
    for wi,wid in enumerate(['A5','A6','A7'] if bi==1 else ['B1','B6','B7'],1):
        w=wallmap[wid];wp=f'{pre}W{wi}';sx=w['start'][0]-b['center'][0];sy=(w['start'][1]-b['center'][1])*flip
        for suffix,value,unit in [('x',sx,True),('y',sy,True),('len',w['length'],True),('tx',w['tangent'][0],False),('ty',w['tangent'][1]*flip,False),('nx',-w['outward'][0],False),('ny',-w['outward'][1]*flip,False)]:eq(calc,f'{wp}{suffix} = {ft(value) if unit else value}')
        for ax in 'xy':eq(calc,f'{wp}{ax}end = {wp}{ax}+{wp}t{ax}*{wp}len')
        for j in range(1,5):
            cp=f'{pre}Wall{wi}Pile{j}'
            eq(calc,f'{cp}u = ({pre}P{j}x-{wp}x)*{wp}tx+({pre}P{j}y-{wp}y)*{wp}ty')
            eq(calc,f'{cp}Face = ({pre}P{j}x-{wp}x)*{wp}nx+({pre}P{j}y-{wp}y)*{wp}ny-Half')
            eq(calc,f'{cp}Extra = Max(0 in,LayoutClear-{cp}Face)')
        # Exact finite back-face segment / row bounding rectangle intersection.
        eq(calc,f'{wp}Hit = And(Max({wp}x,{wp}xend) > {pre}Left,Min({wp}x,{wp}xend) < {pre}Right,Max({wp}y,{wp}yend) > {pre}Bottom,Min({wp}y,{wp}yend) < {pre}Top)')
        eq(calc,f'{wp}Status = If(InputsValid,If({wp}Hit,"INSIDE BOX","OUTSIDE BOX"),"INVALID")')
    eq(calc,f'{pre}CapGap = -{pre}W1x*{pre}W1nx-{pre}W1y*{pre}W1ny-CapX*Abs({pre}W1nx)-CapY*Abs({pre}W1ny)')
    eq(calc,f'{pre}CapStatus = If({pre}CapGap >= 24 in,"✓ PASS","⊗ FAIL")')

    head(f'{bi+2}. END BENT {bi} — DIMENSIONED PLAN',True)
    p(r,'Red outer box encloses the four overlapping pile exclusion boxes. Gray shows the cap; black shows the current wall back faces. Blue dimensions update with the equations. Plan directions: x across the pile row, y into the approach.',fontsize='10')
    c,line,rect,label=canvas(f'{pre}Plan',4.0,'PlotScale','3.25','1.83')
    rect(f'{pre}Left',f'{pre}Right',f'{pre}Bottom',f'{pre}Top','#B44840',2.2)
    for j in range(1,5):
        x=f'{pre}P{j}x';y=f'{pre}P{j}y'
        rect(x+'-BoxHalf',x+'+BoxHalf',y+'-BoxHalf',y+'+BoxHalf','#D18A84',.65)
        rect(x+'-Half',x+'+Half',y+'-Half',y+'+Half','#246B7B',1.7)
        lx=3.25+(j-2.5)*.86-.08
        label(lx,1.37,f'P{j}',size=9)
        line([(x,y+'-Half'),(f'({lx+.08}-3.25)/PlotScale*1 ft','(1.56-1.83)/PlotScale*1 ft')],'#246B7B',.65)
    rect('-CapX','CapX','-CapY','CapY','#87949C',1)
    for wi in range(1,4):
        wp=f'{pre}W{wi}'
        clamp=lambda s:f'Min({pre}Top+1 ft,Max({pre}Bottom-0.5 ft,{s}))'
        line([(wp+'x',clamp(wp+'y')),(wp+'xend',clamp(wp+'yend'))],'#263F49',1.7)
    # Overall dimensions of the conservative row envelope.
    yy=f'{pre}Bottom-0.9 ft';xx=f'{pre}Right+0.5 ft'
    line([(f'{pre}Left',yy),(f'{pre}Right',yy)],'#1766A0',1)
    for x in [f'{pre}Left',f'{pre}Right']:line([(x,f'{pre}Bottom'),(x,f'{pre}Bottom-1.1 ft')],'#1766A0',.7)
    line([(xx,f'{pre}Bottom'),(xx,f'{pre}Top')],'#1766A0',1)
    for y in [f'{pre}Bottom',f'{pre}Top']:line([(f'{pre}Right',y),(f'{pre}Right+0.75 ft',y)],'#1766A0',.7)
    label(.12,3.69,'MSE BACK OF FACING EXCLUDED FROM RED AREA',color='#9F332B',size=10)
    label(.12,3.41,'Each pile face to its box:',size=9);label(1.94,3.41,formula='LayoutClear to in',color='#1766A0')
    label(3.4,3.41,'Individual box:',size=9);label(4.6,3.41,formula='BoxSide to in',color='#1766A0')
    label(2.76,.32,formula=pre+'TotalX to in',color='#1766A0')
    label(5.59,2.93,'Depth',color='#1766A0',size=8);label(5.59,2.71,formula=pre+'TotalY to in',color='#1766A0',size=8)
    label(.13,.09,'Schematic plan | current walls are not relocated by this calculation',size=9)
    label(.28,2.68,'A6 / left' if bi==1 else 'B6 / left',size=8)
    label(4.57,2.54,'A7 / right' if bi==1 else 'B7 / right',size=8)
    label(2.68,.64,'A5 / front' if bi==1 else 'B1 / front',size=8)
    table(pre+'Offsets',['Pile','Front face gap','Left face gap','Right face gap','Required clear'],[
      [f'P{j}',ref(f'{pre}Wall1Pile{j}Face to in'),ref(f'{pre}Wall2Pile{j}Face to in'),ref(f'{pre}Wall3Pile{j}Face to in'),ref('LayoutClear to in')] for j in range(1,5)],[45,120,120,120,125])
    table(pre+'Walls',['Current wall','Exclusion result','Governing extra setback'],[
      ['Front wall',ref(pre+'W1Status'),ref(f'Max({pre}Wall1Pile1Extra,{pre}Wall1Pile2Extra,{pre}Wall1Pile3Extra,{pre}Wall1Pile4Extra) to in')],
      ['Left return / P1',ref(pre+'W2Status'),ref(pre+'Wall2Pile1Extra to in')],
      ['Right return / P4',ref(pre+'W3Status'),ref(pre+'Wall3Pile4Extra to in')]], [150,160,220])
    p(r,'Face gaps are signed perpendicular distances to current wall lines. Extra setback is the geometric shortfall for a parallel wall move; it is not a proposed final alignment. Finite wall segments are checked against the red row box.',fontsize='10')

head('5. SEPARATE REQUIREMENTS AND USE',True)
table('CapSetback',['Separate front-cap check','End Bent 1','End Bent 2'],[
 ['Front cap face to back of front facing',ref('Bent1CapGap to in'),ref('Bent2CapGap to in')],
 ['SDG 3.13.2.N.2.i: 24 in minimum',ref('Bent1CapStatus'),ref('Bent2CapStatus')]], [290,120,120])
p(r,'The pile boxes govern the centered-strap plan clearance. Keep the front face of the cap at least 24 inches from the back of facing as a separate condition. The cap is shown in plan for coordination; it lies above the previous 38-ft trial strap layer.')
p(r,'The 24-inch battered-pile-to-leveling-pad clearance is a different measurement (SDG 3.13.2.N.2.ii). This plan assumes the current plumb piles. Evaluate the whole battered-pile envelope and leveling pad separately if the pile alignment changes.')
p(r,'Outside a box means the wall meets this pile-based setback screen; it does not certify the complete reinforcement route. Check every pile, adjacent wall, connection, reinforcement length, backfill boundary and elevation layer. Ordinary L ≥ max(8 ft, 0.7H), 15° elevation inclination and acute-corner/bin-wall provisions remain separate.')
p(r,'Boxes apply to wall faces parallel to these plan axes, with the centered anchor assumed above. For skewed walls, use pile dimensions projected into the wall axes and recompute. The row rectangle conservatively encloses the union of the four individual boxes.')
p(r,'SOURCE AND PROVENANCE',fontweight='bold')
p(r,'Shared pile and cap dimensions: BridgeGeometry_2Beam. MSE wall back-face lines: saved FreeCAD model, '+source['model_path']+'. Facing thickness projects outward from the profile. Frame rotation is retained in the conservative pile envelope.',fontsize='10')
p(r,'Saved model SHA-256: '+source['model_sha256'],fontsize='9')
E.SubElement(p(r,fontsize='10'),'link',address='https://www.fdot.gov/Structures/StructuresManual/CurrentRelease').text='FDOT Structures Manual, January 2026 — SDG 3.13.2.F, K.8/K.9 and N.2; SDM 19.6.E.'
p(r,'This module reports geometry for the stated trial strap and journal allowance. Vendor dimensions and project construction clearance still require confirmation. No material or resistance factors enter these plan lengths.',background='#FFF8E9',fontsize='10')

# Qualify native drawing references; canvas has its own scope.
names={f.split(' = ')[0] for f in defs}
def qualify(f):
    return re.sub(r'(?<![\w.])([A-Za-z_α][A-Za-z_0-9α]*)(?![\w.])',lambda m:'MSEWallExclusion.'+m[1] if m[1] in names else m[1],f)
for c in r.findall('.//canvas'):
    for el in c.iter():
        if el.get('formula'):el.set('formula',qualify(el.get('formula')))

fragment=E.tostring(r,encoding='utf-8',pretty_print=True).rstrip()
(TASK/'components/000.xml').write_bytes(fragment)
index=base.part('report:PedBridge')
insertion=b'<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0"><link address="#MSEWallExclusion">MSE wall exclusion boxes - both end bents</link></paragraph>'
needle=b'<heading level="1" keepwithnext="True">Specific calculations and foundations</heading>'
assert index.count(needle)==1
(TASK/'components/001.xml').write_bytes(index.replace(needle,needle+insertion))
(TASK/'definitions.json').write_text(json.dumps([{'formula':f} for f in defs],indent=2,ensure_ascii=False),encoding='utf-8')
(TASK/'sketches.json').write_text(json.dumps(sketches,indent=2),encoding='utf-8')
E.ElementTree(doc).write(str(TASK/'module-preview.bpad'),encoding='utf-8',xml_declaration=True,pretty_print=True)
print(json.dumps({'module':'MSEWallExclusion','definitions':len(defs),'canvases':len(sketches),'reports':len(doc.findall('report'))}))
