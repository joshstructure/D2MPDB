/* Read-only browser atlas. Project text is rendered as text, never executable HTML. */
(() => {
  'use strict';
  const data = window.ATLAS_DATA;
  if (!data || data.schema_version !== 1) throw new Error('Unsupported atlas snapshot');
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const byId = new Map(data.nodes.map(n => [n.id,n]));
  const valueById = new Map(data.values.map(v => [v.id,v]));
  const state = { selected:null, value:'inputs.Vu_G', direction:'both', dependencies:false, allValues:false, parameterFocus:false, overview:true, traceCollapsed:true, origin:'all', scale:.7,x:0,y:0, edge:null, depth:0 };
  const params = new URLSearchParams(location.hash.slice(1));
  if (byId.has(params.get('source'))) {state.selected=params.get('source');state.overview=false;state.traceCollapsed=false;}
  if (valueById.has(params.get('value'))) {state.value=params.get('value');state.parameterFocus=params.get('trace')==='value';}
  let directoryOpen = false;
  let oldWidth=0;
  const prettyStatus = {match:'Fingerprint match',changed:'Revision changed',missing:'Source missing',unmapped:'Unmapped',recorded:'Recorded',mismatch:'Conflict',declared:'Registered',context:'Context only',error:'Read error',review:'Review'};
  const badge = (status,label) => `<span class="status ${escape(status)}">${escape(label || prettyStatus[status] || status)}</span>`;
  function format(value) {
    if (value===null || value===undefined) return 'Not available';
    if (typeof value==='boolean') return value ? 'Yes' : 'No';
    if (typeof value==='number') return Number.isInteger(value) ? String(value) : value.toLocaleString('en-US',{maximumFractionDigits:8});
    if (Array.isArray(value)) return value.map(format).join(', ');
    if (typeof value==='object') return 'Structured source record';
    return String(value);
  }
  function unitText(unit) { return unit==='unitless'?'':(unit||'').replace('kip*ft','kip·ft'); }
  const roleNames={received:'Received input',defined:'Local setting',derived:'Derived / formula',unknown:'Origin unconfirmed'};
  const originOf=v=>v.origins[state.selected]||v.origins[v.node_ids.includes('PIER-CASE')?'PIER-CASE':v.node_ids[0]];
  const originNode=v=>v.origins[state.selected]?state.selected:v.node_ids.includes('PIER-CASE')?'PIER-CASE':v.node_ids[0];
  function snapshot() {return {...state, query:$('value-search').value,category:$('value-category').value,scroll:window.scrollY,tableScroll:document.querySelector('.value-table-wrap').scrollTop,detailScroll:$('value-detail').scrollTop};}
  function saveSelection(push=false) {
    const hash=new URLSearchParams(state.selected?{source:state.selected,value:state.value,trace:state.parameterFocus?'value':'node'}:{view:'all'});
    history[push?'pushState':'replaceState']({atlas:snapshot()},'','#'+hash.toString());
    $('nav-back').disabled=state.depth===0;
    $('breadcrumbs').textContent=(byId.get(state.selected)?.title||'All sources')+(state.parameterFocus?' › '+valueById.get(state.value).label:'');
  }
  function navigate(change) {saveSelection();state.depth++;change();saveSelection(true);}
  function resetFilters() {state.origin='all';state.allValues=false;$('value-search').value='';$('value-category').value='';}
  function renderTraceSidebar() {
    document.querySelector('.workspace').classList.toggle('trace-collapsed',state.traceCollapsed);
    $('trace-content').hidden=state.traceCollapsed;$('trace-expand').hidden=!state.traceCollapsed;
    $('trace-collapse').setAttribute('aria-expanded',String(!state.traceCollapsed));
    $('trace-expand').setAttribute('aria-expanded',String(!state.traceCollapsed));
    // A sidebar toggle reveals more canvas without resetting its zoom or pan.
    oldWidth=$('map-canvas').clientWidth;
    if(!state.traceCollapsed)drawTraceFlow();
  }
  function keepSelectedVisible() {
    if(!state.selected)return;
    const box=$('map-canvas').getBoundingClientRect(),p=positions[state.selected],margin=16;
    const left=p[0]*state.scale+state.x,top=p[1]*state.scale+state.y;
    state.x+=Math.max(margin-left,Math.min(0,box.width-margin-left-210*state.scale));
    state.y+=Math.max(margin-top,Math.min(0,box.height-margin-top-86*state.scale));
    applyTransform();
  }
  function toggleTrace(collapsed) {
    state.traceCollapsed=collapsed;renderTraceSidebar();
    if(!collapsed)keepSelectedVisible();
    $(collapsed?'trace-expand':'trace-collapse').focus({preventScroll:true});
    saveSelection();announce(collapsed?'Trace collapsed. More space for the map.':'Trace expanded.');
  }
  $('trace-collapse').onclick=()=>toggleTrace(true);$('trace-expand').onclick=()=>toggleTrace(false);
  function renderSelection() {renderTraceSidebar();paintGraph();renderTrace();renderValues();}
  function scrollToValues() {$('values-panel').scrollIntoView({block:'start'});$('values-title').focus({preventScroll:true});}
  window.addEventListener('popstate',event=>{
    if(!event.state?.atlas)return;
    document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());
    const saved=event.state.atlas;Object.assign(state,saved);
    $('value-search').value=saved.query||'';$('value-category').value=saved.category||'';
    $('include-dependencies').checked=state.dependencies;
    document.querySelectorAll('[data-direction]').forEach(b=>{b.classList.toggle('active',b.dataset.direction===state.direction);b.setAttribute('aria-pressed',String(b.dataset.direction===state.direction));});
    renderSelection();applyTransform();saveSelection();
    document.querySelector('.value-table-wrap').scrollTop=saved.tableScroll||0;$('value-detail').scrollTop=saved.detailScroll||0;
    window.scrollTo(0,saved.scroll||0);
  });
  $('nav-back').onclick=()=>history.back();
  function clearSelection(fitMap=false) {navigate(()=>{resetFilters();state.selected=null;state.parameterFocus=false;state.overview=true;state.traceCollapsed=true;state.direction='both';state.dependencies=false;state.edge=null;$('include-dependencies').checked=false;directoryOpen=false;$('source-search').value='';renderDirectory();renderSelection();if(fitMap)fit(data.nodes.map(n=>n.id));announce('Selection cleared. All sources are visible.');});}
  function overview() {clearSelection(true);window.scrollTo(0,0);}
  $('nav-overview').onclick=overview;
  $('help-button').onclick=()=>{$('quick-help').open=!$('quick-help').open;if($('quick-help').open)$('quick-help').scrollIntoView({block:'start'});};
  function announce(text) { $('announcement').textContent=text; }

  // Every source uses the same stage columns and alphabetical row order.
  // Selecting a trail changes emphasis, never the node positions.
  const positions={};
  const stages=['Basis','Analysis','Design','Detailing','Deliverables'];
  stages.forEach((stage,col)=>data.nodes.filter(n=>n.stage===stage)
    .sort((a,b)=>a.title.localeCompare(b.title,undefined,{numeric:true})||a.id.localeCompare(b.id))
    .forEach((n,row)=>{positions[n.id]=[35+col*270,75+row*135];}));
  const width=35+(stages.length-1)*270+245;
  const bottom=Math.max(...Object.values(positions).map(p=>p[1]))+130;
  $('map-world').style.width=width+'px';
  $('map-world').style.height=bottom+'px';
  $('map-links').setAttribute('width',width);
  $('map-links').style.width=width+'px';
  $('map-links').setAttribute('height',bottom);
  $('map-links').style.height=bottom+'px';
  $('map-labels').innerHTML=stages.map((s,i)=>`<span class="map-group-label" style="left:${35+i*270}px;top:30px">${escape(s.toUpperCase())} · ${data.nodes.filter(n=>n.stage===s).length}</span>`).join('');
  const ns='http://www.w3.org/2000/svg';
  const svg=$('map-links');
  svg.innerHTML='<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/></marker></defs>';
  function edgePath(e,index) {
    const a=positions[e.source],b=positions[e.target];
    const ay=a[1]+43,by=b[1]+43,offset=14+(index%4)*6;
    // Route in the column gutters and row gaps so long edges do not cross cards.
    if (a[0]===b[0]) {
      const x=a[0]+210,rail=x+offset;
      return `M${x},${ay} H${rail} V${by} H${x}`;
    }
    const forward=b[0]>a[0],sign=forward?1:-1;
    const ax=a[0]+(forward?210:0),bx=b[0]+(forward?0:210),exit=ax+sign*offset,entry=bx-sign*offset;
    if(Math.abs(a[0]-b[0])===270){const rail=(exit+entry)/2;return `M${ax},${ay} H${rail} V${by} H${bx}`;}
    const corridor=a[1]+100+(index%3)*8;
    return `M${ax},${ay} H${exit} V${corridor} H${entry} V${by} H${bx}`;
  }
  const edgeElements=new Map();
  data.edges.forEach((e,i)=>{
    const path=document.createElementNS(ns,'path');
    path.setAttribute('d',edgePath(e,i));path.setAttribute('marker-end','url(#arrow)');path.dataset.edge=e.id;
    const hit=document.createElementNS(ns,'path');hit.setAttribute('d',edgePath(e,i));hit.setAttribute('class','edge-hit');
    hit.addEventListener('click',()=>selectEdge(e));
    const title=document.createElementNS(ns,'title');title.textContent=e.label+' · '+e.basis;hit.appendChild(title);
    svg.append(path,hit);edgeElements.set(e.id,path);
  });
  const nodeElements=new Map();
  data.nodes.forEach(n=>{
    const el=document.createElement('button');el.type='button';el.className='map-node';el.dataset.node=n.id;
    el.style.left=positions[n.id][0]+'px';el.style.top=positions[n.id][1]+'px';
    el.innerHTML=`<span class="node-id">${escape(n.id)}<i class="node-dot ${escape(n.status)}"></i></span><span class="node-name">${escape(n.short_title||n.title)}</span><span class="node-status">${escape(prettyStatus[n.status]||n.status)}${n.value_count?' · '+n.value_count+' values':''}</span>`;
    el.setAttribute('aria-label',n.title+', '+(prettyStatus[n.status]||n.status));
    el.addEventListener('click',()=>selectNode(n.id));
    $('map-nodes').appendChild(el);nodeElements.set(n.id,el);
  });
  function traversable(e) {
    if (e.kind==='context') return false;
    if (state.dependencies) return true;
    return e.kind==='flow' || (e.source==='PIER-XML' && ['PIER-CASE','PIER-REPORT'].includes(e.target));
  }
  function walk(direction) {
    const seen=new Set([state.selected]), queue=[state.selected];
    while(queue.length) {
      const id=queue.shift();
      data.edges.filter(traversable).forEach(e=>{
        const from=direction==='upstream'?e.target:e.source, to=direction==='upstream'?e.source:e.target;
        if(from===id && !seen.has(to)){seen.add(to);queue.push(to);}
      });
    }
    seen.delete(state.selected);return seen;
  }
  function traceSets() {
    if(!state.selected&&!state.parameterFocus)return {upstream:new Set(),downstream:new Set(),all:new Set()};
    if(state.parameterFocus) {const v=valueById.get(state.value);return {upstream:new Set(),downstream:new Set(),all:new Set([...v.node_ids,...(v.upstream_context?.node_ids||[])])};}
    const upstream=state.direction==='downstream'?new Set():walk('upstream');
    const downstream=state.direction==='upstream'?new Set():walk('downstream');
    return {upstream,downstream,all:new Set([state.selected,...upstream,...downstream])};
  }
  function paintGraph() {
    const trace=traceSets();
    nodeElements.forEach((el,id)=>{
      el.className='map-node'+(id===state.selected?' selected':state.overview?'':trace.all.has(id)?' related':' dimmed');
      el.setAttribute('aria-pressed',String(id===state.selected));
    });
    data.edges.forEach(e=>{
      const related=trace.all.has(e.source)&&trace.all.has(e.target)&&traversable(e);
      edgeElements.get(e.id).setAttribute('class','map-edge '+e.status+(related?' related':state.overview?'':' dimmed'));
    });
    $('map-selection-label').textContent=state.overview?'All '+data.nodes.length+' sources · select a node to isolate its trail':trace.all.size+' sources in this trace';
  }
  function applyTransform() {
    $('map-world').style.transform=`translate(${state.x}px,${state.y}px) scale(${state.scale})`;
    $('zoom-label').textContent=Math.round(state.scale*100)+'%';
  }
  function fit(ids) {
    const pts=ids.map(id=>positions[id]); if(!pts.length)return;
    const left=Math.min(...pts.map(p=>p[0]))-35,top=Math.min(...pts.map(p=>p[1]))-50;
    const right=Math.max(...pts.map(p=>p[0]))+245,bottom=Math.max(...pts.map(p=>p[1]))+135;
    const box=$('map-canvas').getBoundingClientRect();
    state.scale=Math.max(.2,Math.min(1.1,box.width/(right-left),box.height/(bottom-top)));
    state.x=(box.width-(right-left)*state.scale)/2-left*state.scale;
    state.y=(box.height-(bottom-top)*state.scale)/2-top*state.scale;
    applyTransform();
  }
  function centerOn(id) {
    const box=$('map-canvas').getBoundingClientRect(),p=positions[id];state.scale=.95;
    state.x=box.width/2-(p[0]+105)*state.scale;state.y=box.height/2-(p[1]+43)*state.scale;applyTransform();
  }
  function zoom(factor,x,y) {
    const box=$('map-canvas').getBoundingClientRect();x=x??box.width/2;y=y??box.height/2;
    const next=Math.min(1.9,Math.max(.2,state.scale*factor));
    state.x=x-(x-state.x)*next/state.scale;state.y=y-(y-state.y)*next/state.scale;
    state.scale=next;applyTransform();
  }
  let drag=null;
  $('map-canvas').addEventListener('pointerdown',e=>{
    if(e.target.closest('button,.edge-hit'))return;
    drag={x:e.clientX,y:e.clientY,tx:state.x,ty:state.y};$('map-canvas').setPointerCapture(e.pointerId);$('map-canvas').classList.add('dragging');
  });
  $('map-canvas').addEventListener('pointermove',e=>{if(drag){state.x=drag.tx+e.clientX-drag.x;state.y=drag.ty+e.clientY-drag.y;applyTransform();}});
  const endDrag=()=>{drag=null;$('map-canvas').classList.remove('dragging');};
  $('map-canvas').addEventListener('pointerup',endDrag);$('map-canvas').addEventListener('pointercancel',endDrag);
  $('map-canvas').addEventListener('wheel',e=>{e.preventDefault();const b=$('map-canvas').getBoundingClientRect();zoom(Math.exp(-e.deltaY*.0015),e.clientX-b.left,e.clientY-b.top);},{passive:false});
  $('zoom-in').onclick=()=>zoom(1.2);$('zoom-out').onclick=()=>zoom(1/1.2);
  $('clear-selection').onclick=()=>clearSelection();
  $('fit-all').onclick=()=>{fit(data.nodes.map(n=>n.id));saveSelection();announce('Map fitted to all sources.');};

  function orderedTrace(ids,edges) {
    const remaining=[...ids].sort((a,b)=>positions[a][1]-positions[b][1]||positions[a][0]-positions[b][0]),ordered=[];
    while(remaining.length) {
      const roots=remaining.filter(id=>!edges.some(e=>e.target===id&&remaining.includes(e.source)));
      // Recorded dependency cycles stay visible, with arrows pointing back.
      const next=roots[0]||remaining[0];ordered.push(next);remaining.splice(remaining.indexOf(next),1);
    }
    return ordered;
  }
  function traceButtons(ids,edges=null) {
    const ordered=edges?orderedTrace(ids,edges):[...ids].sort((a,b)=>positions[a][1]-positions[b][1]||positions[a][0]-positions[b][0]);
    return ordered.map(id=>{
      const n=byId.get(id),feeds=edges?.filter(e=>e.source===id).map(e=>byId.get(e.target).title)||[];
      return `<button class="trace-node ${id===state.selected?'selected':''}" data-source="${escape(id)}" ${id===state.selected?'aria-current="true"':''}>${id===state.selected&&edges?'<span class="trace-current">You are here</span>':''}${escape(n.title)}<small>${escape(prettyStatus[n.status]||n.status)} · ${escape(id)}</small>${feeds.length?'<span class="sr-only">Feeds '+escape(feeds.join('; '))+'.</span>':''}</button>`;
    }).join('');
  }
  function drawTraceFlow() {
    if(state.traceCollapsed)return;
    const flow=$('trace-flow');if(!flow)return;
    const cards=[...flow.querySelectorAll('[data-source]')],index=new Map(cards.map((el,i)=>[el.dataset.source,i]));
    const links=data.edges.filter(e=>traversable(e)&&index.has(e.source)&&index.has(e.target));
    // Separate overlapping branches. Routing uses only recorded edges, never list adjacency.
    const lanes=[];
    const routed=links.map(e=>({e,start:Math.min(index.get(e.source),index.get(e.target)),end:Math.max(index.get(e.source),index.get(e.target))})).sort((a,b)=>(a.end-a.start)-(b.end-b.start));
    routed.forEach(link=>{let lane=lanes.findIndex(items=>items.every(item=>link.end<=item.start||link.start>=item.end));if(lane<0){lane=lanes.length;lanes.push([]);}lanes[lane].push(link);link.lane=lane;});
    const gutter=links.length?Math.min(88,24+lanes.length*9):0;
    flow.style.paddingLeft=gutter+'px';
    const box=flow.getBoundingClientRect(),centers=new Map(cards.map(el=>[el.dataset.source,el.getBoundingClientRect().top-box.top+el.offsetHeight/2]));
    const height=flow.scrollHeight;
    const paths=routed.map(({e,lane})=>{
      const a=centers.get(e.source),b=centers.get(e.target),x=gutter-16-lane*(gutter-24)/Math.max(1,lanes.length),end=gutter-2,mid=(a+b)/2;
      const dashed=e.kind!=='flow';
      const description=byId.get(e.source).title+' → '+byId.get(e.target).title+' · '+e.label+' · '+(prettyStatus[e.status]||e.status);
      return `<g class="trace-flow-link${dashed?' dependency':''}" data-flow-source="${escape(e.source)}" data-flow-target="${escape(e.target)}"><title>${escape(description)}</title><path d="M${end},${a} H${x} V${b} H${end}" marker-end="url(#trace-arrow)"/><path class="trace-travel-arrow" d="M${x-3},${mid+(b>a?-4:4)} L${x},${mid} L${x+3},${mid+(b>a?-4:4)}"/><circle cx="${end}" cy="${a}" r="2"/></g>`;
    }).join('');
    $('trace-flow-lines').setAttribute('width',gutter);$('trace-flow-lines').setAttribute('height',height);
    $('trace-flow-lines').innerHTML='<defs><marker id="trace-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#087c72"/></marker></defs>'+paths;
    const feedback=links.some(e=>index.get(e.target)<=index.get(e.source));
    $('trace-flow-note').textContent='Follow arrowheads from source to use.'+(links.some(e=>e.kind!=='flow')?' Dashed lines: registered dependencies.':'')+(feedback?' Upward arrows: recorded feedback links.':'');
  }
  function renderTrace() {
    const trace=traceSets(),node=byId.get(state.selected);
    if(!node&&!state.parameterFocus) {
      $('trace-title').textContent='Select a source';$('parameter-access').innerHTML='';
      document.querySelector('.trace-controls').hidden=true;document.querySelector('.dependency-toggle').hidden=true;
      $('trace-body').innerHTML='<div class="trace-empty"><span aria-hidden="true">↗</span><p>Select any node on the map or find a source above to see what feeds it and what uses it.</p></div>';
      $('source-detail').innerHTML='';return;
    }
    const nodeValues=data.values.filter(v=>v.node_ids.includes(state.selected)),count=nodeValues.length;
    const received=nodeValues.filter(v=>originOf(v).kind==='received').length;
    const local=nodeValues.filter(v=>['defined','derived'].includes(originOf(v).kind)).length;
    $('parameter-access').innerHTML=count?`<button id="view-parameters" class="primary">View parameters (${count}) ↓</button><p>${received} received · ${local} defined / derived · ${count-received-local} unconfirmed</p>`:'<p>Parameters have not been extracted for this node yet.</p><button id="open-case-inputs">Open pier saved case inputs ↓</button>';
    if($('view-parameters'))$('view-parameters').onclick=()=>navigate(()=>{resetFilters();state.parameterFocus=false;renderSelection();scrollToValues();});
    if($('open-case-inputs'))$('open-case-inputs').onclick=()=>selectNode('PIER-CASE',true);
    document.querySelectorAll('[data-direction]').forEach(b=>{b.classList.toggle('active',b.dataset.direction===state.direction);b.setAttribute('aria-pressed',String(b.dataset.direction===state.direction));});
    document.querySelector('.trace-controls').hidden=state.parameterFocus;
    document.querySelector('.dependency-toggle').hidden=state.parameterFocus;
    if(state.parameterFocus) {
      const value=valueById.get(state.value);
      $('trace-title').textContent=value.label;
      $('trace-body').innerHTML=(value.upstream_context?'<div class="trace-group">Model inputs upstream of this result</div>'+traceButtons(value.upstream_context.node_ids)+'<p class="trace-context-note">Journal inputs feed the analysis. They are different quantities from this result.</p>':'')+'<div class="trace-group">Individual value trail</div>'+value.steps.map(s=>
        `<button class="trace-node" data-source="${escape(s.node)}">${escape(s.title)}<small>${escape(format(s.value))} ${escape(unitText(s.unit))} · ${escape(byId.get(s.node).title)}</small></button>`).join('');
      $('trace-body').querySelectorAll('[data-source]').forEach(el=>el.onclick=()=>selectNode(el.dataset.source));
      $('source-detail').innerHTML='<strong>'+escape(value.key)+'</strong><p>'+escape(value.transform||value.note||value.source_status)+'</p><p>Exact source locations and handoff evidence are shown in the value inspector below.</p><button id="exit-parameter" class="quiet">Back to component trace ↗</button>';
      $('exit-parameter').onclick=()=>selectNode(state.selected);
      return;
    }
    $('trace-title').textContent=node.title;
    const edges=data.edges.filter(e=>traversable(e)&&trace.all.has(e.source)&&trace.all.has(e.target));
    const feedback=new Set([...trace.upstream].filter(id=>trace.downstream.has(id)));
    const upstream=new Set([...trace.upstream].filter(id=>!feedback.has(id))),downstream=new Set([...trace.downstream].filter(id=>!feedback.has(id)));
    $('trace-body').innerHTML='<div class="trace-flow-heading">Source → use</div><p id="trace-flow-note" class="trace-context-note"></p><div id="trace-flow" class="trace-flow"><svg id="trace-flow-lines" aria-hidden="true"></svg>'+
      (upstream.size?'<div class="trace-group">Upstream sources</div>'+traceButtons(upstream,edges):'')+
      '<div class="trace-group">Selected component</div>'+traceButtons([state.selected],edges)+
      (downstream.size?'<div class="trace-group">Downstream uses</div>'+traceButtons(downstream,edges):'')+
      (feedback.size?'<div class="trace-group">Recorded feedback</div>'+traceButtons(feedback,edges):'')+'</div>';
    drawTraceFlow();$('trace-body').scrollTop=0;
    $('trace-body').querySelectorAll('[data-source]').forEach(el=>el.onclick=()=>selectNode(el.dataset.source));
    const issues=data.issues.filter(i=>i.node_ids.includes(node.id)&&!['Closed','Not applicable'].includes(i.Status));
    $('source-detail').innerHTML=badge(node.status)+'<p>'+escape(node.detail)+'</p>'+
      (node.registered_status?'<p><strong>Selection:</strong> '+escape(node.registered_status)+'</p>':'')+
      (node.path?'<code>'+escape(node.path)+'</code>':'')+
      (node.notes?'<details><summary>Source notes</summary><p>'+escape(node.notes)+'</p></details>':'')+
      (issues.length?'<p>'+issues.length+' open or deferred tracker items reference this source.</p>':'')+
      '<button class="quiet" id="inspect-source">Inspect source record ↗</button>'+
      '<details><summary>Inspect connected paths</summary>'+data.edges.filter(e=>e.source===node.id||e.target===node.id).map(e=>
        `<p><button class="quiet" data-inspect-edge="${escape(e.id)}">${escape(e.source)} → ${escape(e.target)}<br>${escape(e.label)}</button></p>`).join('')+'</details>';
    $('inspect-source').onclick=()=>showNodeEvidence(node);
    $('source-detail').querySelectorAll('[data-inspect-edge]').forEach(b=>b.onclick=()=>selectEdge(data.edges.find(e=>e.id===b.dataset.inspectEdge)));
  }
  function selectNode(id,openValues=false,valueId=null) {
    navigate(()=>{state.selected=id;if(valueId)state.value=valueId;state.edge=null;resetFilters();state.parameterFocus=false;state.overview=false;state.traceCollapsed=false;
      renderSelection();keepSelectedVisible();if(openValues)scrollToValues();announce('Selected '+byId.get(id).title);});
  }
  function selectEdge(edge) {
    selectNode(edge.target);
    showEvidence({path:edge.evidence[0]?.path||REGISTRY_PATH,locator:edge.source+' → '+edge.target,
      excerpt:JSON.stringify({label:edge.label,status:edge.status,basis:edge.basis,evidence:edge.evidence},null,2),
      note:'Relationship evidence; status is scoped to the stated check.'},edge.label);
  }
  const REGISTRY_PATH='project_current/source_register.csv';
  document.querySelectorAll('[data-direction]').forEach(button=>button.onclick=()=>{
    navigate(()=>{state.direction=button.dataset.direction;state.overview=false;
    document.querySelectorAll('[data-direction]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});
    paintGraph();renderTrace();});
  });
  $('include-dependencies').onchange=e=>navigate(()=>{state.dependencies=e.target.checked;paintGraph();renderTrace();});

  function renderDirectory() {
    const q=$('source-search').value.trim().toLowerCase();
    const matches=data.nodes.filter(n=>(n.id+' '+n.title+' '+n.path).toLowerCase().includes(q));
    $('source-results').hidden=!directoryOpen&&!q;
    $('source-results').innerHTML=matches.map(n=>`<button data-source="${escape(n.id)}">${escape(n.title)}<small>${escape(n.id)} · ${escape(prettyStatus[n.status]||n.status)}</small></button>`).join('')||'<p>No matching sources.</p>';
    $('source-results').querySelectorAll('button').forEach(b=>b.onclick=()=>{selectNode(b.dataset.source);centerOn(b.dataset.source);directoryOpen=false;$('source-search').value='';renderDirectory();});
  }
  $('source-search').oninput=renderDirectory;
  $('sources-button').onclick=()=>{directoryOpen=!directoryOpen;renderDirectory();};
  [...new Set(data.values.map(v=>v.category))].sort().forEach(cat=>{const o=document.createElement('option');o.value=cat;o.textContent=cat;$('value-category').appendChild(o);});
  function renderValues() {
    const empty=!state.selected&&!state.allValues&&!state.parameterFocus;
    $('values-panel').classList.toggle('no-selection',empty);
    document.querySelector('.value-controls').hidden=empty;$('origin-filters').hidden=empty;$('origin-context').hidden=empty;
    if(empty){$('values-title').textContent='Parameters & origins';$('value-rows').innerHTML='';$('value-count').textContent='';$('empty-values').hidden=true;$('value-detail').innerHTML='<h3>Select a source to explore its parameters</h3><p class="value-note">Choose a node on the map, or browse all extracted values.</p>';return;}
    const query=$('value-search').value.toLowerCase(),cat=$('value-category').value;
    const available=data.values.filter(v=>state.allValues||v.node_ids.includes(state.selected));
    const inOrigin=(v,kind)=>kind==='all'||(kind==='local'?['defined','derived'].includes(originOf(v).kind):originOf(v).kind===kind);
    $('origin-filters').innerHTML=[['all','All parameters'],['received','Received inputs'],['local','Defined / derived here'],['unknown','Origin unconfirmed']].map(([key,label])=>`<button data-origin="${key}" class="${state.origin===key?'active':''}" aria-pressed="${state.origin===key}">${label}<strong>${available.filter(v=>inOrigin(v,key)).length}</strong></button>`).join('');
    $('origin-filters').querySelectorAll('button').forEach(b=>b.onclick=()=>navigate(()=>{state.origin=b.dataset.origin;state.parameterFocus=false;renderSelection();}));
    $('origin-context').textContent=state.allValues?'Roles are relative to the node named in each row. “Local setting” does not establish first-ever authorship.':`Roles at ${byId.get(state.selected).title}. “Local setting” means retained here; first-ever authorship is not established.`;
    const shown=available.filter(v=>inOrigin(v,state.origin)&&(!cat||v.category===cat)&&
      (v.label+' '+v.key+' '+v.unit+' '+format(v.value)+' '+(v.expression||'')).toLowerCase().includes(query));
    $('values-title').textContent=state.allValues?'All extracted values':byId.get(state.selected).title+' · parameters';
    $('value-count').textContent=shown.length+' values';$('empty-values').hidden=shown.length>0;
    if(!shown.some(v=>v.id===state.value)&&shown.length)state.value=shown[0].id;
    if(!shown.length)state.parameterFocus=false;
    $('value-rows').innerHTML=shown.map(v=>{
      const role=originOf(v);
      return `<tr class="${v.id===state.value?'selected':''}" data-value="${escape(v.id)}"><td><button data-value-button="${escape(v.id)}">${escape(v.label)}</button><small>${escape(v.key)} · ${escape(v.category)}</small></td><td>${v.value_kind==='expression'?'Formula':escape(format(v.value))} <small>${v.value_kind==='expression'?'Result not evaluated':escape(unitText(v.unit))}</small></td><td><span class="origin-badge ${role.kind}">${roleNames[role.kind]}</span>${role.from_node?`<button class="origin-link" data-origin-node="${escape(role.from_node)}">From ${escape(byId.get(role.from_node).title)} ↗</button>`:''}${state.allValues?`<small>At ${escape(byId.get(originNode(v)).title)}</small>`:''}</td></tr>`;
    }).join('');
    $('value-rows').querySelectorAll('tr').forEach(row=>row.onclick=()=>navigate(()=>{state.value=row.dataset.value;if(!state.selected)state.selected=originNode(valueById.get(state.value));state.parameterFocus=true;state.overview=false;state.traceCollapsed=false;renderTraceSidebar();renderValues();paintGraph();renderTrace();keepSelectedVisible();$('value-detail').scrollTop=0;if(matchMedia('(max-width:760px)').matches)$('value-detail').scrollIntoView({block:'start'});announce('Tracing '+valueById.get(state.value).label);}));
    $('value-rows').querySelectorAll('[data-origin-node]').forEach(b=>b.onclick=e=>{e.stopPropagation();selectNode(b.dataset.originNode,true,b.closest('tr').dataset.value);});
    if(shown.length)renderValue(valueById.get(state.value));
    else $('value-detail').innerHTML=available.length?'<h3>No parameters match these filters</h3><p class="value-note">Clear the filters to see all extracted parameters at this node.</p><button id="clear-value-filters">Clear parameter filters</button>':'<h3>Parameters not yet extracted</h3><p class="value-note">The project map includes every registered source. Detailed extraction covers the pier-cap trail and the journal’s pier/end-bent node-entry tables.</p><button id="open-all-values">Browse all extracted values</button>';
    if($('open-all-values'))$('open-all-values').onclick=showAllValues;
    if($('clear-value-filters'))$('clear-value-filters').onclick=()=>navigate(()=>{resetFilters();renderSelection();});
  }
  function renderValue(v) {
    const role=originOf(v),context=byId.get(originNode(v));
    const flowSteps=v.steps.map((s,i)=>{
      const previous=v.steps[i-1],next=v.steps[i+1],from=v.origins[s.node]?.from_node;
      const nextFrom=next&&v.origins[next.node]?.from_node;
      const connects=next&&(next.node===s.node||nextFrom===s.node);
      const arrow=connects&&next.node!==s.node;
      // Adjacent evidence records are not necessarily sequential handoffs.
      // Restart a branch when, for example, report and worksheet both use the case.
      const branch=previous&&previous.node!==s.node&&from!==previous.node;
      const branchLabel=branch?(from?`<div class="value-flow-branch">Separate handoff from <strong>${escape(byId.get(from).title)}</strong><span class="sr-only">, flowing down to ${escape(byId.get(s.node).title)}</span></div>`:'<p class="value-flow-break">Separate source record · transfer not established</p>'):'';
      return branchLabel+`<div class="value-step${s.node===context.id?' current-component':''}">${connects?`<span class="flow-connector${arrow?' with-arrow':''}" aria-hidden="true"></span>`:''}<h4>${escape(s.title)}${s.node===context.id?'<span class="current-label">Selected component</span>':''}</h4>${badge(s.status,s.status==='match'?'Value matches':s.status==='recorded'?'Source record':s.status)}<div class="step-value">${escape(format(s.value))} ${escape(unitText(s.unit))}</div><code>${escape(s.evidence.locator)}</code>${s.note?'<p>'+escape(s.note)+'</p>':''}<button data-evidence-step="${i}">View exact source ↗</button>${s.mapping?` <button data-mapping-step="${i}">Mapping record</button>`:''}</div>`;
    }).join('');
    $('value-detail').innerHTML=`<div class="value-top"><div><div class="eyebrow">${escape(v.category.toUpperCase())}</div><h3>${escape(v.label)}</h3></div><div class="big-value ${v.value_kind==='expression'?'expression-value':''}">${escape(format(v.value))} <small>${escape(unitText(v.unit))}</small></div></div>`+
      `<div class="origin-card ${role.kind}"><span class="origin-badge ${role.kind}">${roleNames[role.kind]}</span><small> at ${escape(context.title)}</small><p>${escape(role.basis)}</p>${role.from_node?`<button id="follow-origin">Open ${escape(byId.get(role.from_node).title)} ↗</button>`:''}${role.evidence.map((e,i)=>`<button data-origin-evidence="${i}">Origin evidence${role.evidence.length>1?' '+(i+1):''}</button>`).join('')}</div>`+
      (v.expression?`<pre class="formula-expression">${escape(v.expression)}</pre>`:'')+
      (v.upstream_context?`<div class="upstream-context"><strong>Model inputs: project journal</strong><p>${escape(v.upstream_context.detail)}</p>${v.upstream_context.node_ids.map(id=>`<button data-upstream-source="${escape(id)}">Open ${escape(byId.get(id).title)} ↗</button>`).join('')}</div>`:'')+
      (v.sheet_status==='match'?badge('match','Mathcad input matches'):v.sheet_status!=='not mapped'&&v.sheet_status!=='not applicable'?badge(v.sheet_status,'Mathcad: '+v.sheet_status):'')+
      `<p class="value-note">${escape(v.source_status)}${v.transform?' · '+escape(v.transform):''}${v.note?'<br>'+escape(v.note):''}</p>`+
      (v.steps.some(s=>v.origins[s.node]?.from_node)?'<p class="flow-direction">↓ Arrows follow recorded handoffs between components</p>':'')+flowSteps+
      (v.sheet_status==='not mapped'?'<div class="gap-note">This parameter has no explicit worksheet mapping in the current adapter.</div>':'')+
      (v.node_ids.includes('REQUIRED-PIER-XML')?'<div class="gap-note">'+(data.checks.required_xml_present?'Source identity matches. These loads are retained audit records, not independently re-extracted here.':'Upstream limit: the matching raw FBMP export is not registered. These loads are traceable to the saved audit, not independently re-extracted here.')+'</div>':'')+
      (v.node_ids.includes('PIER-MATHCAD')?'<div class="value-note">Worksheet inputs were inspected directly. Native Mathcad recalculation and an issued PDF are not established.</div>':'');
    $('value-detail').querySelectorAll('[data-evidence-step]').forEach(b=>b.onclick=()=>showEvidence(v.steps[+b.dataset.evidenceStep].evidence,v.label));
    $('value-detail').querySelectorAll('[data-mapping-step]').forEach(b=>b.onclick=()=>showEvidence(v.steps[+b.dataset.mappingStep].mapping,v.label+' · mapping'));
    $('value-detail').querySelectorAll('[data-origin-evidence]').forEach(b=>b.onclick=()=>showEvidence(role.evidence[+b.dataset.originEvidence],v.label+' · origin at '+context.title));
    $('value-detail').querySelectorAll('[data-upstream-source]').forEach(b=>b.onclick=()=>selectNode(b.dataset.upstreamSource,true));
    if($('follow-origin'))$('follow-origin').onclick=()=>selectNode(role.from_node,true);
  }
  function showAllValues(){navigate(()=>{resetFilters();state.allValues=true;state.parameterFocus=false;renderSelection();scrollToValues();});}
  function filterValues(){renderValues();paintGraph();renderTrace();saveSelection();}
  $('all-values').onclick=showAllValues;$('value-search').oninput=filterValues;$('value-category').onchange=filterValues;

  function showNodeEvidence(node) {
    showEvidence({path:node.path||node.evidence?.[0]?.path||REGISTRY_PATH,locator:node.id,
      excerpt:JSON.stringify(node,null,2),note:node.fingerprint_detail||node.detail},node.title);
  }
  function showEvidence(evidence,title) {
    const doc=data.documents[evidence.path];
    $('evidence-title').textContent=title;
    $('evidence-content').innerHTML='<p><strong>File</strong><br><code>'+escape(evidence.path)+'</code></p>'+
      '<p><strong>Location</strong><br><code>'+escape(evidence.locator)+'</code></p>'+
      (doc?.sha256?'<div class="hash-block"><strong>Snapshot fingerprint · exact file bytes</strong><br><code>'+escape(doc.sha256)+'</code></div>':'<div class="gap-note">No file fingerprint is available for this record.</div>')+
      (evidence.note?'<p>'+escape(evidence.note)+'</p>':'')+'<pre>'+escape(evidence.excerpt)+'</pre>'+
      (location.protocol==='file:'&&doc?.exists?'<a id="open-original" target="_blank" rel="noopener">Open local source file ↗</a>':'')+
      '<p class="value-note">Evidence captured '+escape(new Date(data.generated_at).toLocaleString())+'. Rebuild the atlas to capture subsequent file changes.</p>';
    if($('open-original'))$('open-original').href=new URL('../../'+evidence.path,location.href).href;
    if(!$('evidence-dialog').open)$('evidence-dialog').showModal();
  }
  $('close-evidence').onclick=()=>$('evidence-dialog').close();$('close-about').onclick=()=>$('about-dialog').close();
  [$('about-dialog'),$('evidence-dialog')].forEach(dialog=>dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}}));
  $('about-button').onclick=()=>{
    const issues=data.issues.filter(i=>i.node_ids.some(id=>id.startsWith('PIER'))&&!['Closed','Not applicable'].includes(i.Status));
    $('about-content').innerHTML='<div class="about-grid"><div><h3>Map coverage</h3><p>'+escape(data.coverage.map)+'</p><h3>Value coverage</h3><p>'+escape(data.coverage.values)+'</p></div><div><h3>Snapshot</h3><p>'+escape(new Date(data.generated_at).toLocaleString())+'</p><p>Repository revision<br><code>'+escape(data.repository_revision)+'</code></p><a href="atlas-data.json" download>Download the evidence snapshot</a></div></div>'+
      '<h3>What the statuses mean</h3><p>Fingerprint match means a file matches its registered revision. Input matches means a literal worksheet input agrees after unit conversion. Recorded means the source states a relationship. None of these statuses establishes engineering approval.</p>'+
      '<h3>Current boundaries</h3><ul>'+data.coverage.limits.map(l=>'<li>'+escape(l)+'</li>').join('')+'</ul>'+
      '<h3>Pier-related tracker records</h3><p>Read directly from the current coherence workbook. No issue status was changed by the atlas.</p>'+
      issues.map(i=>'<div class="issue-card"><strong>'+escape(i['Item ID'])+' · '+escape(i.Item)+'</strong> '+badge('recorded',i.Status)+'<p>'+escape(i.Finding)+'</p><p><strong>Next action:</strong> '+escape(i['Next action'])+'</p><code>Coherence items!A'+escape(i._row)+':M'+escape(i._row)+'</code></div>').join('');
    $('about-dialog').showModal();
  };
  const dt=new Date(data.generated_at);
  $('snapshot-time').textContent=dt.toLocaleString(undefined,{month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit'});
  $('footer-snapshot').textContent='D2 · '+dt.toLocaleDateString()+' snapshot';
  $('summary').innerHTML='<div><strong>'+data.nodes.length+'</strong><span>source nodes</span></div><div><strong>'+data.values.length+'</strong><span>extracted values</span></div><div><strong>'+data.edges.length+'</strong><span>connections</span></div>';
  $('source-count').textContent='('+data.nodes.length+')';
  document.querySelector('.brand').onclick=e=>{e.preventDefault();overview();};
  history.scrollRestoration='manual';
  renderSelection();requestAnimationFrame(()=>{fit(data.nodes.map(n=>n.id));saveSelection();});
  new ResizeObserver(()=>{const width=$('map-canvas').clientWidth;if(Math.abs(width-oldWidth)>60){oldWidth=width;if(state.overview)fit(data.nodes.map(n=>n.id));}}).observe($('map-canvas'));
  new ResizeObserver(drawTraceFlow).observe($('trace-body'));
})();
