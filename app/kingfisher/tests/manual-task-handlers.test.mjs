import {createServer} from 'vite';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const root=fileURLToPath(new URL('..',import.meta.url));
const source=readFileSync(root+'/src/App.tsx','utf8');
test('a status retry cannot submit a simultaneously open new task draft', async()=>{
const oldWindow=globalThis.window,oldDriver=globalThis.__driver;
const server=await createServer({cacheDir:`/private/tmp/kingfisher-ui-test-cache-${process.pid}-manual-task-handlers.test`,root,configFile:false,plugins:[{name:'synthetic-task-hooks',enforce:'pre',resolveId(id){if(id==='virtual:task-review-hooks')return '\0'+id;},load(id){if(id==='\0virtual:task-review-hooks')return `export const useState=(...a)=>globalThis.__driver.state(...a);export const useRef=(...a)=>globalThis.__driver.ref(...a);export const useEffect=()=>{};export const useMemo=f=>f();`;},transform(code,id){if(id.endsWith('/src/App.tsx'))return source.replace('from "react"','from "virtual:task-review-hooks"')+'\nexport {Tasks};';}}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
function nodes(n, predicate, out=[]) {if(!n||typeof n!=='object')return out;if(predicate(n))out.push(n);for(const c of [n.props?.children].flat(10))nodes(c,predicate,out);return out;}
function text(n){return !n?'':typeof n==='object'?[n.props?.children].flat(10).map(text).join(''):String(n);}
try {
 globalThis.window={location:{search:'',href:'http://synthetic/vorhaben',pathname:'/vorhaben'},history:{replaceState(){}}};
 const {Tasks}=await server.ssrLoadModule('/src/App.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 const values=[],refs=[];let si=0,ri=0,creates=0;const d={state(initial){const i=si++;if(!(i in values))values[i]=typeof initial==='function'?initial():initial;return[values[i],v=>{values[i]=typeof v==='function'?v(values[i]):v;}];},ref(initial){const i=ri++;return refs[i]??=( {current:initial});},render(){si=ri=0;globalThis.__driver=d;return Tasks({recentConversation:null});}};
 api.completeTask=async()=>{throw Error('synthetic failure');};api.addTask=async p=>{creates++;return{id:'new-task',...p};};api.tasks=async()=>({tasks:[],total:0,stand:'synthetic',next_cursor:null,limit:50});
 let tree=d.render();const pageSlot=values.findIndex(v=>v && typeof v==='object' && 'selectionKey' in v);assert.notEqual(pageSlot,-1);values[pageSlot]={...values[pageSlot],selectionKey:JSON.stringify({view:'mine',projectId:'',q:''}),tasks:[{id:'existing-task',title:'Existing',status:'open'}]};tree=d.render();
 nodes(tree,n=>n.type==='button'&&text(n)==='Aufgabe')[0].props.onClick();tree=d.render();
 const form=nodes(tree,n=>n.type==='form'&&n.props.className==='task-create')[0];nodes(form,n=>n.type==='input')[0].props.onChange({target:{value:'Unsubmitted new draft'}});tree=d.render();
 nodes(tree,n=>n.type==='button'&&text(n)==='Zur Prüfung')[0].props.onClick();tree=d.render();
 assert.equal(nodes(tree,n=>n.type?.name==='ProjectControls').length,1,'project creation remains mounted while the global review is open');
 nodes(tree,n=>n.type==='button'&&text(n)==='Aufgabe')[0].props.onClick();tree=d.render();
 assert.equal(nodes(tree,n=>n.type==='section'&&n.props.className==='task-table')[0].props.hidden,false,'the primary action reopens an existing draft instead of staying in the review panel');
 assert.equal(nodes(tree,n=>n.type==='form'&&n.props.className==='task-create').flatMap(f=>nodes(f,n=>n.type==='input'))[0].props.value,'Unsubmitted new draft');
 await nodes(tree,n=>n.type?.name==='TaskRow')[0].props.onComplete();tree=d.render();
 const retry=nodes(tree,n=>n.type==='button'&&text(n)==='Wiederholen')[0];assert.ok(retry);assert.match(text(tree),/Aufgabenstatus konnte nicht gespeichert/);
 // HTML form association determines which real handler the button invokes.
 assert.equal(retry.props.type,'button');assert.equal(retry.props.form,undefined);
 if(retry.props.type==='submit')await nodes(tree,n=>n.type==='form'&&n.props.id===retry.props.form)[0].props.onSubmit({preventDefault(){}});
 else retry.props.onClick?.();
 assert.equal(creates,0);
 assert.equal(nodes(d.render(),n=>n.type==='form'&&n.props.className==='task-create').flatMap(f=>nodes(f,n=>n.type==='input'))[0].props.value,'Unsubmitted new draft');
} finally {globalThis.window=oldWindow;globalThis.__driver=oldDriver;await server.close();}
});
