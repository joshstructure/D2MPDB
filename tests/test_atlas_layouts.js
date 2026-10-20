'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const layouts=require('../design_atlas/web/layouts.js');
const stages=['Basis','Analysis','Design','Detailing','Deliverables'];
const node=(id,stage='Basis',status='recorded')=>({id,title:id,stage,status});
const link=(source,target,kind='dependency')=>({source,target,kind});
const graph={nodes:['A','B','C','D','E','F'].map(id=>node(id)),edges:[
  link('A','B'),link('A','C'),link('B','D'),link('C','D'),link('D','E'),link('E','D'),link('F','A','context')
]};
const closure=layouts.reachability(graph.nodes,graph.edges);
assert.deepEqual([...closure.get('A')].sort(),['B','C','D','E']);
assert.deepEqual([...closure.get('D')],['E']);
assert.equal(closure.get('F').size,0);
const flow=layouts.create(graph,'flow');
assert.equal(flow.positions.D[0],flow.positions.E[0]);
assert(flow.positions.A[0]<flow.positions.B[0]);
assert(flow.positions.B[0]<flow.positions.D[0]);
assert.equal(flow.positions.F[0],flow.positions.A[0]);
const impact=layouts.create(graph,'impact');
assert.equal(impact.metrics.A,4);assert.equal(impact.metrics.D,1);
const local=layouts.create(graph,'neighborhood','B');
assert(local.positions.A[0]<local.positions.B[0]);
assert(local.positions.B[0]<local.positions.D[0]);
assert(local.positions.F[0]>local.positions.D[0]);
assert.deepEqual(layouts.create(graph,'neighborhood').positions,layouts.create(graph).positions);
assert.deepEqual(layouts.create(graph,'invalid').positions,layouts.create(graph).positions);

// Assumptions grouping: stale basis, then open entries, then accepted, then none; busiest card first within a group.
const flagged={nodes:[
  Object.assign(node('NONE'),{assumption_total:0,assumption_open:0,assumption_stale:0,assumption_flags:0}),
  Object.assign(node('ACCEPTED'),{assumption_total:2,assumption_open:0,assumption_stale:0,assumption_flags:0}),
  Object.assign(node('OPEN-ONE'),{assumption_total:1,assumption_open:1,assumption_stale:0,assumption_flags:1}),
  Object.assign(node('OPEN-TWO'),{assumption_total:3,assumption_open:2,assumption_stale:0,assumption_flags:2}),
  Object.assign(node('STALE'),{assumption_total:1,assumption_open:0,assumption_stale:1,assumption_flags:1}),
  node('PLAIN')
],edges:[link('STALE','OPEN-ONE')]};
assert(layouts.modes.some(m=>m.id==='assumptions'),'assumptions layout is offered');
const grouped=layouts.create(flagged,'assumptions');
assert(grouped.positions.STALE[0]<grouped.positions['OPEN-TWO'][0],'stale basis is left of open entries');
assert.equal(grouped.positions['OPEN-TWO'][0],grouped.positions['OPEN-ONE'][0],'open entries share a column');
assert(grouped.positions['OPEN-TWO'][1]<grouped.positions['OPEN-ONE'][1],'more flags sort first within a group');
assert(grouped.positions['OPEN-ONE'][0]<grouped.positions.ACCEPTED[0],'accepted entries follow open ones');
assert(grouped.positions.ACCEPTED[0]<grouped.positions.NONE[0],'sources without entries come last');
assert.equal(grouped.positions.NONE[0],grouped.positions.PLAIN[0],'missing counts mean no recorded entry');
assert.deepEqual(grouped.labels.map(l=>l.text),['Stale basis · 1','Open entries · 2','Accepted entries · 1','No recorded entries · 2']);

// Validate actual path segments, including long links and wrapped groups, against every card.
function validate(data,mode,selected) {
  const result=layouts.create(data,mode,selected),entries=Object.entries(result.positions);
  assert.equal(entries.length,data.nodes.length,mode+': every source exactly once');
  for(const [id,[x,y]] of entries) {
    assert(Number.isFinite(x)&&Number.isFinite(y),id+': finite position');
    assert(x>=0&&y>=0&&x+210<=result.width&&y+86<=result.height,id+': in bounds');
    for(const [other,[ox,oy]] of entries)if(other!==id)assert(x+210<=ox||ox+210<=x||y+86<=oy||oy+86<=y,id+': overlapping card');
  }
  data.edges.forEach((edge,index)=>{
    const commands=[...layouts.edgePath(result.positions,edge,index).matchAll(/([MHV])([\d.,-]+)/g)];
    let current=null;
    for(const [,command,values] of commands) {
      const numbers=values.split(',').map(Number);
      const next=command==='M'?numbers:command==='H'?[numbers[0],current[1]]:[current[0],numbers[0]];
      if(current)for(const [id,[x,y]] of entries) {
        if(id===edge.source||id===edge.target)continue;
        const horizontal=current[1]===next[1];
        const crosses=horizontal?current[1]>y&&current[1]<y+86&&Math.max(current[0],next[0])>x&&Math.min(current[0],next[0])<x+210:
          current[0]>x&&current[0]<x+210&&Math.max(current[1],next[1])>y&&Math.min(current[1],next[1])<y+86;
        assert(!crosses,mode+': '+edge.source+' → '+edge.target+' crosses '+id);
      }
      current=next;
    }
    const target=result.positions[edge.target];
    assert.equal(current[1],target[1]+43);
    assert(current[0]===target[0]||current[0]===target[0]+210);
  });
}
const wide={nodes:Array.from({length:45},(_,i)=>node('SOURCE-'+i,stages[i%5],'match')),edges:[]};
wide.edges=wide.nodes.slice(1).map((n,i)=>link(wide.nodes[i].id,n.id));
for(const data of [graph,wide,flagged])for(const mode of layouts.modes)validate(data,mode.id,data.nodes[2].id);
const snapshot=process.argv[2]||path.join(__dirname,'../design_atlas/dist/atlas-data.json');
if(fs.existsSync(snapshot)) {
  const data=JSON.parse(fs.readFileSync(snapshot,'utf8'));
  for(const mode of layouts.modes)validate(data,mode.id,'PIER-REPORT');
  for(const n of data.nodes)validate(data,'neighborhood',n.id);
  const defaults=layouts.create(data);
  stages.forEach((stage,col)=>data.nodes.filter(n=>n.stage===stage).sort((a,b)=>a.title.localeCompare(b.title,undefined,{numeric:true})||a.id.localeCompare(b.id)).forEach((n,row)=>assert.deepEqual(defaults.positions[n.id],[35+col*270,75+row*135])));
  const flaggedNodes=data.nodes.filter(n=>n.assumption_flags>0);
  const byAssumption=layouts.create(data,'assumptions');
  for(const n of flaggedNodes)for(const other of data.nodes)if(!(other.assumption_total>0))assert(byAssumption.positions[n.id][0]<byAssumption.positions[other.id][0],n.id+': flagged source precedes '+other.id);
  console.log('Snapshot: all '+layouts.modes.length+' layouts, all selected neighborhoods, default positions, assumption grouping ('+flaggedNodes.length+' flagged sources) and connection routes verified.');
}
console.log('Atlas layout tests passed: cycles, direction, distinct impact, disconnected sources, assumption grouping, wrapping and route clearance.');
