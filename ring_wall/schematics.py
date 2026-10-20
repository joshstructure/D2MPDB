"""Small offline SVG mechanics sketches for individual report equations.

Every sketch depicts the ledger expression it accompanies (ring_wall/design.py).
Geometry is conceptual and exaggerated for legibility; the active equation's labels
are drawn bold and orange so each dropdown highlights the quantity it computes.
"""
from html import escape
from math import atan2, cos, sin
from .notation import stem, term

BLUE, GREEN, ORANGE, RED, GREY = '#315d82', '#258875', '#b76c25', '#b53333', '#9aa8b5'
CONCRETE, STEEL, PLATE, WELD, PAPER = '#e4f2ec', '#dfe7ee', '#dce8f2', '#f7dfbf', '#f6f9fc'


class Sketch:
    def __init__(self, title, active):
        self.active=stem(active)
        self.parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 250" role="img" aria-label="'+escape(title,quote=True)+'"><title>'+escape(title)+'</title><rect width="720" height="250" rx="8" fill="'+PAPER+'"/>']

    def on(self,key):
        """A label may answer to one key or to several (shared check demands)."""
        keys=(key,) if isinstance(key,str) else tuple(key)
        return any(k and stem(k)==self.active for k in keys)

    def line(self,x,y,X,Y,color=BLUE,dash=False,width=2):
        self.parts.append(f'<path d="M{x},{y} L{X},{Y}" fill="none" stroke="{color}" stroke-width="{width}"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')

    def path(self,d,color=BLUE,fill='none',width=2,dash=False):
        self.parts.append(f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{width}"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')

    def rect(self,x,y,w,h,color=BLUE,fill='none',dash=False):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{color}" stroke-width="2"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')

    def circle(self,x,y,r,color=BLUE,fill='none',dash=False):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{color}" stroke-width="2"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')

    def text(self,x,y,text,key='',color=BLUE,size=13,anchor='start'):
        on=self.on(key)
        self.parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{ORANGE if on else color}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{700 if on else 400}">'+escape(text)+'</text>')

    def arrow(self,x,y,X,Y,color=GREEN,width=2):
        self.line(x,y,X,Y,color,width=width)
        a=atan2(Y-y,X-x)
        for turn in (-.5,.5):self.line(X,Y,X-8*cos(a+turn),Y-8*sin(a+turn),color,width=width)

    def dim(self,x,y,X,Y,label,key='',at=None,size=13):
        """Double-headed dimension; `at`=(x,y[,anchor]) places the label explicitly."""
        self.arrow(x,y,X,Y,ORANGE);self.arrow(X,Y,x,y,ORANGE)
        if at:self.text(at[0],at[1],label,key,anchor=at[2] if len(at)>2 else 'start',size=size)
        elif abs(Y-y)>abs(X-x):self.text((x+X)/2-10,(y+Y)/2+4,label,key,anchor='end',size=size)
        else:self.text((x+X)/2,(y+Y)/2-8,label,key,anchor='middle',size=size)

    def moment(self,cx,cy,r,label,key='',color=ORANGE,at=None):
        """Clockwise curved arrow over a point, labelled above it unless `at` is given."""
        self.path(f'M{cx-r},{cy} A{r},{r} 0 0 1 {cx+r},{cy}',color)
        self.line(cx+r,cy,cx+r-6,cy-7,color);self.line(cx+r,cy,cx+r+6,cy-7,color)
        if at:self.text(at[0],at[1],label,key,color)
        else:self.text(cx,cy-r-6,label,key,color,anchor='middle')

    def end(self):return ''.join(self.parts)+'</svg>'


def weld_joint(s):
    """Shared pipe/plate/double-fillet elevation for the weld, base-metal and detailing sketches."""
    s.rect(80,32,28,184,fill=STEEL);s.rect(118,108,215,36,fill=PLATE)
    s.path('M108,108 V74 L145,108 Z M108,144 V178 L145,144 Z',ORANGE,WELD)
    s.dim(352,108,352,144,'t_p','ring_t_in',at=(359,130));s.dim(60,74,60,108,'w','weld_leg_in')
    s.dim(80,50,108,50,'t_eff','pile_t_effective_in',at=(94,42,'middle'),size=12)
    s.line(108,120,118,120,RED,width=2);s.line(108,132,118,132,RED,width=2)
    s.text(76,239,'Pipe face · root gap g · annular plate','root_gap')


def schematic(kind,name,r,example):
    """Geometry is conceptual; any displayed case values come from the result."""
    meaning=term(name)[1];s=Sketch(meaning,name);active=stem(name)
    if kind=='tributary':
        piles,rows=(70,205,340),(75,120,165)
        s.rect(35,40,350,155);s.rect(35,40,102.5,57.5,GREEN,CONCRETE)
        for x in (137.5,272.5):s.line(x,40,x,195,BLUE,True)
        for y in (97.5,142.5):s.line(35,y,385,y,BLUE,True)
        for x in piles:
            s.line(x,32,x,204,GREY,width=6)
            for y in rows:s.line(x-13,y,x+13,y,ORANGE,width=5)
        s.arrow(86.25,46,86.25,72);s.text(93,62,'R','force')
        s.dim(35,226,137.5,226,'b = x_+ − x_−','width');s.dim(405,40,405,97.5,'h = z_+ − z_−','row_height',at=(412,73))
        s.text(43,30,'Wall elevation · piles, ring rows and one shaded tributary cell',size=12)
        s.text(520,55,'V = b × h × t_w / 1728','volume');s.text(520,84,'W = γ_c V','service');s.text(520,113,'R = γ_DC W','force')
        s.text(412,150,'Cell edges: pile midplanes (dashed) or wall ends;',size=12)
        s.text(412,170,'row edges: ring-row midplanes or wall top/bottom.',size=12)
        s.text(412,200,'R acts downward at the cell centroid onto its ring.',size=12)
    elif kind=='eccentricity':
        xp,xc=115,207.5
        s.rect(45,55,325,110,GREEN,CONCRETE);s.line(xc,38,xc,192,GREEN,True)
        s.rect(82,32,22,138,GREY,dash=True);s.rect(104,32,22,138,GREY,STEEL);s.line(xp,38,xp,192,BLUE,True)
        s.line(97,125,133,125,ORANGE,width=5);s.moment(xp,125,24,'M','moment',at=(xp+30,104))
        s.arrow(xc,22,xc,53);s.text(xc+7,40,'R','force')
        s.dim(xp,192,xc,192,'e_n','eccentricity');s.dim(93,192,xp,192,'Δ_p','placement_tolerance_in',at=(104,184,'middle'),size=12)
        s.dim(93,216,xc,216,'e_d = |e_n| + Δ_p','design_e')
        s.text(xp,240,'Pile x_p','x',anchor='middle');s.text(xc,240,'Cell centroid',anchor='middle')
        s.text(420,52,'e_n = (x_− + x_+) / 2 − x_p','eccentricity')
        s.text(420,80,'e_d = |e_n| + Δ_p','design_e');s.text(420,108,'M = R e_d','moment')
        s.text(420,144,'Elevation of one cell: R is gravity at the centroid;',size=12)
        s.text(420,164,'the dashed pile sits Δ_p farther from it (worst case).',size=12)
        s.text(420,192,'Nominal signed e_n is retained for whole-wall',size=12)
        s.text(420,212,'moment equilibrium; e_d is the local envelope.',size=12)
    elif kind=='grid':
        s.rect(35,40,200,155)
        for x in (65,105,145,185,225):s.line(x,46,x,189,GREEN,width=3)
        for y in (65,100,135,170):s.line(41,y,229,y,ORANGE,width=3)
        s.dim(65,215,105,215,'s','selected_pitch');s.text(35,28,'One face · bars each way at pitch s',size=12)
        s.rect(258,48,122,14,BLUE,CONCRETE);s.text(258,80,'t_w × L section','steel_L',size=12)
        s.rect(258,98,14,97,BLUE,CONCRETE);s.text(280,150,'t_w × H','steel_H',size=12)
        s.text(258,218,'Gross sections, b h','steel_required',size=12)
        s.text(400,46,'A_s,L = 1.3 t_w L / (2 (t_w + L) f_y)','steel_L',size=12)
        s.text(400,68,'A_s,H = 1.3 t_w H / (2 (t_w + H) f_y)','steel_H',size=12)
        s.text(400,90,'A_s,req = max(A_s,L, A_s,H), 0.11 to 0.60 in²/ft','steel_required',size=12)
        s.text(400,112,'A_s,prov = 12 A_b / s ≥ A_s,req (per face, each way)','steel_provided',size=12)
        s.text(400,134,'s_code = min(1.5 t_w, 18 in; 12 in if t_w > 36)','code_pitch',size=12)
        s.text(400,156,'s_lim = min(s_code, s_project) ≥ s','pitch_limit',size=12)
        s.text(400,178,'a_req = max(1.5 in, 1.5 d_b, 1.5 d_agg) ≤ a','clear_required',size=12)
        s.circle(420,220,9,ORANGE,'#f8dfbc');s.circle(470,220,9,ORANGE,'#f8dfbc')
        s.dim(411,203,429,203,'d_b','bar_diameter',at=(420,197,'middle'),size=12)
        s.dim(429,240,461,240,'a = s − d_b','clear_provided',at=(492,244),size=12)
        s.text(492,224,'A_b each bar','bar_area',size=12)
    elif kind=='lap':
        s.line(30,45,330,45);s.line(30,45,30,195);s.line(30,195,330,195);s.path('M330,45 l-6,19 l12,19 l-12,19 l12,19 l-12,19 l12,19 l-12,19 l6,17')
        for y in (63,177):s.line(30,y,330,y,BLUE,True)
        s.line(48,45,48,195,BLUE,True)
        s.line(150,72,330,72,ORANGE,width=4);s.line(150,168,330,168,ORANGE,width=4)
        s.path('M290,84 H110 A38,38 0 0 0 110,160 H290',GREEN,width=4)
        s.dim(60,78,60,166,'B_U','bend_envelope');s.dim(345,63,345,177,'B_avail','u_width',at=(352,124))
        s.dim(150,104,290,104,'Class B lap l_B,h','lap_horizontal');s.dim(110,215,290,215,'Straight U leg l_U','u_leg_in')
        s.text(30,28,'Plan at wall end · U-bar legs lap the face bars inside the cover lines',size=12)
        s.text(400,46,'l_db = 0.17 d_b (f_y / 1.97 f′_c^¼)²','ld_basic',size=12)
        s.text(400,67,'l_d,h = max(12, l_db · min(1.7, 1.3 ψ_e)) · top-cast','ld_horizontal',size=12)
        s.text(400,88,'l_d,v = max(12, l_db ψ_e)','ld_vertical',size=12)
        s.text(400,109,'l_B,h = 1.3 l_d,h ≤ l_U (U-LAP)','lap_horizontal',size=12)
        s.text(400,130,'l_B,v = 1.3 l_d,v ≤ l_v,prov (V-LAP)','lap_vertical',size=12)
        s.text(400,151,'l_U ≤ l_U,avail = L − 2c − 2 d_b (U-FIT)','u_leg_available',size=12)
        s.text(400,172,'B_U = bend ID + 2 d_b ≤ B_avail = t_w − 2c (U-BEND)','u_width',size=12)
        s.text(400,193,'l_v,prov ≤ l_v,avail = H − 2c − 2 d_b (V-FIT)',('vertical_available','vertical_lap_in'),size=12)
        s.text(400,222,'Vertical laps lie in elevation; fit checks do not set the splice schedule.',size=10)
    elif kind=='clearance':
        p1,p2,cy=110,265,115
        s.line(30,35,330,35);s.line(30,35,30,195);s.line(30,195,330,195);s.path('M330,35 l-6,20 l12,20 l-12,20 l12,20 l-12,20 l12,20 l-12,20 l12,20 l-6,20')
        for y in (48,182):s.line(30,y,330,y,BLUE,True)
        s.line(43,35,43,195,BLUE,True)
        for y in (53,177):s.line(48,y,330,y,ORANGE,width=5)
        for y in (62,168):
            for x in range(60,330,20):s.circle(x,y,4.5,GREEN,'#ffffff')
        for x in (p1,p2):
            s.circle(x,cy,26,BLUE,PLATE);s.circle(x,cy,16,BLUE,PAPER);s.circle(x,cy,14,GREY,STEEL);s.circle(x,cy,35,RED,dash=True)
            s.line(x,195,x,222,BLUE,True)
        s.dim(p1,66.5,p1,80,'a_grid','grid_gap',at=(p1+8,77),size=12)
        s.dim(p2,35,p2,80,'c_face','face_clear',at=(p2+8,77),size=12)
        s.dim(190,35,190,48.5,'c ≥ c_req','required_cover_in',at=(197,45),size=12)
        s.dim(30,cy,75,cy,'c_end','end_clear',at=(52,108,'middle'),size=12)
        s.dim(145,cy,230,cy,'a_rings','between_rings',at=(187,108,'middle'),size=12)
        s.dim(30,215,p1,215,'x_end','end_offset',size=12);s.dim(p1,215,p2,215,'s_p','pile_spacing_in',size=12)
        s.text(p1+38,158,'r_o + Δ_p','placement_tolerance_in',RED,size=11)
        s.text(30,27,'Plan at a ring row · outer horizontal bars, inner vertical bars (circles), rings at tolerance',size=11)
        s.text(440,42,'Dashed ring edge: r_o + Δ_p (placement tolerance)','placement_tolerance_in',RED,size=12)
        s.text(440,62,'a_grid = t_w/2 − c − 2 d_b − r_o − Δ_p · inner layer','grid_gap',size=12)
        s.text(440,82,'a_ring,req = max(1 in, 1.5 d_agg) ≤ a_grid, a_rings','ring_grid_required',size=12)
        s.text(440,102,'a_rings = s_p − D_o − 2 Δ_p (adjacent piles)','between_rings',size=12)
        s.text(440,122,'Cover c ≥ c_req at every wall surface (COVER)','required_cover_in',size=12)
        s.text(448,146,'Elevation at one pile · top and bottom ring cover',size=11)
        s.rect(575,150,125,90,BLUE);s.rect(620,150,20,90,GREY,STEEL)
        for y in (166,217):
            s.rect(595,y,70,7,ORANGE,WELD);s.path(f'M620,{y} v-6 h-6 Z M640,{y} v-6 h6 Z M620,{y+7} v6 h-6 Z M640,{y+7} v6 h6 Z',ORANGE,WELD)
        s.dim(585,150,585,160,'c_top = H − z_last − w','top_ring_cover',at=(568,159,'end'),size=12)
        s.dim(585,230,585,240,'c_bottom = z_1 − t_p − w','bottom_ring_cover',at=(568,236,'end'),size=12)
        s.dim(690,217,690,240,'z_1','first_ring_in',at=(684,236,'end'),size=11);s.text(668,176,'t_p','ring_t_in',size=11);s.text(649,160,'w','weld_leg_in',size=11)
    elif kind=='annulus':
        cx,cy=155,125
        s.circle(cx,cy,90,BLUE,PLATE);s.circle(cx,cy,60,ORANGE,'#f7ebd9');s.circle(cx,cy,50,BLUE,PAPER);s.circle(cx,cy,40,GREY,STEEL)
        s.line(cx-90,cy,cx+90,cy,BLUE,True)
        s.arrow(cx,cy,cx+90,cy);s.text(cx+96,cy+4,'r_o','outer_radius')
        s.arrow(cx,cy,cx,cy-60,ORANGE);s.text(cx+6,cy-64,'r_b','bearing_inner')
        s.arrow(cx,cy,cx-35.4,cy+35.4,BLUE);s.text(cx-62,cy+52,'r_i','inner_radius')
        s.arrow(cx,cy,cx+28.3,cy+28.3,'#5d6b78');s.text(cx+30,cy+44,'r_p','pipe_radius')
        s.line(cx-50,cy-8,cx-50,cy+8,RED);s.line(cx-40,cy-8,cx-40,cy+8,RED);s.text(cx-45,cy-12,'g','root_gap',RED,size=12,anchor='middle')
        s.text(40,28,'Plan of one ring · horizontal bearing annulus',size=12)
        s.text(300,50,'r_p = D_p / 2 · pipe face and cantilever root','pipe_radius',size=12)
        s.text(300,72,'r_i = D_i / 2 · plate hole; root gap g = r_i − r_p',('inner_radius','root_gap'),size=12)
        s.text(300,94,'r_o = D_o / 2 · plate outer edge','outer_radius',size=12)
        s.text(300,116,'r_b = max(r_i, r_p + w) · outside the upper weld','bearing_inner',size=12)
        s.text(300,138,'A = π (r_o² − r_b²) · blue annulus','bearing_area',size=12)
        s.text(300,160,'I = π (r_o⁴ − r_b⁴) / 4 · about the dashed diameter','bearing_inertia',size=12)
        s.text(300,188,'Orange: upper weld footprint r_p..r_b carries no concrete.',size=11)
        s.text(300,208,'No supporting-area enhancement is taken in bearing.',size=11)
    elif kind=='pressure':
        qmax,qmin=example['qmax'],example['qmin'];q0,qM=(qmax+qmin)/2,(qmax-qmin)/2
        scale=100/max(abs(qmax),abs(qmin),1e-12);x0,x1,y0=55,350,155;xc=(x0+x1)/2;half=(x1-x0)/2
        case=r['case'];rb=min(.72,max(case['ring_id_in']/2,case['pile_od_in']/2+case['weld_leg_in'])/(case['ring_od_in']/2))  # keep the bearing segments legible
        xa,xb=xc-half*rb,xc+half*rb
        y=lambda x:y0-(q0+qM*(x-xc)/half)*scale
        s.line(40,y0,370,y0,BLUE);s.line(x0,35,x0,217,BLUE,True);s.line(x1,35,x1,217,BLUE,True);s.line(xc,35,xc,214,BLUE,True)
        s.path(f'M{x0},{y0} L{x0},{y(x0):.1f} L{xa:.1f},{y(xa):.1f} L{xa:.1f},{y0} Z',GREEN,CONCRETE)
        s.path(f'M{xb:.1f},{y0} L{xb:.1f},{y(xb):.1f} L{x1},{y(x1):.1f} L{x1},{y0} Z',GREEN,CONCRETE)
        s.line(x0,y(x0),xa,y(xa),GREEN,width=3);s.line(xb,y(xb),x1,y(x1),GREEN,width=3);s.line(xa,y(xa),xb,y(xb),GREEN,True)
        s.rect(xa,y0-4,xb-xa,8,GREY,STEEL)
        s.text(60,29,'Linear elastic pressure across a diameter · bearing only outside ±r_b',size=12)
        s.text(x0+4,min(229,y(x0)+20),'q_min','qmin',RED if qmin<0 else GREEN)
        s.text(x1-44,max(26,y(x1)-10),'q_max','qmax');s.text(xc+5,y0-q0*scale-8,'q_0','qavg')
        s.dim(x1+14,y0-q0*scale,x1+14,y(x1),'q_M','qmoment',at=(x1+20,(y0-q0*scale+y(x1))/2+4))
        for x,label in ((x0,'−r_o'),(xa,'−r_b'),(xb,'+r_b'),(x1,'+r_o')):s.text(x,238,label,size=11,anchor='middle')
        s.text(411,55,'q_0 = R / A','qavg');s.text(411,85,'q_M = M r_o / I','qmoment')
        s.text(411,115,'q_max = q_0 + q_M  ·  q_min = q_0 − q_M',('qmax','qmin'))
        s.text(411,145,'Full contact requires q_min ≥ 0, i.e. q_M ≤ q_0.','qmin',size=12)
        s.text(411,175,'Contact: '+('OK' if example['contact_ok'] else 'FAIL — strength values are trial'),color=GREEN if example['contact_ok'] else RED,size=12)
        if active in ('bearing_limit','qmax'):
            yq=max(y0-118,y0-next(n['value'] for n in r['nodes'] if n['name']=='bearing_limit')*scale)
            s.line(40,yq,370,yq,RED,True);s.text(x0+6,yq+14,'q_R'+(' (not to scale)' if yq==y0-118 else ''),'bearing_limit',RED,size=12)
            s.text(411,205,'q_R = φ_b · 0.85 f′_c ≥ q_max (BEAR)','bearing_limit',size=12)
        else:s.text(411,205,'Bearing strength compares q_max with q_R.',size=12)
        s.text(411,232,'Grey: pipe and upper weld, no horizontal bearing.',size=11)
    elif kind=='plate':
        root,rb,ro,top,bot=72,115,327,145,167
        s.rect(45,50,27,184,fill=STEEL);s.rect(root,top,ro-root,bot-top,fill=PLATE)
        s.path(f'M{root},{top} V{top-43} L{rb},{top} Z M{root},{bot} V{bot+43} L{rb},{bot} Z',ORANGE,WELD)
        for i,x in enumerate(range(rb+10,ro,27)):
            L=34+i*4;s.arrow(x,top-3-L,x,top-3)
        s.text(rb+10,68,'q_max · r / r_p (grows with r)','qmax',size=12)
        s.dim(rb,232,ro,232,'loaded span r_b … r_o','bearing_inner',size=12);s.dim(root,232,rb,232,'w','weld_leg_in',at=(93,224,'middle'),size=12)
        s.line(rb,top-45,rb,bot+45,ORANGE,True)
        for x,label in ((root,'r_p'),(rb,'r_b'),(ro,'r_o')):s.text(x,247,label,size=11,anchor='middle')
        s.dim(ro+18,top,ro+18,bot,'t_p','ring_t_in',at=(ro+24,160))
        s.arrow(58,228,58,bot+10,RED);s.text(46,200,'v','root_shear',RED)
        s.moment(root+22,top-6,18,'m','root_moment')
        if active=='thickness_required':s.text(rb+10,50,'t_p ≥ w + 1/16 in at the weld edge','thickness_required',size=11)
        s.text(390,48,'Radial strip of the ring, root at the pipe face r_p',size=12)
        s.text(390,74,'v = ∫ q_max (r / r_p) dr over r_b … r_o','root_shear',size=12)
        s.text(390,100,'m = ∫ q_max (r / r_p)(r − r_p) dr','root_moment',size=12)
        s.text(390,126,'m_R = φ_f F_y,p t_p² / 6 ≥ m (PLATE)','plate_capacity',size=12)
        s.text(390,152,'v_R = φ_vy · 0.58 F_y,p t_p ≥ v (SHEAR)','plate_shear_capacity',size=12)
        s.text(390,178,'t_b = √(6 m / (φ_f F_y,p))','thickness_bending',size=12)
        s.text(390,204,'t_v = v / (φ_vy · 0.58 F_y,p)','thickness_shear',size=12)
        s.text(390,230,'t_req = max(t_b, t_v, w + 1/16 in) · trial','thickness_required',size=12)
    elif kind=='weld':
        weld_joint(s)
        s.arrow(145,88,215,88,RED);s.arrow(215,168,145,168,RED)
        s.text(235,89,'H_w','weld_radial',RED);s.text(235,184,'H_w','weld_radial',RED)
        s.arrow(152,95,152,126);s.arrow(152,153,152,198);s.text(166,211,'v/2 each','root_shear')
        s.text(405,50,'Two fillets form a couple over t_p; each takes v/2.',size=12)
        s.text(405,74,'H_w = m / t_p','weld_radial')
        s.text(405,98,'F_w = √[(v/2)² + H_w²]','weld_resultant')
        s.text(405,122,'a_w = (w − g) / √2','weld_throat')
        s.text(405,146,'F_R,w = φ_w · 0.60 F_EXX · a_w ≥ F_w (WELD)','weld_capacity',size=12)
        s.text(405,170,'w_strength = g + √2 F_w / (φ_w · 0.60 F_EXX)','weld_strength_leg',size=12)
        s.text(405,194,'w_req = max(w_strength, w_min,g) · trial','weld_required',size=12)
        s.text(405,222,'Root gap g is deducted from the leg before the throat.','root_gap',size=11)
    elif kind=='base':
        weld_joint(s)
        s.line(145,108,145,144,RED,width=5);s.line(80,74,108,74,RED,width=5);s.line(80,178,108,178,RED,width=5)
        s.arrow(190,92,150,104,RED);s.arrow(190,160,150,148,RED);s.text(196,96,'F_w','weld_resultant',RED);s.text(196,164,'F_w','weld_resultant',RED)
        s.text(405,50,'Each fillet force F_w enters the adjacent base metal.','weld_resultant',size=12)
        s.text(405,74,'Ring plane: t_p × l_w at the weld toe','ring_t_in',size=12)
        s.text(405,98,'Pipe plane: t_eff × l_w through the pipe wall','pile_t_effective_in',size=12)
        s.text(405,126,'Ring rupture: φ_vu · 0.58 F_u,p · t_p (RING-BASE)','ring_base_capacity',size=12)
        s.text(405,150,'Pipe yield: φ_vy · 0.58 F_y,pipe · t_eff (PIPE-YIELD)','pipe_yield_capacity',size=12)
        s.text(405,174,'Pipe rupture: φ_vu · 0.58 F_u,pipe · t_eff (PIPE-BASE)','pipe_base_capacity',size=12)
        s.text(405,202,'Red: shear planes, per unit weld length.',size=11)
        s.text(405,222,'Local shell bending remains outside scope.',size=11)
    elif kind=='weld-detail':
        weld_joint(s)
        s.line(118,104,118,148,RED,width=3);s.text(150,162,'ring edge → w_max','weld_maximum',RED,size=11)
        s.text(405,46,'t_max = max(t_p, t_eff)','thicker_part',size=12)
        s.text(405,67,'w_table,3 = 1/4 (t_max ≤ 3/4) else 5/16','minimum_thick_weld',size=12)
        s.text(405,88,'w_table,2 = 3/16 (t_max ≤ 1/2) else w_table,3','minimum_mid_weld',size=12)
        s.text(405,109,'w_table = 1/8 (t_max ≤ 1/4) else w_table,2','minimum_table_weld',size=12)
        s.text(405,130,'w_min = min(w_table, t_p, t_eff)','weld_minimum',size=12)
        s.text(405,151,'w_min,g = w_min + g ≤ w (WELD-MIN)','weld_min_gap',size=12)
        s.text(405,172,'w ≤ w_max = t_p − 1/16 at the ring edge (WELD-MAX)',('weld_maximum','weld_leg_in'),size=12)
        s.text(405,193,'l_w = 2π r_p · each continuous fillet','weld_length',size=12)
        s.text(405,214,'l_w,min = max(4 w, 1.5 in) ≤ l_w (WELD-LENGTH)','weld_length_min',size=12)
        s.text(405,236,'Gap allowance does not approve a WPS.',size=11)
    else:
        raise ValueError('Missing report schematic: '+kind)
    return '<figure class="equation-sketch">'+s.end()+'<figcaption>'+escape(meaning)+'. Conceptual schematic, not to scale; current values are listed below.</figcaption></figure>'
