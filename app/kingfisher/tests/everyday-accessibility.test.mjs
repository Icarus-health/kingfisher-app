import {after,test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
const server=await createServer({cacheDir:`/private/tmp/kingfisher-a11y-cache-${process.pid}`,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'audit-hooks',enforce:'pre',resolveId(id){if(id==='virtual:audit-hooks')return '\0'+id;},load(id){if(id==='\0virtual:audit-hooks')return 'export const useState=(...a)=>globalThis.__auditDriver.state(...a);export const useRef=(...a)=>globalThis.__auditDriver.ref(...a);export const useEffect=(...a)=>globalThis.__auditDriver.effect(...a);export const useMemo=fn=>fn();';},transform(code,id){if(['/src/App.tsx','/src/WorldControls.tsx','/src/ProjectControls.tsx'].some(p=>id.endsWith(p)))return code.replace(/from (["'])react\1/,'from "virtual:audit-hooks"');}}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const app=await server.ssrLoadModule('/src/App.tsx');
const {ProjectControls}=await server.ssrLoadModule('/src/ProjectControls.tsx');
const {api}=await server.ssrLoadModule('/src/api.ts');
const {WorldControls}=await server.ssrLoadModule('/src/WorldControls.tsx');
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);[n.props?.children].flat(30).forEach(c=>nodes(c,p,out));return out;}
function text(n){return n==null?'':typeof n==='object'?[n.props?.children].flat(30).map(text).join(''):String(n);}
function button(n,label){const b=nodes(n,x=>x.type==='button'&&text(x)===label)[0];assert.ok(b,label);return b;}
function driver(render){const states=[],refs=[],effects=[],pending=[];let s,r,e;return {state(initial){const i=s++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial;return [states[i],v=>states[i]=typeof v==='function'?v(states[i]):v];},ref(initial){return refs[r++]??(refs[r-1]={current:initial});},effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},render(){s=r=e=0;globalThis.__auditDriver=this;return render();},flush(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(x=>x.cleanup?.());delete globalThis.__auditDriver;}};}
async function tick(d){d.render();d.flush();await new Promise(setImmediate);d.render();d.flush();await new Promise(setImmediate);return d.render();}

test('briefing is inert when closed; open dialog focuses, traps keyboard and restores its opener',()=>{
 assert.equal(typeof app.BriefingDrawer,'function','briefing is directly testable');
 const before={document:globalThis.document,HTMLElement:globalThis.HTMLElement};let active,closed=0,open=false;
 class Field{isConnected=true;tabIndex=0;focus(){active=this;}getClientRects(){return [1];}}
 const opener=new Field(),first=new Field(),last=new Field();active=opener;globalThis.HTMLElement=Field;globalThis.document={get activeElement(){return active;},body:{style:{overflow:'auto'}}};
 const d=driver(()=>app.BriefingDrawer({briefing:{generated_at:'2026-10-15T07:00:00Z',timezone:'Europe/Berlin',needs_you:[],later_today:[],happening_now:[],greeting:'Guten Morgen.'},open,onClose(){closed++;},onChange(){}}));
 try{let tree=d.render(),panel=nodes(tree,n=>n.props?.className?.startsWith('briefing-drawer'))[0];assert.equal(panel.props.inert,true);d.flush();assert.equal(active,opener);
  open=true;tree=d.render();panel=nodes(tree,n=>n.props?.role==='dialog')[0];assert.ok(panel);panel.props.ref.current={querySelectorAll:()=>[first,last]};button(tree,'Zurück zu Heute').props.ref.current=first;d.flush();assert.equal(active,first);assert.equal(globalThis.document.body.style.overflow,'hidden');
  let prevented=0;panel.props.onKeyDown({key:'Tab',shiftKey:true,preventDefault(){prevented++;}});assert.equal(active,last);panel.props.onKeyDown({key:'Tab',shiftKey:false,preventDefault(){prevented++;}});assert.equal(active,first);assert.equal(prevented,2);
  panel.props.onKeyDown({key:'Escape',preventDefault(){}});assert.equal(closed,1);
  open=false;d.render();d.flush();assert.equal(active,opener);assert.equal(globalThis.document.body.style.overflow,'auto');
 }finally{d.close();Object.assign(globalThis,before);}
});

test('briefing presents one readable reason instead of duplicating the same warning',()=>{
 assert.equal(typeof app.BriefingDrawer,'function');const d=driver(()=>app.BriefingDrawer({briefing:{generated_at:'2026-10-15T07:00:00Z',timezone:'Europe/Berlin',needs_you:[{id:'warning',title:'Prüfen',reason:'Bitte Quelle prüfen.',detail:'Bitte Quelle prüfen.',source:'aufgabe',priority:'Hoch'},{id:'event',title:'Termin',reason:'Termin',detail:'Quelle: termin',source:'termin',priority:'Mittel'}],later_today:[],happening_now:[],greeting:'Guten Morgen.'},open:false,onClose(){},onChange(){}}));
 try{const result=text(d.render());assert.equal(result.match(/Bitte Quelle prüfen\./g)?.length,1);assert.match(result,/Kalender/);assert.doesNotMatch(result,/Quelle: termin/);}finally{d.close();}
});

test('invalid public source keeps its draft and gives an actionable address error without disguising a reload as a save retry',async()=>{
 const previous=globalThis.fetch;globalThis.fetch=async(_url,options)=>options?.method==='POST'?new Response('{}',{status:400}):new Response('{"items":[]}',{status:200});
 const d=driver(()=>WorldControls({initiallyOpen:true}));try{let tree=await tick(d);const fields=nodes(tree,n=>n.type==='input');fields[0].props.onChange({target:{value:'Bedienprobe'}});fields[1].props.onChange({target:{value:'https://example.invalid/'}});await nodes(d.render(),n=>n.type==='form')[0].props.onSubmit({preventDefault(){}});tree=await tick(d);
  assert.match(text(nodes(tree,n=>n.props?.role==='alert')[0]),/öffentliche HTTPS-Adresse/);assert.equal(nodes(tree,n=>n.type==='input')[1].props.value,'https://example.invalid/');assert.equal(nodes(tree,n=>n.type==='button'&&text(n)==='Erneut versuchen').length,0);
 }finally{d.close();globalThis.fetch=previous;}
});


test('project status remains busy until the updated project list is loaded',async()=>{
 const previous=api.updateProject;api.updateProject=async()=>({});let finish,projects=[{id:'p',name:'Projekt',status:'active'}];const d=driver(()=>ProjectControls({projects,selectedId:'p',onSelect(){},onChanged:()=>new Promise(resolve=>{finish=resolve;})}));
 try{let tree=await tick(d);nodes(tree,n=>n.type==='select')[1].props.onChange({target:{value:'done'}});tree=await tick(d);assert.equal(nodes(tree,n=>n.type==='select')[1].props.disabled,true,'an old status must not become interactive during revalidation');
  projects=[{...projects[0],status:'done'}];finish();tree=await tick(d);assert.equal(nodes(tree,n=>n.type==='select')[1].props.value,'done');assert.equal(nodes(tree,n=>n.type==='select')[1].props.disabled,false);
 }finally{d.close();api.updateProject=previous;}
});

test('project closure warning is cleared when a successful task change invalidates its previous count',async()=>{
 const previous=api.updateProject;api.updateProject=async()=>{throw Error('refused');};let revision=0;const d=driver(()=>ProjectControls({projects:[{id:'p',name:'Projekt',status:'active'}],selectedId:'p',contextRevision:revision,onSelect(){},onChanged(){}}));
 try{let tree=await tick(d);nodes(tree,n=>n.type==='select')[1].props.onChange({target:{value:'done'}});tree=await tick(d);assert.equal(nodes(tree,n=>n.props?.role==='alert').length,1);
  revision++;tree=await tick(d);assert.equal(nodes(tree,n=>n.props?.role==='alert').length,0,'do not show an old open-task count after the task context changed');
 }finally{d.close();api.updateProject=previous;}
});
