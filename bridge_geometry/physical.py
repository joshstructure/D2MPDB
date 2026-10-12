"""Station cuts through source-derived bridge solids (feet, local bridge axes).

Support construction follows the registered FreeCAD model's bridge_layout,
bridge_supports, end_bents and current_source controllers. No native model is
modified. Station is longitudinal X, offset is transverse Y, elevation is Z.
"""
import math
import numpy as np

TOL = 1e-9


def require_physical_geometry(model):
    if not getattr(model,'physical',False) or getattr(model,'geometry_version',None)!='physical-station-cuts-2':
        raise ValueError('An older geometry model is still loaded. Reopen the updated notebook and Run all '
                         'to load caps, bearings and piles with physical station extents.')


def in_interval(station, limits):
    return limits[0]-TOL <= station <= limits[1]+TOL


def section_of_support(support, station, pile_heads=True):
    """Exact prism/loft/cylinder cut, with cap sockets and hollow pipe bores."""
    solid = support.get('solid_geometry')
    if not solid or not in_interval(station, solid['cap_bounds']):
        return []
    components = []
    def add(kind, ident, xy, beam=None, **metadata):
        components.append(dict(kind=kind, id=ident, beam=beam, xy=np.asarray(xy,dtype=float), **metadata))
    def cap_top(y):
        return support['top'] + support['slope']*(y-support['center'])
    notches = []
    for pile in solid['piles']:
        dx = station-pile['station']
        radius = pile['diameter']/2
        if (abs(dx)>radius+TOL if pile['shape']=='square' else abs(dx)>=radius-TOL):
            continue  # A cylindrical tangent has zero area; a square face has area.
        outer = radius if pile['shape']=='square' else math.sqrt(max(0,radius*radius-dx*dx))
        inner_radius = max(0,radius-pile['wall']) if pile['shape']=='pipe' else 0
        inner = math.sqrt(max(0,inner_radius**2-dx**2)) if abs(dx)<inner_radius else 0
        center=pile['offset'];left=center-outer;right=center+outer
        top=pile['cutoff'];bottom=pile['bottom']
        if pile_heads:
            bottom=max(bottom,pile['cap_underside']-1.8)
        intervals=[(left,center-inner),(center+inner,right)] if inner>TOL else [(left,right)]
        for side,(a,b) in enumerate(intervals):
            add('Pile',f"{support['name']}-pile-{pile['number']}-{side}",
                [[a,bottom],[b,bottom],[b,top],[a,top]],pile=pile['number'],cutoff=top)
        # Entire outer envelope is absent from cap concrete, including an unfilled bore.
        notches.append((left,right,top))
    left=support['center']-support['length']/2;right=left+support['length']
    cap=[[left,cap_top(left)],[right,cap_top(right)],[right,cap_top(right)-support['depth']]]
    for a,b,z in reversed(sorted(notches)):
        a=max(a,left);b=min(b,right)
        if a>=b or z<=min(cap_top(a),cap_top(b))-support['depth']:
            continue
        cap.extend([[b,cap_top(b)-support['depth']],[b,min(z,cap_top(b))],
                    [a,min(z,cap_top(a))],[a,cap_top(a)-support['depth']]])
    cap.append([left,cap_top(left)-support['depth']])
    # Cap first, so shared interfaces remain visible without covering pipe steel.
    components.insert(0,dict(kind='Cap',id=support['name']+'-cap',beam=None,xy=np.asarray(cap)))
    for ped in solid['pedestals']:
        if not in_interval(station,ped['bounds']):continue
        z=float(np.interp(station,ped['stations'],ped['tops']))
        a=ped['offset']-ped['width']/2;b=ped['offset']+ped['width']/2;c=ped['chamfer']
        add('Pedestal',ped['id'],[[a,cap_top(a)],[b,cap_top(b)],[b,z-c],[b-c,z],[a+c,z],[a,z-c]],
            beam=ped['beam'],top=z)
    for pad in solid['bearings']:
        if not in_interval(station,pad['bounds']):continue
        z=pad['top']+pad['slope']*(station-pad['station'])
        a=pad['offset']-pad['width']/2;b=pad['offset']+pad['width']/2
        add('Bearing',pad['id'],[[a,z-pad['thickness']],[b,z-pad['thickness']],[b,z],[a,z]],
            beam=pad['beam'],span=pad['span'],top=z)
    return components


