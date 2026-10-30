import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';
const server=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),cacheDir:testCache('procedure-review'),plugins:[{
 name:'procedure-hooks',enforce:'pre',resolveId(id){if(id==='virtual:procedure-hooks')return '\0'+id;},
 load(id){if(id==='\0virtual:procedure-hooks')return `export const useState=(...a)=>globalThis.__procedureDriver.state(...a);export const useRef=(...a)=>globalThis.__procedureDriver.ref(...a);export const useEffect=(...a)=>globalThis.__procedureDriver.effect(...a);`;},
 transform(code,id){if(['/src/ProcedureSettings.tsx','/src/Einstellungen/Aufklapp.tsx'].some(p=>id.endsWith(p)))return code.replace(/from (["'])react\1/,'from "virtual:procedure-hooks"');}
}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {ProcedureSettings}=await server.ssrLoadModule('/src/ProcedureSettings.tsx');
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);for(const c of [n.props?.children].flat(30))nodes(c,p,out);return out;}
const text=n=>n==null?'':typeof n==='object'?[n.props?.children].flat(30).map(text).join(''):String(n);
const tick=async()=>{for(let i=0;i<4;i++)await new Promise(setImmediate);};
function driver(Component,props={}){const states=[],refs=[],effects=[],pending=[];let s=0,r=0,e=0;
 const d={props,state(v){const i=s++;if(!(i in states))states[i]=typeof v==='function'?v():v;return[states[i],n=>states[i]=typeof n==='function'?n(states[i]):n];},ref(v){return refs[r++]??={current:v};},effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},render(){s=r=e=0;globalThis.__procedureDriver=d;return Component(d.props);},run(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(x=>x.cleanup?.());delete globalThis.__procedureDriver;}};return d;}
const item=id=>({id,name:id,title:'Gleicher Titel',description:'Eine künstliche Beschreibung.',area:'mail',version:1,state:'pending',current:true,triggers:['zunft'],positive:'Zunftmail prüfen',negative:'Private Mail',checks:{structure:true,routing_examples:true,human_review_required:true}});
const detail=id=>({...item(id),steps:[`Nur Schritte von ${id}`],sources:{},markdown:'# Test'});
async function fixture(search,run){const old={window:globalThis.window,fetch:globalThis.fetch,raf:globalThis.requestAnimationFrame,caf:globalThis.cancelAnimationFrame};
 const events=new Map(),calls=[];let failDetail=false;
 globalThis.window={location:{search},addEventListener(n,fn){events.set(n,fn);},removeEventListener(n){events.delete(n);}};
 globalThis.requestAnimationFrame=()=>1;globalThis.cancelAnimationFrame=()=>{};
 globalThis.fetch=async(path)=>{calls.push(String(path));return new Response(JSON.stringify(path==='/api/v1/procedures'?{items:['a','b','c'].map(item),core:[]}:failDetail?{detail:'Künstlich nicht erreichbar'}:detail(String(path).split('/').at(-1))),{status:path==='/api/v1/procedures'||!failDetail?200:404});};
 const d=driver(ProcedureSettings);
 try{d.render();d.run();await tick();d.render();d.run();await run({d,events,calls,fail(v){failDetail=v;}});}
 finally{d.close();globalThis.window=old.window;globalThis.fetch=old.fetch;globalThis.requestAnimationFrame=old.raf;globalThis.cancelAnimationFrame=old.caf;}
}
const rows=d=>nodes(d.render(),n=>n.type?.name==='ProcedureRow');

test('same titles select only the requested id and read its actual detail',()=>fixture('?ablauf=b',async({d,calls})=>{
 const list=rows(d);assert.deepEqual(list.map(n=>n.props.targeted),[false,true,false]);
 const row=driver(list[1].type,list[1].props);
 try{assert.equal(row.render().props.open,true);row.run();await tick();const tree=row.render();
  assert.match(text(tree),/Nur Schritte von b/);assert.doesNotMatch(text(tree),/Nur Schritte von a/);
  assert.equal(nodes(tree,n=>n.type==='button'&&text(n)==='Geprüft übernehmen')[0].props.disabled,false);
  assert.deepEqual(calls,['/api/v1/procedures','/api/v1/procedures/b']);
 }finally{row.close();}
}));
test('ordinary settings remain compact without a target',()=>fixture('',async({d,calls})=>{
 assert.ok(rows(d).every(n=>n.props.targeted===false));assert.deepEqual(calls,['/api/v1/procedures']);
}));
test('an absent id is explained without choosing another procedure or fetching an unknown path',()=>fixture('?ablauf=missing',async({d,calls})=>{
 assert.match(text(d.render()),/Dieser Ablauf ist nicht mehr verfügbar/);
 assert.ok(rows(d).every(n=>n.props.targeted===false));assert.deepEqual(calls,['/api/v1/procedures']);
}));
test('a second target on the same settings page reacts to browser navigation',()=>fixture('?ablauf=b',async({d,events})=>{
 globalThis.window.location.search='?ablauf=c';events.get('popstate')?.();
 assert.deepEqual(rows(d).map(n=>n.props.targeted),[false,false,true]);
}));
test('detail errors cannot expose acceptance and retry rereads the selected id',()=>fixture('?ablauf=b',async({d,fail,calls})=>{
 const list=rows(d),row=driver(list[1].type,list[1].props);
 try{fail(true);row.render();row.run();await tick();let tree=row.render();
  assert.match(text(tree),/Künstlich nicht erreichbar/);assert.equal(nodes(tree,n=>n.type==='button'&&text(n)==='Geprüft übernehmen').length,0);
  fail(false);nodes(tree,n=>n.type==='button'&&text(n)==='Erneut laden')[0].props.onClick();row.render();row.run();await tick();tree=row.render();
  assert.match(text(tree),/Nur Schritte von b/);assert.ok(calls.filter(p=>p==='/api/v1/procedures/b').length===2);
 }finally{row.close();}
}));

test('a new requested child reopens a manually closed parent without remounting its content',async()=>{
 const {Aufklapp}=await server.ssrLoadModule('/src/Einstellungen/Aufklapp.tsx');
 const d=driver(Aufklapp,{id:'ablaeufe',titel:'Bewährte Abläufe',satz:'Prüfen',offen:true,sprungZiel:'a',children:'Beibehaltener Inhalt'});
 try{d.render();d.run();let tree=d.render();nodes(tree,n=>n.type==='summary')[0].props.onClick({preventDefault(){}});
  assert.equal(d.render().props.open,false);
  d.props={...d.props,sprungZiel:'b'};d.render();d.run();tree=d.render();
  assert.equal(tree.props.open,true);assert.match(text(tree),/Beibehaltener Inhalt/);
 }finally{d.close();}
});

test('a delayed native close event cannot override a newer requested child',async()=>{
 const {Aufklapp}=await server.ssrLoadModule('/src/Einstellungen/Aufklapp.tsx');
 const d=driver(Aufklapp,{id:'ablaeufe',titel:'Abläufe',satz:'Prüfen',offen:true,sprungZiel:'a',children:'Inhalt'});
 try{d.render();d.run();let tree=d.render();
  nodes(tree,n=>n.type==='summary')[0].props.onClick?.({preventDefault(){}});
  d.props={...d.props,sprungZiel:'b'};d.render();d.run();tree=d.render();
  const stale={open:false};tree.props.onToggle({target:stale,currentTarget:stale});
  assert.equal(d.render().props.open,true,'alte Schließmeldung darf den neuen Sprung nicht zurücknehmen');
 }finally{d.close();}
});
