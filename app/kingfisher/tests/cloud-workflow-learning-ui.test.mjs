import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';

const server=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),cacheDir:testCache('cloud-workflow'),plugins:[{
 name:'workflow-hooks',enforce:'pre',resolveId(id){if(id==='virtual:workflow-hooks')return '\0'+id;},
 load(id){if(id==='\0virtual:workflow-hooks')return 'export const useState=(...a)=>globalThis.__workflowDriver.state(...a);export const useRef=(...a)=>globalThis.__workflowDriver.ref(...a);export const useEffect=(...a)=>globalThis.__workflowDriver.effect(...a);';},
 transform(code,id){if(id.endsWith('/src/CloudWorkflowLearning.tsx'))return code.replace(/from (["'])react\1/,'from "virtual:workflow-hooks"');}
}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {CloudWorkflowLearning}=await server.ssrLoadModule('/src/CloudWorkflowLearning.tsx');
const nodes=(n,p,out=[])=>{if(!n||typeof n!=='object')return out;if(p(n))out.push(n);for(const c of [n.props?.children].flat(30))nodes(c,p,out);return out;};
const text=n=>n==null?'':typeof n==='object'?[n.props?.children].flat(30).map(text).join(''):String(n);
const tick=async()=>{for(let i=0;i<5;i++)await new Promise(setImmediate);};
function driver(Component,props){const states=[],refs=[],effects=[],pending=[];let s=0,r=0,e=0;
 const d={props,state(v){const i=s++;if(!(i in states))states[i]=typeof v==='function'?v():v;return[states[i],n=>states[i]=typeof n==='function'?n(states[i]):n];},ref(v){return refs[r++]??={current:v};},effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},render(){s=r=e=0;globalThis.__workflowDriver=d;return Component(d.props);},async flush(){d.render();pending.splice(0).forEach(fn=>fn());await tick();d.render();pending.splice(0).forEach(fn=>fn());await tick();},close(){effects.forEach(x=>x.cleanup?.());delete globalThis.__workflowDriver;}};return d;}
const budget=()=>({provider:'mistral',currency:'USD',budget_id:'shared-source-budget',revision:3,price_id:'price',price_valid_until:'2026-12-01',cap_microusd:1000000,spent_microusd:200000,held_microusd:0,remaining_microusd:800000,reconciliation_required:false,ready:true,blocked_reason:null});
const status=()=>({provider:'mistral',model:'mistral-small-2603',available:true,budget:budget(),job:null,candidates:{mail:2,planning:1,analysis:0}});
const preview=()=>({preview_id:'preview-one',available:true,model:'mistral-small-2603',payload:{corrections:[{id:'c1',request:'Künstlichen Termin vorbereiten',correction:'Zuerst die Zeit prüfen.'},{id:'c2',request:'Anderer Beispielauftrag',correction:'Nur bestätigte Daten verwenden.'}],existing:[{name:'termin-pruefen',title:'Termin prüfen',description:'Katalogbeschreibung',version:2,triggers:['Termin'],contexts:['Verein']}]},budget:budget(),max_requests:2,expires_at:Date.now()/1000+600});
const job=(state='running',result=null)=>({id:'job-one',state,result});
const button=(d,label)=>nodes(d.render(),n=>n.type==='button'&&text(n)===label)[0];
const checkbox=d=>nodes(d.render(),n=>n.type==='input'&&n.props.type==='checkbox')[0];
async function fixture(run,initial=status()){
 const old={fetch:globalThis.fetch,window:globalThis.window};const events=new Map(),calls=[];let state=initial,payload=preview(),startError=null,startWait=null,refreshes=0;
 globalThis.window={addEventListener(n,f){events.set(n,f);},removeEventListener(n){events.delete(n);}};
 globalThis.fetch=async(path,init={})=>{const body=init.body?JSON.parse(init.body):null;calls.push({path,method:init.method||'GET',body});
  if(path.endsWith('/status'))return Response.json(state);
  if(path.endsWith('/preview'))return Response.json(payload);
  if(path.endsWith('/start')){if(startWait)await startWait;if(startError)return Response.json({detail:startError},{status:409});state={...state,job:job()};return Response.json({job:state.job});}
  if(path.endsWith('/revoke')){state={...state,job:job('cancelled')};return Response.json(state);}
  throw Error(`Unexpected request: ${path}`);
 };
 const d=driver(CloudWorkflowLearning,{onProposed(){refreshes++;}});
 const context={d,calls,events,setStatus(v){state=v;},setPreview(v){payload=v;},failStart(v){startError=v;},waitStart(v){startWait=v;},refreshes:()=>refreshes};
 try{await d.flush();await run(context);}finally{d.close();globalThis.fetch=old.fetch;globalThis.window=old.window;}
}
async function prepare(d){button(d,'Vorschau ansehen').props.onClick();await d.flush();}
async function consent(d){checkbox(d).props.onChange({target:{checked:true}});await d.flush();}

test('opening reads status only and preview shows every transmitted request, correction and catalog field',()=>fixture(async({d,calls})=>{
 assert.deepEqual(calls.map(c=>c.path),['/api/v1/procedure-learning/status']);
 assert.match(text(d.render()),/optional/);assert.equal(checkbox(d),undefined);
 await prepare(d);
 assert.deepEqual(calls.find(c=>c.path.endsWith('/preview')).body,{area:'mail'});
 for(const value of ['Künstlichen Termin vorbereiten','Zuerst die Zeit prüfen.','Anderer Beispielauftrag','Nur bestätigte Daten verwenden.','termin-pruefen','Katalogbeschreibung','Verein'])assert.ok(text(d.render()).includes(value),value);
 assert.match(text(d.render()),/höchstens 2/);assert.match(text(d.render()),/EU\/EFTA/);assert.match(text(d.render()),/Quellen und Abläufe/);
 assert.equal(button(d,'Mit Mistral prüfen').props.disabled,true);
 assert.equal(calls.some(c=>c.path.endsWith('/start')),false);
}));

test('explicit consent sends only the preview identity once, then polls and leaves activation separate',()=>fixture(async(ctx)=>{
 const {d,calls}=ctx;await prepare(d);await consent(d);
 let release;ctx.waitStart(new Promise(resolve=>release=resolve));
 const start=button(d,'Mit Mistral prüfen');start.props.onClick();start.props.onClick();await d.flush();
 assert.equal(calls.filter(c=>c.path.endsWith('/start')).length,1);assert.deepEqual(calls.find(c=>c.path.endsWith('/start')).body,{preview_id:'preview-one',consent:true});
 release();await d.flush();assert.match(text(d.render()),/Prüfung läuft/);assert.ok(button(d,'Prüfung abbrechen'));assert.equal(checkbox(d),undefined);
 ctx.setStatus({...status(),job:job('complete',{status:'proposed',proposal_id:'proposal-one',count:2,reused:false,synthesis:{provider:'mistral',model:'mistral-small-2603'}})});
 ctx.events.get('focus')();await d.flush();
 assert.equal(ctx.refreshes(),1);assert.match(text(d.render()),/als Vorschlag gespeichert/);assert.match(text(d.render()),/Mit Mistral entworfen/);
 assert.equal(nodes(d.render(),n=>n.type==='button'&&/übernehmen|aktivieren/i.test(text(n))).length,0);
 ctx.events.get('focus')();await d.flush();assert.equal(ctx.refreshes(),1);
}));

test('receipt refresh follows acceptance and revocation without stale inactive or authorship claims',()=>fixture(async({d,setStatus,calls})=>{
 assert.match(text(d.render()),/als Vorschlag gespeichert/);
 setStatus({...status(),job:job('complete',{status:'active',proposal_id:'proposal-one',reused:false,synthesis:{provider:'mistral',model:'mistral-small-2603'}})});
 d.props={...d.props,refreshKey:1};await d.flush();
 assert.match(text(d.render()),/Ablauf ist übernommen/);assert.doesNotMatch(text(d.render()),/Noch nicht aktiv/);
 setStatus({...status(),job:job('complete',{status:'dismissed',proposal_id:'proposal-one',reused:false,synthesis:{provider:'mistral',model:'mistral-small-2603'}})});
 d.props={...d.props,refreshKey:2};await d.flush();
 assert.match(text(d.render()),/Ablauf wird nicht verwendet/);assert.doesNotMatch(text(d.render()),/Ablauf ist übernommen|Noch nicht aktiv/);
 assert.equal(calls.filter(c=>c.path.endsWith('/start')).length,0);
},{...status(),job:job('complete',{status:'proposed',proposal_id:'proposal-one',reused:false,synthesis:{provider:'mistral',model:'mistral-small-2603'}})}));

test('remounting a reused manual procedure never claims a new inactive Mistral-authored result',async()=>{
 for(const resultStatus of ['proposed','active','dismissed'])await fixture(async({d,calls})=>{
  assert.match(text(d.render()),/vorhandener Ablauf/);assert.doesNotMatch(text(d.render()),/Mit Mistral entworfen|Noch nicht aktiv|Ein neuer/);
  if(resultStatus==='active')assert.match(text(d.render()),/Ablauf ist übernommen/);
  if(resultStatus==='dismissed')assert.match(text(d.render()),/Ablauf wird nicht verwendet/);
  assert.equal(calls.filter(c=>c.path.endsWith('/start')).length,0);
 },{...status(),job:job('complete',{status:resultStatus,proposal_id:'manual-one',reused:true})});
});

test('a withdrawn observed result refreshes the library once and removes its synthesis claim',()=>fixture(async({d,setStatus,events,refreshes})=>{
 assert.equal(refreshes(),1);
 setStatus({...status(),job:job('complete',{status:'changed'})});events.get('focus')();await d.flush();
 assert.equal(refreshes(),2);assert.match(text(d.render()),/nicht mehr verwendbar/);assert.doesNotMatch(text(d.render()),/Mit Mistral entworfen/);
 events.get('focus')();await d.flush();assert.equal(refreshes(),2);
},{...status(),job:job('complete',{status:'proposed',proposal_id:'proposal-one',reused:false,synthesis:{provider:'mistral',model:'mistral-small-2603'}})}));

test('changing area or cloud access invalidates the preview and its consent',()=>fixture(async({d,events,calls})=>{
 await prepare(d);await consent(d);
 nodes(d.render(),n=>n.type==='select')[0].props.onChange({target:{value:'planning'}});await d.flush();
 assert.equal(checkbox(d),undefined);assert.equal(button(d,'Mit Mistral prüfen'),undefined);
 await prepare(d);assert.deepEqual(calls.findLast(c=>c.path.endsWith('/preview')).body,{area:'planning'});assert.equal(checkbox(d).props.checked,false);
 await consent(d);events.get('kingfisher:cloud-access-changed')();await d.flush();assert.equal(checkbox(d),undefined);
 assert.equal(calls.filter(c=>c.path.endsWith('/start')).length,0);
}));

test('a parent library refresh invalidates prior preview and consent',()=>fixture(async({d,calls})=>{
 await prepare(d);await consent(d);d.props={...d.props,refreshKey:1};await d.flush();
 assert.equal(checkbox(d),undefined);assert.equal(button(d,'Mit Mistral prüfen'),undefined);
 assert.equal(calls.filter(c=>c.path.endsWith('/start')).length,0);
}));

test('unavailable key, exhausted shared budget and expired preview never enable a paid start',async()=>{
 for(const change of [{available:false},{budget:{...budget(),ready:false,remaining_microusd:0,blocked_reason:'budget_exhausted'}}])await fixture(async({d,setPreview,calls})=>{
  setPreview({...preview(),...change});await prepare(d);await consent(d);
  assert.equal(button(d,'Mit Mistral prüfen').props.disabled,true);
  assert.ok(nodes(d.render(),n=>n.type==='a'&&n.props.href==='/settings#ki').length);
  assert.equal(calls.filter(c=>c.path.endsWith('/start')).length,0);
 },{...status(),...change});
 await fixture(async({d,setPreview})=>{setPreview({...preview(),expires_at:1});await prepare(d);await consent(d);assert.equal(button(d,'Mit Mistral prüfen').props.disabled,true);assert.match(text(d.render()),/abgelaufen/);});
});

test('a stale-preview rejection is explained and cannot reuse prior consent',()=>fixture(async({d,failStart,calls})=>{
 await prepare(d);await consent(d);failStart('Die Grundlage hat sich geändert. Bitte eine neue Vorschau erstellen.');
 button(d,'Mit Mistral prüfen').props.onClick();await d.flush();
 assert.match(text(d.render()),/Grundlage hat sich geändert/);assert.equal(checkbox(d),undefined);
 await prepare(d);assert.equal(checkbox(d).props.checked,false);assert.equal(calls.filter(c=>c.path.endsWith('/start')).length,1);
}));

test('reopening a running job never starts it again and cancellation is sent once',()=>fixture(async({d,calls})=>{
 assert.match(text(d.render()),/Prüfung läuft/);assert.equal(calls.some(c=>c.path.endsWith('/start')),false);
 const cancel=button(d,'Prüfung abbrechen');cancel.props.onClick();cancel.props.onClick();await d.flush();
 assert.equal(calls.filter(c=>c.path.endsWith('/revoke')).length,1);assert.deepEqual(calls.find(c=>c.path.endsWith('/revoke')).body,{job_id:'job-one'});
 assert.match(text(d.render()),/abgebrochen/);assert.match(text(d.render()),/entstandene Kosten/);
},{...status(),job:job()}));

test('no-pattern, failed and interrupted jobs do not claim or activate a proposal',async()=>{
 for(const terminal of [job('complete',{status:'no_pattern'}),{...job('failed'),message:'Die Prüfung konnte nicht abgeschlossen werden.'},job('interrupted')])await fixture(async({d,calls,refreshes})=>{
  assert.equal(refreshes(),0);assert.equal(calls.some(c=>c.path.endsWith('/start')),false);
  assert.doesNotMatch(text(d.render()),/Vorschlag liegt|Noch nicht aktiv/);
  assert.match(text(d.render()),terminal.state==='complete'?/Kein neuer Ablaufvorschlag/:terminal.state==='failed'?/nicht abgeschlossen/:/unterbrochen/);
 },{...status(),job:terminal});
});

test('withdrawn proposal explains a changed foundation rather than a missing pattern',()=>fixture(async({d,refreshes})=>{
 assert.equal(refreshes(),0);assert.match(text(d.render()),/Grundlage hat sich verändert/);assert.match(text(d.render()),/nicht mehr verwendbar/);
 assert.doesNotMatch(text(d.render()),/Kein neuer Ablaufvorschlag|Noch nicht aktiv/);
},{...status(),job:job('complete',{status:'changed'})}));

test('a budget revision change disables an already consented preview before any paid call',()=>fixture(async({d,calls,setStatus})=>{
 setStatus({...status(),budget:{...budget(),revision:4}});
 // The preview read raced a shared-budget update in another settings surface.
 await prepare(d);await consent(d);
 assert.equal(button(d,'Mit Mistral prüfen').props.disabled,true);
 assert.match(text(d.render()),/Kostenstand hat sich geändert/);
 button(d,'Mit Mistral prüfen').props.onClick();await d.flush();
 assert.equal(calls.filter(c=>c.path.endsWith('/start')).length,0);
}));