class PhysicalBridgeMixin:
    geometry_version = 'physical-station-cuts-2'

    def __init__(self,config):
        self.physical=config.get('physical_geometry',{}).get('enabled',False)
        if self.physical is not True:
            raise ValueError('Physical support geometry is required. Run the updated Project inputs cell, then Run all. '
                             'The older station-only mode is no longer used by this notebook.')
        spans=sorted(config['spans'],key=lambda s:s['start_ft']);physical=config.get('physical_geometry',{})
        self.beam_limits=[];self.bearing_limits=[];self.deck_limits=[]
        for i,span in enumerate(spans):
            a,b=span['start_ft'],span['end_ft']
            if self.physical:
                end_clear=float(physical['beam_end_clear_in'])/12
                gap=float(physical['pier_beam_gap_in'])/12
                setback=float(physical['bearing_setback_in'])/12
                deck_clear=float(physical['deck_end_clear_in'])/12
                if min(end_clear,gap,setback,deck_clear)<0 or not all(np.isfinite([end_clear,gap,setback,deck_clear])):
                    raise ValueError('Physical clearances and bearing setback must be finite and nonnegative.')
                beam=(a+(end_clear if i==0 else gap/2),b-(end_clear if i==len(spans)-1 else gap/2))
                bearing=(beam[0]+setback,beam[1]-setback)
                deck=(a+(deck_clear if i==0 else 0),b-(deck_clear if i==len(spans)-1 else 0))
                if not a<=beam[0]<bearing[0]<bearing[1]<beam[1]<=b or deck[0]>=deck[1]:
                    raise ValueError('Physical beam ends and bearings must fit within each span.')
            else:beam=bearing=deck=(a,b)
            self.beam_limits.append(beam);self.bearing_limits.append(bearing);self.deck_limits.append(deck)
        super().__init__(config)
        self.inspection_start=self.start;self.inspection_end=self.end
        if self.physical:
            # Span schedule elevations refer to physical bearing centerlines.
            self.spans['bearing_start_ft']=[b[0] for b in self.bearing_limits]
            self.spans['bearing_end_ft']=[b[1] for b in self.bearing_limits]
            self.spans['beam_start_ft']=[b[0] for b in self.beam_limits]
            self.spans['beam_end_ft']=[b[1] for b in self.beam_limits]
            self.spans['bottom_start_ft']=self.pgl(self.spans.bearing_start_ft.to_numpy())-self.support_drop
            self.spans['bottom_end_ft']=self.pgl(self.spans.bearing_end_ft.to_numpy())-self.support_drop
            for support in self.supports:
                self._build_solid_geometry(support)
                if support.get('solid_geometry'):
                    self.inspection_start=min(self.inspection_start,support['solid_geometry']['cap_bounds'][0])
                    self.inspection_end=max(self.inspection_end,support['solid_geometry']['cap_bounds'][1])

    def span_components(self,stations,span_index=None):
        index,chord,camber=super().span_components(stations,span_index)
        if not self.physical:return index,chord,camber
        s=np.atleast_1d(np.asarray(stations,dtype=float))
        a=np.array([self.bearing_limits[i][0] for i in index]);b=np.array([self.bearing_limits[i][1] for i in index])
        t=(s-a)/(b-a)
        return index,self.pgl(a)+(self.pgl(b)-self.pgl(a))*t,4*self.spans.camber_in.to_numpy()[index]/12*t*(1-t)

    def breakpoints(self,span_index):
        points=super().breakpoints(span_index)
        if not self.physical:return points
        a,b=self.bearing_limits[span_index]
        return np.unique(np.r_[points,self.beam_limits[span_index],self.deck_limits[span_index],a,(a+b)/2,b])

    def critical_stations(self,span_index,function):
        points=super().critical_stations(span_index,function)
        if not self.physical:return points
        a,b=self.beam_limits[span_index]
        # Extrema in end clearances or the open pier joint are not beam results.
        return points[(points>=a-TOL)&(points<=b+TOL)]

    def evaluate(self,stations,span_index=None):
        values=super().evaluate(stations,span_index)
        if self.physical:
            values['beam_present']=np.array([in_interval(s,self.beam_limits[i]) for s,i in zip(values['station'],values['span'])])
            values['deck_present']=np.array([in_interval(s,self.deck_limits[i]) for s,i in zip(values['station'],values['span'])])
            values['clearance'][~values['beam_present'],:]=np.nan
        else:
            values['beam_present']=np.ones(len(values['station']),dtype=bool)
            values['deck_present']=np.ones(len(values['station']),dtype=bool)
        return values

    def inspect(self,station):
        if not np.isfinite(station) or not self.inspection_start-TOL<=station<=self.inspection_end+TOL:
            raise ValueError('Station is outside the modeled geometry.')
        value=self.evaluate([np.clip(station,self.start,self.end)])
        value['station'][0]=station
        if station<self.start or station>self.end:
            value['beam_present'][:]=False;value['deck_present'][:]=False
            value['clearance'][:]=np.nan;value['pgl'][:]=np.nan
        return value

    def support_geometry(self,p,station,faces,name,kind):
        support=super().support_geometry(p,station,faces,name,kind)
        if not self.physical:return support
        datum=station
        if kind=='end_bent':
            sign=1 if faces[0][1]=='Start' else -1
            station=datum+sign*(support['width']/2-p['backwall_thickness_in']/12-p['rear_face_inset_in']/12)
        support.update(datum_station=datum,station=station,pile_shape='pipe' if kind=='pier' else 'square')
        pad_length=finite(p.get('pad_length_in',10),'Bearing length',True)/12
        rows=[]
        for row in support['seats'].to_dict('records'):
            span=next(i for i,s in self.spans.iterrows() if s['id']==row['Span'])
            beam=int(row['Beam'])-1
            bearing=self.bearing_limits[span][0 if row['Face']=='Start' else 1]
            lo,hi=bearing-pad_length/2,bearing+pad_length/2
            if lo<self.beam_limits[span][0]-TOL or hi>self.beam_limits[span][1]+TOL:
                raise ValueError(f'{name}: bearing extends past a physical beam end.')
            bottoms=self.evaluate([lo,hi],span)['bottom'][:,beam]
            plane=float(np.mean(bottoms));slope=float((bottoms[1]-bottoms[0])/pad_length)
            actual=float(self.evaluate([bearing],span)['bottom'][0,beam])
            row.update({'Bearing station (ft)':bearing,'Bearing start (ft)':lo,'Bearing end (ft)':hi,
                        'Pad top (ft)':plane,'Bearing slope':slope,'Beam bottom (ft)':actual,
                        'Seat chord gap (in)':(actual-plane)*12,'Pedestal top (ft)':plane-row['Pad (in)']/12})
            rows.append(row)
        seats=pd.DataFrame(rows)
        top=p['top_center_ft'];reveal=p['minimum_pedestal_cl_in']
        if top is None and reveal is not None and seats['Pedestal top (ft)'].notna().all():
            top=float(np.min(seats['Pedestal top (ft)']-support['slope']*(seats['Offset (ft)']-support['center']))-reveal/12)
        support['top']=top
        seats['Pedestal height (in)']=(seats['Pedestal top (ft)']-(np.nan if top is None else top+support['slope']*(seats['Offset (ft)']-support['center'])))*12
        support['seats']=seats
        corners=support['corners']
        corners['Elevation (ft)']=(np.nan if top is None else top+support['slope']*(corners['Offset (ft)']-support['center']))
        corners.loc[corners['Corner'].str.startswith('B'),'Elevation (ft)']-=support['depth'] if support['depth'] is not None else np.nan
        piles=support['pile_elevations']
        if not piles.empty:
            piles['Cap top (ft)']=np.nan if top is None else top+support['slope']*(piles['Offset (ft)']-support['center'])
            piles['Cap underside (ft)']=piles['Cap top (ft)']-(support['depth'] if support['depth'] is not None else np.nan)
            piles['Pile cutoff (ft)']=piles['Cap underside (ft)']+support['pile_embedment_ft']
        return support

    def _build_solid_geometry(self,p):
        if p['missing'] or p.get('width') is None:return
        cfg=self.cfg['pier'] if p['kind']=='pier' else self.cfg['end_bents'][p['end_key']]
        cap_bounds=[p['station']-p['width']/2,p['station']+p['width']/2]
        length=finite(cfg['pedestal_length_in'],'Pedestal length',True)/12
        chamfer=finite(cfg['pedestal_chamfer_in'],'Pedestal chamfer')/12
        if chamfer<0:raise ValueError('Pedestal chamfer cannot be negative.')
        if p['kind']=='end_bent':
            bounds=([p['datum_station'],p['datum_station']+length] if p['end_key']=='start' else
                    [p['datum_station']-length,p['datum_station']])
        else:bounds=[p['station']-length/2,p['station']+length/2]
        if bounds[0]<cap_bounds[0]-TOL or bounds[1]>cap_bounds[1]+TOL:
            raise ValueError(f"{p['name']}: pedestal longitudinal footprint extends beyond cap.")
        bearings=[];pedestals=[];piles=[]
        for beam,group in p['seats'].groupby('Beam',sort=True):
            group=group.sort_values('Bearing station (ft)');records=group.to_dict('records')
            for row in records:
                limits=[row['Bearing start (ft)'],row['Bearing end (ft)']]
                if limits[0]<bounds[0]-TOL or limits[1]>bounds[1]+TOL:
                    raise ValueError(f"{p['name']}: bearing extends beyond pedestal footprint.")
                bearings.append(dict(id=f"{p['name']}-bearing-{beam}-{row['Span']}",beam=int(beam),span=int(row['Span']),
                    bounds=limits,station=row['Bearing station (ft)'],offset=row['Offset (ft)'],
                    width=float(p['pad_width'][int(beam)-1]),thickness=row['Pad (in)']/12,
                    top=row['Pad top (ft)'],slope=row['Bearing slope']))
            plane=lambda row,s:row['Pedestal top (ft)']+row['Bearing slope']*(s-row['Bearing station (ft)'])
            if len(records)==1:
                cuts=bounds;tops=[plane(records[0],s) for s in cuts]
            else:
                cuts=[bounds[0],records[0]['Bearing end (ft)'],records[-1]['Bearing start (ft)'],bounds[1]]
                tops=[plane(records[0],cuts[0]),plane(records[0],cuts[1]),plane(records[-1],cuts[2]),plane(records[-1],cuts[3])]
            if not np.all(np.diff(cuts)>0):raise ValueError('Opposed bearing seats must not overlap.')
            width=float(p['pedestal_width'][int(beam)-1]);offset=float(self.offsets[int(beam)-1])
            if chamfer>=width/2:raise ValueError('Pedestal chamfer is larger than its half-width.')
            local_cap=p['top']+p['slope']*(offset-p['center'])+abs(p['slope'])*width/2
            if min(tops)-chamfer<local_cap-TOL:raise ValueError('Pedestal bevel intersects cap top.')
            pedestals.append(dict(id=f"{p['name']}-pedestal-{beam}",beam=int(beam),bounds=bounds,
                stations=cuts,tops=tops,offset=offset,width=width,chamfer=chamfer))
        wall=finite(cfg.get('pile_wall_in',0),'Pipe wall')/12
        trial=finite(self.cfg['physical_geometry']['trial_pile_length_ft'],'Saved trial pile length',True)
        for row in p['pile_elevations'].to_dict('records'):
            diameter=row['Diameter (in)']/12
            if p['pile_shape']=='pipe' and not 0<wall<diameter/2:raise ValueError('Pipe wall must be positive and smaller than its radius.')
            piles.append(dict(number=int(row['Pile']),station=p['station'],offset=row['Offset (ft)'],
                diameter=diameter,wall=wall,shape=p['pile_shape'],cutoff=row['Pile cutoff (ft)'],
                cap_underside=row['Cap underside (ft)'],bottom=row['Pile cutoff (ft)']-trial))
        p['solid_geometry']=dict(cap_bounds=cap_bounds,bearings=bearings,pedestals=pedestals,piles=piles)
        p['pedestal_length_ft']=length

    def support_at(self,station):
        if not self.physical:return super().support_at(station)
        return next((p for p in self.supports if p.get('solid_geometry') and in_interval(station,p['solid_geometry']['cap_bounds'])),None)

    def support_section(self,station):
        p=self.support_at(station)
        return section_of_support(p,station) if p is not None and self.physical else []

    def selected_table(self,station):
        if not self.physical:return super().selected_table(station)
        values=self.inspect(station)
        table=super().selected_table(float(np.clip(station,self.start,self.end)))
        if not values['beam_present'][0]:
            for col in ['Beam top (ft)','Beam bottom (ft)','Camber (in)','Haunch L (in)','Haunch CL (in)','Haunch R (in)','Clearance (ft)']:
                table[col]=np.nan
        if not values['deck_present'][0]:table['Deck CL (ft)']=np.nan
        return table

    def quantities(self):
        if not self.physical:return super().quantities()
        rows=[]
        for i,span in self.spans.iterrows():
            lo,hi=self.beam_limits[i]
            cuts=np.unique(np.r_[lo,[s for s in self.breakpoints(i) if lo<s<hi],hi])
            candidates=np.unique(np.r_[cuts,[s for s in self.haunch_candidates[i] if lo<=s<=hi]])
            hs=self.uncorrected_haunch(candidates,i)+self.support_drop
            for b in range(self.count):
                volume=sum((v-u)/6*(self.flange_area(u,b,i)+4*self.flange_area((u+v)/2,b,i)+self.flange_area(v,b,i))
                           for u,v in zip(cuts[:-1],cuts[1:]))
                k=np.unravel_index(np.argmin(hs[:,b,:]),hs[:,b,:].shape)
                rows.append({'Span':span['id'],'Beam':b+1,'Volume (ft3)':volume,'Volume (yd3)':volume/27,
                    'Min flange haunch (in)':float(hs[k[0],b,k[1]]*12),'Station':station_label(candidates[k[0]]),
                    'Analytical difference (ft3)':np.nan})
        return pd.DataFrame(rows)

    def beam_outline(self,offset,bottom):
        """Source FIB36 section; each circular fillet uses 180 short chords."""
        z=(224.5+15*math.sqrt(1186))/31
        tangent=(18.5-225/math.sqrt(1186),z-465/math.sqrt(1186))
        angle=math.atan2(tangent[1]-z,tangent[0]-18.5)+2*math.pi
        arc=[(18.5+15*math.cos(a),z+15*math.sin(a)) for a in np.linspace(math.pi,angle,181)]
        points=[(-24,36),(24,36),(24,32.5),(7,31),(3.5,27.5),(3.5,z)]
        points+=arc[1:]+[(19,7),(19,.75),(18.25,0),(-18.25,0),(-19,.75),(-19,7)]
        points+=[(-x,y) for x,y in reversed(arc)]+[(-3.5,27.5),(-7,31),(-24,32.5)]
        return np.asarray(points)*[self.flange/48,self.depth/36]+[offset,bottom]
