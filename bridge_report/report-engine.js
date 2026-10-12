function makeBridgeReportEngine(data) {
  if(data.version!==2||!data.physical||data.geometry_version!=='physical-station-cuts-2')
    throw new Error('This report needs physical support geometry. Reopen the updated notebook, Run all, and export a new report.');
  const within=(s,b)=>s>=b[0]-1e-9&&s<=b[1]+1e-9;
  function sliceSupport(support,station){
    const solid=support.solid_geometry;
    if(!solid||!within(station,solid.cap_bounds))return [];
    const components=[],notches=[];
    const add=(kind,id,xy,beam=null,extra={})=>components.push({kind,id,xy,beam,...extra});
    const capTop=y=>support.top+support.slope*(y-support.center);
    for(const pile of solid.piles){
      const dx=station-pile.station,r=pile.diameter/2;
      if(pile.shape==='square'?Math.abs(dx)>r+1e-9:Math.abs(dx)>=r-1e-9)continue;
      const outer=pile.shape==='square'?r:Math.sqrt(Math.max(0,r*r-dx*dx));
      const ri=pile.shape==='pipe'?Math.max(0,r-pile.wall):0;
      const inner=Math.abs(dx)<ri?Math.sqrt(Math.max(0,ri*ri-dx*dx)):0;
      const l=pile.offset-outer,h=pile.offset+outer,z=pile.cutoff,bottom=Math.max(pile.bottom,pile.cap_underside-1.8);
      const intervals=inner>1e-9?[[l,pile.offset-inner],[pile.offset+inner,h]]:[[l,h]];
      intervals.forEach(([a,b],side)=>add('Pile',`${support.name}-pile-${pile.number}-${side}`,[[a,bottom],[b,bottom],[b,z],[a,z]],null,{pile:pile.number,cutoff:z}));
      notches.push([l,h,z]);
    }
    const left=support.center-support.length/2,right=left+support.length;
    const cap=[[left,capTop(left)],[right,capTop(right)],[right,capTop(right)-support.depth]];
    for(const [a0,b0,z] of notches.sort((a,b)=>a[0]-b[0]).reverse()){
      const a=Math.max(a0,left),b=Math.min(b0,right);
      if(a>=b||z<=Math.min(capTop(a),capTop(b))-support.depth)continue;
      cap.push([b,capTop(b)-support.depth],[b,Math.min(z,capTop(b))],[a,Math.min(z,capTop(a))],[a,capTop(a)-support.depth]);
    }
    cap.push([left,capTop(left)-support.depth]);
    components.unshift({kind:'Cap',id:support.name+'-cap',beam:null,xy:cap});
    for(const ped of solid.pedestals){
      if(!within(station,ped.bounds))continue;
      const i=Math.max(0,Math.min(ped.stations.length-2,ped.stations.findIndex((x,j)=>j>0&&station<=x)-1));
      let z;
      if(station<=ped.stations[0])z=ped.tops[0];else if(station>=ped.stations.at(-1))z=ped.tops.at(-1);
      else{const t=(station-ped.stations[i])/(ped.stations[i+1]-ped.stations[i]);z=ped.tops[i]+t*(ped.tops[i+1]-ped.tops[i]);}
      const a=ped.offset-ped.width/2,b=ped.offset+ped.width/2,c=ped.chamfer;
      add('Pedestal',ped.id,[[a,capTop(a)],[b,capTop(b)],[b,z-c],[b-c,z],[a+c,z],[a,z-c]],ped.beam,{top:z});
    }
    for(const pad of solid.bearings){
      if(!within(station,pad.bounds))continue;
      const z=pad.top+pad.slope*(station-pad.station),a=pad.offset-pad.width/2,b=pad.offset+pad.width/2;
      add('Bearing',pad.id,[[a,z-pad.thickness],[b,z-pad.thickness],[b,z],[a,z]],pad.beam,{span:pad.span,top:z});
    }
    return components;
  }
  const polynomial = (c, t) => {
    const evalNested = (a, b, q) => Array.isArray(a)
      ? a.map((v, i) => evalNested(v, b[i], q[i])) : a + t * b + t * t * q;
    return evalNested(c[0], c[1], c[2]);
  };
  function evaluate(station) {
    if (!Number.isFinite(station) || station < (data.inspection_start??data.start) || station > (data.inspection_end??data.end))
      throw new Error('Station is outside the bridge.');
    const s=Math.max(data.start,Math.min(data.end,station));
    const piece = data.pieces.find(p => s >= p.start && s < p.end) || data.pieces.at(-1);
    const t = (s-piece.start)/(piece.end-piece.start);
    const value = Object.fromEntries(Object.entries(piece.fields).map(([k,c]) => [k,polynomial(c,t)]));
    const road = data.road.filter(r => station >= r.start-1e-9 && station <= r.end+1e-9).at(-1);
    const dx = road ? station-road.start : 0;
    value.roadway = road ? road.z+road.g*dx+road.q*dx*dx : null;
    const beamPresent=!data.physical||data.beam_limits.some(b=>within(station,b));
    const deckPresent=!data.physical||data.deck_limits.some(b=>within(station,b));
    value.clearance = value.bottom.map(bottom => road&&beamPresent ? bottom-value.roadway : null);
    const support = data.supports.find(p => p.solid_geometry&&within(station,p.solid_geometry.cap_bounds)) || null;
    let components=piece.components.map((c,i) => ({kind:c.kind,id:`${c.kind}-${c.beam??i}`,beam:c.beam,
      xy:polynomial(c.y,t).map((y,j) => [c.x[j],y])}));
    if(data.physical){
      components=components.filter(c=>c.kind==='Deck'?deckPresent:beamPresent);
      if(beamPresent)data.offsets.forEach((x,b)=>components.push({kind:'Beam',id:`beam-${b+1}`,beam:b+1,
        xy:data.beam_outline.map(([y,z])=>[y+x,z+value.bottom[b]])}));
      if(support)components.push(...sliceSupport(support,station));
    }else if(support)components=support.components;
    if(station<data.start||station>data.end)value.pgl=null;
    return {...value, station, span:piece.span, support, components,beamPresent,deckPresent};
  }
  function parseStation(raw) {
    const value=String(raw).trim();
    if (/^\d+\+\d{1,2}(?:\.\d+)?$/.test(value)) {
      const [hundreds, feet]=value.split('+').map(Number);
      if (feet>=100) return NaN;
      return 100*hundreds+feet;
    }
    return /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(value) ? Number(value) : NaN;
  }
  function stationLabel(value, digits=2) {
    const factor=10**digits;
    const rounded=Math.round(value*factor)/factor;
    const hundreds=Math.floor(rounded/100);
    return `${hundreds}+${(rounded-hundreds*100).toFixed(digits).padStart(digits?3+digits:2,'0')}`;
  }
  return {evaluate,parseStation,stationLabel};
}
if (typeof module !== 'undefined' && module.exports) module.exports={makeBridgeReportEngine};
