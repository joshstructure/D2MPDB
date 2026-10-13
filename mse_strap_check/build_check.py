"""Build the standalone, editable native Blockpad geometry check."""
from pathlib import Path
from lxml import etree as E
import json, math, re, shutil

HERE=Path(__file__).resolve().parent
data=json.loads((HERE/'layout_snapshot.json').read_text())
doc=E.Element('document',version='1.9',language='en-us')
for lib in ['DateTime','Math','Logic','Lookup','Text','Scripts','Geometry']:
    E.SubElement(doc,'include',target='Library.'+lib)
E.SubElement(doc,'stylerule',applytoall='True',type='AnyTableCell',fontfamily='Times New Roman',fontsize='10',valueformat='RoundedNumber(3, 3, {PriorityUnits: []})')
for status,color in [('PASS','#DCECE0'),('FAIL','#F8D4D0'),('REVIEW','#FFF0CC')]:
    E.SubElement(doc,'stylerule',applytoall='True',type='AnyTableCell',condition='"'+status+'"',background=color)
defs=[]
def report(name,title):
    r=E.SubElement(doc,'report',name=name,title=title,unit='in',pagesize='816,1056',margin='48,48,48,48',bordermargin='0,0,0,0',collapsemargins='False')
    E.SubElement(r,'stylerule',type='AnyEquation',name='Input',texthighlight='#F7E6B9')
    return r
def p(r,text='',**attrs):
    opt={'fontfamily':'Times New Roman','fontsize':'10','spacingafter':'5'};opt.update({k:str(v) for k,v in attrs.items()})
    e=E.SubElement(r,'paragraph',**opt);e.text=text;return e
def head(r,text,page=False):return p(r,text,fontweight='bold',fontsize='12',spacingbefore='8',keepwithnext='True',textcolor='#1766A0',**({'pagebreakbefore':'Break'} if page else {}))
def eq(r,formula,caption='',inp=False):
    el=E.SubElement(p(r,'',spacingbefore='3',spacingafter='1'), 'dynexp',formula=formula,mathlayout='on',showsteps='False',showresult='False' if '(' in formula.split(' = ')[0] else 'True',showformula='True',**({'style':'Input'} if inp else {}))
    E.SubElement(el,'expbody').text=formula
    if caption:p(r,caption,fontsize='9',textcolor='#43505C')
    parent=r
    while parent.tag!='report':parent=parent.getparent()
    defs.append({'report':parent.get('name'),'formula':formula,'input':inp})
    return el
def section(r,name,hide=True):return E.SubElement(r,'section',name=name,capture='False',hide='true' if hide else 'false')
def table(r,name,headers,rows,widths):
    t=E.SubElement(E.SubElement(r,'embed',spacingbefore='5',spacingafter='8'),'table',name=name,capture='False',colwidths=', '.join(f'{i+1}:{w}' for i,w in enumerate(widths)))
    last=chr(64+len(headers));n=len(rows)+1
    E.SubElement(t,'stylerule',range=f'A1:{last}{n}',fontfamily='Times New Roman',fontsize='9',border='Border("AllSides", "Solid", 0.6, "#A7B9C6"); Border("BetweenRows", "Solid", 0.4, "#CBD5DD");')
    E.SubElement(t,'stylerule',range=f'A1:{last}1',background='#DCE7F3',fontweight='bold')
    for i,row in enumerate([headers]+rows):
        tr=E.SubElement(t,'row')
        for v in row:
            cell=E.SubElement(tr,'c',capture='False',background='#DCE7F3' if i==0 else '#F3F7F8')
            if isinstance(v,tuple):cell.set('formula',v[0])
            else:E.SubElement(cell,'textvalue').text=str(v)
    return t
def ref(s):return (s,)
def link(r,label,address):E.SubElement(p(r,fontsize='9'),'link',address=address).text=label
def fmt(n):return format(n,'.15g')
def ft(n):return fmt(n)+' ft'

basis=report('Basis','01 - Start here and controls')
p(basis,'D2 MPDB PEDESTRIAN BRIDGE',fontsize='16',fontweight='bold')
p(basis,'MSE STRAP / PILE PLAN CLEARANCE',fontsize='14',fontweight='bold')
p(basis,'Both end bents | 13 October 2026 | Straight strap starting on the pile centerline')
table(basis,'Overview',['Item','Basis'],[
 ['Objective','Can a wall strap starting dead center in line with a pile clear it within 15 degrees?'],
 ['Inputs','Saved end-bent / MSE geometry; editable strap width, clearance, pile offsets and test skew. Amber equations are inputs.'],
 ['Output','Required target skew, maximum strap width, full-length +/- route checks and separate cap setback check.']], [75,455])
