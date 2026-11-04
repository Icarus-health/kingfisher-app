import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Execute the actual standalone recovery page's controller. This is a DOM
// boundary unit test, not a browser/visual acceptance or a live app request.
const source=readFileSync(new URL('../../../sidecar/icarus_memory/restore_inspection.py',import.meta.url),'utf8');
const script=source.match(/<script>([\s\S]*?)<\/script>/)[1];
class Element {
  constructor(){this.children=[];this.textContent='';this.disabled=false;this.hidden=false;this.value='';}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=[...children];}
  get options(){return this.children;}
}
function page(reply,{status}={}){
  const elements=new Map(),calls=[];
  const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  vm.runInNewContext(script,{document:{getElementById:get,createElement:()=>new Element()},fetch:async(url,options)=>{
    calls.push({url,options});
    if(url.endsWith('/status'))return status?await status():{ok:true,json:async()=>({stores:['tasks.sqlite3','procedures.sqlite3']})};
    return reply(url,options);
  }});
  return {get,calls};
}
function text(element){return element.textContent+' '+element.children.map(text).join(' ');}
const report={restored:{files:[{name:'tasks.sqlite3',status:'verified'}]},comparison_groups:[],unresolved:['current_authority_unverified']};

test('preflight runs only on explicit click and does not offer an activation from readable data',async()=>{
  const p=page(async()=>({ok:true,json:async()=>report}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(p.calls.length,1);
  await p.get('check').onclick();
  assert.equal(p.calls[1].url,'/api/v1/recovery/preflight');
  assert.equal(p.calls[1].options.method,'POST');
  assert.equal(p.calls[1].options.body,'{}');
  assert.match(p.get('check-status').textContent,/1 Bereiche lesbar/);
  assert.match(text(p.get('result')),/Spätere Änderungen bleiben ungeklärt/);
  assert.equal(p.get('check').disabled,false);
});

test('unavailable protection or failed request hides old results and leaves a retry',async()=>{
  const p=page(async()=>({ok:false,status:503}));
  p.get('result').append(Object.assign(new Element(),{textContent:'stale comparison'}));
  await p.get('check').onclick();
  assert.equal(p.get('result').hidden,true);
  assert.doesNotMatch(text(p.get('result')),/stale comparison/);
  assert.match(p.get('check-status').textContent,/Zugang.*nicht eingerichtet/);
  assert.equal(p.get('check').disabled,false);
});

test('changed input shows uncertainty rather than reporting a finished comparison',async()=>{
  const p=page(async()=>({ok:true,json:async()=>({...report,unresolved:['changed_during_read']})}));
  await p.get('check').onclick();
  assert.match(p.get('check-status').textContent,/ungeklärt/);
  assert.doesNotMatch(p.get('check-status').textContent,/Bereiche lesbar/);
});

test('busy preflight cannot be repeated before its result arrives',async()=>{
  let finish;const promise=new Promise(resolve=>finish=resolve);
  const p=page(async()=>{await promise;return {ok:true,json:async()=>report};});
  const pending=p.get('check').onclick();
  assert.equal(p.get('check').disabled,true);
  assert.match(p.get('check-status').textContent,/wird gelesen/);
  finish();await pending;
  assert.equal(p.get('check').disabled,false);
});

test('record loading locks the data selection until the corresponding result returns',async()=>{
  let finish;const promise=new Promise(resolve=>finish=resolve);
  const p=page(async()=>{await promise;return {ok:true,json:async()=>({items:[{title:'Synthetic task'}],next_offset:50})};});
  await new Promise(resolve=>setImmediate(resolve));
  p.get('stores').value='tasks.sqlite3';
  const pending=p.get('load').onclick();
  assert.equal(p.get('stores').disabled,true);
  finish();await pending;
  assert.equal(p.get('stores').disabled,false);
  assert.equal(p.get('next').disabled,false);
  assert.match(p.get('records').textContent,/Synthetic task/);
});

test('slow initial inventory cannot start an empty record request or overlap a later request',async()=>{
  let ready,complete;
  const inventory=new Promise(resolve=>ready=resolve),records=new Promise(resolve=>complete=resolve);
  const p=page(async()=>{await records;return {ok:true,json:async()=>({items:[{title:'Current record'}],next_offset:null})};},
    {status:async()=>{await inventory;return {ok:true,json:async()=>({stores:['tasks.sqlite3']})};}});
  assert.equal(p.get('load').disabled,true);
  await p.get('load').onclick();
  assert.equal(p.calls.length,1);
  ready();await new Promise(resolve=>setImmediate(resolve));p.get('stores').value='tasks.sqlite3';
  const pending=p.get('load').onclick();
  await p.get('load').onclick();
  assert.equal(p.calls.length,2);
  complete();await pending;
  assert.match(p.get('records').textContent,/Current record/);
});

test('incompatible historical records report a reading problem rather than an ongoing preflight',async()=>{
  const p=page(async()=>({ok:false,status:409}));
  await new Promise(resolve=>setImmediate(resolve));p.get('stores').value='tasks.sqlite3';
  await p.get('load').onclick();
  assert.match(p.get('record-status').textContent,/Datenbereich.*nicht lesen/);
  assert.doesNotMatch(p.get('record-status').textContent,/Prüfung läuft bereits/);
  assert.equal(p.get('load').disabled,false);
});
