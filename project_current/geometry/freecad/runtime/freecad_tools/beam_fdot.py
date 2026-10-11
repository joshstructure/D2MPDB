"""Source-linked FDOT-style symbolic beam drawings and nominal steel weights.

Presentation only: original Arch rebars and their native sources remain editable.
References: January 2026 SDM 4.3, 4.3.7, 4.3.10; FY2026-27 Spec 415-7.2.
"""
import hashlib
import json
import math
import re
import traceback
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import escape

import FreeCAD as App
import FreeCADGui as Gui
import Part

from . import beam, beam_drawings, beam_hooks
from .geometry import bounds, length, result

PAGES=('BeamFdotAssemblySheet','BeamFdotDetailSheet')
SYMBOLS=('BeamFdotAssembly','BeamFdotDetails')
FACTORS={3:0.376,4:0.668,5:1.043,6:1.502,7:2.044,8:2.670}
FAMILIES=[('A','Bottom',('BottomBars',)),('B','Top',('TopBars',)),
          ('C','Side',('SideBarsLeft','SideBarsRight')),('D','Stirrup',('Stirrups',))]
PREFIXES={'BottomBars':'Bottom','TopBars':'Top','SideBarsLeft':'SideLeft',
          'SideBarsRight':'SideRight','Stirrups':'Stirrup'}
W,H=431.8,279.4
SCALE=1/32
FDOT_URL='https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/structures/structuresmanual/currentrelease/2026/2026-fdot-structures-manual.pdf'
SPEC_URL='https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/specifications/by-year/fy-2026-27/ebook/fy-2026-27-ebook-compressed.pdf'
UNIT_WEIGHT_URL='https://www.cascadesteel.com/products/rebar'


def sources(doc):
    """Use the installed native ArchRebar centerline API, not new bar geometry."""
    data={}
    for name in beam.SETS:
        rb=doc.getObject(name)
        wires,radius=rb.Proxy.getRebarData(rb)
        if len(wires)!=rb.Amount: raise ValueError('Native centerline count mismatch: '+name)
        data[name]=[w.copy() for w in wires]
    return data


def size(doc,prefix):
    return int(getattr(doc.BeamInputs,prefix+'BarNumber'))


def mark(doc,letter,prefix):
    return str(size(doc,prefix))+letter


def source_state(doc):
    state=beam_drawings.model_state(doc)
    # Mark is the sole authorized change to existing rebar expression engines.
    for obj in state['objects'].values():
        obj['expressions']=[e for e in obj['expressions'] if e[0]!='Mark']
    return state


def svg_root():
    return ['<svg xmlns="http://www.w3.org/2000/svg" width="431.8mm" height="279.4mm" viewBox="0 0 431.8 279.4">']


def text(out,x,y,value,pt=2.8,bold=False,anchor='start'):
    out.append('<text x="%.6f" y="%.6f" font-family="Arial" font-size="%.6f" text-anchor="%s" fill="#111111"%s>%s</text>'
               %(x,y,pt,anchor,' font-weight="bold"' if bold else '',escape(str(value))))


def line(out,x1,y1,x2,y2,width=.18,color='#333333',extra=''):
    out.append('<line x1="%.6f" y1="%.6f" x2="%.6f" y2="%.6f" stroke="%s" stroke-width="%.6f" %s/>'%(x1,y1,x2,y2,color,width,extra))


def arrow(out,tip,tail):
    line(out,*tail,*tip,.18)
    dx,dy=tail[0]-tip[0],tail[1]-tip[1]
    le=math.hypot(dx,dy)
    if le==0:return
    ux,uy=dx/le,dy/le
    pts=[tip,(tip[0]+1.6*ux+.55*uy,tip[1]+1.6*uy-.55*ux),(tip[0]+1.6*ux-.55*uy,tip[1]+1.6*uy+.55*ux)]
    out.append('<polygon points="%s" fill="#111111"/>'%' '.join('%.6f,%.6f'%p for p in pts))


def leader(out,tip,label,x,y,anchor='start'):
    text(out,x,y,label,2.6,False,anchor)
    tail=(x if anchor=='start' else x,y+1.4)
    arrow(out,tip,tail)


def inch(value,precision=3):
    return ('%.*f'%(precision,value/25.4)).rstrip('0').rstrip('.')+'"'


