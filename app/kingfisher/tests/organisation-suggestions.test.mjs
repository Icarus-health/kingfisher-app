import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
const server=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),cacheDir:`/private/tmp/kf-org-ui-${process.pid}`,plugins:[{name:'org-hooks',enforce:'pre',resolveId(id){if(id==='virtual:org-hooks')return '\0'+id;},load(id){if(id==='\0virtual:org-hooks')return 'export const useState=(...a)=>globalThis.__orgDriver.state(...a);export const useRef=(...a)=>globalThis.__orgDriver.ref(...a);export const useEffect=(...a)=>globalThis.__orgDriver.effect(...a);';},transform(code,id){if(['/src/OrganisationGroups.tsx','/src/useWorkspaceMemoryView.ts'].some(path=>id.endsWith(path)))return code.replace(/from (['"])react\1/,'from "virtual:org-hooks"');}}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {OrganisationGroups}=await server.ssrLoadModule('/src/OrganisationGroups.tsx');
const {workspaceViewApi}=await server.ssrLoadModule('/src/workspaceViewApi.ts');
const {organisationSuggestionsApi}=await server.ssrLoadModule('/src/organisationSuggestionsApi.ts');
function nodes(node,predicate,out=[]){if(!node||typeof node!=='object')return out;if(predicate(node))out.push(node);[node.props?.children].flat(30).forEach(child=>nodes(child,predicate,out));return out;}
function text(node){return node==null?'':typeof node==='object'?[node.props?.children].flat(30).map(text).join(''):String(node);}
function button(tree,label){const result=nodes(tree,n=>n.type==='button'&&text(n)===label)[0];assert.ok(result,`button ${label}`);return result;}
function driver(render){const states=[],refs=[],effects=[],pending=[];let s,r,e;return {state(initial){const i=s++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial;return [states[i],v=>states[i]=typeof v==='function'?v(states[i]):v];},ref(initial){return refs[r++]??(refs[r-1]={current:initial});},effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},render(){s=r=e=0;globalThis.__orgDriver=this;return render();},flush(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(effect=>effect.cleanup?.());delete globalThis.__orgDriver;}};}
const snapshot={entries:[{id:'organisation:de',name:'Amazon.de'},{id:'organisation:com',name:'Amazon.com'},{id:'organisation:digital',name:'Amazon Digital Germany'}],total:3,complete:true,source_revision:'source-r1',groups_revision:'groups-r1',groups:[],dismissals:[],suggestions:[{id:'candidate',name:'Amazon',members:['organisation:de','organisation:com','organisation:digital'],reason:'Lokale Namensregel: ähnliche Namen. Keine Prüfung von Rechtsperson oder Konzernzugehörigkeit.'}]};
async function scenario(run){const previousWindow=globalThis.window,oldView={...workspaceViewApi},oldSuggestions={...organisationSuggestionsApi};const events=new Map(),confirmed=[],dismissed=[];globalThis.window={location:{search:''},addEventListener:(id,fn)=>events.set(id,fn),removeEventListener:id=>events.delete(id),dispatchEvent(){}};
 workspaceViewApi.overview=async()=>({folders:[],source_folders:[],organisation_groups:[],places:[],avatars:[],online:{logos:false,maps:false},online_revision:0});organisationSuggestionsApi.overview=async()=>snapshot;organisationSuggestionsApi.confirm=async body=>{confirmed.push(body);return {id:'stable',kind:'organisation_group',revision:1,data:{name:body.name,members:body.members}};};organisationSuggestionsApi.dismiss=async(...args)=>{dismissed.push(args);return {id:'candidate',revision:1,data:{dismissed:true}};};
 const d=driver(()=>OrganisationGroups({entries:[{id:'organisation:de',name:'Amazon.de'}]}));try{d.render();d.flush();await new Promise(setImmediate);d.render();d.flush();await new Promise(setImmediate);await run({d,confirmed,dismissed});}finally{d.close();globalThis.window=previousWindow;Object.assign(workspaceViewApi,oldView);Object.assign(organisationSuggestionsApi,oldSuggestions);}}
test('automatic proposal explains local names and edits full membership before explicit confirmation',()=>scenario(async({d,confirmed})=>{
 assert.match(text(d.render()),/ähnliche Namen/);assert.match(text(d.render()),/Konzernzugehörigkeit/);assert.match(text(d.render()),/Amazon Digital Germany/);
 button(d.render(),'Vorschlag bearbeiten').props.onClick();assert.equal(confirmed.length,0);
 nodes(d.render(),n=>n.type==='input'&&n.props.type!=='checkbox')[0].props.onChange({target:{value:'Meine Einkäufe'}});
 const digital=nodes(d.render(),n=>n.type==='label'&&text(n)==='Amazon Digital Germany')[0];nodes(digital,n=>n.type==='input')[0].props.onChange({target:{checked:false}});
 nodes(d.render(),n=>n.type==='form')[0].props.onSubmit({preventDefault(){}});await new Promise(setImmediate);assert.equal(confirmed.length,0);
 button(d.render(),'Gruppierung bestätigen').props.onClick();button(d.render(),'Gruppierung bestätigen').props.onClick();await new Promise(setImmediate);
 assert.equal(confirmed.length,1);assert.deepEqual(confirmed[0].members,['organisation:de','organisation:com']);assert.equal(confirmed[0].name,'Meine Einkäufe');assert.equal(confirmed[0].source_revision,'source-r1');
}));
test('rejected suggestion preserves explicit dismissal and failed confirmation preserves the draft',()=>scenario(async({d,dismissed})=>{
 button(d.render(),'Vorschlag ablehnen').props.onClick();await new Promise(setImmediate);assert.equal(dismissed.length,1);
 button(d.render(),'Vorschlag bearbeiten').props.onClick();nodes(d.render(),n=>n.type==='form')[0].props.onSubmit({preventDefault(){}});await new Promise(setImmediate);
 organisationSuggestionsApi.confirm=async()=>{throw Object.assign(Error('Quelle geändert'),{status:409});};button(d.render(),'Gruppierung bestätigen').props.onClick();await new Promise(setImmediate);
 assert.match(text(d.render()),/Entwurf/);assert.equal(nodes(d.render(),n=>n.type==='input'&&n.props.type!=='checkbox')[0].props.value,'Amazon');
}));
test('complete basis does not mount one logo editor per organisation while browsing',()=>scenario(async({d})=>{
 assert.equal(nodes(d.render(),n=>typeof n.type==='function'&&n.type.name==='MemoryAvatarEditor').length,0);
 const selector=nodes(d.render(),n=>n.type==='select')[0];assert.ok(selector);
 selector.props.onChange({target:{value:'organisation:digital'}});
 const editors=nodes(d.render(),n=>typeof n.type==='function'&&n.type.name==='MemoryAvatarEditor');
 assert.equal(editors.length,1);assert.equal(editors[0].props.id,'organisation:digital');
}));
