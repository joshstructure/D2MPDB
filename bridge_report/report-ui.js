const root=document.getElementById('bridge-station-report');
const $=id=>root.querySelector('#'+id);
let engine;
try{engine=makeBridgeReportEngine(DATA);}catch(error){root.textContent=error.message;throw error;}
const {evaluate,parseStation,stationLabel}=engine;
const inspectionStart=DATA.inspection_start??DATA.start,inspectionEnd=DATA.inspection_end??DATA.end;
const format=(x,digits=3)=>x===null||!Number.isFinite(x)?'Not available':x.toFixed(digits);
const colors={Deck:'var(--viz-series-1)',Beam:'var(--viz-series-2)',Haunch:'var(--viz-series-3)',
  Cap:'var(--viz-series-4)',Pile:'var(--viz-series-5)',Pedestal:'var(--viz-series-4)',Bearing:'var(--foreground)'};
const slider=$('bridge-station-slider'),entry=$('bridge-station-entry'),jump=$('bridge-station-jump');
const tooltip=$('bridge-hover');tooltip.classList.add('bridge-tooltip');
let selected=DATA.initial_station??DATA.supports.find(s=>s.name==='Pier')?.station??DATA.start;
let hiddenSeries=new Set(),hiddenKinds=new Set(),elevationChart=null,sectionChart=null,dragging=false;
let current=evaluate(selected);
const jumps=[...DATA.supports.map(s=>({name:s.name+' cap center',station:s.station})),
  ...(DATA.physical?DATA.bearing_limits.flatMap((b,i)=>b.map((station,j)=>({name:`Span ${i+1} ${j?'end':'start'} bearing`,station}))):[]),
  ...DATA.spans.map(s=>({name:`Span ${s.id} midpoint`,station:(s.start_ft+s.end_ft)/2})),
  ...(DATA.minimum_clearance.available?[{name:'Minimum clearance',station:DATA.minimum_clearance.station}]:[])];
