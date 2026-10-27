import assert from 'node:assert/strict';import {test} from 'node:test';import {createServer} from 'vite';import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('..',import.meta.url));
// Kopfaktionen (Seitenkopf `aktionen`) zählen mit; die Ansichtswahl ist der Baustein `Segmente`.
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);for(const c of [n.props?.children,n.props?.aktionen,n.props?.aktion].flat(10))nodes(c,p,out);return out;}
const ansicht=(tree,wert)=>{const s=nodes(tree,n=>n.type?.name==='Segmente'&&n.props.label==='Kalenderansicht')[0];if(!s||!s.props.optionen.some(o=>o.wert===wert))return null;return {props:{onClick:()=>s.props.onWahl(wert)}};};
function text(n){return n==null?'':typeof n==='object'?[n.props?.children].flat(10).map(text).join(''):String(n);}
test('week has 24 hour labels, selectable calendars, event detail action and day view',async()=>{
 const server=await createServer({root,cacheDir:`/private/tmp/kf-calendar-ssr-${process.pid}`,configFile:false,plugins:[{name:'calendar-hooks',enforce:'pre',resolveId(id){if(id==='virtual:calendar-hooks')return '\0'+id;},load(id){if(id==='\0virtual:calendar-hooks')return 'export const useState=(...a)=>globalThis.__calendarDriver.state(...a);export const useRef=v=>({current:v});export const useEffect=(...a)=>globalThis.__calendarDriver.effect(...a);';},transform(code,id){if(id.endsWith('/CalendarPage.tsx'))return code.replace('from "react"','from "virtual:calendar-hooks"');}}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
 const oldWindow=globalThis.window,oldStorage=globalThis.localStorage,oldDriver=globalThis.__calendarDriver;
 const storage={getItem(){return 'Woche';},setItem(){}};globalThis.localStorage=storage;globalThis.window={location:{search:'',href:'http://synthetic/calendar'},history:{replaceState(){}},addEventListener(){},removeEventListener(){},setInterval(fn){globalThis.__calendarTick=fn;return 1;},clearInterval(){}};
 try{
 const {CalendarPage}=await server.ssrLoadModule('/src/CalendarPage.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 const now=new Date(),start=now.toISOString();const item={uid:'source:123',source_id:'source',source_label:'Arbeit',summary:'Workshop',start,end:new Date(+new Date(start)+3600000).toISOString(),all_day:false,location:'Zimmer'};
 api.calendar=async()=>({items:[item],configured:true,errors:[]});api.calendarActionSources=async()=>({sources:[]});api.integrations=async()=>({calendar_sources:[{id:'source',label:'Arbeit',configured:true,enabled:true}]});api.macCalendar=async()=>({enabled:false,selected:[],calendars:[]});
 const values=[],deps=[],pending=[];let si=0,ei=0;const d={state(initial){const i=si++;if(!(i in values))values[i]=typeof initial==='function'?initial():initial;return[values[i],v=>values[i]=typeof v==='function'?v(values[i]):v];},effect(fn,next){const i=ei++;if(!deps[i]||!next||next.some((v,j)=>v!==deps[i][j])){deps[i]=next;pending.push(fn);}},render(){si=ei=0;globalThis.__calendarDriver=d;return CalendarPage({recentConversation:null});},async flush(){while(pending.length)pending.shift()();await new Promise(r=>setImmediate(r));}};
 d.render();await d.flush();let tree=d.render();await d.flush();tree=d.render();
 const agendaLink=()=>nodes(d.render(),n=>n.type==='button'&&n.props['aria-expanded']!==undefined&&/als Liste/.test(text(n)))[0];
 assert.ok(agendaLink(),'Die Tagesliste ist ein leiser Link unter dem Raster');assert.equal(agendaLink().props['aria-expanded'],false);assert.match(text(agendaLink()),/^1 Termin am/);
 assert.equal(nodes(tree,n=>n.type==='article'&&n.props.className==='calendar-entry').length,0,'eingeklappt steht keine zweite Liste da');
 agendaLink().props.onClick();tree=d.render();assert.equal(agendaLink().props['aria-expanded'],true);assert.match(text(nodes(tree,n=>n.props?.className==='calendar-agenda')[0]),/Workshop/);agendaLink().props.onClick();tree=d.render();
 assert.equal(nodes(tree,n=>n.props?.className==='calendar-hour').length,24);assert.ok(ansicht(tree,'Tag'));
 assert.equal(nodes(tree,n=>n.type==='input'&&n.props.type==='checkbox').length,0,'Ein einziger Kalender braucht keine Auswahl');
 assert.equal(nodes(tree,n=>n.type==='input'&&n.props.type==='date').length,0,'Kein Datumsfeld neben dem Monat');
 assert.equal(nodes(tree,n=>n.props?.className==='month-grid mini-month').length,0,'Kein zweiter Monatskalender');
 assert.equal(nodes(tree,n=>n.type==='details').length,0,'Keine Aufklapper im Kalender');
 assert.equal(nodes(tree,n=>/(^| )(g-knopf|primary-action)( |$)/.test(n.props?.className??'')).length,1,'Genau ein gefüllter Knopf');
 const event=nodes(tree,n=>n.type==='button'&&n.props.className==='calendar-time-event')[0];assert.ok(event);event.props.onClick();tree=d.render();const details=nodes(tree,n=>n.type?.name==='DetailPanel')[0];assert.ok(details);assert.match(text(details),/Workshop/);assert.match(text(details),/Vorbereiten/);
 // Establish a different week explicitly. Otherwise this test depends on the
 // wall clock: during 19–25 October the target is already in the cached week,
 // so changing only the selected day correctly does not fetch again.
 const goTo=async(iso)=>{const [y,m,day]=iso.split('-').map(Number);ansicht(d.render(),'Jahr').props.onClick();d.render();await d.flush();
let shown=Number(text(nodes(d.render(),n=>n.props?.className==='calendar-period')[0]).match(/\d{4}/)[0]);
  while(shown!==y){nodes(d.render(),n=>n.type==='button'&&n.props['aria-label']===(shown<y?'Nächster Zeitraum':'Vorheriger Zeitraum'))[0].props.onClick();d.render();await d.flush();shown+=shown<y?1:-1;}
  const label=new Date(y,m-1,day).toLocaleDateString('de-DE',{weekday:'long',day:'numeric',month:'long'})+','; /* Tagesname im Raster (Paket B, B5) */ nodes(d.render(),n=>n.type==='button'&&String(n.props['aria-label']??'').startsWith(label))[0].props.onClick();d.render();await d.flush();
  ansicht(d.render(),'Woche').props.onClick();d.render();await d.flush();tree=d.render();await d.flush();tree=d.render();};
 await goTo('2026-10-12');
 const oldZone=process.env.TZ;process.env.TZ='Europe/Berlin';
 try {
  api.calendar=async()=>({items:[{...item,uid:'clock',start:'2026-10-25T02:50:00+02:00',end:'2026-10-25T02:10:00+01:00'}],configured:true,errors:[]});
  await goTo('2026-10-25');
  const parts=nodes(tree,n=>n.type==='button'&&n.props.className==='calendar-time-event');assert.equal(parts.length,2);assert.equal(new Set(parts.map(p=>p.key)).size,2);
  assert.ok(parts.some(p=>p.props['aria-label'].includes('02:50–03:00 UTC+02:00')));assert.ok(parts.some(p=>p.props['aria-label'].includes('02:00–02:10 UTC+01:00')));
 }finally{if(oldZone===undefined)delete process.env.TZ;else process.env.TZ=oldZone;}
 let finishIntegrations;api.integrations=()=>new Promise(resolve=>{finishIntegrations=resolve;});
 api.macCalendar=async()=>({enabled:true,selected:['private','work','empty'],calendars:[{id:'private',name:'Privat'},{id:'work',name:'Arbeit'},{id:'empty',name:'Ohne Termine'},{id:'unselected',name:'Nicht ausgewählt'}]});
 api.calendarActionSources=async()=>({sources:[{id:'google'}]});
 const localStart=new Date(2026,9,25,10).toISOString();
 const privateEvent={...item,uid:'mac-calendar:private-event',source_id:'mac-calendar',view_source_id:'mac-calendar:private',source_label:'Mac · Privat',summary:'Privater Termin',start:localStart,end:new Date(+new Date(localStart)+3600000).toISOString()};
 const workEvent={...privateEvent,uid:'google:work-event',source_id:'google',view_source_id:undefined,source_label:'Google',summary:'Arbeitstermin',source_copies:[{uid:'google:work-event',source_id:'google',source_label:'Google',view_source_id:'google'},{uid:'mac-calendar:work-event',source_id:'mac-calendar',source_label:'Mac · Arbeit',view_source_id:'mac-calendar:work'}]};
 api.calendar=async()=>({items:[privateEvent,workEvent],configured:true,errors:[]});
 assert.equal(nodes(tree,n=>n.type==='button'&&text(n)==='Ansicht aktualisieren').length,0,'kein Handbetrieb: der Kalender lädt selbst');globalThis.__calendarTick();d.render();await d.flush();tree=d.render();
 let choices=nodes(tree,n=>n.props?.className==='calendar-source-choice');assert.ok(choices.some(n=>text(n)==='Ohne Termine'));assert.ok(choices.some(n=>text(n)==='Privat'));assert.ok(choices.some(n=>text(n)==='Arbeit'));assert.ok(!choices.some(n=>text(n)==='Nicht ausgewählt'));
 assert.equal(nodes(tree,n=>n.props?.className==='calendar-time-event').length,2);
 finishIntegrations({calendar_sources:[{id:'mac-calendar',label:'Mac-Kalender',configured:true,enabled:true},{id:'google',label:'Google',configured:true,enabled:true}]});await d.flush();tree=d.render();
 choices=nodes(tree,n=>n.props?.className==='calendar-source-choice');assert.ok(choices.some(n=>text(n)==='Ohne Termine'));assert.ok(!choices.some(n=>text(n)==='Mac-Kalender'));
 const toggle=label=>{const choice=nodes(tree,n=>n.props?.className==='calendar-source-choice'&&text(n)===label)[0];nodes(choice,n=>n.type==='input')[0].props.onChange({target:{checked:false}});tree=d.render();};
 toggle('Privat');let visible=nodes(tree,n=>n.props?.className==='calendar-time-event');assert.equal(visible.length,1);assert.match(text(visible[0]),/Arbeitstermin/);
 toggle('Google');visible=nodes(tree,n=>n.props?.className==='calendar-time-event');assert.equal(visible.length,1);assert.match(text(visible[0]),/Arbeitstermin/);
 visible[0].props.onClick();tree=d.render();const mirrorDetails=nodes(tree,n=>n.type?.name==='DetailPanel')[0];nodes(mirrorDetails,n=>n.type==='button'&&/Bearbeiten/.test(text(n)))[0].props.onClick();tree=d.render();const form=nodes(tree,n=>n.type?.name==='CalendarActionForm')[0];assert.equal(nodes(tree,n=>/(^| )g-knopf( |$)/.test(n.props?.className??'')).length,0,'Ist ein Formular offen, ist „＋ Termin“ nur getönt: ein gefüllter Knopf je Ansicht');assert.equal(form.props.event.source_id,'google');assert.equal(form.props.event.uid,'google:work-event');
 toggle('Arbeit');assert.equal(nodes(tree,n=>n.props?.className==='calendar-time-event').length,0);
 assert.equal(nodes(tree,n=>n.props?.className==='calendar-agenda').length,0,'bei null Terminen kein „0 Termine … als Liste“');
 ansicht(tree,'Liste').props.onClick();tree=d.render();await d.flush();tree=d.render();
 assert.ok(nodes(tree,n=>n.type==='section'&&n.props['aria-label']==='Terminliste')[0],'Explicit list view keeps its primary list visible');
 assert.equal(nodes(tree,n=>n.props?.className==='calendar-agenda').length,0);
 }finally{globalThis.window=oldWindow;globalThis.localStorage=oldStorage;globalThis.__calendarDriver=oldDriver;await server.close();}
});
