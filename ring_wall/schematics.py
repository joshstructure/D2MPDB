"""Small offline SVG mechanics sketches for individual report equations."""
from html import escape
from math import atan2, cos, sin
from .notation import stem, term

BLUE, GREEN, ORANGE, RED = '#315d82', '#258875', '#b76c25', '#b53333'


class Sketch:
    def __init__(self, title, active):
        self.active=stem(active)
        self.parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 250" role="img" aria-label="'+escape(title,quote=True)+'"><title>'+escape(title)+'</title><rect width="720" height="250" rx="8" fill="#f6f9fc"/>']

    def line(self,x,y,X,Y,color=BLUE,dash=False,width=2):
        self.parts.append(f'<path d="M{x},{y} L{X},{Y}" fill="none" stroke="{color}" stroke-width="{width}"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')

    def rect(self,x,y,w,h,color=BLUE,fill='none'):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{color}" stroke-width="2"/>')

    def circle(self,x,y,r,color=BLUE,fill='none',dash=False):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{color}" stroke-width="2"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')

    def text(self,x,y,text,key='',color=BLUE,size=13,anchor='start'):
        on=stem(key)==self.active if key else False
        self.parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{ORANGE if on else color}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{700 if on else 400}">'+escape(text)+'</text>')

    def arrow(self,x,y,X,Y,color=GREEN):
        self.line(x,y,X,Y,color)
        a=atan2(Y-y,X-x)
        for turn in (-.5,.5):self.line(X,Y,X-8*cos(a+turn),Y-8*sin(a+turn),color)

    def dim(self,x,y,X,Y,label,key=''):
        self.arrow(x,y,X,Y,ORANGE);self.arrow(X,Y,x,y,ORANGE)
        if abs(Y-y)>abs(X-x):self.text((x+X)/2-10,(y+Y)/2+4,label,key,anchor='end')
        else:self.text((x+X)/2,(y+Y)/2-8,label,key,anchor='middle')

    def end(self):return ''.join(self.parts)+'</svg>'