head(basis,'CURRENT GEOMETRY SCREEN')
table(basis,'Summary',['Check','End Bent 1','End Bent 2'],[
 ['Front-wall 15-degree centerline clearance',ref('EB1.FrontGap to in'),ref('EB2.FrontGap to in')],
 ['Largest centered strip at 15 degrees (no tolerance)',ref('EB1.FrontMaxWidth to in'),ref('EB2.FrontMaxWidth to in')],
 ['Extra front-wall / pile separation for target',ref('EB1.FrontExtra to in'),ref('EB2.FrontExtra to in')],
 ['Front wall / input strap width',ref('EB1.FrontTargetStatus'),ref('EB2.FrontTargetStatus')],
 ['Left return / nearest pile',ref('EB1.LeftTargetStatus'),ref('EB2.LeftTargetStatus')],
 ['Right return / nearest pile',ref('EB1.RightTargetStatus'),ref('EB2.RightTargetStatus')],
 ['Front cap setback >= 24 in',ref('EB1.FrontCapStatus'),ref('EB2.FrontCapStatus')]], [310,110,110])
p(basis,'A line can pass while a finite-width strap touches a pile. A target PASS is necessary but does not establish a clear route past every pile or adjacent wall. Negative margins fail. Tangency is zero margin, not usable construction clearance.',background='#F1F5FA')
head(basis,'COMMON EDITABLE CONTROLS')
for f,c in [
 ('Width = 2 in','Illustrative strap width only; replace with the vendor width. Not a sourced product dimension.'),
 ('Clear = 0 in','Required clear gap from strap edge to pile. Zero means geometric non-intersection only.'),
 ('Tolerance = 0 in','Square pile-location envelope in both plan directions. Zero is the nominal model; enter project allowance (e.g. a 3 in sensitivity).'),
 ('TestAngle = 15 deg','Both signs of this angle are checked. Ordinary skew may not exceed LimitAngle.'),
 ('Layer = 38 ft','Illustrative strap elevation. Piles are modeled plumb. This layer is below both cap soffits and modeled front-wall tops.'),
 ('VendorReady = false','Set true only after confirming width, required gap, placement envelope, layer and design length.')]:eq(basis,f,c,True)
eq(basis,'LimitAngle = 15 deg','SDG 3.13.2.K.8 ordinary limit. Developed special skew details are outside this check.')
eq(basis,'InputsValid = And(Width >= 0 in, Clear >= 0 in, Tolerance >= 0 in, TestAngle > 0 deg, TestAngle <= LimitAngle, LimitAngle <= 15 deg)')
head(basis,'DESIGN BASIS AND STRATEGY',True)
for n,title,text in [(1,'Inspect plan and select a route','Use EB1 / EB2 tabs. WallChoice: 1 front, 2 left return, 3 right return. PileChoice: 1 through 4, left to right. The anchor is the perpendicular projection of that pile onto the back of facing.'),(2,'Check the aligned target','Use the near pile corner, not the pile center station. Show zero-width and finite-width requirements independently.'),(3,'Check the full route','At both signs of TestAngle, check every pile and every shown wall other than the source wall along the full input length. The finite strip is conservatively treated as a capsule.'),(4,'Keep separate requirements visible','Cap setback, reinforcement minimum length, wall-layer range and 70-degree corners are distinct checks. Plan clearance does not establish elevation routing or structural capacity.')]:
    p(basis,f'{n}. {title}',fontweight='bold');p(basis,text)
    link(basis,'Open End Bent 1','#EB1');link(basis,'Open End Bent 2','#EB2') if n==1 else None
table(basis,'Criteria',['Provision','Applied meaning'],[
 ['SDG 3.13.2.N.2.i','24 in front face of cap to BACK of facing; measured separately from strap clearance.'],
 ['SDG 3.13.2.N.2.ii','24 in battered pile face to leveling pad at wall base. Not established by this single-layer plumb-pile screen.'],
 ['SDG 3.13.2.K.8 / K.9','Ordinary plan skew <= 15 deg; elevation inclination <= 15 deg. Elevation deflection is not credited here.'],
 ['SDG 3.13.2.F','L >= max(8 ft, 0.7 H); H from top of pad to top of coping. Longer lengths may govern stability.'],
 ['SDM 19.6.E','Corners < 70 deg require bin-wall design. Current landing corners are 90 deg.']], [170,360])
