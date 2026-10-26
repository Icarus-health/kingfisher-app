import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
const server=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),cacheDir:`/private/tmp/kingfisher-adaptive-tests-${process.pid}`,configFile:false,plugins:[{name:'adaptive-hooks',enforce:'pre',resolveId(id){if(id==='virtual:adaptive-hooks')return '\0'+id;},load(id){if(id==='\0virtual:adaptive-hooks')return `export const useState=(v)=>globalThis.__adaptiveState(v);export const useRef=v=>({current:v});export const useEffect=()=>{};export const useCallback=f=>f;export const useMemo=f=>f();`;},transform(code,id){if(['/App.tsx','/TodayOverview.tsx','/TodaySourceStatus.tsx','/TodayTaskRow.tsx','/TaskReminders.tsx','/KnowledgeQuestions.tsx','/MemoryQuestions.tsx','/TaskSuggestions.tsx','/PersonDigest.tsx'].some(p=>id.endsWith(p)))return code.replace(/from (["'])react\1/,'from "virtual:adaptive-hooks"')+(id.endsWith('/TaskSuggestions.tsx')?'\nexport {Suggestion,initialDraft};':id.endsWith('/App.tsx')?'\nexport {Morning};':'\n');}}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {Morning}=await server.ssrLoadModule('/src/App.tsx');
const {TodayOverview}=await server.ssrLoadModule('/src/TodayOverview.tsx');
const {TodayTaskRow}=await server.ssrLoadModule('/src/TodayTaskRow.tsx');
const {TodaySourceStatus}=await server.ssrLoadModule('/src/TodaySourceStatus.tsx');
const {TaskReminders}=await server.ssrLoadModule('/src/TaskReminders.tsx');
const {KnowledgeQuestions}=await server.ssrLoadModule('/src/KnowledgeQuestions.tsx');
const {Suggestion,initialDraft}=await server.ssrLoadModule('/src/TaskSuggestions.tsx');
const {MemoryQuestions}=await server.ssrLoadModule('/src/MemoryQuestions.tsx');
const {PersonDigest}=await server.ssrLoadModule('/src/PersonDigest.tsx');
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);[n.props?.children].flat(50).forEach(c=>nodes(c,p,out));return out;}
function text(n){return n==null?'':typeof n==='object'?[n.props?.children].flat(50).map(text).join(''):String(n);}
function render(fn,seeds=[]){let i=0;globalThis.__adaptiveState=v=>{const slot=i++;return [slot in seeds?seeds[slot]:(typeof v==='function'?v():v),value=>seeds[slot]=typeof value==='function'?value(seeds[slot]):value];};try{return fn();}finally{delete globalThis.__adaptiveState;}}
const briefing={generated_at:'2026-10-15T08:00:00Z',timezone:'Europe/Berlin',partial_failures:[],happening_now:[],later_today:[],needs_you:[{id:'a',title:'Bericht prüfen',reason:'Dieser Mailverlauf ist nicht vollständig geprüft.',detail:'Dieser Mailverlauf ist nicht vollständig geprüft.',action:'Verlauf prüfen',source:'aufgabe',source_ref:'t1'}]};
test('today keeps the unresolved review warning visible while its full explanation is available on demand',()=>{
 // V1: die Aufgabe ist die Zeile der Liste; der Hinweis steht leise in ihr, die ganze Erklärung in der geöffneten Aufgabe.
 const row=render(()=>TodayTaskRow({item:briefing.needs_you[0],onChanged(){},onOpen(){}}));
 const taskRow=nodes(row,n=>n.type?.name==='TaskRow')[0];assert.equal(taskRow.props.hinweis,'Verlauf ungeprüft','review uncertainty must stay visible in the row');
 const state=[];const draw=()=>TodayOverview({briefing,onChange(){},onTaskDone(){},onOpenMail(){},taskNotice:'',correctionSaved:false});
 let today=render(draw,state);nodes(today,n=>n.type?.name==='TodayTaskRow')[0].props.onOpen();
 today=render(draw,state);
 const panel=nodes(today,n=>n.type?.name==='DetailPanel')[0];assert.ok(panel,'the row opens the task');
 assert.match(text(panel),/Dieser Mailverlauf ist nicht vollständig geprüft\./,'the complete source explanation must remain reachable');
});
test('source status says what is missing in one open line, and nothing when the overview is complete (Paket U, H4)',()=>{
 const tree=TodaySourceStatus({briefing:{...briefing,partial_failures:[{section:'mail',message:'Postfach ist nicht verbunden.'}]},refreshing:false,refreshError:false,onRefresh(){}});
 assert.notEqual(tree.type,'details','was fehlt, steht offen da');assert.equal(tree.props.role,'status');
 assert.match(text(tree),/Postfach ist nicht verbunden\./);assert.doesNotMatch(text(tree),/unvollständig/i,'kein Angstwort ohne Inhalt');
 assert.equal(nodes(tree,n=>n.type==='a')[0].props.href,'/settings#zugaenge');
 assert.equal(TodaySourceStatus({briefing,refreshing:false,refreshError:false,onRefresh(){}}),null,'vollständig: keine Zeile');
 const post=TodaySourceStatus({briefing:{...briefing,post_ausstehend:true},refreshing:false,refreshError:false,onRefresh(){}});
 assert.match(text(post),/Die Post von heute ist noch nicht da\. Kingfisher holt sie gerade\./);
 let retried=0;const failed=TodaySourceStatus({briefing,refreshing:false,refreshError:true,onRefresh(){retried++;}});
 assert.match(text(failed),/letzte geladene Stand/);nodes(failed,n=>n.type==='button'&&text(n)==='Erneut versuchen')[0].props.onClick();assert.equal(retried,1);
});
test('compact followups disappear only for successfully loaded empty results; errors and confirmation messages stay',()=>{
 const props={active:true,compact:true,onChanged(){},onOpenAll(){}};
 assert.equal(render(()=>TaskReminders(props),[[],false,false,false,'','','','']),null);
 assert.equal(render(()=>KnowledgeQuestions(props),[[],false,'','','',null,5,0,false]),null);
 assert.equal(render(()=>MemoryQuestions(props),[[],'','','','']),null);
 assert.notEqual(render(()=>TaskReminders(props),[[{id:'t',title:'Erinnerung',remind_at:'2026-10-15T09:00:00Z'}],false,false,false,'','','','']),null);
 assert.notEqual(render(()=>TaskReminders(props),[[],true,false,false,'','','','']),null,'a truncated result is not a confirmed empty state');
 assert.notEqual(render(()=>MemoryQuestions(props),[[{id:'m',text:'Bitte prüfen'}],'','','','']),null);
 assert.notEqual(render(()=>TaskReminders(props),[[],false,false,false,'Offline','','','']),null);
 assert.notEqual(render(()=>KnowledgeQuestions(props),[[],false,'Fehler','','',null,5,0,false]),null);
 assert.notEqual(render(()=>MemoryQuestions(props),[[],'','','Bestätigt','']),null);
 // The dedicated pages keep their reassuring empty states.
 assert.notEqual(render(()=>MemoryQuestions({...props,compact:false}),[[],'','','','']),null);
});

function firstLayer(n){if(n?.type==='details')return text(nodes(n,x=>x.type==='summary')[0]);if(n==null)return '';return typeof n==='object'?[n.props?.children].flat(50).map(firstLayer).join(''):String(n);}
test('suggestions retain project, exact deadline and temporal warning before optional evidence',()=>{
 const item={id:'c1',statement:'Bericht abgeben',temporal_status:'old',valid_until:'2020-01-01T09:15:00Z',temporal_reason:'Historische Testquelle',evidence:[{episode_id:'e1',quote:'Wörtlicher Testbeleg',digest:'d'}],project_suggestion:{project_id:'p1',name:'Projekt Eins',reason:'Quellenbezug'}};
 const props={projects:[{id:'p1',name:'Projekt Eins',open:true}],onDone(){},onDraftChange(){},selected:false,onSelected(){}};
 let tree=render(()=>Suggestion({...props,item,draft:initialDraft(item)}));
 assert.match(firstLayer(tree),/Historisch/);assert.match(firstLayer(tree),/Projekt Eins/);assert.match(firstLayer(tree),/Ohne Frist/);assert.doesNotMatch(firstLayer(tree),/Wörtlicher Testbeleg/);
 assert.match(text(nodes(tree,n=>n.type==='details')[0]),/Wörtlicher Testbeleg/);
 const recent={...item,temporal_status:'recent',valid_until:'2026-10-15T09:15:00Z'};
 tree=render(()=>Suggestion({...props,item:recent,draft:initialDraft(recent)}));
 assert.ok(firstLayer(tree).includes(new Date(recent.valid_until).toLocaleString('de-DE',{dateStyle:'medium',timeStyle:'short'})),'preserved time must be in the visible confirmation');
});

test('one-time update results are not mounted inside a closed disclosure',()=>{
 const before=globalThis.window;globalThis.window={location:{search:''}};
 try {const tree=render(()=>Morning({recentConversation:null,rememberConversation(){},chatAvailable:true}),[{...briefing,greeting:'Guten Morgen.'}]);
  assert.equal(nodes(tree,n=>n.type?.name==='FassungHeute').length,1);
  for(const detail of nodes(tree,n=>n.type==='details'))assert.equal(nodes(detail,n=>n.type?.name==='FassungHeute').length,0,'update result must be visible before it is consumed');
 } finally {globalThis.window=before;}
});

test('activity is first read only on opening its disclosure and keeps its editor mounted after closing',()=>{
 const state=[];const draw=()=>TodayOverview({briefing,onChange(){},onTaskDone(){},onOpenMail(){},taskNotice:'',correctionSaved:false});
 let tree=render(draw,state);assert.equal(nodes(tree,n=>n.type?.name==='TagesLage').length,0,'closed activity must not consume the since-last-view marker');
 const zeile=()=>nodes(tree,n=>n.type==='button'&&n.props.className==='g-zeile today-activity-zeile')[0];
 assert.equal(zeile().props['aria-expanded'],false);zeile().props.onClick();
 tree=render(draw,state);assert.equal(nodes(tree,n=>n.type?.name==='TagesLage').length,1);assert.equal(zeile().props['aria-expanded'],true);
 zeile().props.onClick();
 tree=render(draw,state);assert.equal(nodes(tree,n=>n.type?.name==='TagesLage').length,1,'an already opened activity keeps local drafts');
 assert.equal(nodes(tree,n=>n.props?.className==='today-activity-inhalt')[0].props.hidden,true,'closed again, but still mounted');
});

test('compact person digest keeps stale status and errors visible outside its closed tools',()=>{
 const stale={status:'stale',digest:{points:[],questions:[],conflicts:[],generated_at:'2026-10-15T09:00:00Z'},source_count:1,total_source_count:2};
 let tree=render(()=>PersonDigest({personId:'test',compact:true}),[stale,false,false,'']);
 assert.match(firstLayer(tree),/Quellen geändert/);assert.match(firstLayer(tree),/veraltet/);assert.doesNotMatch(firstLayer(tree),/Eine Interpretation/);
 assert.equal(Boolean(nodes(tree,n=>n.type==='details')[0].props.open),false);
 tree=render(()=>PersonDigest({personId:'test',compact:true}),[null,false,false,'Quellen nicht erreichbar.']);
 assert.match(firstLayer(tree),/Quellen nicht erreichbar/);assert.equal(nodes(tree,n=>n.props?.role==='alert').length,1);
});
