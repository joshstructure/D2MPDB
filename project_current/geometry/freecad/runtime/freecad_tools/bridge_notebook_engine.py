"""Verbatim BridgeModel from user notebook cell 6; source SHA recorded in reports/bridge/source-manifest.json."""
# @title
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import pandas as pd


def station_label(value):
    sign = '-' if value < 0 else ''
    hundredths = round(abs(float(value)) * 100)
    return f'{sign}{hundredths // 10000}+{(hundredths % 10000)/100:05.2f}'


def finite(value, name, positive=False):
    if isinstance(value, (bool, np.bool_)) or not np.isscalar(value):
        raise ValueError(f'{name}: enter a finite number.')
    value = float(value)
    if not np.isfinite(value) or (positive and value <= 0):
        raise ValueError(f'{name}: enter a {"positive " if positive else ""}finite number.')
    return value


def beam_values(value, n, name, positive=False):
    a = np.asarray(value, dtype=float)
    if a.ndim == 0:
        a = np.full(n, float(a))
    if a.shape != (n,) or not np.all(np.isfinite(a)) or (positive and np.any(a <= 0)):
        raise ValueError(f'{name}: enter one finite {"positive " if positive else ""}value or exactly {n} values.')
    return a


def configuration_id(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:10]


class BridgeModel:
    """One resolved geometry model; tables and figures only consume its results.

    Feet internally; inputs explicitly labeled _in are converted once. Span
    camber is an upward quadratic, and supports share one vertical translation.
    XML station mapping is an explicit project assumption, not inferred survey geometry.
    """
    def __init__(self, config):
        self.cfg = copy.deepcopy(config)
        self.model_id = configuration_id(config)
        p, d, b = self.cfg['profile'], self.cfg['deck'], self.cfg['beams']
        self.start = finite(p['start_sta_ft'], 'Profile start')
        self.end = finite(p['end_sta_ft'], 'Profile end')
        if self.end <= self.start:
            raise ValueError('Profile end must follow its start.')
        self.z0 = finite(p['start_elev_ft'], 'Profile start elevation')
        self.z1 = finite(p['end_elev_ft'], 'Profile end elevation')
        self.peak = finite(p['intersection_sta_ft'], 'Tangent intersection station')
        if not self.start < self.peak < self.end:
            raise ValueError('Tangent intersection must be inside the profile.')
        self.profile_mode = p['mode']
        length = self.end-self.start
        if self.profile_mode == 'brokeback':
            magnitude = finite(p['nominal_grade'], 'Nominal tangent grade', True)
            self.peak_elev = (self.z0+magnitude*(self.peak-self.start)
                              +self.z1+magnitude*(self.end-self.peak))/2
            self.g1 = (self.peak_elev-self.z0)/(self.peak-self.start)
            self.g2 = (self.z1-self.peak_elev)/(self.end-self.peak)
        elif self.profile_mode == 'parabolic':
            delta = finite(p['parabolic_grade_change'], 'Parabolic grade change')
            # Endpoint elevations and grade change govern; entering grade is derived.
            self.g1 = (self.z1-self.z0)/length-delta/2
            self.g2 = self.g1+delta
        else:
            raise ValueError('Profile mode must be brokeback or parabolic.')
        self.deck_width = finite(d['width_ft'], 'Deck width', True)
        self.deck_center = finite(d['center_offset_ft'], 'Deck center offset')
        self.deck_thickness = finite(d['thickness_ft'], 'Deck thickness', True)
        self.deck_mode = d['mode']
        for name in ['crown_slope','uniform_slope','transition_start_ft','transition_end_ft','slope_start','slope_end']:
            finite(d[name], name)
        if self.deck_mode not in ['crowned','uniform','transition']:
            raise ValueError('Deck mode must be crowned, uniform, or transition.')
        if self.deck_mode == 'transition' and d['transition_end_ft'] <= d['transition_start_ft']:
            raise ValueError('Slope transition end must follow its start.')
        self.count = b['count']
        if isinstance(self.count,bool) or not isinstance(self.count,int) or self.count < 1:
            raise ValueError('Beam count must be a positive integer.')
        if b['gaps_ft'] is None:
            gaps = np.full(self.count-1, finite(b['spacing_ft'],'Beam spacing',True))
        else:
            gaps = np.asarray(b['gaps_ft'],dtype=float)
            if gaps.shape != (self.count-1,) or not np.all(np.isfinite(gaps)) or np.any(gaps<=0):
                raise ValueError('Unequal gaps require count-1 positive finite values.')
        self.offsets = np.r_[0.,np.cumsum(gaps)]
        self.offsets += (-self.offsets[-1]/2 if b['first_offset_ft'] is None
                         else finite(b['first_offset_ft'],'First beam offset'))
        self.raises = beam_values(b['raise_in'],self.count,'Beam vertical offsets')/12
        self.depth = finite(b['depth_ft'],'Beam depth',True)
        self.flange = finite(b['top_flange_width_in'],'Top flange width',True)/12
        self.minimum_haunch = finite(b['minimum_haunch_in'],'Minimum haunch')/12
        if self.minimum_haunch < 0 or np.any(gaps < self.flange-1e-9):
            raise ValueError('Minimum haunch must be nonnegative and beam flanges must not overlap.')
        self.deck_left = self.deck_center-self.deck_width/2
        self.deck_right = self.deck_center+self.deck_width/2
        if self.offsets[0]-self.flange/2 < self.deck_left-1e-9 or self.offsets[-1]+self.flange/2 > self.deck_right+1e-9:
            raise ValueError('Beam flanges extend outside the entered deck width.')
        self.spans = pd.DataFrame(self.cfg['spans']).sort_values('start_ft').reset_index(drop=True)
        if len(self.spans)<1 or self.spans['id'].duplicated().any():
            raise ValueError('Provide spans with unique IDs.')
        for name in ['start_ft','end_ft','camber_in']:
            if not np.all(np.isfinite(self.spans[name].to_numpy(dtype=float))):
                raise ValueError('Span inputs must be finite.')
        self.spans['length_ft'] = self.spans['end_ft']-self.spans['start_ft']
        if np.any(self.spans['length_ft']<=0) or np.any(self.spans['camber_in']<0):
            raise ValueError('Span lengths must be positive and camber cannot be negative.')
        if not np.allclose(self.spans['end_ft'].to_numpy()[:-1],self.spans['start_ft'].to_numpy()[1:],rtol=0,atol=1e-8):
            raise ValueError('Spans must meet without gaps or overlaps.')
        if not np.isclose(self.spans.iloc[0].start_ft,self.start,rtol=0,atol=1e-8) or not np.isclose(self.spans.iloc[-1].end_ft,self.end,rtol=0,atol=1e-8):
            raise ValueError('Spans must cover the entered profile limits.')
        self.clearance_required = finite(self.cfg['roadway']['clearance_required_ft'],'Required clearance',True)
        points = self.cfg['evaluation']['points_per_span']
        if isinstance(points,bool) or not isinstance(points,int) or points<5:
            raise ValueError('points_per_span must be an integer of at least 5.')
        self.road, self.road_note = self.load_roadway()
        # Find every quadratic extremum, not just the stations of a sampling grid.
        self.haunch_candidates = [self.critical_stations(i, self.uncorrected_haunch) for i in range(len(self.spans))]
        worst = min(np.min(self.uncorrected_haunch(s,i)) for i,s in enumerate(self.haunch_candidates))
        self.support_drop = self.minimum_haunch-worst
        self.spans['bottom_start_ft'] = self.pgl(self.spans.start_ft.to_numpy())-self.support_drop
        self.spans['bottom_end_ft'] = self.pgl(self.spans.end_ft.to_numpy())-self.support_drop
        self.clearance_candidates = [self.critical_stations(i,lambda s,j:self.evaluate(s,j)['clearance'])
                                     for i in range(len(self.spans))]
        grids=[]
        for i,row in self.spans.iterrows():
            grids.append(np.unique(np.r_[np.linspace(row.start_ft,row.end_ft,points),self.breakpoints(i),
                                          self.haunch_candidates[i],self.clearance_candidates[i],
                                          (row.start_ft+row.end_ft)/2]))
        self.stations = np.unique(np.concatenate(grids))
        self.results = self.evaluate(self.stations)
        self.haunch_min, self.haunch_station, self.haunch_beam = self.minimum('haunch')
        self.clearance_min, self.clearance_station, self.clearance_beam = self.minimum('clearance')
        self.covered_length = sum(max(0,min(r['end'],self.end)-max(r['start'],self.start)) for r in self.road)
        self.full_road_coverage = abs(self.covered_length-(self.end-self.start)) <= 1e-6
        self.quantity_table = self.quantities()
        self.pier = self.pier_geometry()

    def pgl(self, stations):
        s=np.asarray(stations,dtype=float)
        if self.profile_mode=='brokeback':
            return np.where(s<=self.peak,self.z0+self.g1*(s-self.start),self.peak_elev+self.g2*(s-self.peak))
        x=s-self.start
        return self.z0+self.g1*x+.5*(self.g2-self.g1)/(self.end-self.start)*x*x

    def deck_delta(self, stations, offsets):
        s,x=np.broadcast_arrays(np.asarray(stations,dtype=float),np.asarray(offsets,dtype=float))
        d=self.cfg['deck']
        if self.deck_mode=='crowned': return np.abs(x)*d['crown_slope']
        slope=(d['uniform_slope'] if self.deck_mode=='uniform' else
               np.interp(s,[d['transition_start_ft'],d['transition_end_ft']],[d['slope_start'],d['slope_end']]))
        return x*slope

    def deck_top(self, stations, offsets):
        return self.pgl(stations)+self.deck_delta(stations,offsets)

    def span_components(self, stations, span_index=None):
        s=np.atleast_1d(np.asarray(stations,dtype=float))
        if not np.all(np.isfinite(s)) or np.any(s<self.start-1e-8) or np.any(s>self.end+1e-8):
            raise ValueError('Station is outside the bridge.')
        if span_index is None:
            # Interior support belongs to the departing span; final support to last span.
            index=np.minimum(np.searchsorted(self.spans.end_ft.to_numpy(),s,side='right'),len(self.spans)-1)
        else:
            index=np.full(s.shape,int(span_index))
        a=self.spans.start_ft.to_numpy()[index];L=self.spans.length_ft.to_numpy()[index]
        if np.any(s<a-1e-8) or np.any(s>a+L+1e-8): raise ValueError('Station does not belong to selected span.')
        t=(s-a)/L
        chord=self.pgl(a)+(self.pgl(a+L)-self.pgl(a))*t
        camber=4*self.spans.camber_in.to_numpy()[index]/12*t*(1-t)
        return index,chord,camber

    def flange_offsets(self):
        x=self.offsets[:,None]+np.array([-self.flange/2,0,self.flange/2])
        # The fourth point captures a crown break even when it is not at beam CL.
        return np.c_[x,np.clip(np.zeros(self.count),x[:,0],x[:,-1])]

    def uncorrected_haunch(self, stations, span_index):
        s=np.atleast_1d(stations);_,chord,camber=self.span_components(s,span_index)
        x=self.flange_offsets()
        return self.deck_top(s[:,None,None],x[None,:,:])-self.deck_thickness-(
            chord[:,None,None]+camber[:,None,None]+self.raises[None,:,None]+self.depth)

    def breakpoints(self, span_index):
        row=self.spans.iloc[span_index];points=[row.start_ft,row.end_ft]
        if self.profile_mode=='brokeback':points.append(self.peak)
        elif abs(self.g2-self.g1)>1e-14:
            points.append(self.start-self.g1*(self.end-self.start)/(self.g2-self.g1))
        if self.deck_mode=='transition':points.extend([self.cfg['deck']['transition_start_ft'],self.cfg['deck']['transition_end_ft']])
        for segment in self.road:points.extend([segment['start'],segment['end']])
        return np.unique([float(p) for p in points if row.start_ft<=p<=row.end_ft])

    def critical_stations(self, span_index, function):
        cuts=self.breakpoints(span_index);points=list(cuts)
        for a,b in zip(cuts[:-1],cuts[1:]):
            y=np.asarray(function(np.array([a,(a+b)/2,b]),span_index)).reshape(3,-1)
            # y(t) = A*t^2+B*t+C, t in [0,1], exact within each modeled interval.
            A=2*(y[2]-2*y[1]+y[0]);B=y[2]-y[0]-A
            with np.errstate(divide='ignore',invalid='ignore'): roots=-B/(2*A)
            valid=np.isfinite(roots)&(np.abs(A)>1e-12)&(roots>0)&(roots<1)
            points.extend(a+(b-a)*roots[valid])
        return np.unique(points)

    def load_roadway(self):
        cfg=self.cfg['roadway'];path=Path(cfg['xml_path'])
        if not path.exists():return [],f'XML not found: {path}. Clearance not evaluated.'
        try:
            root=ET.parse(path).getroot()
            # Strip namespaces while retaining source element names.
            for node in root.iter():node.tag=node.tag.split('}')[-1]
            alignments=list(root.iter('VerticalAlignment'))
            name=cfg['alignment_name']
            choices=[a for a in alignments if a.get('name')==name] if name is not None else alignments
            if len(choices)!=1:raise ValueError('Select one unique XML vertical alignment by name.')
            shift=finite(cfg['bridge_station_at_xml_zero_ft'],'XML station mapping')
            def point(e):return float(e.find('station').get('externalStation'))+shift,float(e.get('elevation'))
            segments=[]
            for elements in choices[0].iter('VerticalElements'):
                for e in elements:
                    if e.tag not in ['VerticalLine','VerticalParabola']:raise ValueError(f'Unsupported roadway element: {e.tag}')
                    a,z0=point(e.find('VerticalStart'));b,z1=point(e.find('VerticalEnd'));L=b-a
                    if L<=0:raise ValueError('Roadway elements must have positive length.')
                    grade=(z1-z0)/L;quad=0.
                    if e.tag=='VerticalParabola':
                        pi,zi=point(e.find('VerticalPI'))
                        if not a<pi<b:raise ValueError('Invalid roadway VPI station.')
                        grade=(zi-z0)/(pi-a);g2=(z1-zi)/(b-pi);quad=(g2-grade)/(2*L)
                        if abs(z0+grade*L+quad*L*L-z1)>.001:raise ValueError('Roadway parabola endpoint is inconsistent.')
                    if not np.all(np.isfinite([a,b,z0,grade,quad])):raise ValueError('Nonfinite roadway data.')
                    segments.append(dict(start=a,end=b,z=z0,g=grade,q=quad))
            segments.sort(key=lambda r:r['start'])
            if not segments:raise ValueError('No roadway segments found.')
            for a,b in zip(segments[:-1],segments[1:]):
                if b['start']<a['end']-1e-6:raise ValueError('Overlapping roadway segments.')
                if abs(b['start']-a['end'])<1e-6:
                    z=a['z']+a['g']*(a['end']-a['start'])+a['q']*(a['end']-a['start'])**2
                    if abs(z-b['z'])>.001:raise ValueError('Discontinuous roadway segment elevations.')
            return segments,f"Alignment {choices[0].get('name','(unnamed)')}; no extrapolation."
        except (ET.ParseError,OSError,ValueError,AttributeError,TypeError) as error:
            return [],f'Roadway unavailable: {error}'

    def roadway(self, stations):
        s=np.atleast_1d(np.asarray(stations,dtype=float));out=np.full(s.shape,np.nan)
        for row in self.road:
            mask=(s>=row['start']-1e-9)&(s<=row['end']+1e-9);x=s[mask]-row['start']
            out[mask]=row['z']+row['g']*x+row['q']*x*x
        return out

    def evaluate(self, stations, span_index=None):
        s=np.atleast_1d(np.asarray(stations,dtype=float));idx,chord,camber=self.span_components(s,span_index)
        bottom=chord[:,None]-self.support_drop+camber[:,None]+self.raises[None,:]
        top=bottom+self.depth
        deck=self.deck_top(s[:,None,None],self.flange_offsets()[None,:,:])
        road=self.roadway(s)
        return dict(station=s,span=idx,pgl=self.pgl(s),camber=camber,bottom=bottom,top=top,deck=deck,
                    haunch=deck-self.deck_thickness-top[:,:,None],roadway=road,
                    clearance=bottom-road[:,None])

    def minimum(self, kind):
        best=(np.inf,np.nan,None)
        candidates=self.haunch_candidates if kind=='haunch' else self.clearance_candidates
        for i,s in enumerate(candidates):
            values=(self.uncorrected_haunch(s,i)+self.support_drop if kind=='haunch'
                    else self.evaluate(s,i)['clearance'])
            if not np.any(np.isfinite(values)):continue
            index=np.unravel_index(np.nanargmin(values),values.shape)
            if values[index]<best[0]:best=(float(values[index]),float(s[index[0]]),index[1]+1)
        return best if np.isfinite(best[0]) else (np.nan,np.nan,None)

    def flange_area(self, station, beam, span):
        row=self.evaluate([station],span)
        left,right=self.offsets[beam]+np.array([-self.flange/2,self.flange/2])
        xs=np.unique([left,right]+([0.] if left<0<right else []))
        h=self.deck_top(station,xs)-self.deck_thickness-row['top'][0,beam]
        return float(np.trapezoid(h,xs))

    def quantities(self):
        rows=[]
        for i,span in self.spans.iterrows():
            cuts=self.breakpoints(i)
            hs=self.uncorrected_haunch(self.haunch_candidates[i],i)+self.support_drop
            for b in range(self.count):
                volume=sum((v-u)/6*(self.flange_area(u,b,i)+4*self.flange_area((u+v)/2,b,i)+self.flange_area(v,b,i))
                           for u,v in zip(cuts[:-1],cuts[1:]))
                # Independent closed-form camber integral when profile is linear within the span.
                analytical=np.nan
                if self.profile_mode=='brokeback' and not span.start_ft<self.peak<span.end_ft and self.deck_mode!='transition':
                    analytical=span.length_ft*((self.flange_area(span.start_ft,b,i)+self.flange_area(span.end_ft,b,i))/2
                                               -self.flange*(2/3)*span.camber_in/12)
                k=np.unravel_index(np.argmin(hs[:,b,:]),hs[:,b,:].shape)
                rows.append({'Span':span['id'],'Beam':b+1,'Volume (ft3)':volume,'Volume (yd3)':volume/27,
                             'Min flange haunch (in)':float(hs[k[0],b,k[1]]*12),
                             'Station':station_label(self.haunch_candidates[i][k[0]]),
                             'Analytical difference (ft3)':volume-analytical})
        return pd.DataFrame(rows)

    def pier_geometry(self):
        p=self.cfg['pier'];missing=[]
        joints=self.spans.end_ft.to_numpy()[:-1]
        station=p['station_ft']
        if station is None and len(joints)==1:station=float(joints[0])
        if station is None:return dict(missing=['Select an interior pier station.'],seats=pd.DataFrame(),corners=pd.DataFrame())
        station=finite(station,'Pier station');matches=np.flatnonzero(np.isclose(joints,station,rtol=0,atol=1e-8))
        if len(matches)!=1:raise ValueError('Pier must coincide with an interior support.')
        j=int(matches[0]);pads=p['pad_height_in']
        if pads is None:
            pads=np.full((2,self.count),np.nan);missing.append('Bearing-pad height')
        else:
            pads=np.asarray(pads,dtype=float)
            if pads.ndim==0:pads=np.full((2,self.count),float(pads))
            elif pads.shape==(self.count,):pads=np.tile(pads,(2,1))
            if pads.shape!=(2,self.count) or not np.all(np.isfinite(pads)) or np.any(pads<=0):raise ValueError('Pad heights require positive scalar, N, or 2-by-N values.')
        ped_width=beam_values(p['pedestal_width_in'],self.count,'Pedestal width',True)/12
        pad_width=None if p['pad_width_in'] is None else beam_values(p['pad_width_in'],self.count,'Pad width',True)/12
        if pad_width is not None and (np.any(pad_width>ped_width+1e-9) or np.any(pad_width>self.flange*38/48+1e-9)):
            raise ValueError('Bearing-pad width exceeds pedestal or modeled beam bottom flange width.')
        center=finite(p['center_offset_ft'],'Cap center');slope=finite(p['cross_slope'],'Cap cross slope')
        length=p['length_ft'];depth=p['depth_ft']
        width=None if p.get('width_ft') is None else finite(p['width_ft'],'Cap width',True)
        pile_layout=pd.DataFrame();pile_basis=None
        pile_keys=['pile_count','pile_diameter_in','pile_spacing_diameters','pile_end_clear_in']
        if any(k in p for k in pile_keys):
            if not all(k in p for k in pile_keys):raise ValueError('Complete all four pile-layout inputs.')
            count=p['pile_count']
            if isinstance(count,bool) or not isinstance(count,int) or count<2:raise ValueError('Pile count must be an integer of at least two.')
            diameter=finite(p['pile_diameter_in'],'Pile diameter',True)/12
            ratio=finite(p['pile_spacing_diameters'],'Pile spacing in diameters',True)
            clear=finite(p['pile_end_clear_in'],'Pile-face end clearance')/12
            if ratio<1 or clear<0:raise ValueError('Piles cannot overlap or extend past the cap ends.')
            spacing=ratio*diameter
            derived=(count-1)*spacing+diameter+2*clear
            if length is not None and not np.isclose(float(length),derived,rtol=0,atol=1e-8):
                raise ValueError('Cap length conflicts with the pile layout. Use length_ft=None to derive it.')
            length=derived
            offsets=center+(np.arange(count)-(count-1)/2)*spacing
            pile_layout=pd.DataFrame({'Pile':np.arange(1,count+1),'Offset (ft)':offsets,'Diameter (in)':diameter*12})
            pile_basis=dict(count=count,diameter_ft=diameter,spacing_ft=spacing,end_clear_ft=clear)
        for val,name in [(length,'Cap length'),(depth,'Cap depth')]:
            if val is None:missing.append(name)
            else:finite(val,name,True)
        if length is not None and (np.any(self.offsets-ped_width/2<center-length/2-1e-9) or np.any(self.offsets+ped_width/2>center+length/2+1e-9)):
            raise ValueError('Pedestal extends beyond the cap.')
        if np.any(self.offsets[:-1]+ped_width[:-1]/2>self.offsets[1:]-ped_width[1:]/2+1e-9):raise ValueError('Pedestals overlap.')
        rows=[]
        for face,span in enumerate([j,j+1]):
            at=self.evaluate([station],span)
            for b in range(self.count):
                bottom=at['bottom'][0,b]
                rows.append({'Span':self.spans.iloc[span]['id'],'Face':'End' if face==0 else 'Start','Beam':b+1,
                             'Offset (ft)':self.offsets[b],'Beam bottom (ft)':bottom,'Pad (in)':pads[face,b],
                             'Pedestal top (ft)':bottom-pads[face,b]/12,'Width (in)':ped_width[b]*12})
        seats=pd.DataFrame(rows);top=p['top_center_ft'];reveal=p['minimum_pedestal_cl_in']
        if top is not None and reveal is not None:raise ValueError('Choose fixed cap top OR pedestal-height placement.')
        if reveal is not None:
            reveal=finite(reveal,'Pedestal height')
            if reveal<0:raise ValueError('Pedestal height cannot be negative.')
        if top is not None:top=finite(top,'Cap top elevation')
        elif reveal is not None and np.all(np.isfinite(pads)):
            top=float(np.min(seats['Pedestal top (ft)']-slope*(seats['Offset (ft)']-center))-reveal/12)
        else:missing.append('Cap-top elevation or minimum pedestal height')
        seats['Pedestal height (in)']=(seats['Pedestal top (ft)']-(np.nan if top is None else top+slope*(seats['Offset (ft)']-center)))*12
        if top is not None and np.all(np.isfinite(pads)):
            edge_top=top+slope*(self.offsets-center)+abs(slope)*ped_width/2
            if np.any(seats['Pedestal top (ft)'].to_numpy().reshape(2,-1)<edge_top-1e-9):raise ValueError('Cap intersects a pedestal top at its edge.')
        corners=[]
        for label,side,bottom in [('TL',-1,False),('TR',1,False),('BR',1,True),('BL',-1,True)]:
            x=np.nan if length is None else center+side*length/2
            z=np.nan if top is None or (slope!=0 and not np.isfinite(x)) else top+(slope*(x-center) if slope else 0)
            if bottom:z=np.nan if depth is None else z-depth
            corners.append({'Corner':label,'Offset (ft)':x,'Elevation (ft)':z})
        return dict(station=station,missing=missing,seats=seats,corners=pd.DataFrame(corners),top=top,
                    pedestal_width=ped_width,pad_width=pad_width,center=center,slope=slope,length=length,depth=depth,
                    width=width,pile_layout=pile_layout,pile_basis=pile_basis,
                    volume_ft3=None if None in [width,length,depth] else width*length*depth)

    def selected_table(self, station):
        e=self.evaluate([station]);rows=[]
        for b in range(self.count):
            rows.append({'Beam':b+1,'Offset (ft)':self.offsets[b],'Deck CL (ft)':e['deck'][0,b,1],
                         'Beam top (ft)':e['top'][0,b],'Beam bottom (ft)':e['bottom'][0,b],
                         'Camber (in)':e['camber'][0]*12,'Haunch L (in)':e['haunch'][0,b,0]*12,
                         'Haunch CL (in)':e['haunch'][0,b,1]*12,'Haunch R (in)':e['haunch'][0,b,2]*12,
                         'Clearance (ft)':e['clearance'][0,b]})
        return pd.DataFrame(rows)

    def summary(self):
        clear_status=('Fail' if np.isfinite(self.clearance_min) and self.clearance_min<self.clearance_required-1e-8 else
                      'Pass' if self.full_road_coverage else 'Not evaluated')
        return pd.DataFrame([
            {'Check':'Minimum haunch','Value':f'{self.haunch_min*12:.3f} in','Status':'Pass' if self.haunch_min>=self.minimum_haunch-1e-8 else 'Fail',
             'Location / basis':f'Beam {self.haunch_beam}, {station_label(self.haunch_station)}'},
            {'Check':'Vertical clearance','Value':f'{self.clearance_min:.3f} ft (covered region)' if np.isfinite(self.clearance_min) else 'Unavailable',
             'Status':clear_status,'Location / basis':f'Beam {self.clearance_beam}, {station_label(self.clearance_station)}' if np.isfinite(self.clearance_station) else self.road_note},
            {'Check':'Roadway coverage','Value':f'{self.covered_length:.3f} / {self.end-self.start:.3f} ft',
             'Status':'Pass' if self.full_road_coverage else 'Not evaluated','Location / basis':'No extrapolation or substitute elevation'},
            {'Check':'Haunch quantity','Value':f"{self.quantity_table['Volume (yd3)'].sum():.4f} yd3",'Status':'Calculated','Location / basis':'All spans and beams; flange-width integration'},
            {'Check':'Pier geometry','Value':'Complete' if not self.pier['missing'] else 'Missing inputs','Status':'Pass' if not self.pier['missing'] else 'Not evaluated',
             'Location / basis':'; '.join(self.pier['missing']) or 'Geometric fit only; not a structural capacity check'},
        ])