def feet(value):
    units=int(math.floor(value/25.4+0.5))
    return "%d'-%d\""%(units//12,units%12)


def hd(out,x1,x2,y,object_y,label):
    line(out,x1,object_y,x1,y-2,.13)
    line(out,x2,object_y,x2,y-2,.13)
    line(out,x1,y,x2,y,.15)
    arrow(out,(x1,y),(x1+2.5,y));arrow(out,(x2,y),(x2-2.5,y))
    text(out,(x1+x2)/2,y-1.8,label,2.7,False,'middle')


def vd(out,y1,y2,x,object_x,label):
    line(out,object_x,y1,x-2,y1,.13);line(out,object_x,y2,x-2,y2,.13)
    line(out,x,y1,x,y2,.15)
    arrow(out,(x,y1),(x,y1+2.5));arrow(out,(x,y2),(x,y2-2.5))
    # Horizontal dimension text is easier to read at these small scales.
    text(out,x-2,(y1+y2)/2+1,label,2.5,False,'end')


def projection(p,kind):
    if kind=='front': return p.x,-p.z
    if kind=='plan': return p.x,p.y
    if kind=='section': return p.y,-p.z
    raise ValueError(kind)


def drawing_geometry(wires,kind,origin):
    """Return one stroke per native edge and dots for end-on straight segments.

    Curve tessellation is confined to paper graphics. The model's exact curves
    are retained and independently checked against physical nominal solids.
    """
    paths={};dots={}
    def paper(p):
        x,y=projection(p,kind)
        return origin[0]+x*SCALE,origin[1]+y*SCALE
    for wire in wires:
        for edge in wire.Edges:
            is_line=isinstance(edge.Curve,(Part.Line,Part.LineSegment))
            pts=[v.Point for v in edge.Vertexes] if is_line else edge.discretize(Deflection=.025)
            if len(pts)<2: raise ValueError('Unsupported centerline edge')
            xy=[paper(p) for p in pts]
            spread=max(math.hypot(x-xy[0][0],y-xy[0][1]) for x,y in xy)
            if spread<1e-7:
                if not is_line: raise ValueError('A curved edge unexpectedly projects to one point')
                dots[tuple(round(v,7) for v in xy[0])]=xy[0]
            else:
                key=tuple((round(x,7),round(y,7)) for x,y in xy)
                key=min(key,key[::-1])
                paths[key]=xy
    return list(paths.values()),list(dots.values())


def draw_wires(out,wires,kind,origin,group):
    paths,dots=drawing_geometry(wires,kind,origin)
    out.append('<g id="%s" data-kind="%s">'%(group,kind))
    for pts in paths:
        out.append('<polyline data-role="rebar-centerline" points="%s" stroke="#111111" stroke-width="0.38" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
                   %' '.join('%.6f,%.6f'%p for p in pts))
    for x,y in dots:
        out.append('<circle data-role="end-on" cx="%.6f" cy="%.6f" r="0.5" fill="#111111"/>'%(x,y))
    out.append('</g>')
    return len(paths),len(dots)


def section_points(doc,data):
    xcut=doc.BeamInputs.Length.Value/2
    points=[]
    for name in beam.SETS[:-1]:
        for wi,wire in enumerate(data[name]):
            candidates=[]
            for e in wire.Edges:
                if isinstance(e.Curve,(Part.Line,Part.LineSegment)):
                    a,b=[v.Point for v in e.Vertexes]
                    if abs(b.x-a.x)>1e-10 and min(a.x,b.x)<=xcut<=max(a.x,b.x):
                        p=a+(b-a)*((xcut-a.x)/(b.x-a.x))
                        candidates.append(p)
            if len(candidates)!=1: raise ValueError('Section needs exactly one crossing per longitudinal bar')
            points.append((name,wi,candidates[0]))
    return points


def outline(out,x,y,w,h):
    out.append('<rect x="%.6f" y="%.6f" width="%.6f" height="%.6f" fill="none" stroke="#777777" stroke-width="0.18"/>'%(x,y,w,h))


def stirrup_elevation_symbols(doc, data):
    """Presentation at nominal stations; native wires still govern bar quantities.

    The rounded nonplanar stirrup projects to several strokes in side view.
    This intentionally replaces only that view with the requested line/dot symbol.
    """
    wires=data['Stirrups']
    indices=sorted(set((0,len(wires)-1)))
    i=doc.BeamInputs
    output=[]
    for index in indices:
        box=bounds(wires[index])
        x=i.StirrupFirstDatum.Value+index*doc.Stirrups.Spacing.Value
        if not box.XMin <= x <= box.XMax:
            raise ValueError('Nominal stirrup station is outside native wire extent')
        output.append((index,x,box.ZMin,box.ZMax))
    return output


def draw_stirrup_elevation(out,doc,data,origin):
    out.append('<g id="elevation-stirrups" data-source="Stirrups" data-kind="front">')
    for index,x,zmin,zmax in stirrup_elevation_symbols(doc,data):
        px=origin[0]+x*SCALE
        ys=[origin[1]-zmin*SCALE,origin[1]-zmax*SCALE]
        out.append('<polyline data-role="stirrup-elevation-line" data-index="%d" points="%.6f,%.6f %.6f,%.6f" stroke="#111111" stroke-width="0.38" fill="none"/>'%(index,px,ys[0],px,ys[1]))
        for py in ys:
            out.append('<circle data-role="stirrup-elevation-end" data-index="%d" cx="%.6f" cy="%.6f" r="0.5" fill="#111111"/>'%(index,px,py))
    out.append('</g>')


def assembly_svg(doc):
    data=sources(doc);i=doc.BeamInputs
    out=svg_root();L=i.Length.Value*SCALE;B=i.Width.Value*SCALE;D=i.Height.Value*SCALE
    text(out,112,46,'ELEVATION',3.5,True,'middle')
    text(out,112,52,'3/8" = 1\'-0"',2.7,False,'middle')
    x,y=74,112
    outline(out,x,y-D,L,D)
    longitudinal=[w for n in beam.SETS[:-1] for w in data[n]]
    view_wires=longitudinal+[data['Stirrups'][0],data['Stirrups'][-1]]
    draw_wires(out,longitudinal,'front',(x,y),'elevation-rebar')
    draw_stirrup_elevation(out,doc,data,(x,y))
    hd(out,x,x+L,y-D-11,y-D,feet(i.Length.Value))
    vd(out,y-D,y,x-10,x,feet(i.Height.Value))
    text(out,112,122,'%d ~ %s @ %s (first and last shown)'%(doc.Stirrups.Amount,doc.Stirrups.Mark,inch(doc.Stirrups.Spacing.Value)),2.7,False,'middle')
    text(out,112,129,'%d ~ %s bottom; %d ~ %s top'%(doc.BottomBars.Amount,doc.BottomBars.Mark,doc.TopBars.Amount,doc.TopBars.Mark),2.7,False,'middle')
    text(out,112,136,'%d ~ %s @ %s each side'%(doc.SideBarsLeft.Amount,doc.SideBarsLeft.Mark,inch(doc.SideBarsLeft.Spacing.Value)),2.7,False,'middle')
    text(out,112,143,'Stirrups in elevation: straight line with filled ends.',2.4,False,'middle')
    # A-A datum is the actual mid-length plane used for the section dots.
    cx=x+L/2
    line(out,cx,y-D-4,cx,y+4,.13,extra='stroke-dasharray="3,1,0.5,1"')
    text(out,cx+3,y-D-4,'A',2.5);text(out,cx+3,y+5,'A',2.5)
    text(out,112,157,'PLAN',3.5,True,'middle')
    text(out,112,163,'3/8" = 1\'-0"',2.7,False,'middle')
    xp,yp=74,180
    outline(out,xp,yp,L,B)
    draw_wires(out,view_wires,'plan',(xp,yp),'plan-rebar')
    vd(out,yp,yp+B,xp-10,xp,feet(i.Width.Value))
    text(out,112,211,'Bars shown above and below; coincident lines merge.',2.6,False,'middle')
    text(out,112,218,'End-on hook legs use the same filled-circle symbol.',2.6,False,'middle')
    text(out,313,46,'SECTION A-A',3.5,True,'middle')
    text(out,313,52,'3/8" = 1\'-0"; at mid-length',2.7,False,'middle')
    sx,sy=296,109
    outline(out,sx,sy-D,B,D)
    nearest=min(data['Stirrups'],key=lambda w:abs(w.CenterOfMass.x-i.Length.Value/2))
    draw_wires(out,[nearest],'section',(sx,sy),'section-stirrup')
    pts=section_points(doc,data)
    out.append('<g id="section-bars">')
    for name,wi,p in pts:
        out.append('<circle data-role="section-bar" data-source="%s" data-index="%d" cx="%.6f" cy="%.6f" r="0.5" fill="#111111"/>'%(name,wi,sx+p.y*SCALE,sy-p.z*SCALE))
    out.append('</g>')
    top=[p for n,j,p in pts if n=='TopBars'];bottom=[p for n,j,p in pts if n=='BottomBars']
    left=[p for n,j,p in pts if n=='SideBarsLeft'];right=[p for n,j,p in pts if n=='SideBarsRight']
    leader(out,(sx+top[-1].y*SCALE,sy-top[-1].z*SCALE),doc.TopBars.Mark,346,77)
    leader(out,(sx+bottom[-1].y*SCALE,sy-bottom[-1].z*SCALE),doc.BottomBars.Mark,346,117)
    leader(out,(sx+left[1].y*SCALE,sy-left[1].z*SCALE),doc.SideBarsLeft.Mark,274,96,'end')
    leader(out,(sx+right[1].y*SCALE,sy-right[1].z*SCALE),doc.SideBarsRight.Mark,346,96)
    leader(out,(sx+doc.Stirrups.Base.Shape.BoundBox.YMax*SCALE,sy-(i.Height.Value/2)*SCALE),doc.Stirrups.Mark,365,105)
    text(out,313,134,'All %d longitudinal bars shown in section.'%len(pts),2.7,False,'middle')
    text(out,313,141,'Nearest stirrup projected at section for clarity.',2.7,False,'middle')
    text(out,254,168,'REPRESENTATION',3.2,True)
    line(out,254,178,268,178,.38,'#111111');text(out,274,179,'Single unbroken line: rebar centerline',2.7)
    out.append('<circle cx="261" cy="189" r="0.5" fill="#111111"/>')
    text(out,274,190,'Filled circle: bar viewed end-on / cut bar',2.7)
    line(out,254,200,268,200,.18,'#777777');text(out,274,201,'Light outline: concrete boundary',2.7)
    text(out,254,216,'Bill quantities once on R-04; other views are references.',2.6)
    text(out,254,223,'Geometry and quantities remain linked to the model.',2.6)
    out.append('</svg>')
    return '\n'.join(out)


def detail_svg(doc):
    data=sources(doc);out=svg_root()
    text(out,W/2,44,'LIVE REINFORCING BAR LIST - ONE DEMONSTRATION BEAM',3.3,True,'middle')
    text(out,20,108,'Listed L: modeled centerline rounded to nearest inch. Unit weights: nominal lb/ft.',2.6)
    text(out,20,114,'Model wt uses full-precision centerlines; listed wt uses listed L. Both include modeled bends.',2.6)
    positions=[(104,154,'BottomBars','front','BOTTOM MAIN BAR'),(309,154,'TopBars','front','TOP MAIN BAR'),
               (104,209,'SideBarsLeft','plan','SIDE BARS - BOTH FACES'),(309,211,'Stirrups','section','STIRRUP')]
    for cx,cy,name,kind,title in positions:
        rb=doc.getObject(name);wire=data[name][0]
        samples=[p for e in wire.Edges for p in e.discretize(Number=12)]
        xy=[projection(p,kind) for p in samples]
        xmin=min(p[0] for p in xy);xmax=max(p[0] for p in xy)
        ymin=min(p[1] for p in xy);ymax=max(p[1] for p in xy)
        origin=(cx-(xmin+xmax)*SCALE/2,cy-(ymin+ymax)*SCALE/2)
        text(out,cx,cy-22,rb.Mark+' - '+title,3.0,True,'middle')
        draw_wires(out,[wire],kind,origin,'detail-'+name)
        bb=bounds(rb.Shape.Solids[0])
        if kind=='front': a,b,c,d=bb.XMin,bb.XMax,-bb.ZMax,-bb.ZMin
        elif kind=='plan': a,b,c,d=bb.XMin,bb.XMax,bb.YMin,bb.YMax
        else:a,b,c,d=bb.YMin,bb.YMax,-bb.ZMax,-bb.ZMin
        x1,x2=origin[0]+a*SCALE,origin[0]+b*SCALE
        y1,y2=origin[1]+c*SCALE,origin[1]+d*SCALE
        hd(out,x1,x2,y2+6,y2,inch(b-a)+' out-to-out')
        if name not in ('SideBarsLeft',): vd(out,y1,y2,x1-6,x1,inch(d-c))
        text(out,cx,cy+22,'3/8" = 1\'-0" | dimensions out-to-out',2.5,False,'middle')
    out.append('</svg>')
    return '\n'.join(out)


class SymbolProxy:
    def __init__(self,obj,kind):
        obj.addProperty('App::PropertyLinkList','Sources','Sources')
        obj.Sources=[obj.Document.getObject(n) for n in ('BeamInputs','ConcreteBeam',*beam.SETS,'BeamQuantities')]
        obj.addProperty('App::PropertyString','DiagramKind','Presentation');obj.DiagramKind=kind
        obj.addProperty('App::PropertyFloat','ModelScale','Presentation');obj.ModelScale=SCALE
        obj.addProperty('App::PropertyString','DraftingBasis','Presentation')
        obj.DraftingBasis='FDOT SDM January 2026 4.3, 4.3.7; single line at 3/8 in = 1 ft; filled end-on symbols'
        obj.addProperty('App::PropertyString','SvgContent','Output')
        for name in ('Sources','DiagramKind','ModelScale','DraftingBasis','SvgContent'):obj.setEditorMode(name,1)
        obj.Proxy=self
    def execute(self,obj):
        content=assembly_svg(obj.Document) if obj.DiagramKind=='assembly' else detail_svg(obj.Document)
        if obj.SvgContent!=content:obj.SvgContent=content
    def dumps(self):return None
    def loads(self,state):pass


def weights_and_marks(doc):
    q=doc.BeamQuantities
    changes={}
    for letter,input_prefix,names in FAMILIES:
        for name in names:
            rb=doc.getObject(name);prefix=PREFIXES[name]
            old=rb.Mark
            rb.setExpression('Mark','str(BeamInputs.'+input_prefix+'BarNumber) + <<'+letter+'>>')
            changes[name]={'old':old,'new':mark(doc,letter,input_prefix)}
            expr='0'
            for n,value in reversed(list(FACTORS.items())):
                expr='BeamInputs.%sBarNumber == %d ? %.6f : (%s)'%(input_prefix,n,value,expr)
            beam.prop(q,'App::PropertyFloat',prefix+'UnitWeightLbFt',group='Rebar weight',expression=expr)
            beam.prop(q,'App::PropertyFloat',prefix+'WeightLb',group='Rebar weight',expression=name+'.TotalLength / (1 ft) * '+prefix+'UnitWeightLbFt')
            beam.prop(q,'App::PropertyFloat',prefix+'ListedLengthIn',group='Rebar weight',expression='round('+name+'.Length / (1 in))')
            beam.prop(q,'App::PropertyFloat',prefix+'ListedWeightLb',group='Rebar weight',expression=prefix+'ListedLengthIn / 12 * '+name+'.Amount * '+prefix+'UnitWeightLbFt')
    beam.prop(q,'App::PropertyFloat','TotalRebarWeightLb',group='Rebar weight',expression=' + '.join(p+'WeightLb' for p in PREFIXES.values()))
    beam.prop(q,'App::PropertyFloat','TotalListedRebarWeightLb',group='Rebar weight',expression=' + '.join(p+'ListedWeightLb' for p in PREFIXES.values()))
    beam.prop(q,'App::PropertyString','WeightBasis','Rebar weight = centerline length x CRSI nominal unit weight; listed weight uses nearest-inch length; no waste/coating/tie-wire allowance.','Rebar weight')
    doc.recompute()
    return changes


def schedules(doc,folder):
    old=doc.BeamSchedule
    old.set('H1','Wt (lb)')
    for row,(_,name,_) in enumerate(beam_drawings.ROWS,2):
        old.set('A'+str(row),'='+name+'.Mark')
        old.set('N'+str(row),'=BeamQuantities.'+PREFIXES[name]+'WeightLb')
        old.set('H'+str(row),'=round(N'+str(row)+' * 1000) / 1000')
    old.set('N7','=BeamQuantities.TotalRebarWeightLb');old.set('H7','=round(N7 * 1000) / 1000')
    for row in range(9,20):
        old.splitCell('E'+str(row));old.mergeCells('E'+str(row)+':H'+str(row))
    for row,label in ((16,'Bottom inside bend diameter (in)'),(17,'Top inside bend diameter (in)'),
                      (18,'Bottom hook straight tail (in)'),(19,'Top hook straight tail (in)')):old.set('A'+str(row),label)
    for col,width in zip('ABCDEFGH',(56,45,40,72,120,108,75,94)):old.setColumnWidth(col,width)
    old.setStyle('A1:H1','bold','add');old.setStyle('A7:H7','bold','add')
    old.setBackground('A1:H1',(0.88,0.92,0.95));old.setBackground('A7:H7',(0.88,0.92,0.95))
    old.setAlignment('B1:H7','center','keep')
    doc.BeamScheduleView.CellEnd='H19'
    # The existing detail headings become size-independent; row marks are live.
    old_template=doc.BeamDetailSheet.Template
    raw=__import__('pathlib').Path(old_template.Template).read_text(encoding='utf-8')
    for a,b in [('B1 - BOTTOM BAR CENTERLINE','BOTTOM MAIN BAR CENTERLINE'),('T1 - TOP BAR CENTERLINE','TOP MAIN BAR CENTERLINE'),
                ('W1 / W2 - SIDE BAR CENTERLINE','SIDE BAR CENTERLINE - BOTH FACES'),('S1 - STIRRUP CENTERLINE','STIRRUP CENTERLINE')]:raw=raw.replace(a,b)
    dest=folder/'BeamDetailSheet-fdot-marks-template.svg';dest.write_text(raw,encoding='utf-8');old_template.Template=str(dest)
    s=doc.addObject('Spreadsheet::Sheet','BeamFdotSchedule');s.Label='FDOT marks and LIVE steel weights'
    heads=['Mark','Qty','Each CL (in)','Listed L (in)','Total CL (ft)','Unit (lb/ft)','Model wt (lb)','Listed wt (lb)']
    for c,t in zip('ABCDEFGH',heads):s.set(c+'1',t)
    for row,(letter,input_prefix,names) in enumerate(FAMILIES,2):
        name=names[0];prefix=PREFIXES[name]
        s.set('A'+str(row),'='+name+'.Mark')
        s.set('B'+str(row),'='+' + '.join(n+'.Amount' for n in names))
        raw={'J':name+'.Length / (1 in)','K':'BeamQuantities.'+prefix+'ListedLengthIn',
             'L':' + '.join(n+'.TotalLength / (1 ft)' for n in names),
             'M':'BeamQuantities.'+prefix+'UnitWeightLbFt',
             'N':' + '.join('BeamQuantities.'+PREFIXES[n]+'WeightLb' for n in names),
             'O':' + '.join('BeamQuantities.'+PREFIXES[n]+'ListedWeightLb' for n in names)}
        for c,expr in raw.items():s.set(c+str(row),'='+expr)
        for c,rc in zip('CDEFGH','JKLMNO'):s.set(c+str(row),'=round('+rc+str(row)+' * 1000) / 1000')
    s.set('A6','TOTAL');s.set('B6','=BeamQuantities.TotalBars')
    s.set('E6','=round(BeamQuantities.TotalSteelLength / (1 ft) * 1000) / 1000')
    s.set('G6','=round(BeamQuantities.TotalRebarWeightLb * 1000) / 1000')
    s.set('H6','=round(BeamQuantities.TotalListedRebarWeightLb * 1000) / 1000')
    for c,width in zip('ABCDEFGH',(90,70,185,185,185,165,230,230)):s.setColumnWidth(c,width)
    for row in range(1,7):s.setRowHeight(str(row),26)
    for region in ('A1:H1','A6:H6'):
        s.setStyle(region,'bold','add');s.setBackground(region,(.90,.92,.94))
    s.setAlignment('A1:H6','center','keep')
    beam.prop(doc.BeamQuantities,'App::PropertyLink','FdotSchedule',s,'Presentation')
    return s


def page_template(index):
    out=svg_root()
    outline(out,12.7,12.7,406.4,254)
    line(out,12.7,33,419.1,33);line(out,12.7,249,419.1,249)
    text(out,18,22,'REINFORCED CONCRETE BEAM | SYMBOLIC REINFORCEMENT',4.2,True)
    text(out,18,29,('R-03 | ELEVATION, PLAN AND SECTION' if index==0 else 'R-04 | BAR DETAILS AND LIVE WEIGHTS')+' | FDOT DRAFTING CONVENTIONS',2.6)
    text(out,18,256,'DEMONSTRATION - NOT FOR CONSTRUCTION. Drafting conventions do not establish design or fabrication approval.',2.6,True)
    text(out,18,263,'Basis: FDOT SDM Jan. 2026 Sections 4.3, 4.3.7, 4.3.10; Spec. 415-7.2. Original physical-geometry sheets: R-01 / R-02.',2.4)
    out.append('</svg>');return '\n'.join(out)


def build(doc,folder):
    changes=weights_and_marks(doc)
    schedule=schedules(doc,folder)
    for j,name in enumerate(PAGES):
        path=folder/(name+'-template.svg');path.write_text(page_template(j),encoding='utf-8')
        page=doc.addObject('TechDraw::DrawPage',name);page.Label='R-03 - FDOT symbolic views' if j==0 else 'R-04 - FDOT bar details and LIVE weights'
        t=doc.addObject('TechDraw::DrawSVGTemplate',name+'Template');t.Template=str(path);page.Template=t
        page.ViewObject.ShowFrames=False;page.ViewObject.show()
        generator=doc.addObject('App::FeaturePython',SYMBOLS[j]+'Source')
        SymbolProxy(generator,'assembly' if j==0 else 'details')
        generator.Proxy.execute(generator)
        v=doc.addObject('TechDraw::DrawViewSymbol',SYMBOLS[j])
        for kind,prop,value in [('App::PropertyLinkList','Sources',generator.Sources),
                                ('App::PropertyString','DiagramKind',generator.DiagramKind),
                                ('App::PropertyFloat','ModelScale',generator.ModelScale)]:
            beam.prop(v,kind,prop,value,'Sources')
            v.setEditorMode(prop,1)
        v.Owner=generator
        v.setExpression('Symbol',generator.Name+'.SvgContent')
        page.addView(v);v.X=W/2;v.Y=H/2;v.Scale=1;v.ScaleType='Custom'
        beam_drawings.optional(v.ViewObject,'KeepLabel',False)
    tv=doc.addObject('TechDraw::DrawViewSpreadsheet','BeamFdotScheduleView');doc.BeamFdotDetailSheet.addView(tv)
    tv.Source=schedule;tv.CellStart='A1';tv.CellEnd='H6';tv.Font='Arial';tv.TextSize=11;tv.LineWidth=.35
    tv.ScaleType='Custom';tv.Scale=1;tv.X=W/2;tv.Y=H-78
    beam_drawings.optional(tv.ViewObject,'LegacyScaling',True);beam_drawings.optional(tv.ViewObject,'KeepLabel',False)
    doc.recompute()
    from PySide import QtWidgets
    QtWidgets.QApplication.processEvents()
    return changes


def checks(doc,tol):
    c=[];data=sources(doc);q=doc.BeamQuantities;total_weight=0;listed_weight=0
    for letter,ip,names in FAMILIES:
        bn=size(doc,ip)
        c.append(result(ip+'.nominal_weight_size_supported',bn in FACTORS,bar_number=bn))
        if bn not in FACTORS:continue
        first=doc.getObject(names[0])
        c.append(result(letter+'.same_mark_same_bar_pattern',all(
            abs(doc.getObject(n).Diameter.Value-first.Diameter.Value)<=tol
            and abs(doc.getObject(n).Length.Value-first.Length.Value)<=tol
            and len(data[n][0].Edges)==len(data[names[0]][0].Edges) for n in names)))
        for name in names:
            rb=doc.getObject(name);prefix=PREFIXES[name]
            physical=rb.Shape.Volume/(math.pi*rb.Diameter.Value**2/4)
            nominal=physical/304.8*FACTORS[bn];listed=math.floor(rb.Length.Value/25.4+.5)/12*rb.Amount*FACTORS[bn]
            total_weight+=nominal;listed_weight+=listed
            c.append(result(name+'.native_centerline',len(data[name])==len(rb.Shape.Solids)
                            and abs(sum(w.Length for w in data[name])-physical)<=tol,
                            source_length_mm=sum(w.Length for w in data[name]),physical_length_mm=physical))
            # Native centerline samples must lie inside the original nominal steel.
            misplaced=[]
            for wi,w in enumerate(data[name]):
                for ei,e in enumerate(w.Edges):
                    p=e.valueAt((e.FirstParameter+e.LastParameter)/2)
                    if not rb.Shape.isInside(p,tol,True):misplaced.append([wi,ei])
            c.append(result(name+'.centerline_inside_physical_steel',not misplaced,failures=misplaced))
            c.append(result(name+'.fdot_mark',rb.Mark==str(bn)+letter and dict(rb.ExpressionEngine).get('Mark')=='str(BeamInputs.'+ip+'BarNumber) + <<'+letter+'>>',mark=rb.Mark))
            c.append(result(name+'.live_weight',abs(getattr(q,prefix+'UnitWeightLbFt')-FACTORS[bn])<1e-10
                            and abs(getattr(q,prefix+'WeightLb')-nominal)<1e-6
                            and abs(getattr(q,prefix+'ListedWeightLb')-listed)<1e-6,
                            model_weight_lb=nominal,listed_weight_lb=listed))
    c.append(result('live_weight_totals',abs(q.TotalRebarWeightLb-total_weight)<1e-6 and abs(q.TotalListedRebarWeightLb-listed_weight)<1e-6,
                    model_weight_lb=total_weight,listed_weight_lb=listed_weight))
    s=doc.BeamFdotSchedule
    c.append(result('weight_schedule_source',q.FdotSchedule==s and doc.BeamFdotScheduleView.Source==s))
    c.append(result('weight_schedule_display_totals',beam_drawings.number(s.get('B6'))==q.TotalBars
                    and abs(beam_drawings.number(s.get('E6'))-round(q.TotalSteelLength.Value/304.8,3))<1e-8
                    and abs(beam_drawings.number(s.get('G6'))-round(q.TotalRebarWeightLb,3))<1e-8
                    and abs(beam_drawings.number(s.get('H6'))-round(q.TotalListedRebarWeightLb,3))<1e-8
                    and abs(beam_drawings.number(doc.BeamSchedule.get('H7'))-round(q.TotalRebarWeightLb,3))<1e-8))
    tv=doc.BeamFdotScheduleView
    tw=sum(s.getColumnWidth(col) for col in 'ABCDEFGH')/96*25.4*tv.Scale
    th=sum(s.getRowHeight(str(row)) for row in range(1,7))/96*25.4*tv.Scale
    c.append(result('weight_schedule_paper_fit',tv.X.Value-tw/2>=18 and tv.X.Value+tw/2<=414
                    and H-tv.Y.Value-th/2>=53 and H-tv.Y.Value+th/2<=102,
                    paper_bounds_mm=[tv.X.Value-tw/2,H-tv.Y.Value-th/2,tv.X.Value+tw/2,H-tv.Y.Value+th/2]))
    for row,(letter,ip,names) in enumerate(FAMILIES,2):
        vals={col:beam_drawings.number(s.get(col+str(row))) for col in 'BCDEFGH'}
        expected=[sum(doc.getObject(n).Amount for n in names),round(doc.getObject(names[0]).Length.Value/25.4,3),
                  math.floor(doc.getObject(names[0]).Length.Value/25.4+.5),round(sum(doc.getObject(n).TotalLength.Value for n in names)/304.8,3),
                  FACTORS[size(doc,ip)],round(sum(getattr(q,PREFIXES[n]+'WeightLb') for n in names),3),round(sum(getattr(q,PREFIXES[n]+'ListedWeightLb') for n in names),3)]
        c.append(result('fdot_schedule_row_'+letter,s.get('A'+str(row))==mark(doc,letter,ip)
                        and all(abs(v-e)<1e-8 for v,e in zip(vals.values(),expected))))
    for row,(_,name,_) in enumerate(beam_drawings.ROWS,2):
        c.append(result(name+'.existing_schedule_mark_and_weight',doc.BeamSchedule.get('A'+str(row))==doc.getObject(name).Mark
                        and abs(beam_drawings.number(doc.BeamSchedule.get('H'+str(row)))-round(getattr(q,PREFIXES[name]+'WeightLb'),3))<1e-8))
    ns={'s':'http://www.w3.org/2000/svg'}
    root=ET.fromstring(doc.BeamFdotAssembly.Symbol)
    symbol_group=root.find("s:g[@id='elevation-stirrups']",ns)
    strokes=[] if symbol_group is None else symbol_group.findall('s:polyline',ns)
    ends=[] if symbol_group is None else symbol_group.findall('s:circle',ns)
    indices=sorted(set((0,doc.Stirrups.Amount-1)))
    solids=sorted(doc.Stirrups.Shape.Solids,key=lambda s:s.CenterOfMass.x)
    okay=len(strokes)==len(indices) and len(ends)==2*len(indices)
    for index in indices:
        paths=[p for p in strokes if p.get('data-index')==str(index)]
        tips=[p for p in ends if p.get('data-index')==str(index)]
        if len(paths)!=1 or len(tips)!=2:
            okay=False;continue
        xy=[tuple(map(float,p.split(','))) for p in paths[0].get('points').split()]
        expected_x=74+(doc.BeamInputs.StirrupFirstDatum.Value+index*doc.Stirrups.Spacing.Value)*SCALE
        physical=bounds(solids[index]);radius=doc.Stirrups.Diameter.Value/2
        expected_y=sorted((112-(physical.ZMin+radius)*SCALE,112-(physical.ZMax-radius)*SCALE))
        okay &= len(xy)==2 and max(abs(p[0]-expected_x) for p in xy)<=tol*SCALE
        okay &= max(abs(a-b) for a,b in zip(sorted(p[1] for p in xy),expected_y))<=tol*SCALE
        okay &= all(any(abs(float(t.get('cx'))-x)<tol*SCALE and abs(float(t.get('cy'))-y)<tol*SCALE for t in tips) for x,y in xy)
        okay &= all(t.get('fill')=='#111111' and float(t.get('r'))==0.5 for t in tips)
    c.append(result('stirrup_elevation_line_and_filled_ends',bool(okay),symbols=len(strokes),filled_ends=len(ends),basis='Nominal station and independently measured physical bar height minus radius'))
    long_group=root.find("s:g[@id='elevation-rebar']",ns)
    long_paths,_=drawing_geometry([w for n in beam.SETS[:-1] for w in data[n]],'front',(74,112))
    actual_paths=[] if long_group is None else long_group.findall('s:polyline',ns)
    c.append(result('elevation_longitudinal_centerlines_preserved',len(actual_paths)==len(long_paths)
                    and all(p.get('points')==' '.join('%.6f,%.6f'%q for q in expected) for p,expected in zip(actual_paths,long_paths))))
    dots=root.findall('.//s:circle[@data-role="section-bar"]',ns)
    plane=beam_drawings.section_plane(doc)
    for name in beam.SETS[:-1]:
        measured=[]
        for solid in doc.getObject(name).Shape.Solids:
            circ=[e.Curve for e in solid.section(plane).Edges if isinstance(e.Curve,Part.Circle)]
            if len(circ)!=1:raise ValueError('Unexpected physical section topology: '+name)
            measured.append(circ[0].Center)
        drawn=[dot for dot in dots if dot.get('data-source')==name]
        matches=all(any(abs(float(dot.get('cx'))-(296+p.y*SCALE))<tol*SCALE
                            and abs(float(dot.get('cy'))-(109-p.z*SCALE))<tol*SCALE for dot in drawn) for p in measured)
        c.append(result(name+'.filled_symbols_match_physical_cut',len(drawn)==len(measured) and matches and all(d.get('fill')=='#111111' for d in drawn),count=len(drawn)))
    for name,page_name in zip(SYMBOLS,PAGES):
        v=doc.getObject(name);xml=ET.fromstring(v.Symbol)
        paths=xml.findall('.//s:polyline[@data-role="rebar-centerline"]',ns)
        ends=xml.findall('.//s:circle[@data-role="end-on"]',ns)
        c.append(result(name+'.source_links',set(o.Name for o in v.Sources)==set(('BeamInputs','ConcreteBeam',*beam.SETS,'BeamQuantities')) and v in doc.getObject(page_name).Views))
        c.append(result(name+'.single_line_convention',v.ModelScale<1/24 and abs(v.ModelScale-SCALE)<1e-12
                        and bool(paths) and all(p.get('fill')=='none' and 'stroke-dasharray' not in p.attrib for p in paths)
                        and all(d.get('fill')=='#111111' for d in ends),stroke_count=len(paths),end_on_symbols=len(ends)))
        c.append(result(name+'.live_svg',v.Symbol==(assembly_svg(doc) if v.DiagramKind=='assembly' else detail_svg(doc))))
        xy=[]
        for p in paths:
            xy.extend(tuple(float(vv) for vv in pair.split(',')) for pair in p.get('points').split())
        c.append(result(name+'.geometry_paper_fit',all(18<=x<=414 and 36<=y<=247 for x,y in xy)))
    invalid=[o.Name for o in doc.Objects if any('Invalid' in str(s) or 'Error' in str(s) for s in o.State)]
    c.append(result('fdot_dependency_state',not invalid,invalid_objects=invalid))
    return c


def refresh(job):
    from .api import ROOT,document,atomic,compact,check_gui
    doc=document(job.get('document'))
    if job.get('targets')!=list(PAGES):raise ValueError('Explicit FDOT sheet Names required')
    req=job.get('request_id','fdot-refresh-'+uuid.uuid4().hex)
    if not isinstance(req,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',req):raise ValueError('Invalid request_id')
    tol=length(job.get('tolerance','0.001 in'),positive=True)
    path=ROOT/'reports/transactions'/(req+'.json')
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old['request']!=job:raise ValueError('Request ID already used by another job')
        if old['status'] in ('PREPARED','VALIDATED'):raise RuntimeError('Unknown prior outcome; inspect first')
        return compact(old)
    check_gui(doc);before=source_state(doc)
    hashes={n:hashlib.sha256(doc.getObject(n).Shape.cleaned().exportBrepToString().encode()).hexdigest() for n in ('ConcreteBeam',*beam.SETS)}
    record={'timestamp':datetime.now(timezone.utc).isoformat(),'document':doc.Name,'operation':'refresh_beam_fdot_sheets','transaction_id':req,'request':job,'status':'PREPARED','checks':[],'errors':[],'saved':False,'rollback':'NOT NEEDED','report_path':str(path)}
    atomic(path,record);opened=False
    try:
        doc.openTransaction('CAD_AI '+req);opened=True
        for name in SYMBOLS:
            generator=doc.getObject(name+'Source')
            generator.Proxy=SymbolProxy.__new__(SymbolProxy)
            generator.Proxy.execute(generator)
        doc.recompute()
        preserved=beam_hooks.equivalent(before,source_state(doc),tol) and all(hashes[n]==hashlib.sha256(doc.getObject(n).Shape.cleaned().exportBrepToString().encode()).hexdigest() for n in hashes)
        record['checks']=[result('physical_model_preserved',preserved)]+checks(doc,tol)
        if any(c['status']=='FAIL' for c in record['checks']):raise ValueError('FDOT refresh validation failed')
        record['status']='VALIDATED';atomic(path,record);doc.commitTransaction();opened=False;record['status']='PASS'
    except Exception as e:
        record['status']='FAIL';record['errors'].append(str(e));record['traceback']=traceback.format_exc()
        if opened:
            doc.abortTransaction();doc.recompute();record['rollback']='COMPLETE' if beam_hooks.equivalent(before,source_state(doc),tol) else 'INCOMPLETE'
    atomic(path,record)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(compact(record))+'\n')
    return compact(record)


def add(job):
    from .api import ROOT,document,atomic,compact,check_gui
    if set(job)-{'operation','document','targets','tolerance','request_id'}:raise ValueError('Unsupported FDOT job fields')
    doc=document(job.get('document'))
    if job.get('targets')!=['BeamQuantities']:raise ValueError('Explicit BeamQuantities target required')
    req=job.get('request_id','fdot-'+uuid.uuid4().hex)
    if not isinstance(req,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',req):raise ValueError('Invalid request_id')
    tol=length(job.get('tolerance','0.001 in'),positive=True)
    path=ROOT/'reports/transactions'/(req+'.json')
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old['request']!=job:raise ValueError('request_id belongs to another job')
        if old['status'] in ('PREPARED','VALIDATED'):raise RuntimeError('Unknown outcome; inspect actual state before retry')
        return compact(old)
    check_gui(doc)
    if doc.BeamInputs.AdapterIdentifier!=beam.MARKER or not all(doc.getObject(n) for n in beam_drawings.PAGES):raise ValueError('Expected hooked beam with original two sheets')
    if any(doc.getObject(n) for n in (*PAGES,*SYMBOLS,'BeamFdotSchedule')) or 'TotalRebarWeightLb' in doc.BeamQuantities.PropertiesList:raise ValueError('FDOT presentation already exists; inspect instead of duplicate')
    before=source_state(doc);names=set(o.Name for o in doc.Objects)
    hashes={n:hashlib.sha256(doc.getObject(n).Shape.cleaned().exportBrepToString().encode()).hexdigest() for n in ('ConcreteBeam',*beam.SETS)}
    folder=ROOT/'reports/drawings'/doc.Name;folder.mkdir(parents=True,exist_ok=True)
    record={'timestamp':datetime.now(timezone.utc).isoformat(),'document':doc.Name,'operation':'add_beam_fdot_sheets','transaction_id':req,'request':job,'status':'PREPARED','saved':False,'checks':[],'errors':[],'rollback':'NOT NEEDED','report_path':str(path),'warnings':['Drafting conventions only; design and fabrication approval remain NOT CONFIGURED.'],'sources':[FDOT_URL,SPEC_URL,UNIT_WEIGHT_URL]}
    atomic(path,record);opened=False;undo=doc.UndoMode
    try:
        if not undo:doc.UndoMode=1
        doc.openTransaction('CAD_AI '+req);opened=True
        marks=build(doc,folder)
        same={n:hashes[n]==hashlib.sha256(doc.getObject(n).Shape.cleaned().exportBrepToString().encode()).hexdigest() for n in hashes}
        record['checks']=[result('physical_geometry_and_native_sources_preserved',all(same.values()) and beam_hooks.equivalent(before,source_state(doc),tol),identical_analytic_brep=same)]
        record['checks'].extend(checks(doc,tol))
        record['changes']={'additional_sheets':{'old':0,'new':2},'marks':marks,'weight_lb':{'old':None,'new':doc.BeamQuantities.TotalRebarWeightLb},'listed_weight_lb':{'old':None,'new':doc.BeamQuantities.TotalListedRebarWeightLb}}
        if any(c['status']=='FAIL' for c in record['checks']):raise ValueError('FDOT drawing/quantity validation failed')
        record['status']='VALIDATED';atomic(path,record);doc.commitTransaction();opened=False;record['status']='PASS'
    except Exception as e:
        record['status']='FAIL';record['errors'].append(str(e));record['traceback']=traceback.format_exc()
        if opened:
            doc.abortTransaction();doc.recompute()
            record['rollback']='COMPLETE' if set(o.Name for o in doc.Objects)==names and beam_hooks.equivalent(before,source_state(doc),tol) else 'INCOMPLETE'
    finally:
        if not undo:doc.UndoMode=undo
    atomic(path,record)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(compact(record))+'\n')
    return compact(record)
