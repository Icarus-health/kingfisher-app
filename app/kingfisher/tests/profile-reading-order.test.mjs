import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';

import {testCache} from './testcache.mjs';
const server = await createServer({cacheDir:testCache('profile-reading-order.test'),root:fileURLToPath(new URL('..',import.meta.url)),
  plugins:[{name:'profile-reading-hooks',enforce:'pre',
    resolveId(id){if(id==='virtual:profile-reading-hooks')return '\0'+id;},
    load(id){if(id==='\0virtual:profile-reading-hooks')return `export const useState=(...args)=>globalThis.__profileReadingDriver.state(...args); export const useEffect=(...args)=>globalThis.__profileReadingDriver.effect(...args); export const useMemo=fn=>fn();`;},
    transform(code,id){if(['/src/MemoryProfile.tsx','/src/ProfileSource.tsx'].some(path=>id.endsWith(path)))return code.replace(/from (["'])react\1/,'from "virtual:profile-reading-hooks"');}
  }],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {MemoryProfile,RegistryProfile}=await server.ssrLoadModule('/src/MemoryProfile.tsx');
const {ProfileSource}=await server.ssrLoadModule('/src/ProfileSource.tsx');
const {api}=await server.ssrLoadModule('/src/api.ts');
function nodes(node,predicate,out=[]){if(!node||typeof node!=='object')return out; if(predicate(node))out.push(node);for(const child of [node.props?.children].flat(20))nodes(child,predicate,out);return out;}
function text(node){return node===null||node===undefined?'':typeof node==='object'?[node.props?.children].flat(20).map(text).join(''):String(node);}
function driver(render){const values=[],effects=[],pending=[];let s=0,e=0;const d={
  state(initial){const i=s++;if(!(i in values))values[i]=typeof initial==='function'?initial():initial;return [values[i],next=>values[i]=typeof next==='function'?next(values[i]):next];},
  effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},
  render(){s=e=0;globalThis.__profileReadingDriver=d;return render();},runEffects(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(item=>item.cleanup?.());delete globalThis.__profileReadingDriver;}};return d;}
const personData={id:'a:anna@example.test',authority:'projection',person:{name:'Anna',adressen:['anna@example.test'],letzter_kontakt:'2024-09-12T10:30:00Z',kontakt_text:'vor 2 Jahren',herkuenfte:['email'],themen:[],offene_aufgaben:[{id:'task-one',title:'Bestätigte Einladung vorbereiten',status:'open',created_at:'2026-10-12T10:00:00Z',due:'2026-10-14T10:00:00Z',notes:null,tags:[],wartet_auf:'Anna',wartet_seit:null,wartet_tage:null,overdue:false,project_id:null,provenance:{source_ref:'episode:e1'}}],aussagen:[],nur_von_aussen:false,episoden_anzahl:1,tage_her:761},contexts:[],interactions:[],claims:[],claim_history:[]};
async function loadedProfile(component,props,data,run){const oldWindow=globalThis.window,oldPopStateEvent=globalThis.PopStateEvent,oldApi=component===RegistryProfile?api.registryProfile:props.kind==='project'?api.projectProfile:api.personProfile;
  const key=component===RegistryProfile?'registryProfile':props.kind==='project'?'projectProfile':'personProfile';api[key]=async()=>data;
  globalThis.window={location:{search:`?return_to=${encodeURIComponent('/memory?tab=people&q=Anna&page=3')}`},history:{pushState(_state,_title,path){globalThis.__profileReturnTarget=path;}},dispatchEvent(){}};
  globalThis.PopStateEvent=class {constructor(type){this.type=type;}};
  const d=driver(()=>component(props));try{d.render();d.runEffects();await new Promise(setImmediate);await run(d.render());}finally{d.close();api[key]=oldApi;globalThis.window=oldWindow;globalThis.PopStateEvent=oldPopStateEvent;delete globalThis.__profileReturnTarget;}}

test('person profile presents summary, actual confirmed tasks and dated contact before long files',()=>loadedProfile(MemoryProfile,{kind:'person',identifier:'Anna',recentConversation:null},personData,tree=>{
  const node=nodes(tree,n=>n.type?.name==='PersonProfile')[0];assert.ok(node);const profile=node.type(node.props);
  const sections=nodes(profile,n=>n.type==='section'||n.type?.name==='AkteAnsicht'||n.type?.name==='PersonDigest');
  const fileIndex=sections.findIndex(n=>n.type?.name==='AkteAnsicht');assert.ok(fileIndex>=0);
  for(const label of ['Zusammenfassung','Worauf ich warte','Letzter Kontakt']){const index=sections.findIndex(n=>text(n).includes(label));assert.ok(index>=0&&index<fileIndex,`${label} comes before the file`);}
  const current=sections.find(n=>text(n).includes('Worauf ich warte'));assert.match(text(current),/Bestätigte Einladung vorbereiten/);assert.match(text(current),/2026/);
  assert.match(text(sections.find(n=>text(n).includes('Zusammenfassung'))),/2024/);
  assert.ok(nodes(current,n=>n.type?.name==='TaskSource').length,'confirmed task keeps its source access');
}));
test('person and registry back buttons restore the originating list state',async()=>{
  for(const component of [MemoryProfile,RegistryProfile])await loadedProfile(component,component===MemoryProfile?{kind:'person',identifier:'Anna',recentConversation:null}:{identifier:'anna',recentConversation:null},component===MemoryProfile?personData:null,tree=>{
    nodes(tree,n=>n.type==='button'&&n.props.className==='profile-back')[0].props.onClick();assert.equal(globalThis.__profileReturnTarget,'/memory?tab=people&q=Anna&page=3');
  });
});
test('person profile keeps the first five tasks upfront and all remaining tasks with sources in a counted disclosure', () => {
  const tasks=Array.from({length:8},(_,index)=>({...personData.person.offene_aufgaben[0],id:`task-${index+1}`,title:`Confirmed task ${index+1}`}));
  return loadedProfile(MemoryProfile,{kind:'person',identifier:'Anna',recentConversation:null},{...personData,person:{...personData.person,offene_aufgaben:tasks}},tree=>{
    const node=nodes(tree,n=>n.type?.name==='PersonProfile')[0],profile=node.type(node.props);
    const current=nodes(profile,n=>n.type==='section'&&text(n).includes('Worauf ich warte'))[0];
    const disclosure=nodes(current,n=>n.type==='details')[0];assert.ok(disclosure,'remaining tasks are expandable');
    const upfront=nodes(current,n=>n.type==='div'&&n.props.className?.split(' ').includes('profile-list'))[0];
    assert.equal(nodes(upfront,n=>n.type==='article').length,5);
    assert.match(text(disclosure),/Weitere offene Aufgaben \(3\)/);
    assert.deepEqual(nodes(disclosure,n=>n.type==='strong').map(text),['Confirmed task 6','Confirmed task 7','Confirmed task 8']);
    assert.deepEqual(nodes(disclosure,n=>n.type?.name==='TaskSource').map(n=>n.props.taskId),['task-6','task-7','task-8']);
  });
});
test('empty waiting list does not deny tasks present in shared sources',()=>loadedProfile(MemoryProfile,{kind:'person',identifier:'Anna',recentConversation:null},{...personData,person:{...personData.person,offene_aufgaben:[]}},tree=>{
  const node=nodes(tree,n=>n.type?.name==='PersonProfile')[0],profile=node.type(node.props);
  const current=nodes(profile,n=>n.type==='section'&&text(n).includes('Worauf ich warte'))[0];
  assert.ok(current); assert.match(text(current),/Noch keine Rückmeldung.*vorgemerkt/);
  assert.match(text(current),/Weitere Aufgaben.*gemeinsamen Quellen/);
  assert.doesNotMatch(text(current),/Keine offene Aufgabe.*zugeordnet/);
}));
async function openedSource(props,data,run){const oldApi=api.profileSource,oldWindow=globalThis.window;api.profileSource=async()=>data;globalThis.window={setInterval:()=>0,clearInterval:()=>{}};const d=driver(()=>ProfileSource({kind:'episode',id:'source-one',...props}));try{nodes(d.render(),n=>n.type==='button')[0].props.onClick();d.render();d.runEffects();await new Promise(setImmediate);await run(d.render());}finally{d.close();api.profileSource=oldApi;globalThis.window=oldWindow;}}
test('source original text precedes category, relationship and provenance details',()=>openedSource({}, {title:'Synthetic source',body:'Original wording for inspection',state:'new',provenance:{source_ref:'synthetic'},source_incomplete:true},tree=>{
  const order=nodes(tree,n=>n.props?.className==='task-source-body'||['SourceCategories','SourceBezuege','SourceProject','Herkunft'].includes(n.type?.name));assert.equal(order[0].props.className,'task-source-body');assert.match(text(tree),/Nur teilweise erfasst/);
}));
test('ignored sources remain visibly excluded with no classification or relationship controls',()=>openedSource({readOnly:true}, {title:'Excluded',body:'Preserved original',state:'ignored',provenance:{}},tree=>{
  assert.match(text(tree),/ausgeschlossen.*Wissensbeleg/);assert.equal(nodes(tree,n=>['SourceCategories','SourceBezuege','SourceProject','SourceCorrection'].includes(n.type?.name)).length,0);assert.equal(nodes(tree,n=>n.type==='button').length,1);
}));

test('co-mentioned and completed tasks do not appear as explicit waiting commitments',()=>loadedProfile(MemoryProfile,{kind:'person',identifier:'Anna',recentConversation:null},{...personData,person:{...personData.person,offene_aufgaben:[{...personData.person.offene_aufgaben[0],wartet_auf:null,title:'Only co-mentioned'},{...personData.person.offene_aufgaben[0],status:'done',title:'Already done'}]}},tree=>{
 const node=nodes(tree,n=>n.type?.name==='PersonProfile')[0],profile=node.type(node.props);
 const current=nodes(profile,n=>n.type==='section'&&text(n).includes('Worauf ich warte'))[0];
 assert.doesNotMatch(text(current),/Only co-mentioned|Already done/);assert.match(text(current),/Noch keine Rückmeldung/);
}));

function visibleText(n){if(n==null)return '';if(typeof n!=='object')return String(n);const children=[n.props?.children].flat(20);return(n.type==='details'&&!n.props.open?children.filter(c=>c?.type==='summary'):children).map(visibleText).join('');}
test('person overview uses one identity, retains contact and uncertainty, and starts its tools closed',()=>loadedProfile(MemoryProfile,{kind:'person',identifier:'Anna',recentConversation:null},{...personData,person:{...personData.person,nur_von_aussen:true}},tree=>{
 const node=nodes(tree,n=>n.type?.name==='PersonProfile')[0],profile=node.type(node.props);
 assert.equal(visibleText(profile).split('anna@example.test').length-1,1,'contact address must not be repeated across cards');
 assert.match(visibleText(profile),/Nur aus fremden Quellen bekannt/);assert.match(visibleText(profile),/2024/);
 const file=nodes(profile,n=>n.type?.name==='AkteAnsicht')[0];assert.equal(file.props.compact,true);
 const digest=nodes(profile,n=>n.type?.name==='PersonDigest')[0];assert.equal(digest.props.compact,true);
 assert.equal(nodes(profile,n=>n.props?.className==='profile-metrics').length,0,'no second row of duplicate metrics');
}));
