// Unit-test the exported control script without a browser or network.
// Usage: node tests/test_report_controls.js path/to/calculation_report.html
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const markup = fs.readFileSync(process.argv[2], 'utf8');
const script = markup.slice(markup.lastIndexOf('<script>') + 8, markup.lastIndexOf('</script>'));
const callbacks = new Map();
const buttons = new Map(['expand-all', 'collapse-all', 'print-report'].map(id => [id, {
  addEventListener: (_, fn) => callbacks.set(id, fn)
}]));
const sections = [true, false, false].map(open => ({open, tagName:'DETAILS', parentElement:null}));
const figures = sections.map((section, i) => ({
  id:`plot-${i}`, dataset:{figure:`data-${i}`},
  closest:() => section.open ? null : section
}));
const events = new Map();
const windowEvents = new Map();
const draws = []; const resizes = [];
let printCalls = 0;
const anchor = {parentElement:sections[2], tagName:'ARTICLE', scrollIntoView() {this.scrolled=true;}};
const sandbox = {
  document:{
    querySelectorAll:selector => selector === 'details' ? sections : figures,
    getElementById:id => buttons.get(id) || (id === 'equation' ? anchor : id.startsWith('data-') ? {textContent:'{"data":[],"layout":{}}'} : null),
    addEventListener:(event, callback) => events.set(event,callback)
  },
  Plotly:{newPlot:async plot => {draws.push(plot.id);}, Plots:{resize:async plot => {resizes.push(plot.id);}}},
  requestAnimationFrame:callback => setImmediate(callback),
  location:{hash:''},
  window:{addEventListener:(event,callback) => windowEvents.set(event,callback),print:() => {
    printCalls++;
    assert(sections.every(d=>d.open));
    windowEvents.get('beforeprint')();
    windowEvents.get('afterprint')();
  }}
};
const settle = async () => {for(let i=0;i<4;i++) await new Promise(setImmediate);};
(async () => {
  vm.runInNewContext(script,sandbox);
  await settle();
  assert.deepEqual(draws,['plot-0']);
  callbacks.get('expand-all')();
  await settle();
  assert(sections.every(d=>d.open));
  assert.deepEqual(draws,['plot-0','plot-1','plot-2']);
  callbacks.get('collapse-all')();
  await settle();
  assert(sections.every(d=>!d.open));
  sandbox.location.hash='#equation';
  windowEvents.get('hashchange')();
  await settle();
  assert(sections[2].open && anchor.scrolled);
  const prior=sections.map(d=>d.open);
  await callbacks.get('print-report')();
  await settle();
  assert.equal(printCalls,1);
  assert.deepEqual(sections.map(d=>d.open),prior);
  assert.equal(draws.length,3,'plots must not be initialized twice');
  assert(resizes.length>0);
  console.log('PASS: expand/collapse, lazy plot initialization, anchor reveal, print expansion and state restoration.');
})().catch(error => {console.error(error);process.exitCode=1;});