jumps.sort((a,b)=>a.station-b.station);
jump.innerHTML='<option value="custom">Custom station</option>'+jumps.map((j,i)=>`<option value="${i}">${j.name} · ${stationLabel(j.station)}</option>`).join('');
slider.min=inspectionStart;slider.max=inspectionEnd;
$('bridge-range-start').textContent=stationLabel(inspectionStart);
$('bridge-range-end').textContent=stationLabel(inspectionEnd);
$('bridge-source-label').textContent=`${DATA.source} · model ${DATA.model_id} · ${DATA.profile} profile / ${DATA.deck_mode} deck${DATA.geometry_source?.source_file?` · Base geometry: ${DATA.geometry_source.source_file.split('/').at(-1)}`:''}`;
const savedState=state=>{
  const saved=state?.modelContent;
  if(saved?.modelId!==DATA.model_id)return;
  if(Number.isFinite(saved.station)&&saved.station>=inspectionStart&&saved.station<=inspectionEnd)selected=saved.station;
  hiddenSeries=new Set(state?.privateContent?.hiddenSeries||[]);
  hiddenKinds=new Set(state?.privateContent?.hiddenKinds||[]);
};
savedState(window.openai?.widgetState);
function saveState(){
  const state={modelContent:{modelId:DATA.model_id,station:selected,stationLabel:stationLabel(selected),
    span:current.span,clearance_ft:current.clearance},
    privateContent:{hiddenSeries:[...hiddenSeries],hiddenKinds:[...hiddenKinds]}};
  window.openai?.setWidgetState?.(state)?.catch(()=>{});
}
function makeChart(id,height,xExtent,yExtent,equal=false){
  const host=$(id),width=Math.max(260,host.getBoundingClientRect().width);
  const margin={left:64,right:16,top:22,bottom:52};
  const innerWidth=width-margin.left-margin.right;
  let xd=[...xExtent],yd=[...yExtent];
  const xp=Math.max((xd[1]-xd[0])*.035,.1),yp=Math.max((yd[1]-yd[0])*.1,.08);
  xd=[xd[0]-xp,xd[1]+xp];yd=[yd[0]-yp,yd[1]+yp];
  if(equal){
    height=Math.max(240,Math.min(350,innerWidth*(yd[1]-yd[0])/(xd[1]-xd[0])+margin.top+margin.bottom));
    const wantedRatio=(innerWidth-6)/(height-margin.top-margin.bottom-6),ratio=(xd[1]-xd[0])/(yd[1]-yd[0]);
    if(ratio>wantedRatio){const c=(yd[1]+yd[0])/2,h=(xd[1]-xd[0])/wantedRatio/2;yd=[c-h,c+h];}
    else{const c=(xd[1]+xd[0])/2,h=(yd[1]-yd[0])*wantedRatio/2;xd=[c-h,c+h];}
  }
  const svg=d3.select(host).selectAll('svg').data([0]).join('svg').attr('class','bridge-chart').attr('role','img')
    .attr('viewBox',`0 0 ${width} ${height}`).attr('height',height);
  const x=d3.scaleLinear().domain(xd).range([margin.left+3,width-margin.right-3]);
  const y=d3.scaleLinear().domain(yd).range([height-margin.bottom-3,margin.top+3]);
  const frame={left:margin.left,top:margin.top,right:width-margin.right,bottom:height-margin.bottom};
  svg.selectAll('rect[data-chart-frame]').data([0]).join('rect').attr('data-chart-frame','')
    .attr('x',frame.left).attr('y',frame.top).attr('width',frame.right-frame.left).attr('height',frame.bottom-frame.top);
  const clipId=id+'-clip';
  const defs=svg.selectAll('defs').data([0]).join('defs');
  defs.selectAll('clipPath').data([0]).join('clipPath').attr('id',clipId).selectAll('rect').data([0]).join('rect')
    .attr('x',frame.left).attr('y',frame.top).attr('width',frame.right-frame.left).attr('height',frame.bottom-frame.top);
  const axisX=svg.selectAll('g.axis-x').data([0]).join('g').attr('class','axis-x').attr('transform',`translate(0,${frame.bottom})`);
  const axisY=svg.selectAll('g.axis-y').data([0]).join('g').attr('class','axis-y').attr('transform',`translate(${frame.left},0)`);
  axisX.call(d3.axisBottom(x).ticks(width<400?3:width<600?4:6).tickSizeOuter(0).tickFormat(equal?d3.format('~g'):v=>stationLabel(v,0)));
  axisY.call(d3.axisLeft(y).ticks(5).tickSizeOuter(0));
  svg.selectAll('text.axis-title[data-axis="x"]').data([0]).join('text').attr('class','axis-title').attr('data-axis','x')
    .attr('x',(frame.left+frame.right)/2).attr('y',height-7).attr('text-anchor','middle').text(equal?'Offset from PGL (ft)':'Bridge station (ft)');
  svg.selectAll('text.axis-title[data-axis="y"]').data([0]).join('text').attr('class','axis-title').attr('data-axis','y')
    .attr('transform',`translate(15,${(frame.top+frame.bottom)/2}) rotate(-90)`).attr('text-anchor','middle').text('Elevation (ft)');
  const grid=svg.selectAll('g.chart-grid').data([0]).join('g').attr('class','chart-grid');
  grid.selectAll('line').data(y.ticks(5)).join('line').attr('x1',frame.left).attr('x2',frame.right)
    .attr('y1',d=>y(d)).attr('y2',d=>y(d)).attr('stroke','var(--border)').attr('stroke-opacity',.5);
  const plot=svg.selectAll('g.chart-data').data([0]).join('g').attr('class','chart-data').attr('clip-path',`url(#${clipId})`);
  const labels=svg.selectAll('g.chart-labels').data([0]).join('g').attr('class','chart-labels');
  function checkLabels(){
    const labels=[...svg.node().querySelectorAll('.tick text,.axis-title,.value-label')].filter(n=>n.textContent);
    // Optional labels yield to axis labels; thin dense ticks at small widths.
    const kept=[];
    for(const n of labels){const b=n.getBoundingClientRect();
      const collision=kept.some(p=>b.left<p.right+4&&b.right+4>p.left&&b.top<p.bottom+4&&b.bottom+4>p.top);
      if(collision&&!n.classList.contains('axis-title')){n.style.visibility='hidden';continue;}
      n.style.visibility='visible';kept.push(b);
    }
  }
  return {svg,x,y,plot,labels,width,height,frame,checkLabels};
}
const stationSamples=[...new Set([...DATA.pieces.flatMap(p=>d3.range(65).map(i=>p.start+(p.end-p.start)*i/64)),
  ...DATA.road.flatMap(r=>[r.start,r.end,r.end+1e-6,r.start-1e-6]).filter(s=>s>=DATA.start&&s<=DATA.end)])].sort((a,b)=>a-b);