link(basis,'FDOT Structures Manual - January 2026 (SDG pp. 3-55, 3-62, 3-63; SDM 19.6)','https://www.fdot.gov/structures/structuresmanual/currentrelease')
p(basis,'Basis: saved native model registered under project_current/geometry/freecad. Wall profiles mark the back of the modeled facing; facing thickness extends outward. This standalone file contains an editable source snapshot, not a live connection to CAD. Refresh deliberately when CAD changes.')
p(basis,'The modeled front-wall top is used as the coping proxy. Final vendor coping and wall height are not confirmed. Current model piles are plumb and have provisional tips. Layer shifts may be entered per pile for a separately established batter/as-built section; this does not check the entire battered shaft.',background='#FFF8E9')
p(basis,'VERIFICATION: native equations were independently evaluated with dimensional checks and compared with separate segment geometry. Display caches are independently computed starting values. Blockpad native recalculation and print pagination have not been verified; recalculate on opening.',background='#FFF8E9',fontsize='9')
link(basis,'Source snapshot and exact model fingerprint','layout_snapshot.json')

methods=report('RouteMath','04 - Geometry method')
head(methods,'STRAIGHT-STRIP GEOMETRY')
p(methods,'At the back of facing the anchor lies exactly on the normal through the selected pile center. Let d be center distance normal to wall, a the pile half-size normal to wall plus location allowance, b the tangential half-size plus allowance, and r = strap width / 2 + required clear gap.')
p(methods,'At skew theta, the signed near-corner distance from the ray is (d-a) sin(theta) - b cos(theta). A target clears when this distance is at least r, the pile is ahead of the wall, and the strap reaches beyond the pile. The drawings and full-route check use finite segments; the target-angle equation describes the continuing ray.')
p(methods,'Required target angle = ATan[b/(d-a)] + ASin[r/Sqrt((d-a)^2+b^2)]. Invalid domains are rejected. The square enclosing the slightly rotated source pile is conservative. Finite segment-to-rectangle distance is zero on intersection; otherwise it is the minimum endpoint-to-rectangle or rectangle-corner-to-segment distance.')
p(methods,'A full-route PASS means one tested sign clears all modeled obstacles at that angle, length and layer. A full-route FAIL means neither tested sign works. Unless the target-angle check also fails, other angles within 15 degrees may still work; adjust TestAngle. No dog-leg, strap bending, attaching to a pile, or change of connection position is assumed.')
helpers=section(methods,'GeometryFunctions',True)
for f in [
 'Safe(x) = If(Abs(x) < 0.000000001 ft, 0.000000001 ft, x)',
 'Clamp(x) = Min(1,Max(0,x))',
 'Low(a,b,p,q) = If(Abs(q) < 0.000000001 ft, If(And(p >= a,p <= b),-1000000000,1000000000),Min((a-p)/Safe(q),(b-p)/Safe(q)))',
 'High(a,b,p,q) = If(Abs(q) < 0.000000001 ft, If(And(p >= a,p <= b),1000000000,-1000000000),Max((a-p)/Safe(q),(b-p)/Safe(q)))',
 'PointRect(x,y,a,b,c,d) = Sqrt(Max(a-x,0 ft,x-b)^2+Max(c-y,0 ft,y-d)^2)',
 'Part(x,y,p,q,u,v) = Clamp(((x-p)*(u-p)+(y-q)*(v-q))/Max((u-p)^2+(v-q)^2,0.000000000001 ft^2))',
 'PointSeg(x,y,p,q,u,v) = Sqrt((x-p-Part(x,y,p,q,u,v)*(u-p))^2+(y-q-Part(x,y,p,q,u,v)*(v-q))^2)',
 'Dist(p,q,u,v,a,b,c,d) = If(Max(0,Low(a,b,p,u-p),Low(c,d,q,v-q)) <= Min(1,High(a,b,p,u-p),High(c,d,q,v-q)),0 ft,Min(PointRect(p,q,a,b,c,d),PointRect(u,v,a,b,c,d),PointSeg(a,c,p,q,u,v),PointSeg(a,d,p,q,u,v),PointSeg(b,c,p,q,u,v),PointSeg(b,d,p,q,u,v)))',
 'Needed(d,a,b,r) = If(Or(d <= a,r >= Sqrt((d-a)^2+b^2)),90 deg,ATan(b/Max(d-a,0.000000001 ft))+ASin(Min(1,r/Max(Sqrt((d-a)^2+b^2),0.000000001 ft))))'
]:eq(helpers,f)

