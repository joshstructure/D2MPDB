/* Layouts change positions only; source records and relationship evidence stay intact. */
(function(root) {
  'use strict';
  const stages=['Basis','Analysis','Design','Detailing','Deliverables'];
  const modes=[
    {id:'default',label:'Default',description:'Project stages from basis to deliverables, with sources alphabetized within each column.'},
    {id:'component',label:'Component × stage',description:'Components in rows, project stages in columns. Shared sources appear once in their own row.'},
    {id:'flow',label:'Flow',description:'Recorded source-to-use links run left to right. Sources in a feedback cycle share a step; context-only links do not set the order.'},
    {id:'role',label:'File role',description:'Sources grouped by their role: journals, inputs, tools, models, saved cases and reports.'},
    {id:'evidence',label:'Evidence gaps',description:'Sources grouped by their recorded status, with gaps and changed revisions first. Line colors still show the status of each handoff.'},
    {id:'impact',label:'Impact',description:'Groups count distinct downstream sources reachable through recorded links, excluding context-only links. Connectivity does not establish engineering risk.'},
    {id:'neighborhood',label:'Neighborhood',description:'Upstream sources, feedback links and downstream uses arranged around your selected component. All other sources remain on the map.'}
  ];
  const alphabetical=(a,b)=>a.title.localeCompare(b.title,undefined,{numeric:true})||a.id.localeCompare(b.id);
  function component(n) {
    if(n.component)return n.component;
    if(n.id==='JOURNAL-EB-ENTRY')return 'End bents · shared';
    if(/^(PIER-|REQUIRED-PIER-|JOURNAL-PIER-)/.test(n.id))return 'Pier';
    if(/^EB2-/.test(n.id))return 'End Bent 2';
    if(/^(EB-|REQUIRED-EB-)/.test(n.id))return 'End Bent 1';
    if(/^BACKWALL-/.test(n.id))return 'Backwall / cheek walls';
    if(/^(MCAD-|PSB-)/.test(n.id))return 'Spans / superstructure';
    return 'Shared / project-wide';
  }
  function fileRole(n) {
    if(/^JOURNAL/.test(n.id))return 'Journal & entries';
    if(/-CASE$/.test(n.id))return 'Saved cases';
    if(/-REPORT$|-AUDIT$|-ISSUED-PDF$/.test(n.id))return 'Reports & evidence';
    if(/\.ipynb$/i.test(n.path||'')||n.id==='CAD-RUNTIME')return 'Tools & notebooks';
    if(/-XML$|^MCAD-S|^PSB-|MATHCAD$/.test(n.id)||n.id==='CAD-MODEL')return 'Analysis & models';
    return 'Input data & drawings';
  }
  function reachability(nodes,edges) {
    const outgoing=new Map(nodes.map(n=>[n.id,new Set()]));
    edges.filter(e=>e.kind!=='context').forEach(e=>{
      if(outgoing.has(e.source)&&outgoing.has(e.target))outgoing.get(e.source).add(e.target);
    });
    return new Map(nodes.map(n=>{
      const seen=new Set([n.id]),queue=[n.id];
      for(let i=0;i<queue.length;i++)outgoing.get(queue[i]).forEach(id=>{if(!seen.has(id)){seen.add(id);queue.push(id);}});
      seen.delete(n.id);return [n.id,seen];
    }));
  }
  function create(data,mode='default',selected=null) {
    if(!modes.some(m=>m.id===mode))mode='default';
    const nodes=[...data.nodes].sort(alphabetical),positions={},labels=[],metrics={};
    let description=modes.find(m=>m.id===mode).description;
    const place=(n,col,row,x=35)=>{positions[n.id]=[x+col*270,75+row*135];};
    const heading=(text,x,y=30,width=245,kind='column')=>labels.push({text,x,y,width,kind});
    // All modes share row/column spacing, leaving clear routing gutters between cards.
    function groups(names,key,sort=alphabetical,wrap=8) {
      let col=0;
      names.forEach(name=>{
        const members=nodes.filter(n=>key(n)===name).sort(sort);if(!members.length)return;
        const columns=Math.max(1,Math.ceil(members.length/wrap));
        heading(name+' · '+members.length,35+col*270,30,columns*270-25);
        members.forEach((n,i)=>place(n,col+Math.floor(i/wrap),i%wrap));col+=columns;
      });
    }
    function defaultLayout() {
      stages.forEach((stage,col)=>{
        const members=nodes.filter(n=>n.stage===stage);heading(stage+' · '+members.length,35+col*270);
        members.forEach((n,row)=>place(n,col,row));
      });
    }
    if(mode==='default')defaultLayout();
    if(mode==='component') {
      const components=['Shared / project-wide','Spans / superstructure','Pier','End bents · shared','End Bent 1','End Bent 2','Backwall / cheek walls'];
      // Wide stage bands keep a busy component from becoming a long vertical stack.
      const widths=stages.map(stage=>Math.max(1,...components.map(group=>Math.ceil(nodes.filter(n=>n.stage===stage&&component(n)===group).length/2))));
      const starts=widths.map((_,i)=>widths.slice(0,i).reduce((sum,w)=>sum+w,0));
      stages.forEach((stage,col)=>heading(stage,240+starts[col]*270,30,widths[col]*270-25));
      let row=0;
      components.forEach(group=>{
        const members=nodes.filter(n=>component(n)===group);if(!members.length)return;
        heading(group+' · '+members.length,35,75+row*135+22,175,'row');
        let rows=1;
        stages.forEach((stage,col)=>{
          const cell=members.filter(n=>n.stage===stage);rows=Math.max(rows,Math.ceil(cell.length/widths[col]));
          cell.forEach((n,i)=>place(n,starts[col]+i%widths[col],row+Math.floor(i/widths[col]),240));
        });
        row+=rows;
      });
    }
    if(mode==='role')groups(['Journal & entries','Input data & drawings','Tools & notebooks','Analysis & models','Saved cases','Reports & evidence'],fileRole);
    if(mode==='evidence') {
      const statuses={missing:'Source missing',changed:'Revision changed',mismatch:'Conflict',unmapped:'Unmapped / read error',error:'Unmapped / read error',match:'Fingerprint match'};
      groups(['Source missing','Revision changed','Conflict','Unmapped / read error','Recorded / unconfirmed','Fingerprint match'],n=>statuses[n.status]||'Recorded / unconfirmed');
    }
    if(['flow','impact','neighborhood'].includes(mode)) {
      const reach=reachability(nodes,data.edges);
      if(mode==='flow') {
        // Condense strongly connected components before assigning source-to-use ranks.
        const clusters=[],clusterOf=new Map();
        nodes.forEach(n=>{
          if(clusterOf.has(n.id))return;
          const ids=nodes.filter(other=>other.id===n.id||(reach.get(n.id).has(other.id)&&reach.get(other.id).has(n.id))).map(other=>other.id);
          ids.forEach(id=>clusterOf.set(id,clusters.length));clusters.push(ids);
        });
        const parents=clusters.map(()=>new Set()),ranks=new Map();
        data.edges.filter(e=>e.kind!=='context').forEach(e=>{
          const a=clusterOf.get(e.source),b=clusterOf.get(e.target);
          if(a!==undefined&&b!==undefined&&a!==b)parents[b].add(a);
        });
        function rank(i){if(!ranks.has(i))ranks.set(i,parents[i].size?1+Math.max(...[...parents[i]].map(rank)):0);return ranks.get(i);}
        clusters.forEach((_,i)=>rank(i));
        const names=Array.from({length:Math.max(0,...ranks.values())+1},(_,i)=>'Flow step '+(i+1));
        // Keep each rank in a single column so no forward link can run backwards.
        groups(names,n=>names[rank(clusterOf.get(n.id))],alphabetical,Infinity);
      }
      if(mode==='impact') {
        nodes.forEach(n=>{metrics[n.id]=reach.get(n.id).size;});
        const band=n=>metrics[n.id]>=10?'10+ downstream':metrics[n.id]>=4?'4–9 downstream':metrics[n.id]>0?'1–3 downstream':'No downstream links';
        groups(['10+ downstream','4–9 downstream','1–3 downstream','No downstream links'],band,(a,b)=>metrics[b.id]-metrics[a.id]||alphabetical(a,b));
      }
      if(mode==='neighborhood') {
        if(!reach.has(selected)) {
          defaultLayout();description='Select any node to arrange its neighborhood. Until then, the complete map stays in the default stage layout.';
        } else {
          const downstream=reach.get(selected),upstream=new Set(nodes.filter(n=>reach.get(n.id).has(selected)).map(n=>n.id));
          const group=n=>n.id===selected?'Selected component':upstream.has(n.id)&&downstream.has(n.id)?'Feedback connections':upstream.has(n.id)?'Upstream sources':downstream.has(n.id)?'Downstream uses':'Other sources';
          groups(['Upstream sources','Feedback connections','Selected component','Downstream uses','Other sources'],group);
          description='Around '+nodes.find(n=>n.id===selected).title+': upstream → selected → downstream. Feedback and other sources stay visible. Arrangement uses all recorded links except context-only links.';
        }
      }
    }
    // Include group labels as well as cards in the fit bounds.
    const width=Math.max(0,...Object.values(positions).map(p=>p[0]+245),...labels.map(l=>l.x+l.width+20));
    const height=Math.max(0,...Object.values(positions).map(p=>p[1]+135));
    return {positions,labels,width,height,description,metrics};
  }
  function edgePath(positions,e,index) {
    const a=positions[e.source],b=positions[e.target];
    const ay=a[1]+43,by=b[1]+43,offset=14+(index%4)*6;
    if(a[0]===b[0]){const x=a[0]+210,rail=x+offset;return `M${x},${ay} H${rail} V${by} H${x}`;}
    const forward=b[0]>a[0],sign=forward?1:-1;
    const ax=a[0]+(forward?210:0),bx=b[0]+(forward?0:210),exit=ax+sign*offset,entry=bx-sign*offset;
    if(Math.abs(a[0]-b[0])===270){const rail=(exit+entry)/2;return `M${ax},${ay} H${rail} V${by} H${bx}`;}
    const corridor=a[1]+100+(index%3)*8;
    return `M${ax},${ay} H${exit} V${corridor} H${entry} V${by} H${bx}`;
  }
  const api={modes,create,edgePath,reachability};
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.AtlasLayouts=api;
})(globalThis);