const observations=stationSamples.map(evaluate);
const groups=[];
DATA.offsets.forEach((offset,b)=>{
  const same=groups.find(g=>observations.every(e=>['bottom','top'].every(k=>Math.abs(e[k][g.beams[0]]-e[k][b])<1e-9)&&Math.abs(e.deck[g.beams[0]][1]-e.deck[b][1])<1e-9));
  if(same)same.beams.push(b);else groups.push({beams:[b]});
});
const lineSeries=[{id:'pgl',name:'PGL',color:'var(--foreground)',dash:'4 4',get:e=>e.pgl},
  ...groups.flatMap(g=>{
    const b=g.beams[0],name=g.beams.map(b=>`B${b+1}`).join('/');
    return [{id:`deck-${b}`,name:`Deck CL · ${name}`,color:colors.Deck,get:e=>e.deckPresent?e.deck[b][1]:null},
      {id:`top-${b}`,name:`Beam top · ${name}`,color:colors.Beam,get:e=>e.beamPresent?e.top[b]:null},
      {id:`bottom-${b}`,name:`Beam bottom · ${name}`,color:colors.Beam,dash:'2 3',get:e=>e.beamPresent?e.bottom[b]:null}];
  }),{id:'road',name:'Roadway',color:colors.Pile,get:e=>e.roadway},
  {id:'envelope',name:`${DATA.required_clearance}-ft clearance envelope`,color:colors.Haunch,dash:'7 4',get:e=>e.roadway===null?null:e.roadway+DATA.required_clearance}];