wallmap={w['id']:w for w in data['walls']}
angle=math.radians(data['frame_angle_deg'])
rot=abs(math.cos(angle))+abs(math.sin(angle))
layout_reports=[]
for bi,b in enumerate(data['bents']):
    rid=b['id'];r=report(rid,f'0{bi+2} - End Bent {bi+1}')
    # Move method tab after both plan tabs at final assembly.
    layout_reports.append(r)
    source_walls=['A5','A6','A7'] if bi==0 else ['B1','B6','B7']
    obstacles=source_walls+(['A2','A4'] if bi==0 else ['B2','B3'])
    source_xy=b['center'];flip=1 if bi==0 else -1
    capx=(b['cap_length']*abs(math.sin(angle))+b['cap_width']*abs(math.cos(angle)))/2
    capy=(b['cap_length']*abs(math.cos(angle))+b['cap_width']*abs(math.sin(angle)))/2
    p(r,f'END BENT {bi+1} | PILE / MSE PLAN',fontsize='14',fontweight='bold')
    p(r,'Dimensions in feet unless shown otherwise. Strap begins at the BACK of facing, perpendicular projection of selected pile center. Plan is live; positive sheet y points into the approach.')
    controls=section(r,'RouteControls',False)
    for formula,cap in [('WallChoice = 1','Wall: 1 front, 2 left return, 3 right return.'),('PileChoice = 2','Selected pile: 1 through 4, left to right.'),('Direction = 1','Selected drawing sign: +1 or -1 relative to wall tangent.'),('LengthOverride = 0 ft','Zero uses ordinary minimum from local H. Enter longer vendor design length here.')]:eq(controls,formula,cap,True)
    head(r,'STEP 1 OF 4 | PLAN AND SELECTED ROUTE')
    canvas=E.SubElement(E.SubElement(r,'embed',spacingbefore='3',spacingafter='5'),'canvas',name='Plan',title='Live plan',unit='in',size='6.5 in; 6 in; scaletofit')
    E.SubElement(canvas,'include',target='Library.Geometry')
    # Qualify report definitions after all definitions have been created.
    def plot(xs,ys,color='#52616B',width=1):
        E.SubElement(canvas,'plot',formula=f'PlotLines([{",".join(xs)}],[{",".join(ys)}])',linecolor=color,linethickness=str(width))
    def xy(x,y):
        def coordinate(s,origin):
            if s.startswith('If(') and ',null,' in s:
                condition,body=s[3:-1].split(',null,',1)
                return f'If({condition},null,{origin}+({body})/(1 ft)*0.225)'
            return f'{origin}+({s})/(1 ft)*0.225'
        return coordinate(x,'3.25'),coordinate(y,'1.25')
    def line(points,color='#52616B',width=1):
        xx,yy=zip(*(xy(x,y) for x,y in points));plot(xx,yy,color,width)
    def label(x,y,text,color='#253744',size=9):
        e=E.SubElement(canvas,'planecontainer',origin=f'{x},{y},0',dir='1,0,0',normal='0,0,1',fontfamily='Times New Roman',fontsize=str(size),textcolor=color)
        E.SubElement(e,'textvalue').text=text
    def rect(xa,xb,ya,yb,col,width=1):line([(xa,ya),(xb,ya),(xb,yb),(xa,yb),(xa,ya)],col,width)
    rect('-CapX','CapX','-CapY','CapY','#7B8993',1.4)
    for wi,wid in enumerate(obstacles,1):
        pre=f'W{wi}';w=wallmap[wid]
        # Clipping only affects the drawing; collision checks retain entire walls.
        outside=f'Or({pre}xmin > 12 ft,{pre}xmax < -12 ft,{pre}ymin > 16.25 ft,{pre}ymax < -4 ft)'
        cx=lambda s:f'If({outside},null,Min(12 ft,Max(-12 ft,{s})))'
        cy=lambda s:f'If({outside},null,Min(16.25 ft,Max(-4 ft,{s})))'
        rect(cx(pre+'xmin'),cx(pre+'xmax'),cy(pre+'ymin'),cy(pre+'ymax'),'#374B55',2)
        xx=(w['start'][0]+w['end'][0])/2-source_xy[0];yy=((w['start'][1]+w['end'][1])/2-source_xy[1])*flip
        if wi<=3:
            if wi==1:lx,ly=3.0,.19
            elif wi==2:lx,ly=1.02,3.60
            else:lx,ly=5.30,2.95
            label(lx,ly,wid+' / '+['front','left','right'][wi-1],size=9)
    for j in range(1,5):
        rect(f'P{j}x-Half',f'P{j}x+Half',f'P{j}y-Half',f'P{j}y+Half','#2D6675',1.7)
        label(3.25+(j-2.5)*4.5*.225-.07,1.18,f'P{j}',size=9)
    line([('Ox','Oy'),('Cx','Cy')],'#A7B0B8',.8)
    for sign in ['Plus','Minus']:line([('Ox','Oy'),('E'+sign+'x','E'+sign+'y')],'#397CC0',1.2)
    # Finite strap outline, with width measured normal to its axis.
    corners=[('Ox-Vy*Basis.Width/2','Oy+Vx*Basis.Width/2'),('Ex-Vy*Basis.Width/2','Ey+Vx*Basis.Width/2'),('Ex+Vy*Basis.Width/2','Ey-Vx*Basis.Width/2'),('Ox+Vy*Basis.Width/2','Oy-Vx*Basis.Width/2')]
    line(corners+[corners[0]],'#CB7025',1.7)
    label(.22,5.75,'BLUE: +/- test angle    ORANGE: selected strap    GRAY: cap projection',size=8)
    label(.22,5.48,'18 in square piles; live center offsets and clearances below.',size=8)
    label(.22,5.20,'Walls are clipped to this view; route checks retain their full length.',size=8)
    table(r,'Selected',['Selected route','Live result'],[
     ['Wall / pile',ref('SelectedLabel')],['Anchor to selected pile CL, normal d',ref('NormalDistance to ft')],['Selected route length',ref('RouteLength to ft')],['Local wall height H',ref('LocalHeight to ft')],['Required skew to selected pile',ref('TargetTheta to deg')],['Selected strip / all piles: edge clearance',ref('SelectedPileGap to in')],['Selected strip / other walls: edge clearance',ref('SelectedWallGap to in')],['Selected route at this angle and layer',ref('SelectedStatus')]], [340,190])
    head(r,'STEP 2 OF 4 | ALL ALIGNED ORIGINS',True)
    p(r,'Every row starts from the wall normal through that target pile. Width limit is the nominal centered-strip limit at 15 degrees for that target alone, with zero required gap and zero tolerance. Route columns include all four piles, other walls, input width/gap/tolerance, full length and layer checks.')
    calc=section(r,'LiveEquations',True)
    geom=section(r,'EditableGeometry',True)
    p(geom,'Editable snapshot of registered model; feet in local cap-centered plan. x right across pile row; y toward approach. Wall back-face line is the input, thickness extends outward. Pile center offsets can represent an independently established layer/batter/as-built section.')
    eq(geom,f'SourceStation = {ft(b["station"])}','Bent station, source reference only.')
    for name,value in [('CapX',capx),('CapY',capy),('PileSize',b['piles'][0]['size']),('PanelThickness',data['wall_thickness_ft']),('CapBottom',b['cap_bottom']),('PileTop',b['pile_top']),('TrialPileLength',b['trial_pile_length'])]:eq(geom,f'{name} = {ft(value)}',inp=True)
    eq(calc,f'Half = PileSize/2*{fmt(rot)}')
    eq(calc,'Envelope = Half+Basis.Tolerance')
    eq(calc,'Buffer = Basis.Width/2+Basis.Clear')
    for j,pile in enumerate(b['piles'],1):
        for axis,ix,sg in [('x',0,1),('y',1,flip)]:
            value=(pile['center'][ix]-source_xy[ix])*sg
            eq(geom,f'P{j}{axis}Source = {ft(value)}')
            eq(geom,f'P{j}{axis}Offset = 0 ft',inp=True)
            eq(calc,f'P{j}{axis} = P{j}{axis}Source+P{j}{axis}Offset')
    for wi,wid in enumerate(obstacles,1):
        w=wallmap[wid];pre=f'W{wi}';sx=w['start'][0]-source_xy[0];sy=(w['start'][1]-source_xy[1])*flip
        tx,ty=w['tangent'][0],w['tangent'][1]*flip;nx,ny=-w['outward'][0],-w['outward'][1]*flip
        for name,value,unit in [('x',sx,True),('y',sy,True),('len',w['length'],True),('tx',tx,False),('ty',ty,False),('nx',nx,False),('ny',ny,False)]:eq(geom,f'{pre}{name} = {ft(value) if unit else fmt(value)}',f'{wid}: '+name,True)
        for ax in 'xy':
            eq(calc,f'{pre}{ax}end = {pre}{ax}+{pre}t{ax}*{pre}len')
            eq(calc,f'{pre}{ax}min = Min({pre}{ax},{pre}{ax}end)-Max({pre}n{ax},0)*PanelThickness')
            eq(calc,f'{pre}{ax}max = Max({pre}{ax},{pre}{ax}end)-Min({pre}n{ax},0)*PanelThickness')
        if wi>3:continue
        # Preserve actual local height steps. User can override the resultant H.
        def profile_expr(controls,u,step=False):
            expr=ft(controls[-1][1])
            for (x0,z0),(x1,z1) in reversed(list(zip(controls,controls[1:]))):
                if x1-x0<1e-8:continue
                v=ft(z0) if step else f'({ft(z0)}+({u}-{ft(x0)})*{fmt((z1-z0)/(x1-x0))})'
                expr=f'If({u} < {ft(x1)},{v},{expr})'
            return expr
        eq(geom,f'{pre}HeightOverride = 0 ft',f'{wid}: zero uses source top-minus-pad profile; enter final coping height if different.',True)
        rows=[]
        for j in range(1,5):
            q=f'C{wi}{j}'
            for name,expr in [
             ('u',f'(P{j}x-{pre}x)*{pre}tx+(P{j}y-{pre}y)*{pre}ty'),
             ('d',f'(P{j}x-{pre}x)*{pre}nx+(P{j}y-{pre}y)*{pre}ny'),
             ('x',f'{pre}x+{q}u*{pre}tx'),('y',f'{pre}y+{q}u*{pre}ty'),
             ('top',profile_expr(w['top_controls'],q+'u')),('base',profile_expr(w['base_controls'],q+'u',True)),
             ('H',f'If({pre}HeightOverride > 0 ft,{pre}HeightOverride,{q}top-{q}base)'),
             ('Lmin',f'Max(8 ft,0.7*{q}H)'),('L',f'If(LengthOverride > 0 ft,LengthOverride,{q}Lmin)'),
             ('gap',f'({q}d-Half)*Sin(Basis.LimitAngle)-Half*Cos(Basis.LimitAngle)'),
             ('width',f'Max(0 in,2*{q}gap) to in'),
             ('theta',f'RouteMath.Needed({q}d,Envelope,Envelope,Buffer) to deg'),
             ('extra',f'Max(0 in,Envelope+(Envelope*Cos(Basis.LimitAngle)+Buffer)/Sin(Basis.LimitAngle)-{q}d) to in'),
             ('valid',f'And({q}d > Envelope,{q}u >= 0 ft,{q}u <= {pre}len,{q}L >= {q}Lmin,Basis.Layer > {q}base,Basis.Layer < {q}top,Basis.Layer < CapBottom,Basis.Layer < PileTop,Basis.Layer > PileTop-TrialPileLength,Basis.InputsValid,PanelThickness > 0 ft,PileSize > 0 ft,CapX > 0 ft,CapY > 0 ft,{pre}len > 0 ft,Abs({pre}tx^2+{pre}ty^2-1) < 0.000001,Abs({pre}nx^2+{pre}ny^2-1) < 0.000001,Abs({pre}tx*{pre}nx+{pre}ty*{pre}ny) < 0.000001,Min(Abs({pre}nx),Abs({pre}ny)) < 0.000001)'),
             ('target',f'If(And({q}valid,{q}theta <= Basis.LimitAngle),"PASS","FAIL")')]:eq(calc,f'{q}{name} = {expr}')
            for sign,sg in [('Plus','+'),('Minus','-')]:
                endx=f'({q}x+{q}L*({pre}nx*Cos(Basis.TestAngle){sg}{pre}tx*Sin(Basis.TestAngle)))'
                endy=f'({q}y+{q}L*({pre}ny*Cos(Basis.TestAngle){sg}{pre}ty*Sin(Basis.TestAngle)))'
                eq(calc,f'{q}{sign}x = {endx}');eq(calc,f'{q}{sign}y = {endy}')
                route=f'{q}x,{q}y,{q}{sign}x,{q}{sign}y'
                piles=[f'RouteMath.Dist({route},P{k}x-Envelope,P{k}x+Envelope,P{k}y-Envelope,P{k}y+Envelope)' for k in range(1,5)]
                walls=[f'RouteMath.Dist({route},W{k}xmin,W{k}xmax,W{k}ymin,W{k}ymax)' for k in range(1,len(obstacles)+1) if k!=wi]
                eq(calc,f'{q}{sign}Pile = Min({",".join(piles)})-Basis.Width/2')
                eq(calc,f'{q}{sign}Wall = Min({",".join(walls)})-Basis.Width/2')
                # Require actual length to extend beyond target's back edge normal to wall.
                eq(calc,f'{q}{sign}OK = And({q}valid,{q}{sign}Pile >= Basis.Clear,{q}{sign}Wall >= 0 in,{q}L*Cos(Basis.TestAngle) >= {q}d+Envelope)')
                eq(calc,f'{q}{sign}Status = If({q}{sign}OK,"PASS","FAIL")')
            rows.append([f'P{j}',ref(q+'d to ft'),ref(q+'width'),ref(q+'theta'),ref(q+'extra'),ref(q+'PlusStatus'),ref(q+'MinusStatus')])
        head(r,f'{wid} | '+['FRONT WALL','LEFT RETURN','RIGHT RETURN'][wi-1])
        table(r,f'Cases{wi}',['Target','d (ft)','Max w (in)','Need skew','Extra d (in)','+ test','- test'],rows,[45,65,85,90,85,80,80])
    p(r,'Extra d is added wall-normal separation needed to clear the TARGET at 15 degrees, with current width/gap/tolerance. It is a geometric sensitivity, not a proposed wall relocation; recheck all piles, walls and cap after changing layout.')
    # Selected values from scalar cases. A simple If lookup stays native and editable.
    def choose_suffix(suffix):
        ex=f'C34{suffix}'
        for wi,j in reversed([(a,k) for a in range(1,4) for k in range(1,5)][:-1]):ex=f'If(And(WallChoice == {wi},PileChoice == {j}),C{wi}{j}{suffix},{ex})'
        return ex
    for name,suffix in [('Ox','x'),('Oy','y'),('NormalDistance','d'),('LocalHeight','H'),('RouteLength','L'),('TargetTheta','theta'),('EPlusx','Plusx'),('EPlusy','Plusy'),('EMinusx','Minusx'),('EMinusy','Minusy')]:eq(calc,f'{name} = {choose_suffix(suffix)}')
    eq(calc,'Cx = If(PileChoice == 1,P1x,If(PileChoice == 2,P2x,If(PileChoice == 3,P3x,P4x)))')
    eq(calc,'Cy = If(PileChoice == 1,P1y,If(PileChoice == 2,P2y,If(PileChoice == 3,P3y,P4y)))')
    eq(calc,'Ex = If(Direction == 1,EPlusx,EMinusx)');eq(calc,'Ey = If(Direction == 1,EPlusy,EMinusy)')
    eq(calc,'Vx = (Ex-Ox)/Max(RouteLength,0.000001 ft)');eq(calc,'Vy = (Ey-Oy)/Max(RouteLength,0.000001 ft)')
    eq(calc,f'SelectedPileGap = If(Direction == 1,{choose_suffix("PlusPile")},{choose_suffix("MinusPile")})')
    eq(calc,f'SelectedWallGap = If(Direction == 1,{choose_suffix("PlusWall")},{choose_suffix("MinusWall")})')
    eq(calc,'SelectionValid = And(WallChoice >= 1,WallChoice <= 3,WallChoice == Round(WallChoice,0),PileChoice >= 1,PileChoice <= 4,PileChoice == Round(PileChoice,0),Or(Direction == 1,Direction == -1))')
    eq(calc,f'SelectedStatus = If(SelectionValid,If(Direction == 1,{choose_suffix("PlusStatus")},{choose_suffix("MinusStatus")}),"INVALID SELECTION")')
    labels=[f'"{wid} / P{j}"' for wid in source_walls for j in range(1,5)];ex=labels[-1]
    for (wi,j),lab in reversed(list(zip([(a,k) for a in range(1,4) for k in range(1,5)],labels))[:-1]):ex=f'If(And(WallChoice == {wi},PileChoice == {j}),{lab},{ex})'
    eq(calc,f'SelectedLabel = If(SelectionValid,{ex},"INVALID")')
    for name,expr in [('FrontGap','Min(C11gap,C12gap,C13gap,C14gap)'),('FrontMaxWidth','Max(0 in,2*FrontGap)'),('FrontExtra','Max(C11extra,C12extra,C13extra,C14extra)'),('FrontTargetStatus','If(And(C11theta <= Basis.LimitAngle,C12theta <= Basis.LimitAngle,C13theta <= Basis.LimitAngle,C14theta <= Basis.LimitAngle,C11valid,C12valid,C13valid,C14valid),"PASS","FAIL")'),('LeftTargetStatus','C21target'),('RightTargetStatus','C34target')]:eq(calc,f'{name} = {expr}')
    head(r,'STEP 3 OF 4 | CAP / LENGTH / LAYER',True)
    for wi,wid in enumerate(source_walls,1):
        pre=f'W{wi}'
        # Signed normal setback; small cap overhang beyond returns is kept negative.
        eq(calc,f'CapSetback{wi} = -{pre}x*{pre}nx-{pre}y*{pre}ny-Abs({pre}nx)*CapX-Abs({pre}ny)*CapY')
    eq(calc,'FrontCapStatus = If(CapSetback1 >= 24 in,"PASS","FAIL")')
    table(r,'Separate',['Independent check','Live result'],[
     ['Front cap face to back of front panel',ref('CapSetback1 to in')],['Front setback requirement',ref('FrontCapStatus')],
     ['Cap signed setback from left return',ref('CapSetback2 to in')],['Cap signed setback from right return',ref('CapSetback3 to in')],
     ['Strap layer elevation',ref('Basis.Layer')],['Cap soffit elevation',ref('CapBottom')],['Selected route length',ref('RouteLength')]], [340,190])
    p(r,'Negative return setback means the cap footprint overlaps the wall line; it is not a 24-in front-wall pass. The selected layer is below the cap, so the cap projection is shown but not treated as an obstruction at that layer. No vertical detour through/under the cap is calculated.')
    p(r,'Current landing wall interior angles are 90 deg. Layer and local wall H are checked at the anchor. The wall envelope is conservatively retained along the entire route without taking credit for wall height steps. Vendor development length, opposing reinforcement interference, connection width/edge offsets and full backfill domain require separate detailing.')
    head(r,'STEP 4 OF 4 | USE AND LIMITATIONS')
    p(r,'Edit common controls on the first tab. Expand EditableGeometry here for wall lines, panel thickness, pile sizes and layer offsets. Walls must remain parallel to the sheet axes; rotated-wall inputs are rejected. Recalculate in Blockpad. Inspect both signed routes and the all-origin table after each change.')
    p(r,'A source snapshot is not an approved as-built survey. Geometry outputs are unfactored lengths and angles. Plumb-pile plan clearance does not verify 24-in battered-pile-to-leveling-pad clearance at depth. Set VendorReady only when the trial inputs have been confirmed.')
    eq(r,'ReviewState = If(Basis.VendorReady,"INPUTS MARKED CONFIRMED - GEOMETRY SCREEN ONLY","REVIEW - VENDOR INPUTS UNCONFIRMED")')

    # Plot expressions require qualified references because canvas has its own scope.
    names={d['formula'].split(' = ')[0].split('(')[0] for d in defs if d['report']==rid}
    for el in canvas.findall('plot'):
        f=el.get('formula')
        f=re.sub(r'(?<![\w.])([A-Za-z][A-Za-z0-9]*)(?![\w.])',lambda m:rid+'.'+m[1] if m[1] in names else m[1],f)
        el.set('formula',f)

doc.remove(methods);doc.append(methods)
path=HERE/'MSE Strap Clearance - Both End Bents.bpad'
E.ElementTree(doc).write(str(path),encoding='utf-8',xml_declaration=True,pretty_print=True)
(HERE/'formulas.json').write_text(json.dumps(defs,indent=2))
print(json.dumps({'file':str(path),'native_definitions':len(defs),'reports':len(doc.findall('report')),'live_plots':len(doc.findall('.//plot'))}))
