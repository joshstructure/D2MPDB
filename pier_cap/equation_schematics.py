"""Offline SVG explanations shared by report equations and live check disclosures.

Diagrams are conceptual, with current operands alongside them. They never
replace actual cage drawings or assign design credit to a schematic bar.
"""
from html import escape
import math
import re
import textwrap

from .model import DEFINITIONS

DEFS = {d['name']: d for d in DEFINITIONS}
INK = '#233548'
BLUE = '#1766a0'
RED = '#bd4c24'
GREEN = '#21806b'


class Sketch:
    def __init__(self): self.items = []

    def line(self, x, y, xx, yy, color=INK, dash=False, width=1.5):
        self.items.append(f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{xx:.2f}" y2="{yy:.2f}" stroke="{color}" stroke-width="{width}"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')

    def rect(self, x, y, w, h, fill='#e8eef3', color=INK):
        self.items.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{fill}" stroke="{color}"/>')

    def text(self, x, y, text, color=INK, size=13, anchor='start'):
        self.items.append(f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}" font-size="{size}" text-anchor="{anchor}" font-family="Arial,sans-serif">{escape(str(text))}</text>')

    def circle(self, x, y, radius=5, color=BLUE):
        self.items.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{color}"/>')

    def poly(self, points, color, fill='none'):
        self.items.append('<polyline points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in points)+f'" fill="{fill}" stroke="{color}" stroke-width="2"/>')

    def arrow(self, x, y, xx, yy, color=RED):
        self.line(x,y,xx,yy,color,width=2)
        a=math.atan2(yy-y,xx-x)
        self.poly([(xx-8*math.cos(a-.4),yy-8*math.sin(a-.4)),(xx,yy),
                   (xx-8*math.cos(a+.4),yy-8*math.sin(a+.4))],color)

    def dim(self, x,y,xx,yy,label,color=BLUE,anchor='start',dx=7,dy=-7):
        self.line(x,y,xx,yy,color)
        for a,b in ((x,y),(xx,yy)): self.line(a-4,b-4,a+4,b+4,color)
        self.text((x+xx)/2+dx,(y+yy)/2+dy,label,color,12,anchor)


def family(name):
    """Concept selection for both named formulas and recorded check keys."""
    low=name.lower()
    if any(t in low for t in ('hook','development','anchorage','closure','bend')): return 'development'
    if any(t in low for t in ('clear','alignment','fit','cover','engage')) and name not in ('E_clear',): return 'clearance'
    if name in ('alpha_1','beta_1'):return 'flexure'
    if name in ('fr','Ig','yt','Mcr','Mmin_cr','tstress','K_limit'):return 'gross'
    if name in ('S_leg','S_leg_detail') or name.startswith(('Sw_','Chk_drawn_hoop_legs_')):return 'legs'
    if name.startswith(('eps_t','Chk_strain')):return 'strain'
    if any(t in low for t in ('fatigue','fmin_','df_','fth_','dc_fat','chk_fat')): return 'fatigue'
    if name=='As_skin_eff':return 'longitudinal'
    if any(t in low for t in ('shrink','skin','face_','ash_','ashraw')) or name=='As_side': return 'face'
    if name.startswith(('P_','Pile_')) or name in ('SP_P_auto','SP_P'):return 'spacing'
    if name in ('V_cap','A_surface','VS_cap','Mass_required','W_steel'): return 'quantity'
    if any(t in low for t in ('torsion','torsteel','t_threshold','tcr','k_t')) or name in ('Ag','Pcp','Aoh','Ao','ph') or name.startswith(('At_','Acomb_')): return 'torsion'
    if any(t in low for t in ('chk_long','f_long','f_vt','as_add','dc_long','as_skin_eff')): return 'longitudinal'
    if (name in ('Ec','n_mod','fs_I_limit','S_allow','fs_I_max') or
        name.startswith(('fs_','fo_','SI_','SIII_','bs_','nAs_','ccr_','Icr_','Ss_','Chk_I_','Chk_III_','Chk_drawn_I','Status_III'))):
        return 'spacing' if name.startswith(('SI_','SIII_','bs_','S_allow','Chk_drawn')) else 'cracked'
    if any(t in low for t in ('shear','pitch','spacing_g','spacing_l','actual_min','actual_end','lrfd_strain')) or name in ('dv','cot_theta','g_shear','Vn_limit','Vc','Av') or name.startswith(('Vs_','Vr_','Vn_','vu_','s_','Av_','theta','beta','epsilon','f_flange','F_compression','M_epsilon','f_cracking')): return 'shear'
    if name=='DC_flex_max' or name.startswith(('a_','c_','Mn_','Mr_','Asreq_','Asmin_','Mmin_','DC_flex','DC_min','Chk_flex','Chk_min')): return 'flexure'
    if name.startswith('SP_'): return 'spacing'
    if name in ('Tol_pile','E_end','E_CL','L_cap','S_pile_min','Chk_piles','Status_layout'): return 'beam'
    if name.startswith(('As_','d_','dc_','do_','y_','Bar_')): return 'section'
    return 'gate'


CAPTIONS = {
    'beam':'Cap length is assembled from pile spacing, pile width, pile tolerance and end extensions.',
    'section':'Bar areas and row coordinates locate the steel centroid and effective depth.',
    'flexure':'Concrete compression and steel tension form the resisting bending couple.',
    'gross':'Elastic bending stress increases from zero at the gross neutral axis to the extreme-fiber value.',
    'strain':'The linear strain profile relates the compression depth to the tension-steel strain.',
    'cracked':'The cracked transformed section (n·As) places the neutral axis where compression and tension balance.',
    'spacing':'Crack control compares the actual bar-center spacing with the stress-dependent allowable spacing.',
    'fatigue':'The repeated stress range is compared with the threshold set by the permanent stress.',
    'legs':'Transverse legs across the cap width are spaced no wider than the stress-dependent limit.',
    'shear':'The inclined shear field crosses transverse legs within the investigated window.',
    'torsion':'Torsional shear flow needs a closed path; enclosed area and perimeter set the geometry.',
    'longitudinal':'Moment, axial force, shear and torsion contribute to longitudinal tension demand.',
    'development':'Available anchorage length is compared with the required development or hook length.',
    'clearance':'Surface clearance differs from center spacing; cover, diameter and alignment control fit.',
    'face':'Check reinforcement area and spacing on each applicable face and direction.',
    'quantity':'Section dimensions and length determine gross volume and surface quantities.',
    'gate':'The current operands are tested against the stated criterion; prerequisites remain part of the result.',
}


def _draw(s, kind, e, name):
    p=e.case['inputs'];negative=bool(re.search(r'_N(?:\d|_|$)',name))
    pile=kind=='spacing' and (name.startswith(('P_','Pile_')) or name in ('SP_P_auto','SP_P'))
    negative=negative and not pile
    z='N' if negative else name[-1] if name.endswith(('_P','_B')) else 'B'
    if kind=='beam':
        s.rect(40,105,330,65)
        for x in (85,205,325):
            s.rect(x-13,170,26,85,'#becbd5');s.arrow(x,220,x,178,BLUE)
        s.dim(85,88,205,88,'S_pile');s.dim(40,275,370,275,'L_cap')
        s.dim(40,195,72,195,'E_end',anchor='end',dx=-20,dy=-6)
        s.dim(312,262,338,262,'D_pile',anchor='start',dx=18,dy=4)
        s.dim(325,88,370,88,'E_CL',anchor='middle',dx=0,dy=-6)
        s.text(40,55,'Elevation along the pile row',BLUE)
        s.text(40,295,'L_cap = (N_pile − 1) S_pile + D_pile + 2 E_end',INK,11)
        s.text(40,312,'E_end = E_clear + Tol_pile + E_detail; Tol_pile = min(3 in, D_pile/6)',INK,11)
    elif kind in ('section','flexure','cracked','spacing','clearance','face','torsion','gross','strain','legs'):
        s.rect(55,70,210,190)
        tension=92 if negative else 238
        comp=260 if negative else 70
        if kind in ('section','clearance','legs') or pile:s.rect(70,85,180,160,'none',GREEN)
        for x in (80,120,160,200,240):
            if not pile:s.circle(x,tension,5,RED)
            s.circle(x,330-tension,4,BLUE)
        for x in (80,100,220,240) if pile else ():s.circle(x,238,5,RED)
        if kind=='section':
            s.line(65,tension,260,tension,RED,True)
            s.dim(285,comp,285,tension,'d',BLUE)
            s.dim(310,70,310,92,'dc') if negative else s.dim(310,238,310,260,'dc')
            s.dim(35,70,35,260,'h');s.dim(55,285,265,285,'b')
            if name.startswith(('As_','dc_','d_')):
                s.text(75,175,'As = Σ bar areas',RED);s.text(75,198,'dc = Σ(Ai yi) / As')
            else:
                s.text(75,175,'y1 = cover + hoop ⌀ + db/2',RED);s.text(75,198,'next rows: + s_row each')
                if name.endswith(('2','3')):
                    row=118 if negative else 212
                    for x in (80,120,160,200,240):s.circle(x,row,5,'#e5a08c')
                    s.dim(310,tension,310,row,'s_row')
        elif kind=='gross':
            s.line(40,165,375,165,BLUE,True)
            s.poly([(335,70),(335,260),(370,260),(335,165),(300,70),(335,70)],RED)
            s.dim(30,165,30,260,'yt',anchor='end',dx=-5,dy=4)
            s.dim(285,70,285,260,'h');s.dim(55,55,265,55,'b',anchor='middle',dx=0,dy=-4)
            s.text(300,287,'f = M yt / Ig',RED,12);s.text(372,263,'fr',RED,11)
            s.text(40,310,'yt = h/2; Ig = b h³/12; first cracking when the extreme stress reaches fr.',INK,11)
        elif kind=='strain':
            scaled=max(12,min(120,190*e.value('c_'+z)/p['h']))
            na=comp-scaled if negative else comp+scaled
            s.line(40,na,375,na,BLUE,True)
            s.poly([(345,comp),(300,na),(245,tension)],RED)
            s.line(300,65,300,255,INK)
            s.text(295,comp+(22 if negative else -15),'εc = 0.003',BLUE,12)
            s.text(275,tension+(-12 if negative else 22),'εt',RED)
            s.dim(30,comp,30,na,'c',anchor='end',dx=-5,dy=4);s.dim(30,na,30,tension,'d−c',anchor='end',dx=-5,dy=4)
            s.text(65,310,'εt = 0.003 (d − c) / c; profile uses compression-face depth.',INK,11)
        elif kind in ('cracked','flexure'):
            depth=e.value(('ccr_' if kind=='cracked' else 'a_')+z)
            scaled=max(12,min(120,190*depth/p['h']))
            y=comp-scaled if negative else comp
            s.rect(55,y,210,scaled,'#b9d6e8' if kind=='flexure' else '#d5e7f2',BLUE)
            na=comp-scaled if negative else comp+scaled
            s.line(45,na,275,na,BLUE,True)
            s.text(276,na+4,'ccr' if kind=='cracked' else 'a',BLUE)
            if kind=='cracked':
                s.poly([(335,comp),(370,comp),(335,na)],BLUE,'#d5e7f2')
                s.text(372,comp-8 if negative else comp+14,'fc',BLUE,11)
                s.text(300,tension+(22 if negative else 16),'n As (transformed)',RED,11)
            else:
                s.arrow(300,comp-10 if negative else comp+10,365,comp-10 if negative else comp+10,BLUE)
                s.text(300,comp-20 if negative else comp+24,'C = α1 fc a b',BLUE,11)
                if name.startswith('c_'):
                    cs=max(12,min(120,190*e.value('c_'+z)/p['h']))
                    cy=comp-cs if negative else comp+cs
                    s.line(45,cy,275,cy,BLUE,True)
                    ct=comp-20 if negative else comp+24
                    near=abs(cy-na)<13 or abs(cy+4-ct)<13
                    s.text(276,(na+17 if negative else na-9) if near else cy+4,'c = a / β1',BLUE,11)
                if negative:s.dim(55,278,265,278,'b',anchor='middle',dx=0,dy=12)
                else:s.dim(55,55,265,55,'b',anchor='middle',dx=0,dy=-4)
            s.arrow(365,tension,300,tension,RED)
            s.text(300,tension-10,'T = As fs' if kind=='cracked' else 'T = As fy',RED,11)
            s.dim(30,comp,30,tension,'d')
            if kind=='cracked' and name.startswith('fo_III_'):
                s.dim(285,70 if negative else 238,285,92 if negative else 260,'do',anchor='end',dx=-5,dy=4)
            tight=kind=='flexure' and negative
            s.text(65,300 if tight else 290,'Top tension (N)' if negative else 'Bottom tension (P / B)',RED,11 if tight else 13)
            note='Lever arm = d − a/2'
            if kind=='cracked':
                note=('fs = M n / Ss at the steel centroid.' if name.startswith('fs_') else
                      'fo = M n (h − ccr − do) / Icr at the outer bar.' if name.startswith('fo_III_') else
                      'Cracked concrete carries no tension.')
            s.text(65,320 if tight else 312,note,INK,11 if tight else 12)
        elif kind=='spacing' and pile:
            s.rect(125,215,70,45,'#becbd5')
            s.line(117,215,117,260,INK,True);s.line(203,215,203,260,INK,True)
            s.dim(117,205,203,205,'Pile_left → Pile_right',anchor='middle',dx=0,dy=-8)
            s.dim(100,222,220,222,'P_center_gap',anchor='middle',dx=0,dy=14)
            s.dim(80,270,100,270,'P_side_span',anchor='end',dx=-16,dy=4)
            s.dim(203,250,215,250,'C_pile',anchor='start',dx=12,dy=7)
            s.text(65,295,'Outer bottom row splits beside the embedded pile (P_split).',INK,11)
            s.text(65,312,'The gap across the pile stays in the service spacing check.',INK,11)
        elif kind=='spacing':
            s.dim(120,tension-24,160,tension-24,'s')
            s.dim(290,tension,290,70 if negative else 260,'dc')
            for x in (101,181,221):s.poly([(x,70 if negative else 260),(x+4,tension),(x-3,140 if negative else 190)],RED)
            s.text(65,155,'fs ↑  →  allowable spacing ↓',RED,12)
            s.text(65,285,'s ≤ 700 γe / (βs fs) − 2 dc',BLUE,13)
            s.text(65,309,'Pile gap excluded only beside an embedded pile.',INK,11)
        elif kind=='legs':
            for x in (70,250):s.line(x,85,x,245,GREEN,width=4)
            s.dim(70,160,250,160,'S_leg',anchor='middle',dx=0,dy=-6)
            s.text(65,290,'S_leg ≤ Sw; Sw depends on the shear stress vu.',INK,11)
            s.text(65,312,'Multiple loops add inner legs; a spacing override adds none.',INK,11)
        elif kind=='clearance':
            align='alignment' in name
            if align:
                a,b=(92,130) if negative else (238,200)
                for y in (a,b):
                    for x in (80,120,160,200,240):s.circle(x,y,5,RED)
                s.line(160,min(a,b)-10,160,max(a,b)+12,BLUE,True)
                s.dim(290,b,290,a,'layer gap ≤ 6 in')
            else:
                s.circle(105,165,15,RED);s.circle(190,165,22,BLUE)
                s.dim(120,195,168,195,'clear gap',anchor='middle',dx=0,dy=18)
                s.dim(105,130,190,130,'center spacing')
            s.dim(55,287,70,287,'cover',anchor='middle',dx=0,dy=-6)
            s.text(65,309,'Bars in layers ≤ 6 in apart align vertically.' if align else 'Gap = center distance − (db1 + db2)/2',INK,12)
        elif kind=='face':
            skin='skin' in name.lower()
            rows=((160,135,110) if negative else (170,195,220)) if skin else (125,160,195)
            for y in rows:s.circle(80,y,5,GREEN);s.circle(240,y,5,GREEN)
            s.rect(70,85,180,160,'none',GREEN)
            s.dim(320 if skin else 290,rows[0],320 if skin else 290,rows[1],'s_face',GREEN)
            if skin:
                s.dim(290,70,290,165,'d/2') if negative else s.dim(290,260,290,165,'d/2')
                s.text(65,285,'Skin steel over d/2 from the tension face; s ≤ min(d/6, 12 in)',GREEN,11)
            elif 'shrink' in name.lower() or name.lower().startswith('ash'):
                s.text(65,285,'Rate per face = As / face width; hoop rate = Ab / max(s_G, s_L)',GREEN,11)
            else:s.text(65,285,'Area per unit width / length',GREEN)
            s.text(65,309,'Each face and direction checked separately.',INK,12)
        else:
            s.rect(75,90,170,150,'none',GREEN)
            for a,b,c,d in ((100,98,220,98),(237,115,237,220),(220,232,100,232),(83,218,83,112)):s.arrow(a,b,c,d,RED)
            geom=name in ('Aoh','Ao','ph') or name.startswith(('At_','Acomb_'))
            s.text(122,168,'Ao / Aoh',GREEN);s.text(285,120 if geom else 162,'ph',GREEN)
            if geom:
                s.dim(75,82,245,82,'x_h',anchor='middle',dx=0,dy=-4)
                s.dim(260,90,260,240,'y_h',anchor='start',dx=5,dy=4)
                s.text(65,285,'Aoh = x_h · y_h; ph = 2 (x_h + y_h); Ao = Ao_factor · Aoh',RED,11)
            elif name in ('Ag','Pcp','K_t','Tcr','T_threshold'):
                s.text(65,285,'Ag = b h; Pcp = 2 (b + h); Tcr = 0.126 √fc Ag² / Pcp · K_t',INK,11)
            else:s.text(65,285,'Closed shear-flow path',RED)
            s.text(65,309,'An open U-bar does not enclose torsion area.',INK,12)
    elif kind=='shear':
        s.rect(40,95,335,150)
        for x in range(65,370,30):s.line(x,105,x,235,GREEN,width=3)
        s.line(105,235,295,105,RED,width=3)
        s.arrow(52,165,52,110,BLUE);s.arrow(370,170,370,225,BLUE)
        s.text(156,178,'θ',RED,16);s.dim(105,270,295,270,'dv cot θ')
        s.dim(25,105,25,235,'dv',anchor='end',dx=-5,dy=4)
        s.dim(65,85,95,85,'s',anchor='middle',dx=0,dy=-4)
        if name=='Chk_actual_end':s.dim(40,255,65,255,'end distance',anchor='start',dx=20,dy=4)
        s.text(45,65,'Inclined field + intersected stirrup legs',BLUE,13)
        s.text(45,309,'Window is clipped at physical cap ends.',INK,12)
    elif kind=='longitudinal':
        s.rect(50,100,305,145)
        s.line(60,225,345,225,RED,width=4)
        s.arrow(220,225,370,225,RED);s.text(180,280,'Tension ≤ As,eff fy',RED)
        s.arrow(75,170,35,170,BLUE);s.text(50,150,'N / 2',BLUE)
        s.arrow(335,130,335,200,BLUE);s.text(270,123,'V, T',BLUE)
        s.dim(392,100,392,245,'dv',anchor='end',dx=-5,dy=4)
        s.text(65,65,'M / (φ dv) + axial + shear / torsion',INK,13)
        s.text(65,309,'Only developed tension-half steel is credited.',INK,12)
    elif kind=='fatigue':
        s.line(45,255,375,255);s.line(60,275,60,70)
        points=[(65+i*3,165-45*math.sin(i*math.pi/18)) for i in range(100)]
        s.poly(points,BLUE)
        s.line(65,210,370,210,GREEN,True);s.text(70,233,'Permanent stress fmin',GREEN)
        s.dim(340,120,340,210,'Δf',RED);s.text(80,85,'Repeated loading',BLUE)
        s.text(80,290,'Δf ≤ FTH(fmin)',RED);s.text(300,275,'Time',INK,12)
    elif kind=='development':
        hook='hook' in name.lower() or name.startswith('Chk_end_grid_bend')
        s.rect(40,90,335,160)
        s.poly([(65,220),(310,220),(327,213),(335,195),(335,130)],RED)
        s.line(150,75,150,270,BLUE,True)
        s.dim(150,275,335,275,'available length')
        s.text(65,65,'Critical section',BLUE)
        if hook:
            s.line(40,105,375,105,INK,True);s.text(45,100,'h − C_t − d_v',INK,11)
            s.dim(350,220,350,130,'hook height',anchor='end',dx=22,dy=-53)
            s.text(165,205,'Hook / straight end',RED)
            s.text(45,310,'Inside bend 6db (#3–#8) or 8db (#9–#11); straight tail 12db.',INK,12)
        else:
            s.text(185,185,'Hook / straight end',RED)
            s.text(45,310,'Required length, bend and end conditions all apply.',INK,12)
    elif kind=='quantity':
        s.rect(50,135,245,115);s.poly([(50,135),(115,80),(360,80),(295,135)],BLUE,'#dbe7ee')
        s.poly([(295,135),(360,80),(360,195),(295,250)],BLUE,'#c2d3df')
        s.dim(50,278,295,278,'L_cap');s.dim(375,135,375,250,'h',anchor='start',dx=6,dy=4);s.text(68,103,'b',BLUE)
        s.text(60,310,'Gross volume = b h L; all six faces give surface area.',INK,12)
    else:
        for y,label,color in ((75,'Current inputs',BLUE),(150,'Equation / condition',RED),(225,'Result + prerequisites',GREEN)):
            s.rect(55,y,300,45,'#f3f7fa',color);s.text(205,y+28,label,color,14,'middle')
            if y<225:s.arrow(205,y+47,205,y+73,color)
    return CAPTIONS[kind]


def _operands(e, name):
    from .check_working import _names
    from .engine import Q
    d=DEFS.get(name);ast=e.engine.defs.get(name)
    if not d or ast is None:return []
    result=[]
    if name in e.engine.overrides:
        match=re.search(r'_([NPB])(?:\d|_|$)',name)
        names=['b','h','As_'+(match.group(1) if match else 'B')]
    else:names=list(dict.fromkeys(_names(ast,e.engine)))
    for n in names:
        if n not in DEFS:continue
        value=e.engine.get(n)
        unit=DEFS[n]['unit']
        if isinstance(value,Q):value=e.value(n,unit)
        if isinstance(value,(int,float,bool)):result.append((n,value,'' if unit in ('unitless',None) else unit))
    return result


def schematic_html(e, name, *, caption='', values=None, pending=False, check=None, concept_name=None):
    """One accessible, equation-specific sketch, with no external assets or IDs."""
    kind=family(concept_name or name);s=Sketch();concept=_draw(s,kind,e,concept_name or name)
    s.line(410,40,410,315,'#ccd7e0')
    s.text(428,55,'THIS EQUATION',BLUE,12)
    y=80
    for line in textwrap.wrap(name.replace('_',' '),39):s.text(428,y,line,RED,16);y+=20
    d=DEFS.get(name)
    if pending:
        s.text(428,y+8,'PENDING — values not adopted',RED,13);y+=33
        rows=[]
    else:
        if check is not None:
            ratio=f'{check.ratio:.5g}' if isinstance(check.ratio,(int,float)) else str(check.ratio)
            result=f'Check: {check.status} · ratio / flag {ratio}'
        elif d and '(' not in name:
            value=e.engine.get(name)
            if isinstance(value,bool):result=str(value)
            elif isinstance(value,str):result=value
            else:result=f'{e.value(name,d["unit"]):.5g} '+('' if d['unit'] in ('unitless',None) else d['unit'])
        else:result='Current calculation operands'
        for line in textwrap.wrap(str(result),40):s.text(428,y+5,line,RED,13);y+=19
        y+=12
        parts=getattr(check,'components',None)
        if values is not None:rows=list(values)
        elif isinstance(parts,tuple) and parts:
            rows=[row for c in parts for row in ((c.label+' · actual',c.actual,c.unit),(c.label+' · limit',c.limit,c.unit))]
        else:rows=_operands(e,name)
    for label,value,unit in rows[:8]:
        val=f'{value:.5g}' if isinstance(value,(float,int)) and not isinstance(value,bool) else str(value)
        for line in textwrap.wrap(f'{label}: {val} {unit}',43)[:2]:
            if y>300:break
            s.text(428,y,line,INK,12);y+=17
        y+=4
    meaning=caption or (d or {}).get('caption') or concept
    description=f'{name}: {concept}'
    return ('<figure class="equation-schematic" data-equation="'+escape(name,quote=True)+'" data-concept="'+kind+'" style="margin:12px 0;break-inside:avoid">'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 340" role="img" aria-label="'+escape(description,quote=True)+'" '
        'style="display:block;width:100%;max-width:800px;height:auto;background:#fff;border:1px solid #d6e0e8">'
        '<title>'+escape(description)+'</title>'+''.join(s.items)+'</svg>'
        '<figcaption style="font-size:12px;line-height:1.45">'+escape(meaning)+' '+escape(concept)+
        ' Conceptual schematic; not to scale. Values follow the current calculation.</figcaption></figure>')
