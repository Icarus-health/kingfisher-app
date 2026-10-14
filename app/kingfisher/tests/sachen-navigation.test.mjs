import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';

const server=await createServer({cacheDir:`/private/tmp/kingfisher-ui-test-cache-${process.pid}-sachen-navigation.test`,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{
  name:'sachen-navigation-hooks',enforce:'pre',
  resolveId(id){if(id==='virtual:sachen-navigation-hooks')return '\0'+id;},
  load(id){if(id==='\0virtual:sachen-navigation-hooks')return `export const useState=(...args)=>globalThis.__sachenNavigation.state(...args);export const useEffect=(...args)=>globalThis.__sachenNavigation.effect(...args);export const useRef=(...args)=>globalThis.__sachenNavigation.ref(...args);`;},
  transform(code,id){if(id.endsWith('/src/SachenListe.tsx'))return code.replace(/from (["'])react\1/,'from "virtual:sachen-navigation-hooks"');}
}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {SachenListe}=await server.ssrLoadModule('/src/SachenListe.tsx');
const {SachenAkte}=await server.ssrLoadModule('/src/AkteAbschnitte.tsx');
const {api}=await server.ssrLoadModule('/src/api.ts');
function nodes(node,predicate,out=[]){if(!node||typeof node!=='object')return out;if(predicate(node))out.push(node);for(const child of [node.props?.children].flat(20))nodes(child,predicate,out);return out;}
function text(node){return node==null?'':typeof node==='object'?[node.props?.children].flat(20).map(text).join(''):String(node);}
function driver(render){let s=0,e=0,r=0;const values=[],effects=[],pending=[],refs=[];const d={state(initial){const i=s++;if(!(i in values))values[i]=typeof initial==='function'?initial():initial;return [values[i],next=>values[i]=typeof next==='function'?next(values[i]):next];},ref(initial){return refs[r++]??(refs[r-1]={current:initial});},effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},render(){s=e=r=0;globalThis.__sachenNavigation=d;return render();},flush(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(item=>item.cleanup?.());delete globalThis.__sachenNavigation;}};return d;}
async function withWindow(search,run){const oldWindow=globalThis.window,oldEvent=globalThis.PopStateEvent;const timers=new Map();let serial=0;const paths=[];
  globalThis.PopStateEvent=class{constructor(type){this.type=type;}};
  globalThis.window={location:{pathname:'/memory',search},history:{pushState(_state,_title,path){paths.push(path);}},dispatchEvent(){},setTimeout(fn){timers.set(++serial,fn);return serial;},clearTimeout(id){timers.delete(id);}};
  try{await run({paths,flushTimers(){for(const [id,fn] of [...timers]){timers.delete(id);fn();}}});}finally{globalThis.window=oldWindow;globalThis.PopStateEvent=oldEvent;}}
const data={art:'thema',gesamt:150,sachen:[{sache:'thema:gesundheit',name:'Gesundheit',quellen:4,letzte:'2024-10-12T10:00:00Z'}],berechnung:{offen:0}};

test('controlled SachenListe reads the restored query and one-based page without resetting parent state',()=>withWindow('?tab=topics&q=Gesund&page=3',async({flushTimers})=>{
  const calls=[],changes=[],old=api.akteSachen;api.akteSachen=async(...args)=>{calls.push(args);return data;};let props={art:'thema',query:'Gesund',page:3,onQueryChange:q=>changes.push(['q',q]),onPageChange:p=>changes.push(['page',p])};const d=driver(()=>SachenListe(props));
  try{d.render();d.flush();flushTimers();await new Promise(setImmediate);let tree=d.render();
    assert.deepEqual(calls,[['thema',100,'Gesund']]);assert.deepEqual(changes,[]);assert.equal(nodes(tree,n=>n.type==='input')[0].props.value,'Gesund');assert.match(text(tree),/Seite 3 von 3/);
    nodes(tree,n=>n.type==='button'&&text(n)==='Zurück')[0].props.onClick();assert.deepEqual(changes,[['page',2]]);
    nodes(tree,n=>n.type==='input')[0].props.onChange({target:{value:'Termin'}});assert.deepEqual(changes,[['page',2],['q','Termin'],['page',1]]);
    props={...props,query:'Termin',page:1};d.render();d.flush();flushTimers();await new Promise(setImmediate);assert.deepEqual(calls.at(-1),['thema',0,'Termin']);
  }finally{d.close();api.akteSachen=old;}
}));
test('SachenListe row opens the file with a safe directory return preserving search, page and filters',()=>withWindow('?tab=organizations&q=Verein&page=2&people=all&unknown=discard',async({paths,flushTimers})=>{
  const old=api.akteSachen;api.akteSachen=async()=>({...data,art:'organisation'});const d=driver(()=>SachenListe({art:'organisation',query:'Verein',page:2}));try{d.render();d.flush();flushTimers();await new Promise(setImmediate);const tree=d.render();nodes(tree,n=>n.type==='button'&&n.props['aria-label']?.startsWith('Akte öffnen:'))[0].props.onClick();
    const url=new URL(paths[0],'https://local.test');assert.equal(url.pathname,'/memory/akte/thema%3Agesundheit');assert.equal(url.searchParams.get('return_to'),'/memory?tab=organizations&q=Verein&page=2&people=all');
  }finally{d.close();api.akteSachen=old;}
}));
test('SachenAkte restores a validated directory return and retains the legacy fallback without one',async()=>{
  for(const [search,want] of [[`?return_to=${encodeURIComponent('/memory?tab=places&q=Staufen&page=2')}`,'/memory?tab=places&q=Staufen&page=2'],['','/memory'],[`?return_to=${encodeURIComponent('https://evil.test/memory')}`,'/memory?tab=people']])await withWindow(search,({paths})=>{const tree=SachenAkte({sache:'ort:staufen',recentConversation:null});nodes(tree,n=>n.type==='button'&&n.props.className==='profile-back')[0].props.onClick();assert.deepEqual(paths,[want]);});
});
test('topic directory heading aligns with the Themen navigation',()=>withWindow('',()=>{const d=driver(()=>SachenListe({art:'thema'}));try{const tree=d.render();assert.equal(text(nodes(tree,n=>n.type==='h1')[0]),'Themen');assert.equal(tree.props['aria-label'],'Themen');}finally{d.close();}}));