function makeLegend(id,items,hidden,onChange){
  const buttons=d3.select($(id)).selectAll('button').data(items,d=>d.id).join(enter=>{
    const b=enter.append('button').attr('type','button').attr('class','cursor-interaction');
    b.append('span').attr('class','bridge-swatch').attr('aria-hidden','true');b.append('span').attr('class','legend-label');return b;
  }).attr('aria-pressed',d=>String(!hidden.has(d.id))).attr('aria-label',d=>`Show ${d.name}`)
    .on('click',(_,d)=>{hidden.has(d.id)?hidden.delete(d.id):hidden.add(d.id);onChange();saveState();});
  buttons.select('.bridge-swatch').style('--series-color',d=>d.color);
  buttons.select('.legend-label').text(d=>d.name);
}
function drawElevation(){
  const visible=lineSeries.filter(s=>!hiddenSeries.has(s.id));
  const bounds=visible.flatMap(s=>observations.map(s.get)).filter(v=>v!==null&&Number.isFinite(v));
  bounds.push(...DATA.supports.flatMap(s=>[s.top,s.top-s.depth]));
  const xbounds=d3.extent([...stationSamples,...DATA.supports.flatMap(s=>[s.station-s.width/2,s.station+s.width/2])]);
  elevationChart=makeChart('bridge-elevation-chart',320,xbounds,d3.extent(bounds));
  const {svg,x,y,plot,labels,frame,width}=elevationChart;
  svg.attr('aria-label','Bridge longitudinal elevation. Drag in the plot to move the inspection station.');
  const line=s=>d3.line().defined(e=>s.get(e)!==null&&Number.isFinite(s.get(e))).x(e=>x(e.station)).y(e=>y(s.get(e)))(observations);
  plot.selectAll('path.elevation-line').data(visible,d=>d.id).join('path').attr('class','elevation-line')
    .attr('fill','none').attr('stroke',d=>d.color).attr('stroke-width',1.6).attr('stroke-dasharray',d=>d.dash||null).attr('d',line);
  plot.selectAll('rect.cap-projection').data(DATA.supports).join('rect').attr('class','cap-projection')
    .attr('x',s=>x(s.station-s.width/2)).attr('y',s=>y(s.top)).attr('width',s=>x(s.station+s.width/2)-x(s.station-s.width/2))
    .attr('height',s=>y(s.top-s.depth)-y(s.top)).attr('fill',colors.Cap).attr('fill-opacity',.25);
  plot.selectAll('line.support-line').data(DATA.supports).join('line').attr('class','support-line')
    .attr('x1',s=>x(s.station)).attr('x2',s=>x(s.station)).attr('y1',frame.top).attr('y2',frame.bottom)
    .attr('stroke','var(--border)').attr('stroke-width',1);
  labels.selectAll('text.support-label').data(DATA.supports).join('text').attr('class','support-label value-label')
    .attr('x',s=>x(s.station)).attr('y',frame.top-8).attr('text-anchor',(_,i)=>i===0?'start':i===DATA.supports.length-1?'end':'middle')
    .text(s=>width<420?s.name.replace('End Bent ','EB '):s.name);
  plot.selectAll('line.selected-guide').data([0]).join('line').attr('class','selected-guide')
    .attr('stroke','var(--viz-series-6)').attr('stroke-width',2).attr('y1',frame.top).attr('y2',frame.bottom);
  plot.selectAll('line.hover-guide').data([0]).join('line').attr('class','hover-guide').attr('data-chart-hover-guide','')
    .attr('stroke','var(--foreground)').attr('stroke-opacity',.5).attr('y1',frame.top).attr('y2',frame.bottom).style('display','none');
  const overlay=svg.selectAll('rect.hover-hit').data([0]).join('rect').attr('class','hover-hit')
    .attr('data-chart-hit','').attr('data-chart-hover-overlay','cross-series').attr('fill','transparent')
    .attr('x',frame.left).attr('y',frame.top).attr('width',frame.right-frame.left).attr('height',frame.bottom-frame.top)
    .style('touch-action','pan-y').style('cursor','crosshair');
  const stationAt=event=>Math.max(inspectionStart,Math.min(inspectionEnd,x.invert(d3.pointer(event,svg.node())[0])));
  overlay.on('pointermove',event=>{const station=stationAt(event);if(dragging)setStation(Math.round(station*100)/100,false);showHover(event,station);})
    .on('pointerleave',()=>{if(!dragging)hideHover();})
    .on('pointerdown',event=>{dragging=true;event.currentTarget.setPointerCapture(event.pointerId);setStation(Math.round(stationAt(event)*100)/100,false);showHover(event,selected);})
    .on('pointerup pointercancel',event=>{dragging=false;if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);saveState();});
  drawSelected();elevationChart.checkLabels();
  makeLegend('bridge-line-legend',lineSeries,hiddenSeries,drawElevation);
}
function hideHover(){tooltip.hidden=true;elevationChart?.plot.select('.hover-guide').style('display','none');elevationChart?.plot.selectAll('[data-chart-hover-marker]').remove();}
function showHover(event,station){
  const {svg,x,y,plot}=elevationChart,e=evaluate(station),visible=lineSeries.filter(s=>!hiddenSeries.has(s.id));
  plot.select('.hover-guide').style('display',null).attr('x1',x(station)).attr('x2',x(station));
  plot.selectAll('circle[data-chart-hover-marker]').data(visible.filter(s=>s.get(e)!==null),d=>d.id).join('circle')
    .attr('data-chart-hover-marker','').attr('r',3).attr('cx',x(station)).attr('cy',s=>y(s.get(e))).attr('fill',s=>s.color);
  tooltip.innerHTML=`<strong>Sta. ${stationLabel(station)}</strong>`+visible.map(s=>`<div><span>${s.name}</span><span class="tabular-nums">${format(s.get(e))}${s.get(e)===null?'':' ft'}</span></div>`).join('');
  tooltip.hidden=false;
  const bounds=root.getBoundingClientRect(),tb=tooltip.getBoundingClientRect();
  tooltip.style.left=Math.max(0,Math.min(bounds.width-tb.width,event.clientX-bounds.left+14))+'px';
  tooltip.style.top=Math.max(0,event.clientY-bounds.top-tb.height-12)+'px';
}
function drawSelected(){
  if(!elevationChart)return;
  const {x,plot}=elevationChart;
  plot.select('.selected-guide').interrupt().attr('x1',x(selected)).attr('x2',x(selected));
}
function drawSection(){
  const allPoints=current.components.flatMap(c=>c.xy);
  if(!allPoints.length)allPoints.push([-DATA.deck_width/2,0],[DATA.deck_width/2,DATA.depth]);
  sectionChart=makeChart('bridge-section-chart',320,d3.extent(allPoints,p=>p[0]),d3.extent(allPoints,p=>p[1]),true);
  const {svg,x,y,plot,labels,frame}=sectionChart;
  svg.attr('aria-label',`Cross-section at station ${stationLabel(selected)}, ${current.support?.name||`span ${current.span}`}. Physical station cut.`);
  const components=current.components.filter(c=>!hiddenKinds.has(c.kind));
  const shape=d3.line().x(p=>x(p[0])).y(p=>y(p[1]));
  const paths=plot.selectAll('path.component').data(components,(c,i)=>c.id||`${c.kind}-${c.beam}-${i}`).join('path')
    .attr('class','component').attr('fill',c=>colors[c.kind]).attr('fill-opacity',c=>c.kind==='Bearing'?.65:.28)
    .attr('stroke',c=>colors[c.kind]).attr('stroke-width',1)
    .attr('data-tooltip',c=>`${c.kind}${c.beam?` · beam ${c.beam}`:''} · EL ${format(d3.min(c.xy,p=>p[1]))}–${format(d3.max(c.xy,p=>p[1]))} ft`);
  // A station cut changes topology at solid boundaries; never morph between them.
  paths.interrupt().attr('d',c=>shape(c.xy)+'Z');
  plot.selectAll('line.center-line').data([0]).join('line').attr('class','center-line').attr('x1',x(0)).attr('x2',x(0))
    .attr('y1',frame.top).attr('y2',frame.bottom).attr('stroke','var(--border)').attr('stroke-width',1);
  labels.selectAll('text.beam-label').data(current.beamPresent?DATA.offsets:[]).join('text').attr('class','beam-label value-label')
    .attr('x',d=>x(d)).attr('y',(_,i)=>y(current.deck[i][1]) - 10).attr('text-anchor','middle').text((_,i)=>`B${i+1}`);
  const pileCuts=components.filter(c=>c.kind==='Pile');
  const piles=(current.support?.piles||[]).filter(p=>!DATA.physical||pileCuts.some(c=>c.pile===p.Pile));
  plot.selectAll('line.pile-cutoff').data(pileCuts).join('line').attr('class','pile-cutoff')
    .attr('x1',p=>x(d3.min(p.xy,v=>v[0]))).attr('x2',p=>x(d3.max(p.xy,v=>v[0])))
    .attr('y1',p=>y(d3.max(p.xy,v=>v[1]))).attr('y2',p=>y(d3.max(p.xy,v=>v[1]))).attr('stroke',colors.Pile).attr('stroke-width',2.5);
  labels.selectAll('text.pile-label').data(piles).join('text').attr('class','pile-label value-label')
    .attr('x',p=>x(p['Offset (ft)'])).attr('y',p=>y(p['Cap underside (ft)']-1.25)).attr('text-anchor','middle').text(p=>`P${p.Pile}`);
  $('bridge-section-heading').textContent=`Cross-section · ${current.support?.name||`span ${current.span}`} · ${stationLabel(selected)}`;
  $('bridge-section-note').textContent=DATA.physical
    ?`Source geometry · FIB36 fillets tessellated${current.support?` · ${(selected-current.support.station).toFixed(3)} ft from cap center · pile heads cropped; tips remain trial values`:''}${!current.beamPresent?' · no beam intersects this station':''} · provisional walls omitted`
    :'Approximate FIB36 outline · pile heads only; final tips undefined';
  makeLegend('bridge-component-legend',[...new Set(current.components.map(c=>c.kind))].map(kind=>({id:kind,name:kind,color:colors[kind]})),hiddenKinds,drawSection);
  sectionChart.checkLabels();
}
function updateReadouts(){
  slider.value=selected;slider.setAttribute('aria-valuetext',stationLabel(selected));
  entry.value=stationLabel(selected,Math.abs(selected*100-Math.round(selected*100))<1e-7?2:5);
  $('bridge-station-label').textContent=`Sta. ${stationLabel(selected)}`;
  const index=jumps.findIndex(j=>Math.abs(j.station-selected)<1e-7);jump.value=index<0?'custom':String(index);
  const clearance=current.clearance.filter(v=>v!==null);
  const hmin=Math.min(...current.haunch.flat())*12;
  $('bridge-station-summary').textContent=`${current.support?.name||`Span ${current.span}`} · ${current.beamPresent?`minimum flange haunch ${format(hmin)} in · ${clearance.length?`clearance ${format(Math.min(...clearance))} ft`:'roadway / clearance unavailable'}`:'No beam at this station'}`;
  const rows=[['Offset from PGL (ft)',DATA.offsets],['Deck at beam CL (ft)',current.deck.map(v=>v[1])],
    ['Beam top (ft)',current.top],['Beam bottom (ft)',current.bottom],['Camber (in)',DATA.offsets.map(()=>current.camber*12)],
    ['Haunch left (in)',current.haunch.map(h=>h[0]*12)],
    ['Haunch CL (in)',current.haunch.map(h=>h[1]*12)],
    ['Haunch right (in)',current.haunch.map(h=>h[2]*12)],
    ['Vertical clearance (ft)',current.clearance]];
  rows.forEach((row,i)=>{if((i===1&&!current.deckPresent)||(i>=2&&!current.beamPresent))row[1]=DATA.offsets.map(()=>null);});
  const table=$('bridge-beam-results').closest('table');
  table.querySelector('thead').innerHTML='<tr><th>Result</th>'+DATA.offsets.map((_,i)=>`<th class="text-end">Beam ${i+1}</th>`).join('')+'</tr>';
  $('bridge-beam-results').innerHTML=rows.map(([label,values])=>`<tr><th scope="row">${label}</th>${values.map(v=>`<td class="text-end">${typeof v==='string'?v:format(v)}</td>`).join('')}</tr>`).join('');
  const p=current.support;
  const nearest=p||DATA.supports.filter(s=>s.solid_geometry).reduce((a,b)=>!a||Math.abs(b.station-selected)<Math.abs(a.station-selected)?b:a,null);
  $('bridge-support-extent').textContent=nearest
    ?`${p?'Cut intersects':'No substructure at this station. Nearest support:'} ${nearest.name} · cap limits ${stationLabel(nearest.solid_geometry.cap_bounds[0])}–${stationLabel(nearest.solid_geometry.cap_bounds[1])}`:'';
  const visiblePiles=(p?.piles||[]).filter(v=>!DATA.physical||current.components.some(c=>c.kind==='Pile'&&c.pile===v.Pile));
  $('bridge-support-results').textContent=p?`Cap center top ${format(p.top,4)} ft · cap center underside ${format(p.top-p.depth,4)} ft${visiblePiles.length?` · intersected pile cutoffs ${visiblePiles.map(v=>`P${v.Pile}: ${format(v['Pile cutoff (ft)'],4)} ft`).join(' / ')}`:' · no piles intersect this station'}`:'';
}
function setStation(station,persist=true){
  if(!Number.isFinite(station)||station<inspectionStart||station>inspectionEnd){
    $('bridge-station-error').hidden=false;
    $('bridge-station-error').textContent=`Enter a station from ${stationLabel(inspectionStart)} to ${stationLabel(inspectionEnd)}.`;
    entry.setAttribute('aria-invalid','true');return false;
  }
  selected=station;current=evaluate(station);$('bridge-station-error').hidden=true;entry.removeAttribute('aria-invalid');
  updateReadouts();drawSelected();drawSection();if(persist)saveState();return true;
}
slider.addEventListener('input',()=>{dragging=true;setStation(Number(slider.value),false);dragging=false;});
slider.addEventListener('change',saveState);
$('bridge-step-back').addEventListener('click',()=>setStation(Math.max(inspectionStart,Math.round((selected-.01)*1e8)/1e8)));
$('bridge-step-forward').addEventListener('click',()=>setStation(Math.min(inspectionEnd,Math.round((selected+.01)*1e8)/1e8)));
entry.addEventListener('change',()=>setStation(parseStation(entry.value)));
entry.addEventListener('keydown',event=>{if(event.key==='Enter')setStation(parseStation(entry.value));});
jump.addEventListener('change',()=>{if(jump.value!=='custom')setStation(jumps[Number(jump.value)].station);});
window.addEventListener('openai:set_globals',event=>{if(event.detail?.globals?.widgetState){savedState(event.detail.globals.widgetState);drawElevation();setStation(selected,false);}});
let lastWidth=0;
new ResizeObserver(entries=>{const width=entries[0].contentRect.width;if(Math.abs(width-lastWidth)<1)return;lastWidth=width;drawElevation();drawSection();}).observe(root);
current=evaluate(selected);drawElevation();setStation(selected,false);
