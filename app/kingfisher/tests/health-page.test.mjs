import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {test} from 'node:test';
import {build} from 'vite';
const require=createRequire(import.meta.url);
async function page(fetchPage, fetchHistory=async()=>({items:[],next_cursor:null,invalid_sources:0})) {
  assert.ok(existsSync(new URL('../src/HealthPage.tsx',import.meta.url)), 'Dated original-backed health page is missing');
  const compiled=await build({configFile:false,logLevel:'silent',build:{write:false,minify:false,
    lib:{entry:fileURLToPath(new URL('../src/HealthPage.tsx',import.meta.url)),formats:['cjs']},
    rollupOptions:{external:['react','react/jsx-runtime','./api','./chrome','./ProfileSource','./HealthObservationEditor']}}});
  const code=[compiled].flat().flatMap(r=>r.output).find(x=>x.type==='chunk').code;
  const slots=[],effects=[];let index=0;
  const hooks={useState(v){const i=index++;if(!(i in slots))slots[i]=typeof v==='function'?v():v;return [slots[i],next=>slots[i]=typeof next==='function'?next(slots[i]):next];},useRef(v){const i=index++;return slots[i]??={current:v};},
    useEffect(fn,deps){const i=index++;const before=slots[i];if(!before||JSON.stringify(before.deps)!==JSON.stringify(deps)){before?.cleanup?.();slots[i]={deps};effects.push(()=>slots[i].cleanup=fn());}}};
  const callbacks={};
  globalThis.window={addEventListener(name,fn){callbacks[name]=fn;},removeEventListener(){},setInterval(){return 1;},clearInterval(){}};
  globalThis.document={hidden:false,addEventListener(name,fn){callbacks[name]=fn;},removeEventListener(){}};
  const module={exports:{}};
  new Function('require','module','exports',code)(name=>{
    if(name==='react')return hooks;
    if(name==='./api')return {api:{healthObservations:fetchPage,ignoreSource:async()=>{},healthObservationHistory:fetchHistory}};
    if(name==='./chrome')return {Sidebar(){}};
    if(name==='./ProfileSource')return {ProfileSource(){}};
    if(name==='./HealthObservationEditor')return {HealthObservationEditor(){}};
    return require(name);
  },module,module.exports);
  const expand=node=>{if(Array.isArray(node))return node.map(expand);if(!node||typeof node!=='object')return node;if(typeof node.type==='function'&&['HealthEntry','HealthHistory'].includes(node.type.name))return expand(node.type(node.props));return {...node,props:{...node.props,children:expand(node.props?.children)}};};
  const render=()=>{index=0;const tree=expand(module.exports.HealthPage({recentConversation:null}));while(effects.length)effects.shift()();return tree;};
  const nodes=node=>!node||typeof node!=='object'?[]:[node,...[node.props?.children].flat(Infinity).flatMap(nodes)];
  const settle=async()=>{await new Promise(r=>setImmediate(r));return nodes(render());};
  const click=async label=>{const button=nodes(render()).find(n=>n.type==='button'&&[n.props.children].flat(Infinity).join('').includes(label));assert.ok(button,`button ${label}`);await button.props.onClick?.();render();};
  const dispose=()=>{for(const slot of slots)slot?.cleanup?.();};
  return {render,nodes,settle,click,callbacks,dispose};
}
const record={id:'e-one',subject:'self',metric:'Gewicht',value:'072,50',unit:'kg',observed_at:'2023-07-02T09:30:00+02:00',note:'',recorded_at:'2026-10-09T09:00:00Z',status:'current',support_fingerprint:'a'.repeat(64)};
const result=(items,next_cursor=null)=>({items,next_cursor,scanned_sources:items.length,invalid_sources:0,complete:!next_cursor});

test('entry shows literal original time/value and offers readonly original plus explicit correction',async()=>{
  const ui=await page(async()=>result([record]));ui.render();const tree=await ui.settle();
  assert.ok(tree.some(n=>n.type==='time'&&n.props.dateTime===record.observed_at));
  assert.ok(tree.some(n=>n.type?.name==='ProfileSource'&&n.props.id===record.id&&n.props.readOnly===true));
  await ui.click('Korrigieren');
  assert.ok(ui.nodes(ui.render()).some(n=>n.type?.name==='HealthObservationEditor'&&n.props.observation.id===record.id));
  ui.dispose();
});

test('failed refresh clears formerly active records instead of showing stale health data',async()=>{
  let fail=false;const ui=await page(async()=>{if(fail)throw new Error('offline');return result([record]);});
  ui.render();await ui.settle();fail=true;await ui.click('Neu laden');const tree=await ui.settle();
  assert.equal(tree.some(n=>n.type==='time'),false);assert.ok(tree.some(n=>n.props?.role==='alert'));
  ui.dispose();
});

test('empty bounded page still offers continuation to older measurements',async()=>{
  const calls=[];const ui=await page(async cursor=>{calls.push(cursor);return cursor ? result([record]) : result([],'next');});
  ui.render();await ui.settle();await ui.click('Ältere Angaben');await ui.settle();
  assert.deepEqual(calls,[null,'next']);assert.ok(ui.nodes(ui.render()).some(n=>n.type==='time'));
  ui.dispose();
});

test('late older-page response cannot replace a freshly reloaded source set',async()=>{
  let count=0,finishOld;const ui=await page(async cursor=>{if(cursor)return new Promise(r=>finishOld=r);return ++count===1 ? result([record],'next') : result([]);});
  ui.render();await ui.settle();await ui.click('Ältere Angaben');await ui.click('Neu laden');await ui.settle();
  finishOld(result([record]));await ui.settle();assert.equal(ui.nodes(ui.render()).some(n=>n.type==='time'),false);
  ui.dispose();
});


test('history is visibly a loaded snapshot and explicit refresh replaces stale current labels',async()=>{
  let count=0;
  const ui=await page(async()=>result([record]),async()=>result([{...record,status:++count===1 ? 'current' : 'excluded'}]));
  ui.render();await ui.settle();await ui.click('Fassungsverlauf öffnen');await ui.settle();
  await ui.click('Fassungen neu prüfen');await ui.settle();
  assert.equal(count,2);
  assert.ok(ui.nodes(ui.render()).some(n=>n.type==='span'&&n.props.children==='Ausgeschlossen'));
  assert.equal(ui.nodes(ui.render()).some(n=>n.type==='span'&&n.props.children==='Aktuell beim Abruf'),false);
  ui.dispose();
});