def schematic(kind,name,r,example):
    """Geometry is conceptual; any displayed case values come from the result."""
    meaning=term(name)[1];s=Sketch(meaning,name)
    if kind=='tributary':
        s.rect(35,40,350,155);s.rect(35,125,115,70,GREEN,'#e4f2ec')
        for x in (150,265):s.line(x,40,x,195,BLUE,True)
        for y in (85,125):s.line(35,y,385,y,BLUE,True)
        for x in (70,205,340):s.line(x,32,x,204,'#9aa8b5',width=5)
        s.line(52,160,88,160,ORANGE,width=5)
        s.dim(35,220,150,220,'b','width');s.dim(405,125,405,195,'h','row_height')
        s.text(43,30,'Wall elevation · one shaded tributary cell')
        s.text(450,62,'V = b × h × t_w / 1728','volume')
        s.text(450,91,'W = γ_c V','service');s.text(450,120,'R = γ_DC W','force')
        s.arrow(500,145,500,196);s.line(465,198,540,198,BLUE,width=5)
        s.text(550,180,'R on ring','force');s.text(450,228,'Cell edges: midplanes or wall edge',size=12)
    elif kind=='eccentricity':
        s.rect(45,70,325,85,BLUE,'#e4f2ec');s.line(115,40,115,188,BLUE,True)
        s.line(235,40,235,188,GREEN,True);s.circle(115,115,30)
        s.text(74,210,'Pile center x_p','x');s.text(211,210,'Cell centroid')
        s.arrow(235,20,235,72);s.text(249,40,'R','force')
        s.dim(115,177,235,177,'e_n','eccentricity')
        s.text(435,80,'e_d = |e_n| + Δ_p','design_e')
        s.text(435,112,'M = R e_d','moment');s.text(435,152,'Δ_p adds a local radial envelope',size=12)
        s.text(435,177,'Nominal signed e_n is retained',size=12);s.text(435,197,'for whole-wall moment equilibrium.',size=12)
    elif kind=='grid':
        s.rect(35,40,300,155)
        for x in range(65,330,45):s.line(x,48,x,187,GREEN,width=3)
        for y in range(65,190,35):s.line(43,y,327,y,ORANGE,width=3)
        s.dim(65,222,110,222,'s','selected_pitch');s.text(43,28,'One face · each direction')
        s.text(390,52,'A_s,prov = 12 A_b / s','steel_provided')
        s.circle(440,115,14,ORANGE,'#f8dfbc');s.circle(560,115,14,ORANGE,'#f8dfbc')
        s.dim(454,150,546,150,'a = s − d_b','clear_provided')
        s.dim(426,90,454,90,'d_b','bar_diameter')
        s.text(390,190,'Area is per foot, per direction, per face.',size=12)
        s.text(390,214,'Larger section minimum governs both mats.',size=12)
    elif kind=='lap':
        s.rect(30,45,330,150);s.line(50,83,260,83,ORANGE,width=4);s.line(130,98,340,98,GREEN,width=4)
        s.dim(130,127,260,127,'Class B lap = 1.3 l_d','lap_horizontal')
        s.text(43,170,'Straight bars transfer force through concrete.',size=12)
        s.arrow(110,70,55,70,ORANGE);s.arrow(275,110,330,110,GREEN)
        s.parts.append(f'<path d="M650,65 H495 A45,45 0 0 0 495,155 H650" fill="none" stroke="{ORANGE}" stroke-width="4"/>')
        s.dim(495,191,650,191,'Straight U leg l_U','u_leg_in')
        s.dim(423,65,423,155,'B_U','bend_envelope')
        s.text(400,28,'End return · schematic bend and lap')
        s.text(400,228,'Fit checks do not define the splice schedule.',size=12)
    elif kind=='clearance':
        s.rect(35,43,325,155);s.line(48,65,348,65,ORANGE,width=4);s.line(48,175,348,175,ORANGE,width=4)
        s.circle(155,120,38);s.circle(155,120,50,BLUE,'#dce8f2');s.circle(155,120,38,BLUE,'#f6f9fc');s.circle(155,120,66,RED,dash=True)
        s.line(48,75,348,75,GREEN,width=3);s.line(48,165,348,165,GREEN,width=3)
        s.dim(35,220,89,220,'c_end','end_clear');s.text(43,28,'Plan · ring, tolerance and two face layers')
        s.text(401,65,'Dashed ring: r_o + Δ_p','placement_tolerance_in',RED)
        s.text(401,98,'Orange: outer horizontal bars',color=ORANGE)
        s.text(401,126,'Green: inner vertical bars',color=GREEN)
        s.text(401,165,'a_grid is measured to the inner layer.','grid_gap')
        s.text(401,192,'Cover and clearances use wall surfaces.',size=12)
        s.text(401,220,'Top/bottom checks also include the fillets.',size=12)
    elif kind=='annulus':
        s.circle(155,125,90,BLUE,'#dce8f2');s.circle(155,125,59,ORANGE,'#f7ebd9');s.circle(155,125,48,BLUE,'#f6f9fc')
        s.arrow(155,125,245,125);s.text(198,115,'r_o','outer_radius')
        s.arrow(155,125,155,66,ORANGE);s.text(165,79,'r_b','bearing_inner')
        s.text(50,28,'Horizontal bearing area A','bearing_area')
        s.text(290,68,'Blue annulus carries concrete pressure.','bearing_area')
        s.text(290,99,'Upper fillet footprint is excluded.','bearing_inner')
        s.text(290,130,'r_b = max(r_i, r_p + w)','bearing_inner')
        s.line(65,125,245,125,BLUE,True);s.text(290,170,'I is about a diameter through the center.','bearing_inertia')
        s.text(290,201,'Area enhancement is not taken in bearing.',size=12)
    elif kind=='pressure':
        q0=(example['qmax']+example['qmin'])/2;scale=100/max(abs(example['qmax']),abs(example['qmin']),1e-12)
        x0,x1,y0=55,350,155;y1=y0-example['qmin']*scale;y2=y0-example['qmax']*scale
        s.line(40,y0,370,y0,BLUE);s.line(x0,35,x0,217,BLUE,True);s.line(x1,35,x1,217,BLUE,True)
        s.line(x0,y1,x1,y2,GREEN,width=3);s.line(202,35,202,214,BLUE,True)
        s.text(60,29,'Linear elastic pressure across a diameter')
        s.text(x0+4,min(229,y1+20),'q_min','qmin',RED if example['qmin']<0 else GREEN)
        s.text(285,max(26,y2-10),'q_max','qmax');s.text(205,y0-q0*scale-8,'q_0','qavg')
        s.text(x0,238,'−r_o',size=12,anchor='middle');s.text(202,238,'0',size=12,anchor='middle');s.text(x1,238,'+r_o',size=12,anchor='middle')
        s.text(411,65,'q_0 = R / A','qavg');s.text(411,97,'q_M = M r_o / I','qmoment')
        s.text(411,129,'q_max,min = q_0 ± q_M','qmax')
        s.text(411,171,'Compression requires q_min ≥ 0.','qmin')
        s.text(411,203,'Contact: '+('OK' if example['contact_ok'] else 'FAIL — strength values are trial'),color=GREEN if example['contact_ok'] else RED,size=12)
        if stem(name)=='bearing_limit':s.text(411,232,'q_R = φ_b · 0.85 f′_c','bearing_limit',size=12)
    elif kind=='plate':
        s.rect(45,50,27,145,fill='#dfe7ee');s.rect(72,145,255,22,fill='#dce8f2')
        for x in range(120,325,36):s.arrow(x,65,x,142)
        s.text(144,50,'q_max on bearing strip','qmax');s.dim(72,211,327,211,'r_o − r_p','outer_radius')
        s.line(115,130,115,180,ORANGE,True);s.text(109,193,'r_b','bearing_inner')
        s.arrow(86,177,86,218,RED);s.text(41,230,'v','root_shear',RED)
        s.parts.append(f'<path d="M77,105 C16,103 16,155 42,170" fill="none" stroke="{ORANGE}" stroke-width="2"/>')
        s.text(13,100,'m','root_moment',ORANGE)
        s.text(390,61,'Radial strip fixed at the pipe face.')
        s.text(390,94,'Load per root length grows with r / r_p.',size=12)
        s.text(390,127,'Shear: integrate q_max (r/r_p) dr.','root_shear',size=12)
        s.text(390,159,'Moment adds the lever arm (r − r_p).','root_moment',size=12)
        if stem(name) in ('plate_shear_capacity','thickness_shear'):
            s.text(390,199,'Shear resistance uses 0.58 F_y,p t_p.','plate_shear_capacity',size=12)
        else:s.text(390,199,'Elastic resistance uses t_p² / 6.','plate_capacity',size=12)
        s.text(390,225,'Dimensions are per unit root circumference.',size=12)
    elif kind in ('weld','weld-detail','base'):
        s.rect(80,32,28,184,fill='#dfe7ee');s.rect(118,108,215,36,fill='#dce8f2')
        s.parts.append(f'<path d="M108,108 V74 L145,108 Z M108,144 V178 L145,144 Z" fill="#f7dfbf" stroke="{ORANGE}" stroke-width="2"/>')
        s.dim(352,108,352,144,'t_p','ring_t_in');s.dim(60,75,60,108,'w','weld_leg_in')
        s.text(76,239,'Pipe face     g     Annular plate','root_gap')
        if kind=='weld':
            s.arrow(145,88,215,88,RED);s.arrow(215,168,145,168,RED)
            s.text(235,89,'H_w','weld_radial',RED);s.text(235,184,'H_w','weld_radial',RED)
            s.arrow(152,95,152,126);s.arrow(152,153,152,198);s.text(166,211,'v/2 each','root_shear')
            s.text(405,55,'Two fillets form a moment couple.')
            s.text(405,90,'H_w = m / t_p','weld_radial')
            s.text(405,123,'F_w = √[(v/2)² + H_w²]','weld_resultant')
            s.text(405,164,'a_w = (w − g) / √2','weld_throat')
            s.text(405,205,'F_R,w = φ_w · 0.60 F_EXX · a_w','weld_capacity',size=12)
        elif kind=='base':
            s.line(86,75,86,180,RED,width=5);s.line(155,108,155,144,RED,width=5)
            s.text(405,60,'Adjacent base metal carries weld force.')
            s.text(405,95,'Ring thickness: t_p','ring_t_in');s.text(405,124,'Pipe thickness: t_eff','pile_t_effective_in')
            s.text(405,158,'Yield: φ_vy · 0.58 F_y · t','pipe_yield_capacity',size=12)
            s.text(405,189,'Rupture: φ_vu · 0.58 F_u · t','pipe_base_capacity',size=12)
            s.text(405,221,'Local shell bending remains outside scope.',size=12)
        else:
            s.text(405,58,'Minimum leg depends on joined thicknesses.')
            s.text(405,92,'Increase provided leg for fit-up gap g.','weld_min_gap',size=12)
            s.text(405,125,'Maximum leg protects the ring edge.','weld_maximum',size=12)
            s.text(405,160,'Each weld runs around the pipe: 2πr_p.','weld_length',size=12)
            s.text(405,193,'Both upper and lower fillets are required.',size=12)
            s.text(405,223,'Gap allowance does not approve a WPS.',size=12)
    else:
        raise ValueError('Missing report schematic: '+kind)
    return '<figure class="equation-sketch">'+s.end()+'<figcaption>'+escape(meaning)+'. Conceptual schematic, not to scale; current values are listed below.</figcaption></figure>'
