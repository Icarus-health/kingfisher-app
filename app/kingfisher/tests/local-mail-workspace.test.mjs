import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('..',import.meta.url));
// Bausteine der Grundlage: Kopfaktionen (`aktionen`) und der Satz eines leeren Zustands (`satz`) zählen mit.
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);for(const c of [n.props?.children,n.props?.aktionen].flat(10))nodes(c,p,out);return out;}
function text(n){return n==null?'':typeof n==='object'?[n.props?.children,n.props?.satz].flat(10).map(text).join(''):String(n);}
async function harness(run){
 const server=await createServer({root,cacheDir:`/private/tmp/kf-mail-ssr-${process.pid}`,configFile:false,plugins:[{name:'local-mail-hooks',enforce:'pre',resolveId(id){if(id==='virtual:local-mail-hooks')return '\0'+id;},load(id){if(id==='\0virtual:local-mail-hooks')return 'export const useState=(...a)=>globalThis.__mailDriver.state(...a);export const useRef=(...a)=>globalThis.__mailDriver.ref(...a);export const useEffect=(...a)=>globalThis.__mailDriver.effect(...a);export const useCallback=f=>f;';},transform(code,id){if(/\/(Messages|MailReader)\.tsx$/.test(id))return code.replace(/from ["']react["']/g,'from "virtual:local-mail-hooks"');}}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
 const oldWindow=globalThis.window,oldDriver=globalThis.__mailDriver;
 const listeners=globalThis.__mailListeners={};
 globalThis.window={location:{search:'',pathname:'/messages',href:'http://synthetic/messages'},localStorage:{getItem(){return null;},setItem(){}},addEventListener(type,fn){(listeners[type]??=[]).push(fn);},removeEventListener(type,fn){listeners[type]=(listeners[type]??[]).filter(x=>x!==fn);}};
 function driver(Component,props){const values=[],refs=[],deps=[],pending=[];let si=0,ri=0,ei=0;const d={state(initial){const i=si++;if(!(i in values))values[i]=typeof initial==='function'?initial():initial;return[values[i],v=>values[i]=typeof v==='function'?v(values[i]):v];},ref(initial){return refs[ri++]??=({current:initial});},effect(fn,next){const i=ei++;if(!deps[i]||next.some((v,j)=>v!==deps[i][j])){deps[i]=next;pending.push(fn);}},render(){si=ri=ei=0;globalThis.__mailDriver=d;return Component(props);},async flush(){while(pending.length)pending.shift()();await new Promise(r=>setImmediate(r));}};return d;}
 try{await run(server,driver);}finally{globalThis.window=oldWindow;globalThis.__mailDriver=oldDriver;await server.close();}
}
test('saved mail reader loads local original and never starts provider or model actions on browsing',()=>harness(async(server,driver)=>{
 const {MailReader}=await server.ssrLoadModule('/src/MailReader.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 let remote=0;api.mailMessage=async()=>{remote++;throw Error('must not read');};
 const {localMailApi}=await server.ssrLoadModule('/src/localMailApi.ts');let reads=0;localMailApi.detail=async()=>{reads++;return{episode_id:'e-local',uid:'e-local',subject:'Saved',from:'Anna',body:'Original body',date:null,recorded_at:'2020-01-01T00:00:00Z',source_current:true,remote_uid:null,can_reply:false};};
 const entry=MailReader({uid:'e-local',localEpisodeId:'e-local',onClose(){}});
 const d=driver(entry.type,entry.props);d.render();await d.flush();const tree=d.render();
 assert.equal(reads,1);assert.equal(remote,0);assert.match(text(tree),/Original body/);assert.match(text(tree),/Datum unbekannt/);
 assert.equal(nodes(tree,n=>n.type?.name==='MailBriefing').length,0);
 assert.equal(nodes(tree,n=>n.type==='button'&&/Antwort entwerfen|Aktuelle Mail/.test(text(n))).length,0,'ohne Postfachkennung kein Antwortknopf');assert.match(text(tree),/nicht beantworten/);
}));

test('mail opens as readable original with compact sender and source details rather than a metadata form',()=>harness(async(server,driver)=>{
 const {MailReader}=await server.ssrLoadModule('/src/MailReader.tsx');const {localMailApi}=await server.ssrLoadModule('/src/localMailApi.ts');
 localMailApi.detail=async()=>({episode_id:'e-read',uid:'e-read',subject:'Projektabstimmung',from:'Anna <anna@example.invalid>',body:'Hallo,\n\nbitte prüfe den Entwurf.',date:'2020-01-01',recorded_at:'2026-10-14',account_label:'Privat',remote_uid:null});
 const entry=MailReader({uid:'e-read',localEpisodeId:'e-read',onClose(){}}),d=driver(entry.type,entry.props);d.render();await d.flush();const tree=d.render();
 const sourceDetails=nodes(tree,n=>n.type==='details'&&n.props.className==='mail-source-details')[0];assert.ok(sourceDetails);assert.equal(Boolean(sourceDetails.props.open),false);
 assert.match(text(sourceDetails),/Gespeichert/);assert.match(text(sourceDetails),/Privat/);
 const body=nodes(tree,n=>n.type==='section'&&n.props.className==='mail-reader-body')[0];assert.match(text(body),/bitte prüfe den Entwurf/);
 assert.equal(nodes(sourceDetails,n=>n===body).length,0,'The mail text must be readable without opening source details');
 const order=nodes(tree,n=>n===body||n.type?.name==='SavedMailWorkflow');assert.equal(order[0],body,'Read the actual message before the workflow form');
 assert.doesNotMatch(text(tree),/aktueller Postfachstand unbekannt/i,'Keine Plakette über der Mail');
 const order2=nodes(tree,n=>n===body||n===sourceDetails);assert.equal(order2[0],body,'Quelle steht unter der Mail, nicht darüber');
}));

test('compact account choice filters only local mail and resets pagination without provider retrieval',()=>harness(async(server,driver)=>{
 const {Messages}=await server.ssrLoadModule('/src/Messages.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');const {localMailApi}=await server.ssrLoadModule('/src/localMailApi.ts');
 let remote=0;api.messages=async()=>{remote++;throw Error('must not fetch');};const calls=[];
 localMailApi.page=async args=>{calls.push(args);return{items:[],accounts:[{id:'private',label:'Privat',count:3},{id:'work',label:'Arbeit',count:2}],total:0,offset:args.offset,has_more:false};};
 const d=driver(Messages,{recentConversation:null});d.render();await d.flush();let tree=d.render();
 const account=nodes(tree,n=>n.type==='select'&&n.props['aria-label']==='Postfach auswählen')[0];assert.ok(account);account.props.onChange({target:{value:'private'}});d.render();await d.flush();
 assert.equal(calls.at(-1).account_id,'private');assert.equal(calls.at(-1).offset,0);assert.equal(remote,0);
 tree=d.render();nodes(tree,n=>n.type==='select'&&n.props['aria-label']==='Postfach auswählen')[0].props.onChange({target:{value:''}});d.render();await d.flush();assert.equal(calls.at(-1).account_id,undefined);assert.equal(remote,0);
}));

test('opening a different mail resets its reading scroll while the return only restores list focus',()=>harness(async(server,driver)=>{
 const {Messages}=await server.ssrLoadModule('/src/Messages.tsx');const {localMailApi}=await server.ssrLoadModule('/src/localMailApi.ts');
 localMailApi.page=async()=>({items:[{episode_id:'saved',subject:'Deep mail',sender:'Anna'},{episode_id:'next',subject:'Next mail',sender:'Anna'}],accounts:[],total:2,has_more:false});
 const d=driver(Messages,{recentConversation:null});d.render();await d.flush();let tree=d.render();let readerFocus=0,listFocus=0,returnedOptions;
 const region=nodes(tree,n=>n.type==='section'&&n.props['aria-label']==='Lesebereich')[0];const scroller={scrollTop:420,querySelector(){return{focus(){readerFocus++;}};}};region.props.ref.current=scroller;
 nodes(tree,n=>n.type==='button'&&/Deep mail/.test(text(n)))[0].props.onClick({currentTarget:{focus(){listFocus++;}}});d.render();await d.flush();tree=d.render();
 assert.equal(scroller.scrollTop,0,'A newly selected mail must begin at the top of its reading column');assert.ok(readerFocus>=1);
 scroller.scrollTop=280;nodes(tree,n=>n.type==='button'&&/Next mail/.test(text(n)))[0].props.onClick({currentTarget:{focus(options){listFocus++;returnedOptions=options;}}});d.render();await d.flush();tree=d.render();assert.equal(scroller.scrollTop,0);
 nodes(tree,n=>n.type?.name==='MailReader')[0].props.onClose();d.render();await d.flush();assert.ok(listFocus>=1);assert.deepEqual(returnedOptions,{preventScroll:true});
}));
test('mail workspace keeps list next to selection and searches pages locally without retrieving provider mail',()=>harness(async(server,driver)=>{
 const {Messages}=await server.ssrLoadModule('/src/Messages.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');const {localMailApi}=await server.ssrLoadModule('/src/localMailApi.ts');
 let remote=0;api.messages=async()=>{remote++;throw Error('offline');};api.integrations=async()=>({mail_accounts:[]});
 const calls=[];localMailApi.page=async(args)=>{calls.push(args);return{items:[{episode_id:'e-a',account_id:'a',subject:'Budget',sender:'Anna',date:null,preview:'saved text'}],accounts:[{id:'a',label:'Privat',count:41,last_sync:null}],total:41,offset:args.offset,limit:40,has_more:args.offset===0,detail:'Saved scope'};};
 const d=driver(Messages,{recentConversation:null});d.render();await d.flush();let tree=d.render();
 assert.equal(remote,0);nodes(tree,n=>n.type==='button'&&/Budget/.test(text(n)))[0].props.onClick();tree=d.render();
 assert.equal(nodes(tree,n=>n.type?.name==='MailReader').length,1);assert.match(text(tree),/Budget/);
 nodes(tree,n=>n.type==='button'&&text(n)==='Weiter')[0].props.onClick();tree=d.render();await d.flush();tree=d.render();assert.equal(calls.at(-1).offset,40);
 const input=nodes(tree,n=>n.type==='input'&&n.props.type==='search')[0];input.props.onChange({target:{value:'Rechnung'}});tree=d.render();await d.flush();assert.equal(calls.at(-1).q,'Rechnung');assert.equal(calls.at(-1).offset,0);assert.equal(remote,0);
 nodes(d.render(),n=>n.type==='button'&&/Neue Mails abrufen/.test(text(n)))[0].props.onClick();await d.flush();tree=d.render();assert.equal(remote,1);assert.match(text(tree),/Budget/);
}));
test('explicit fresh retrieval exposes its current rows while a later provider failure preserves saved originals',()=>harness(async(server,driver)=>{
 const {Messages}=await server.ssrLoadModule('/src/Messages.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');const {localMailApi}=await server.ssrLoadModule('/src/localMailApi.ts');
 localMailApi.page=async()=>({items:[{episode_id:'saved',account_id:'a',subject:'Historical',sender:'Anna',date:null,preview:'Original'}],accounts:[],total:1,offset:0,limit:40,has_more:false});
 let remote=0;api.messages=async()=>{if(remote++)throw Error('offline');return{messages:[{id:'a:9.1',account_id:'a',subject:'Fresh incoming',sender:'Anna',date:null,preview:'Fresh'}],partial_failure:null};};
 const d=driver(Messages,{recentConversation:null});d.render();await d.flush();let tree=d.render();
 nodes(tree,n=>n.type==='button'&&/Neue Mails abrufen/.test(text(n)))[0].props.onClick();await d.flush();tree=d.render();assert.match(text(tree),/Fresh incoming/);assert.match(text(tree),/Historical/);
 nodes(tree,n=>n.type==='button'&&/Fresh incoming/.test(text(n)))[0].props.onClick({currentTarget:{focus(){}}});tree=d.render();const reader=nodes(tree,n=>n.type?.name==='MailReader')[0];assert.equal(reader.props.uid,'a:9.1');assert.equal(reader.props.localEpisodeId,undefined);
 nodes(tree,n=>n.type==='button'&&/Neue Mails abrufen/.test(text(n)))[0].props.onClick();await d.flush();tree=d.render();assert.match(text(tree),/Fresh incoming/);assert.match(text(tree),/Historical/);
}));
test('source exclusion immediately clears the saved body and only the original-only view is mounted during browsing',()=>harness(async(server,driver)=>{
 const {MailReader}=await server.ssrLoadModule('/src/MailReader.tsx');const {localMailApi}=await server.ssrLoadModule('/src/localMailApi.ts');let excluded=false;
 localMailApi.detail=async()=>{if(excluded)throw Error('HTTP 409');return{uid:'saved',episode_id:'saved',subject:'Saved',from:'Anna',body:'Sensitive original',date:null,recorded_at:'2020-01-01',remote_uid:null};};
 const entry=MailReader({uid:'saved',localEpisodeId:'saved',onClose(){}}),d=driver(entry.type,entry.props);d.render();await d.flush();let tree=d.render();
 const original=nodes(tree,n=>n.type?.name==='ProfileSource')[0];assert.equal(original.props.originalOnly,true);
 nodes(tree,n=>n.type==='button'&&text(n)==='Quelle zuordnen oder ausschließen')[0].props.onClick();tree=d.render();const management=nodes(tree,n=>n.type?.name==='ProfileSource'&&!n.props.originalOnly)[0];assert.ok(management);
 excluded=true;management.props.onChange();tree=d.render();assert.doesNotMatch(text(tree),/Sensitive original/);await d.flush();tree=d.render();assert.match(text(tree),/ausgeschlossen/);
}));
test('the list reloads by itself when the window returns and revalidates an open saved source even when it is no longer in the page',()=>harness(async(server,driver)=>{
 const {Messages}=await server.ssrLoadModule('/src/Messages.tsx');const {MailReader}=await server.ssrLoadModule('/src/MailReader.tsx');const {localMailApi}=await server.ssrLoadModule('/src/localMailApi.ts');let excluded=false,reads=0;
 localMailApi.page=async()=>({items:excluded?[]:[{episode_id:'saved',subject:'Saved subject',sender:'Anna'}],accounts:[],total:excluded?0:1,limit:40,has_more:false});
 localMailApi.detail=async()=>{reads++;if(excluded)throw Error('HTTP 409');return{uid:'saved',episode_id:'saved',subject:'Saved subject',body:'Withdrawn original',remote_uid:'a:1.2'};};
 const d=driver(Messages,{recentConversation:null});d.render();await d.flush();let tree=d.render();nodes(tree,n=>n.type==='button'&&/Saved subject/.test(text(n)))[0].props.onClick({currentTarget:{focus(){}}});tree=d.render();
 const listFocus=[...(globalThis.__mailListeners.focus??[])];assert.ok(listFocus.length>=1,'Die Liste horcht auf die Rückkehr ins Fenster');
 const entry=MailReader(nodes(tree,n=>n.type?.name==='MailReader')[0].props),savedProps={...entry.props},reader=driver(entry.type,savedProps);reader.render();await reader.flush();let opened=reader.render();assert.match(text(opened),/Withdrawn original/);
 nodes(opened,n=>n.type?.name==='SavedMailWorkflow')[0].props.nebenAktion.props.onClick();assert.equal(nodes(reader.render(),n=>n.type?.name==='RemoteMailReader').length,1);
 excluded=true;assert.equal(nodes(tree,n=>n.type==='button'&&n.props['aria-label']==='Lokale Nachrichtenliste aktualisieren').length,0,'kein Handbetrieb');for(const fn of listFocus)fn();tree=d.render();await d.flush();tree=d.render();
 const selected=nodes(tree,n=>n.type?.name==='MailReader')[0];assert.equal(selected.props.localEpisodeId,'saved');Object.assign(savedProps,MailReader(selected.props).props);reader.render();await reader.flush();const refreshed=reader.render();
 assert.equal(reads,2);assert.doesNotMatch(text(refreshed),/Withdrawn original/);assert.match(text(refreshed),/ausgeschlossen/);
 assert.equal(nodes(refreshed,n=>n.type?.name==='RemoteMailReader').length,0);
}));

test('remote action panels keep reply drafts and a briefing suggestion opens and focuses the task editor without submitting',()=>harness(async(server,driver)=>{
 const {MailReader}=await server.ssrLoadModule('/src/MailReader.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 let writes=0;api.mailMessage=async()=>({uid:'live',subject:'Projektbrief',from:'Anna',body:'Original',source_digest:'d',can_reply:true});
 api.prepareMailReply=async()=>{writes++;};window.localStorage={getItem(){return null;},setItem(){}};
 const entry=MailReader({uid:'live',onClose(){}}),d=driver(entry.type,entry.props);d.render();await d.flush();let tree=d.render();
 const findPanel=(t,label)=>nodes(t,n=>n.type==='details'&&text(nodes(n,x=>x.type==='summary')[0]).startsWith(label))[0];
 assert.equal(Boolean(findPanel(tree,'Antwort schreiben').props.open),false);assert.equal(Boolean(findPanel(tree,'Aufgabe aus dieser Mail').props.open),false);
 assert.equal(nodes(tree,n=>n.type?.name==='MailTaskForm')[0].props.initiallyOpen,true,'outer action opens the usable form in one step');
 nodes(tree,n=>n.type==='textarea'&&n.props.id==='mail-reply')[0].props.onChange({target:{value:'Mein Antwortentwurf'}});tree=d.render();
 assert.equal(findPanel(tree,'Antwort schreiben').props.open,true);assert.equal(nodes(tree,n=>n.type==='textarea'&&n.props.id==='mail-reply')[0].props.value,'Mein Antwortentwurf');
 let focused=0,scrolled=0;const panel={open:false,scrollIntoView(){scrolled++;},querySelector(){return{focus(){focused++;}};}};
 findPanel(tree,'Aufgabe aus dieser Mail').props.ref.current=panel;
 const suggestion={title:'Belege prüfen',quote:'Bitte die Belege prüfen.',source_digest:'d'};
 nodes(tree,n=>n.type?.name==='MailBriefing')[0].props.onPrepareTask(suggestion);tree=d.render();
 assert.equal(panel.open,true);assert.equal(focused,1);assert.equal(scrolled,1);assert.equal(writes,0);
 assert.deepEqual(nodes(tree,n=>n.type?.name==='MailTaskForm')[0].props.initialSuggestion,suggestion);
 assert.equal(nodes(tree,n=>n.type==='textarea'&&n.props.id==='mail-reply')[0].props.value,'Mein Antwortentwurf');
}));

test('on a wide window the newest mail opens by itself without taking focus; on a narrow one the list stays',()=>harness(async(server,driver)=>{
 const {Messages}=await server.ssrLoadModule('/src/Messages.tsx');const {localMailApi}=await server.ssrLoadModule('/src/localMailApi.ts');
 localMailApi.page=async()=>({items:[{episode_id:'neu',subject:'Neueste',sender:'Anna'},{episode_id:'alt',subject:'Ältere',sender:'Ben'}],accounts:[],total:2,has_more:false});
 for(const breit of [true,false]){
  globalThis.window.matchMedia=query=>({matches:breit&&/min-width/.test(query)});
  const d=driver(Messages,{recentConversation:null});d.render();await d.flush();let tree=d.render();
  const region=nodes(tree,n=>n.type==='section'&&n.props['aria-label']==='Lesebereich')[0];let fokus=0;region.props.ref.current={scrollTop:0,querySelector(){return{focus(){fokus++;}};}};
  await d.flush();tree=d.render();await d.flush();tree=d.render();
  const leser=nodes(tree,n=>n.type?.name==='MailReader');
  if(breit){assert.equal(leser.length,1,'breit: Lesebereich ist nicht leer');assert.equal(leser[0].props.localEpisodeId,'neu');assert.equal(fokus,0,'die Suche behält den Fokus');}
  else{assert.equal(leser.length,0,'schmal: erst die Liste');assert.match(text(tree),/Wähle eine Nachricht/);}
  // Wer schließt, bekommt nicht gleich wieder dieselbe Mail aufgedrängt.
  if(breit){leser[0].props.onClose();d.render();await d.flush();tree=d.render();assert.equal(nodes(tree,n=>n.type?.name==='MailReader').length,0);}
 }
 delete globalThis.window.matchMedia;
}));

test('P4: Postfachwahl und Seitenwahl stehen nur da, wenn es etwas zu wählen gibt',()=>harness(async(server,driver)=>{
 const {Messages}=await server.ssrLoadModule('/src/Messages.tsx');const {localMailApi}=await server.ssrLoadModule('/src/localMailApi.ts');
 let konten=[{id:'a',label:'Privat',count:2}],mehr=false;
 localMailApi.page=async args=>({items:[{episode_id:'e1',subject:'Eins',sender:'Anna'},{episode_id:'e2',subject:'Zwei',sender:'Ben'}],accounts:konten,total:2,offset:args.offset,has_more:mehr});
 let d=driver(Messages,{recentConversation:null});d.render();await d.flush();let tree=d.render();
 assert.equal(nodes(tree,n=>n.type==='select'&&n.props['aria-label']==='Postfach auswählen').length,0,'ein Postfach: keine Wahl');
 assert.equal(nodes(tree,n=>n.type==='nav'&&n.props['aria-label']==='Nachrichtenseiten').length,0,'eine Seite: keine Seitenwahl');
 konten=[...konten,{id:'b',label:'Arbeit',count:41}];mehr=true;
 d=driver(Messages,{recentConversation:null});d.render();await d.flush();tree=d.render();
 assert.equal(nodes(tree,n=>n.type==='select'&&n.props['aria-label']==='Postfach auswählen').length,1);
 assert.equal(nodes(tree,n=>n.type==='nav'&&n.props['aria-label']==='Nachrichtenseiten').length,1);
}));

test('P4: Aufgabe, Termin und Antwort klappen wie eine Liste; öffnet eines, schließen die anderen',()=>harness(async(server,driver)=>{
 const {MailReader}=await server.ssrLoadModule('/src/MailReader.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 api.mailMessage=async()=>({uid:'live',subject:'Projektbrief',from:'Anna <anna@example.invalid>',body:'Original',source_digest:'d',can_reply:true});window.localStorage={getItem(){return null;},setItem(){}};
 const entry=MailReader({uid:'live',onClose(){}}),d=driver(entry.type,entry.props);d.render();await d.flush();const tree=d.render();
 const panels=nodes(tree,n=>n.type==='details'&&/mail-action-panel/.test(n.props.className??''));assert.equal(panels.length,3);
 const fakes=panels.map(()=>({open:true}));panels.forEach((p,i)=>{p.props.ref.current=fakes[i];});
 panels[1].props.onToggle({currentTarget:fakes[1]});
 assert.deepEqual(fakes.map(f=>f.open),[false,true,false]);
 fakes[2].open=false;panels[2].props.onToggle({currentTarget:fakes[2]});assert.deepEqual(fakes.map(f=>f.open),[false,true,false],'Schließen schließt nichts anderes');
}));
