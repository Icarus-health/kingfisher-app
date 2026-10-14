import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('..',import.meta.url));
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);for(const c of [n.props?.children].flat(10))nodes(c,p,out);return out;}
function text(n){return n==null?'':typeof n==='object'?[n.props?.children].flat(10).map(text).join(''):String(n);}
const ready=()=>({episode_id:'e1',source_digest:'sha256:'+'b'.repeat(64),fingerprint:'a'.repeat(64),status:'ready',quotes:['Bitte prüfe die Belege.'],items:[{id:'v1',statement:'Belege prüfen',evidence:[{quote:'Bitte prüfe die Belege.'}],review_required:true}],projects:[],temporal_reason:'Historische Quelle.',detail:'Originalpassagen.'});
async function harness(run){
 const server=await createServer({root,cacheDir:`/private/tmp/kf-saved-mail-ui-${process.pid}`,configFile:false,plugins:[{name:'saved-mail-hooks',enforce:'pre',resolveId(id){if(id==='virtual:saved-mail-hooks')return '\0'+id;},load(id){if(id==='\0virtual:saved-mail-hooks')return 'export const useState=(...a)=>globalThis.__savedMailDriver.state(...a);export const useRef=(...a)=>globalThis.__savedMailDriver.ref(...a);export const useEffect=(...a)=>globalThis.__savedMailDriver.effect(...a);';},transform(code,id){if(/\/SavedMailWorkflow\.tsx$/.test(id))return code.replace(/from ["']react["']/g,'from "virtual:saved-mail-hooks"');}}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
 const oldWindow=globalThis.window,oldDriver=globalThis.__savedMailDriver;const listeners={};
 globalThis.window={addEventListener(type,fn){listeners[type]=fn;},removeEventListener(type){delete listeners[type];}};
 function driver(Component,props){const values=[],refs=[],deps=[],pending=[];let si=0,ri=0,ei=0;const d={state(initial){const i=si++;if(!(i in values))values[i]=typeof initial==='function'?initial():initial;return[values[i],v=>values[i]=typeof v==='function'?v(values[i]):v];},ref(initial){return refs[ri++]??=({current:initial});},effect(fn,next){const i=ei++;if(!deps[i]||next.some((v,j)=>v!==deps[i][j])){deps[i]=next;pending.push(fn);}},render(){si=ri=ei=0;globalThis.__savedMailDriver=d;return Component(props);},async flush(){while(pending.length)pending.shift()();await new Promise(r=>setImmediate(r));}};return d;}
 try{await run(server,driver,listeners);}finally{globalThis.window=oldWindow;globalThis.__savedMailDriver=oldDriver;await server.close();}
}
test('browsing and focus only read prepared original passages, source preparation is deliberate',()=>harness(async(server,driver,listeners)=>{
 const {SavedMailWorkflow}=await server.ssrLoadModule('/src/SavedMailWorkflow.tsx');const {savedMailWorkflowApi:api}=await server.ssrLoadModule('/src/savedMailWorkflowApi.ts');
 let reads=0,prepares=0;api.read=async()=>{reads++;return{...ready(),status:'unprepared',quotes:[],items:[]};};api.prepare=async()=>{prepares++;return ready();};
 const d=driver(SavedMailWorkflow,{episodeId:'e1',sourceDigest:ready().source_digest});d.render();await d.flush();let tree=d.render();
 assert.equal(prepares,0);assert.equal(reads,1);listeners.focus();await d.flush();tree=d.render();assert.equal(reads,2);assert.equal(prepares,0);
 nodes(tree,n=>n.type==='button'&&/Diese Mail lokal vorbereiten/.test(text(n)))[0].props.onClick();await d.flush();tree=d.render();
 assert.equal(prepares,1);assert.match(text(tree),/Bitte prüfe die Belege/);assert.match(nodes(tree,n=>n.type==='input')[0].props.value,/Aktualität der Bitte prüfen/);
}));
test('single visible confirmation sends task plus project, errors keep edited draft and retry identity',()=>harness(async(server,driver)=>{
 const {SavedMailWorkflow}=await server.ssrLoadModule('/src/SavedMailWorkflow.tsx');const {savedMailWorkflowApi:api}=await server.ssrLoadModule('/src/savedMailWorkflowApi.ts');
 api.read=async()=>ready();const calls=[];api.accept=async(...args)=>{calls.push(args);if(calls.length===1)throw Error('HTTP 500');return{title:args[2].title};};
 const d=driver(SavedMailWorkflow,{episodeId:'e1',sourceDigest:ready().source_digest});d.render();await d.flush();let tree=d.render();
 nodes(tree,n=>n.type==='input')[0].props.onChange({target:{value:'Eigene Prüfung'}});tree=d.render();nodes(tree,n=>n.type==='select')[0].props.onChange({target:{value:'new'}});tree=d.render();
 nodes(tree,n=>n.type==='input')[1].props.onChange({target:{value:'Prüfprojekt'}});tree=d.render();
 const submit=()=>nodes(d.render(),n=>n.type==='form')[0].props.onSubmit({preventDefault(){}});
 submit();await d.flush();tree=d.render();assert.match(text(tree),/Eingaben bleiben erhalten/);assert.equal(nodes(tree,n=>n.type==='input')[0].props.value,'Eigene Prüfung');assert.equal(nodes(tree,n=>n.type==='input')[1].props.value,'Prüfprojekt');
 assert.equal(calls[0][2].new_project_name,'Prüfprojekt');assert.equal(calls[0][2].due,null);assert.equal(calls[0][2].waiting_for,null);
 submit();await d.flush();tree=d.render();assert.deepEqual(calls[0],calls[1]);assert.match(text(tree),/Aufgabe gespeichert: Eigene Prüfung/);
}));
test('unverified source disables confirmation and preparation',()=>harness(async(server,driver)=>{
 const {SavedMailWorkflow}=await server.ssrLoadModule('/src/SavedMailWorkflow.tsx');const {savedMailWorkflowApi:api}=await server.ssrLoadModule('/src/savedMailWorkflowApi.ts');
 api.read=async()=>ready();const props={episodeId:'e1',sourceDigest:ready().source_digest,sourceVerified:false};const d=driver(SavedMailWorkflow,props);d.render();await d.flush();
 assert.equal(nodes(d.render(),n=>n.type==='button'&&/Aufgabe bestätigen/.test(text(n)))[0].props.disabled,true);
}));
