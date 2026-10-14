import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
const server=await createServer({cacheDir:`/private/tmp/kingfisher-documents-cache-${process.pid}`,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'document-hooks',enforce:'pre',resolveId(id){if(id==='virtual:document-hooks')return '\0'+id;},load(id){if(id==='\0virtual:document-hooks')return 'export const useState=(...a)=>globalThis.__docDriver.state(...a);export const useRef=(...a)=>globalThis.__docDriver.ref(...a);export const useEffect=(...a)=>globalThis.__docDriver.effect(...a);export const useMemo=fn=>fn();';},transform(code,id){if(id.endsWith('/src/MemoryFolders.tsx')||id.endsWith('/src/useWorkspaceMemoryView.ts'))return code.replace(/from (['"])react\1/,'from "virtual:document-hooks"');}}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
globalThis.PopStateEvent=class extends Event {};
const {MemoryFolders,SourceFolderAssignment}=await server.ssrLoadModule('/src/MemoryFolders.tsx');
const {workspaceViewApi}=await server.ssrLoadModule('/src/workspaceViewApi.ts');
const {memoryProfileHref,rememberMemoryPresentation,readMemoryViewPosition}=await server.ssrLoadModule('/src/MemoryViewState.ts');
const {navigate}=await server.ssrLoadModule('/src/ui.ts');
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);[n.props?.children].flat(30).forEach(c=>nodes(c,p,out));return out;}
function text(n){return n==null?'':typeof n==='object'?[n.props?.children].flat(30).map(text).join(''):String(n);}
function button(tree,label){const node=nodes(tree,n=>n.type==='button'&&text(n)===label)[0];assert.ok(node,`button ${label}`);return node;}
function driver(render){const states=[],refs=[],effects=[],pending=[];let s,r,e;return {state(initial){const i=s++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial;return [states[i],v=>states[i]=typeof v==='function'?v(states[i]):v];},ref(initial){return refs[r++]??(refs[r-1]={current:initial});},effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},render(){s=r=e=0;globalThis.__docDriver=this;return render();},flush(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(effect=>effect.cleanup?.());delete globalThis.__docDriver;}};}
async function tick(d){d.render();d.flush();await new Promise(setImmediate);d.render();d.flush();await new Promise(setImmediate);return d.render();}
const folders=[{id:'root',kind:'folder',revision:1,data:{name:'Akten',parent_id:null}},{id:'nested',kind:'folder',revision:1,data:{name:'Unterordner',parent_id:'root'}}];
function page(offset=0,overrides={}){return {items:[{id:`note:current-${offset}`,kind:'note',title:`Aktuelles Dokument ${offset}`,preview:'Kurzer Inhalt',folder_id:'nested',source_folder_revision:1,project_id:'closed',project_name:'Abgeschlossen',project_area:'health',source_areas:['work'],revision:2}],total:64,limit:25,offset,has_more:offset<50,options:{folders,projects:[{id:'closed',name:'Abgeschlossen',status:'done'}],source_areas:[{id:'work',label:'Arbeit / Projekte'}],project_areas:['health']},...overrides};}
async function scenario(run){const old={window:globalThis.window,document:globalThis.document,fetch:globalThis.fetch,overview:workspaceViewApi.overview};const events=new Map(),calls=[];let read=async params=>page(Number(params.get('offset')??0));
 const target={location:{pathname:'/memory',search:'?tab=documents'},scrollX:0,scrollY:0,history:{state:{},replaceState(state){this.state=state;},pushState(state,_,path){this.state=state;const u=new URL(path,'https://synthetic.test');target.location={pathname:u.pathname,search:u.search};}},addEventListener:(id,fn)=>events.set(id,fn),removeEventListener:id=>events.delete(id),dispatchEvent:e=>events.get(e.type)?.(e)};
 globalThis.window=target;globalThis.document={querySelector:()=>null};globalThis.fetch=async url=>{assert.match(url,/^\/api\/v1\/workspace-documents\?/);const params=new URL(url,'https://synthetic.test').searchParams;calls.push(params);return new Response(JSON.stringify(await read(params)),{status:200});};workspaceViewApi.overview=async()=>({folders:[],source_folders:[],organisation_groups:[],places:[],avatars:[],online:{logos:false,maps:false},online_revision:0});
 let d=driver(()=>MemoryFolders());try{await run({d,calls,target,events,setRead:fn=>{read=fn;},remount:()=>{d.close();d=driver(()=>MemoryFolders());return d;}});}finally{d.close();Object.assign(globalThis,{window:old.window,document:old.document,fetch:old.fetch});workspaceViewApi.overview=old.overview;}}

test('documents read full server pages, send all filters and reset offset on search/folder change',()=>scenario(async({d,calls})=>{
 let tree=await tick(d);assert.match(text(tree),/64/);button(tree,'Nächste Seite').props.onClick();tree=await tick(d);assert.equal(calls.at(-1).get('offset'),'25');assert.match(text(tree),/Aktuelles Dokument 25/);
 nodes(tree,n=>n.type==='input'&&n.props.type==='search')[0].props.onChange({target:{value:'Straße %_'}});tree=await tick(d);assert.equal(calls.at(-1).get('q'),'Straße %_');assert.equal(calls.at(-1).get('offset'),'0');
 button(tree,'Akten →').props.onClick();tree=await tick(d);assert.equal(calls.at(-1).get('folder_id'),'root');
 const selects=nodes(tree,n=>n.type==='select');selects[0].props.onChange({target:{value:'closed'}});selects[1].props.onChange({target:{value:'work'}});selects[2].props.onChange({target:{value:'health'}});tree=await tick(d);assert.equal(calls.at(-1).get('project_id'),'closed');assert.equal(calls.at(-1).get('source_area'),'work');assert.equal(calls.at(-1).get('project_area'),'health');assert.match(text(tree),/Gesundheit/);assert.match(text(tree),/Arbeit \/ Projekte/);assert.doesNotMatch(text(tree),/geladenen Ausschnitt|ersten 25/);
}));
test('source to profile and return retains folder, query, filters and page but reads current sources',()=>scenario(async({d,calls,target,remount,setRead})=>{
 rememberMemoryPresentation('folders',{selected:'root',project:'closed',area:'health',sourceArea:'work',sourceListOpen:true,q:'Übergabe',offset:50,limit:25});d=remount();let tree=await tick(d);assert.equal(calls.at(-1).get('offset'),'50');assert.equal(calls.at(-1).get('q'),'Übergabe');
 navigate(memoryProfileHref('/memory/akte/person%3Aone'));navigate('/memory?tab=documents');assert.equal(readMemoryViewPosition().folders.offset,50);setRead(()=>page(50,{items:[],total:0,has_more:false}));d=remount();tree=await tick(d);assert.equal(nodes(tree,n=>n.props?.['data-memory-row']).length,0);assert.equal(calls.at(-1).get('q'),'Übergabe');assert.doesNotMatch(JSON.stringify(target.history.state),/Kurzer Inhalt|Aktuelles Dokument|revision/);
}));
test('slow prior page cannot replace current filter result and failures clear stale rows',()=>scenario(async({d,setRead})=>{
 let tree=await tick(d),finish;setRead(()=>new Promise(resolve=>{finish=resolve;}));button(tree,'Nächste Seite').props.onClick();tree=d.render();d.flush();assert.equal(tree.props['data-memory-loading'],true);
 setRead(()=>page(0,{items:[{...page().items[0],title:'Neuer Suchtreffer'}]}));nodes(d.render(),n=>n.type==='input'&&n.props.type==='search')[0].props.onChange({target:{value:'neu'}});tree=await tick(d);finish(page(25));tree=await tick(d);assert.match(text(tree),/Neuer Suchtreffer/);assert.doesNotMatch(text(tree),/Aktuelles Dokument 25/);
 setRead(()=>{throw Error('offline');});button(tree,'Nächste Seite').props.onClick();tree=await tick(d);assert.equal(tree.props['data-memory-loading'],false);assert.match(text(tree),/nicht erreichbar/);assert.equal(nodes(tree,n=>n.props?.['data-memory-row']).length,0);setRead(()=>page(25));button(tree,'Erneut laden').props.onClick();tree=await tick(d);assert.match(text(tree),/Aktuelles Dokument 25/);
}));
test('folder history validates pagination bounds and whitelists fields',()=>scenario(async({target})=>{
 for(const folders of [{offset:-1},{offset:1.5},{offset:Infinity},{limit:101},{q:'x'.repeat(201)}]){target.history.state={kingfisherMemoryView:{path:'/memory?tab=documents',folders:{selected:null,project:'',area:'',...folders}}};assert.equal(readMemoryViewPosition(),null);}
 target.history.state={kingfisherMemoryView:{path:'/memory?tab=documents',folders:{selected:null,project:'',area:'',q:'Übergabe',offset:25,limit:25,body:'secret',response:page(),revision:999}}};assert.deepEqual(Object.keys(readMemoryViewPosition().folders).sort(),['area','limit','offset','project','q','selected','sourceArea','sourceListOpen']);
}));

test('background metadata refresh retains mounted source rows until the current result settles',()=>scenario(async({d,events,setRead})=>{
 let tree=await tick(d),finish;setRead(()=>new Promise(resolve=>{finish=resolve;}));events.get('workspace-view-changed')();tree=d.render();d.flush();assert.equal(tree.props['data-memory-loading'],true);assert.equal(nodes(tree,n=>n.props?.['data-memory-row']).length,1,'background read keeps an opened original mounted');finish(page(0,{items:[],total:0,has_more:false}));tree=await tick(d);assert.equal(nodes(tree,n=>n.props?.['data-memory-row']).length,0,'withdrawn source disappears after current read');
}));


test('source assignment builds complete folder choices only after its panel is opened',()=>scenario(async()=>{
 const many=Array.from({length:2001},(_,i)=>({id:`folder-${i}`,kind:'folder',revision:1,data:{name:`Ordner ${i}`,parent_id:null}}));const d=driver(()=>SourceFolderAssignment({sourceId:'note:one',folders:many,initialRecord:{kind:'source_folder',id:'note:one',revision:2,data:{folder_id:'folder-2000'}}}));
 try{let tree=await tick(d);assert.equal(nodes(tree,n=>n.type==='select').length,0,'closed source panels do not multiply a large folder tree');tree.props.onToggle({currentTarget:{open:true}});tree=await tick(d);assert.equal(nodes(tree,n=>n.type==='option').length,2002);assert.match(text(tree),/Ordner 2000/);}finally{d.close();}
}));
