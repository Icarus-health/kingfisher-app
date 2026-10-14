import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
const server=await createServer({cacheDir:`/private/tmp/kingfisher-documents-cache-${process.pid}`,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'document-hooks',enforce:'pre',resolveId(id){if(id==='virtual:document-hooks')return '\0'+id;},load(id){if(id==='\0virtual:document-hooks')return 'export const useState=(...a)=>globalThis.__docDriver.state(...a);export const useRef=(...a)=>globalThis.__docDriver.ref(...a);export const useEffect=(...a)=>globalThis.__docDriver.effect(...a);export const useMemo=fn=>fn();';},transform(code,id){if(id.endsWith('/src/MemoryFolders.tsx')||id.endsWith('/src/useWorkspaceMemoryView.ts')||id.endsWith('/src/ProfileSource.tsx'))return code.replace(/from (['"])react\1/,'from "virtual:document-hooks"');}}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
globalThis.PopStateEvent=class extends Event {};
const {MemoryFolders,SourceFolderAssignment}=await server.ssrLoadModule('/src/MemoryFolders.tsx');
const {ProfileSource}=await server.ssrLoadModule('/src/ProfileSource.tsx');
const {api}=await server.ssrLoadModule('/src/api.ts');
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
 target.clearInterval=()=>{};
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


test('opened note follows the real folder list revision without closing and hides the older body before effects run',()=>scenario(async({d,events,setRead})=>{
 const old=api.profileSource;let reads=0,finish;let current=1;
 api.profileSource=async()=>{reads++;return current===1?{title:'Notiz',body:'Alter Notizinhalt',revision:1}:new Promise(resolve=>{finish=resolve;});};
 setRead(()=>page(0,{items:[{...page().items[0],revision:1,preview:'Alter Notizinhalt'}]}));
 let tree=await tick(d),props=nodes(tree,n=>n.type===ProfileSource)[0].props;
 const child=driver(()=>ProfileSource(props));
 try{
  let pane=await tick(child);button(pane,'Inhalt öffnen').props.onClick();pane=await tick(child);assert.match(text(pane),/Alter Notizinhalt/);assert.equal(reads,1);
  current=2;setRead(()=>page(0,{items:[{...page().items[0],revision:2,preview:'Aktueller Notizinhalt'}]}));events.get('workspace-view-changed')();tree=await tick(d);assert.match(text(tree),/Aktueller Notizinhalt/);
  props=nodes(tree,n=>n.type===ProfileSource)[0].props;pane=child.render();assert.equal(button(pane,'Inhalt schließen').props['aria-expanded'],true);assert.doesNotMatch(text(pane),/Alter Notizinhalt/,'old body is hidden before the revision read effect runs');child.flush();assert.equal(reads,2);
  finish({title:'Notiz',body:'Aktueller Notizinhalt',revision:2});pane=await tick(child);assert.match(text(pane),/Aktueller Notizinhalt/);assert.match(text(pane),/Revision 2/);assert.equal(button(pane,'Inhalt schließen').props['aria-expanded'],true);
 }finally{child.close();api.profileSource=old;}
}));

test('note revision reads discard stale in-flight replies and preserve open state through failure and retry',()=>scenario(async()=>{
 const old=api.profileSource;let props={kind:'note',id:'synthetic',sourceRevision:1};let read=async()=>({title:'Notiz',body:'Erster Inhalt',revision:1});let finishOld;api.profileSource=(...args)=>read(...args);const child=driver(()=>ProfileSource(props));
 try{let pane=await tick(child);button(pane,'Inhalt öffnen').props.onClick();pane=await tick(child);assert.match(text(pane),/Erster Inhalt/);
  read=()=>new Promise(resolve=>{finishOld=resolve;});props={...props,sourceRevision:2};child.render();child.flush();
  read=async()=>({title:'Notiz',body:'Neuester Inhalt',revision:3});props={...props,sourceRevision:3};pane=await tick(child);finishOld({title:'Notiz',body:'Verspäteter Inhalt',revision:2});pane=await tick(child);assert.match(text(pane),/Neuester Inhalt/);assert.doesNotMatch(text(pane),/Verspäteter Inhalt/);
  read=async()=>{throw Error('offline');};props={...props,sourceRevision:4};pane=await tick(child);assert.match(text(pane),/nicht verfügbar/);assert.doesNotMatch(text(pane),/Neuester Inhalt/);assert.equal(button(pane,'Inhalt schließen').props['aria-expanded'],true);read=async()=>({title:'Notiz',body:'Wieder aktueller Inhalt',revision:4});button(pane,'Erneut versuchen').props.onClick();pane=await tick(child);assert.match(text(pane),/Wieder aktueller Inhalt/);assert.match(text(pane),/Revision 4/);
 }finally{child.close();api.profileSource=old;}
}));

test('a note read newer than its list revision requests list revalidation and never displays mismatched text',()=>scenario(async()=>{
 const old=api.profileSource;let changes=0;let props={kind:'note',id:'synthetic',sourceRevision:2,onChange:()=>{changes++;}};api.profileSource=async()=>({title:'Notiz',body:'Dritter Inhalt',revision:3});const child=driver(()=>ProfileSource(props));
 try{let pane=await tick(child);button(pane,'Inhalt öffnen').props.onClick();pane=await tick(child);assert.equal(changes,1);assert.doesNotMatch(text(pane),/Dritter Inhalt/);assert.equal(button(pane,'Inhalt schließen').props['aria-expanded'],true);props={...props,sourceRevision:3};pane=await tick(child);assert.match(text(pane),/Dritter Inhalt/);
 }finally{child.close();api.profileSource=old;}
}));

test('source views without a list revision keep their existing one-read note behavior',()=>scenario(async()=>{
 const old=api.profileSource;let reads=0;api.profileSource=async()=>{reads++;return {title:'Andere Notiz',body:'Unabhängiger Notizinhalt',revision:7};};const child=driver(()=>ProfileSource({kind:'note',id:'other',readOnly:true}));
 try{let pane=await tick(child);button(pane,'Inhalt öffnen').props.onClick();pane=await tick(child);assert.match(text(pane),/Unabhängiger Notizinhalt/);pane=await tick(child);assert.equal(reads,1);assert.equal(button(pane,'Inhalt schließen').props['aria-expanded'],true);button(pane,'Inhalt schließen').props.onClick();pane=await tick(child);assert.equal(button(pane,'Inhalt öffnen').props['aria-expanded'],false);
 }finally{child.close();api.profileSource=old;}
}));

test('a concurrent note edit revalidates the actual folder list and the same open source instance together',()=>scenario(async({d,setRead,calls})=>{
 const old=api.profileSource;let snapshot=2,reads=0;setRead(()=>page(0,{items:[{...page().items[0],revision:snapshot,preview:snapshot===2?'Zweiter Inhalt':'Dritter Inhalt'}]}));
 api.profileSource=async()=>{reads++;snapshot=3;return {title:'Notiz',body:'Dritter Inhalt',revision:3};};let tree=await tick(d),props=nodes(tree,n=>n.type===ProfileSource)[0].props;const child=driver(()=>ProfileSource(props));
 try{let pane=await tick(child);button(pane,'Inhalt öffnen').props.onClick();pane=await tick(child);assert.doesNotMatch(text(pane),/Dritter Inhalt/,'body newer than the displayed list is held back');tree=await tick(d);assert.match(text(tree),/Dritter Inhalt/);assert.equal(calls.length,2,'the real embedding refreshes its current page');props=nodes(tree,n=>n.type===ProfileSource)[0].props;pane=await tick(child);assert.match(text(pane),/Dritter Inhalt/);assert.match(text(pane),/Revision 3/);assert.equal(reads,2);assert.equal(button(pane,'Inhalt schließen').props['aria-expanded'],true);}finally{child.close();api.profileSource=old;}
}));
