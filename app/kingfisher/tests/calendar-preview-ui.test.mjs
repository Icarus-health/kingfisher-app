import assert from 'node:assert/strict';import {test} from 'node:test';import {createServer} from 'vite';import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('..',import.meta.url));
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);for(const c of [n.props?.children,n.props?.aktionen].flat(10))nodes(c,p,out);return out;}
function text(n){return n==null?'':typeof n==='object'?[n.props?.children].flat(10).map(text).join(''):String(n);}
async function harness(run){
 const server=await createServer({root,cacheDir:`/private/tmp/kf-calendar-preview-ui-${process.pid}`,configFile:false,plugins:[{name:'preview-hooks',enforce:'pre',resolveId(id){if(id==='virtual:preview-hooks')return '\0'+id;},load(id){if(id==='\0virtual:preview-hooks')return 'export const useState=(...a)=>globalThis.__previewDriver.state(...a);export const useRef=(...a)=>globalThis.__previewDriver.ref(...a);export const useEffect=(...a)=>globalThis.__previewDriver.effect(...a);';},transform(code,id){if(/\/(CalendarPage|CalendarActionForm)\.tsx$/.test(id))return code.replace(/from ["']react["']/g,'from "virtual:preview-hooks"');}}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
 const oldWindow=globalThis.window,oldStorage=globalThis.localStorage,oldDriver=globalThis.__previewDriver;let tick=()=>{};
 globalThis.localStorage={getItem(){return 'Liste';},setItem(){}};
 globalThis.window={location:{search:'',href:'http://synthetic/calendar'},history:{replaceState(){}},addEventListener(){},removeEventListener(){},setInterval(fn){tick=fn;return 1;},clearInterval(){}};
 function driver(Component,props){const values=[],refs=[],deps=[],pending=[],cleanups=[];let si=0,ri=0,ei=0;const d={state(initial){const i=si++;if(!(i in values))values[i]=typeof initial==='function'?initial():initial;return[values[i],v=>values[i]=typeof v==='function'?v(values[i]):v];},ref(initial){return refs[ri++]??=({current:initial});},effect(fn,next){const i=ei++;if(!deps[i]||next.some((v,j)=>v!==deps[i][j])){deps[i]=next;pending.push(()=>{cleanups[i]?.();cleanups[i]=fn();});}},render(){si=ri=ei=0;globalThis.__previewDriver=d;return Component(props);},async flush(){while(pending.length)pending.shift()();await new Promise(r=>setImmediate(r));}};return d;}
 try{await run(server,driver,()=>tick());}finally{globalThis.window=oldWindow;globalThis.localStorage=oldStorage;globalThis.__previewDriver=oldDriver;await server.close();}
}
const event=()=>{const start=new Date();start.setDate(start.getDate()+1);start.setHours(10,0,0,0);return {uid:'a:event',source_id:'a',source_label:'Arbeit',summary:'Künstliche Besprechung',start:start.toISOString(),end:new Date(+start+3600000).toISOString(),all_day:false,location:''};};
const response=(items,failed=[])=>({items,configured:true,errors:failed.length?['Künstlicher Ausfall']:[],failed_sources:failed,read_context:'one',read_at:'2026-11-04T10:00:00Z'});

test('provider failure retains a visibly stale readable event with no event actions, recovery replaces it',()=>harness(async(server,driver,tick)=>{
 const {CalendarPage}=await server.ssrLoadModule('/src/CalendarPage.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');const item=event();let view=response([item]);
 api.calendar=async()=>view;api.calendarActionSources=async()=>({sources:[{id:'a'}]});api.integrations=async()=>({calendar_sources:[{id:'a',label:'Arbeit',configured:true,enabled:true}]});api.macCalendar=async()=>({enabled:false,selected:[],calendars:[]});
 const d=driver(CalendarPage,{recentConversation:null});d.render();await d.flush();let tree=d.render();await d.flush();
 view=response([],['a']);tick();d.render();await d.flush();tree=d.render();
 assert.match(text(tree),/Künstliche Besprechung/);assert.match(text(tree),/Zuletzt geladen.*ungeprüft/);
 const button=nodes(tree,n=>n.type==='button'&&/Künstliche Besprechung/.test(text(n)))[0];button.props.onClick();tree=d.render();
 const panel=nodes(tree,n=>n.type?.name==='DetailPanel')[0];assert.ok(panel);assert.match(text(panel),/Stand.*04.11.2026/);
 assert.equal(nodes(panel,n=>n.type==='button'&&/Vorbereiten|Nachbereiten|Bearbeiten/.test(text(n))).length,0);
 view=response([{...item,summary:'Aktualisierte Besprechung'}]);tick();d.render();await d.flush();tree=d.render();
 assert.match(text(tree),/Aktualisierte Besprechung/);assert.doesNotMatch(text(tree),/ungeprüft/);
 view=response([]);tick();d.render();await d.flush();assert.doesNotMatch(text(d.render()),/Aktualisierte Besprechung/);
}));
test('authority conflict removes cached events',()=>harness(async(server,driver,tick)=>{
 const {CalendarPage}=await server.ssrLoadModule('/src/CalendarPage.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');const item=event();let failure=false;
 api.calendar=async()=>{if(failure)throw Error('HTTP 409');return response([item]);};api.calendarActionSources=async()=>({sources:[]});api.integrations=async()=>({calendar_sources:[]});api.macCalendar=async()=>({enabled:false,selected:[],calendars:[]});
 const d=driver(CalendarPage,{recentConversation:null});d.render();await d.flush();assert.match(text(d.render()),/Künstliche Besprechung/);
 failure=true;tick();d.render();await d.flush();assert.doesNotMatch(text(d.render()),/Künstliche Besprechung/);
}));
for (const change of ['failure','authority','empty']) test(`preparation cannot revive on navigation after ${change}`,()=>harness(async(server,driver,tick)=>{
 const {CalendarPage}=await server.ssrLoadModule('/src/CalendarPage.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');let view=response([event()]);
 api.calendar=async()=>view;api.calendarActionSources=async()=>({sources:[]});api.integrations=async()=>({calendar_sources:[]});api.macCalendar=async()=>({enabled:false,selected:[],calendars:[]});
 const d=driver(CalendarPage,{recentConversation:null});d.render();await d.flush();let tree=d.render();
 nodes(tree,n=>n.type==='button'&&/Künstliche Besprechung/.test(text(n)))[0].props.onClick();tree=d.render();
 nodes(tree,n=>n.type==='button'&&text(n)==='Vorbereiten')[0].props.onClick();tree=d.render();await d.flush();tree=d.render();await d.flush();tree=d.render();
 assert.equal(nodes(tree,n=>n.type?.name==='CalendarPreparation').length,1);
 view=change==='failure'?response([],['a']):change==='authority'?{...response([]),read_context:'two'}:response([]);
 tick();d.render();await d.flush();tree=d.render();await d.flush();tree=d.render();
 assert.equal(nodes(tree,n=>n.type?.name==='CalendarPreparation').length,0);
 nodes(tree,n=>n.type==='button'&&n.props['aria-label']==='Nächster Zeitraum')[0].props.onClick();tree=d.render();
 assert.equal(nodes(tree,n=>n.type?.name==='CalendarPreparation').length,0);
 await d.flush();tree=d.render();assert.equal(nodes(tree,n=>n.type?.name==='CalendarPreparation').length,0);
 assert.doesNotMatch(text(tree),/Künstliche Besprechung/);
}));
test('month view identifies stale events individually while keeping fresh events unmarked',()=>harness(async(server,driver,tick)=>{
 globalThis.localStorage.getItem=()=> 'Monat';
 const {CalendarPage}=await server.ssrLoadModule('/src/CalendarPage.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 const stale=event(),fresh={...event(),uid:'b:other',source_id:'b',summary:'Frischer Termin'};let view=response([stale,fresh]);
 api.calendar=async()=>view;api.calendarActionSources=async()=>({sources:[]});api.integrations=async()=>({calendar_sources:[]});api.macCalendar=async()=>({enabled:false,selected:[],calendars:[]});
 const d=driver(CalendarPage,{recentConversation:null});d.render();await d.flush();d.render();
 view=response([fresh],['a']);tick();d.render();await d.flush();const tree=d.render();
 const buttons=nodes(tree,n=>n.type==='button'&&n.props.className==='calendar-month-event');
 const old=buttons.find(n=>/Künstliche Besprechung/.test(text(n))),current=buttons.find(n=>/Frischer Termin/.test(text(n)));
 assert.ok(old);assert.ok(current);assert.match(text(old),/ungeprüft/);assert.match(old.props.title,/Stand.*ungeprüft/);assert.match(old.props['aria-label'],/Stand.*ungeprüft/);assert.doesNotMatch(text(current),/ungeprüft/);
}));
test('an open event edit retains its component but loses write verification during a source outage',()=>harness(async(server,driver,tick)=>{
 const {CalendarPage}=await server.ssrLoadModule('/src/CalendarPage.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');let view=response([event()]);
 api.calendar=async()=>view;api.calendarActionSources=async()=>({sources:[{id:'a'}]});api.integrations=async()=>({calendar_sources:[]});api.macCalendar=async()=>({enabled:false,selected:[],calendars:[]});
 const d=driver(CalendarPage,{recentConversation:null});d.render();await d.flush();let tree=d.render();
 nodes(tree,n=>n.type==='button'&&/Künstliche Besprechung/.test(text(n)))[0].props.onClick();tree=d.render();nodes(tree,n=>n.type==='button'&&/Bearbeiten/.test(text(n)))[0].props.onClick();tree=d.render();
 const first=nodes(tree,n=>n.type?.name==='CalendarActionForm')[0];assert.ok(first);
 view=response([],['a']);tick();d.render();await d.flush();tree=d.render();const later=nodes(tree,n=>n.type?.name==='CalendarActionForm')[0];assert.equal(later.key,first.key);assert.equal(later.props.sourceVerified,false);
}));
test('unverified calendar edit does not submit but retains typed title for recovery',()=>harness(async(server,driver)=>{
 const {CalendarActionForm}=await server.ssrLoadModule('/src/CalendarActionForm.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');let calls=0;
 api.calendarActionSources=async()=>({sources:[{id:'a',label:'Arbeit',can_write:true}]});api.calendarActionDraft=async()=>{calls++;throw Error('Simulierter Speicherfehler');};
 const props={event:event(),sourceVerified:true,onClose(){},onDone(){}};const d=driver(CalendarActionForm,props);d.render();await d.flush();let tree=d.render();
 nodes(tree,n=>n.type==='input'&&n.props.maxLength===500)[0].props.onChange({target:{value:'Eigener Titel'}});props.sourceVerified=false;tree=d.render();
 nodes(tree,n=>n.type==='form')[0].props.onSubmit({preventDefault(){}});await d.flush();tree=d.render();assert.equal(calls,0);assert.equal(nodes(tree,n=>n.type==='input'&&n.props.maxLength===500)[0].props.value,'Eigener Titel');
 assert.match(text(tree),/Kalenderstand.*ungeprüft/);props.sourceVerified=true;tree=d.render();nodes(tree,n=>n.type==='form')[0].props.onSubmit({preventDefault(){}});await d.flush();assert.equal(calls,1);
}));

test('legacy UID-only preparation links resolve a date and wait for the fresh range',()=>harness(async(server,driver)=>{
 globalThis.window.location.search='?prepare=a%3Aevent';globalThis.window.location.href='http://synthetic/calendar?prepare=a%3Aevent';
 const {CalendarPage}=await server.ssrLoadModule('/src/CalendarPage.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 const future=event();future.start=new Date(Date.now()+40*86400000).toISOString();future.end=new Date(Date.parse(future.start)+3600000).toISOString();let legacyReads=0;
 api.calendar=async(from,until)=>{if(!from){legacyReads++;return response([future]);}return response(Date.parse(from)<=Date.parse(future.start)&&Date.parse(future.start)<Date.parse(until)?[future]:[]);};
 api.calendarActionSources=async()=>({sources:[]});api.integrations=async()=>({calendar_sources:[]});api.macCalendar=async()=>({enabled:false,selected:[],calendars:[]});
 const d=driver(CalendarPage,{recentConversation:null});let tree;
 for(let i=0;i<6;i++){tree=d.render();await d.flush();}tree=d.render();
 assert.equal(legacyReads,1);const preparation=nodes(tree,n=>n.type?.name==='CalendarPreparation');assert.equal(preparation.length,1);assert.equal(preparation[0].props.event.start,future.start);
}));
