import {test, after} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';

const server = await createServer({root:fileURLToPath(new URL('..', import.meta.url)), configFile:false,
  cacheDir:`/private/tmp/kingfisher-settings-tests-${process.pid}`,
  plugins:[{name:'settings-hooks', enforce:'pre', resolveId(id){if(id==='virtual:settings-hooks')return '\0'+id;},
    load(id){if(id==='\0virtual:settings-hooks')return `export const useState=v=>globalThis.__settingsState(v);export const useEffect=()=>{};export const useRef=v=>({current:v});export const useCallback=f=>f;`;},
    transform(code,id){if(['/SettingsSections.tsx','/CloudAccess.tsx','/ChatGPTAccess.tsx','/CloudMemory.tsx','/GoogleSignIn.tsx','/ModelRecommendation.tsx','/WeltSettings.tsx','/Einrichtung/KingfisherLernt.tsx','/Einstellungen/Aufklapp.tsx'].some(p=>id.endsWith(p)))return code.replace(/from (["'])react\1/,'from "virtual:settings-hooks"');}}],
  server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {SettingsSections}=await server.ssrLoadModule('/src/SettingsSections.tsx');
const {Aufklapp}=await server.ssrLoadModule('/src/Einstellungen/Aufklapp.tsx');
const {CloudAccess}=await server.ssrLoadModule('/src/CloudAccess.tsx');
const {ChatGPTAccess}=await server.ssrLoadModule('/src/ChatGPTAccess.tsx');
const {CloudMemory}=await server.ssrLoadModule('/src/CloudMemory.tsx');
const {GoogleSignIn}=await server.ssrLoadModule('/src/GoogleSignIn.tsx');
const {ModelRecommendation}=await server.ssrLoadModule('/src/ModelRecommendation.tsx');
const {Nachrichten}=await server.ssrLoadModule('/src/WeltSettings.tsx');
const {KingfisherLernt}=await server.ssrLoadModule('/src/Einrichtung/KingfisherLernt.tsx');
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);[n.props?.children].flat(50).forEach(c=>nodes(c,p,out));return out;}
function text(n){return n==null?'':typeof n==='object'?[n.props?.children].flat(50).map(text).join(''):String(n);}
function render(fn,seeds=[]){let i=0;globalThis.__settingsState=v=>{const slot=i++;if(!(slot in seeds))seeds[slot]=typeof v==='function'?v():v;return [seeds[slot],value=>seeds[slot]=typeof value==='function'?value(seeds[slot]):value];};try{return fn();}finally{delete globalThis.__settingsState;}}
function firstLayer(n){if(n?.type==='details')return text(nodes(n,x=>x.type==='summary')[0]);return n==null?'':typeof n==='object'?[n.props?.children].flat(50).map(firstLayer).join(''):String(n);}

test('compact settings selector retains the separate technical group and uses the same navigation',()=>{
  let selected;
  const tree=render(()=>SettingsSections({sections:[{id:'ki',label:'KI & Modelle',description:'Modell',content:'KI-Inhalt'},{id:'technik',label:'Für Techniker',description:'Details',content:'Technik-Inhalt',hinten:true}],selected:'ki',onSelect:id=>selected=id}));
  const select=nodes(tree,n=>n.type==='select'&&n.props['aria-label']==='Einstellungsbereich')[0];assert.ok(select);
  assert.match(text(nodes(select,n=>n.type==='optgroup'&&n.props.label==='Für Techniker')[0]),/Für Techniker/);
  select.props.onChange({target:{value:'technik'}});assert.equal(selected,'technik');
  assert.equal(nodes(tree,n=>n.type==='section'&&n.props.hidden===true)[0].props.children[1].props.children,null,'unvisited sections do not start loading');
});
test('reopening an optional setting preserves its mounted editor',()=>{
  const state=[];const draw=()=>Aufklapp({id:'test',titel:'Modell wählen',satz:'Details',children:'editor'});
  let tree=render(draw,state);assert.doesNotMatch(text(tree),/editor/);
  tree.props.onToggle({currentTarget:{open:true}});tree=render(draw,state);assert.match(text(tree),/editor/);
  tree.props.onToggle({currentTarget:{open:false}});tree=render(draw,state);assert.match(text(tree),/editor/);assert.equal(tree.props.open,false);
});
const provider={id:'mistral',label:'Mistral',endpoint:'https://api.mistral.ai/v1',key_present:true,model:'test-model'};
test('provider status is visible while credential fields stay closed and keep unsaved edits',()=>{
  const state=[{storage_available:true,providers:[provider]},false,{mistral:{apiKey:'',model:'test-model'}},null,null];
  let tree=render(()=>CloudAccess(),state);
  const panel=nodes(tree,n=>n.type==='details'&&text(n).includes('Mistral'))[0];assert.ok(panel);assert.equal(Boolean(panel.props.open),false);
  assert.match(firstLayer(tree),/Schlüssel hinterlegt/);assert.doesNotMatch(firstLayer(tree),/EU-Endpunkt/);
  const model=nodes(panel,n=>n.type==='input'&&n.props.value==='test-model')[0];model.props.onChange({target:{value:'ungespeicherter Entwurf'}});
  tree=render(()=>CloudAccess(),state);assert.ok(nodes(tree,n=>n.type==='input'&&n.props.value==='ungespeicherter Entwurf').length);
  assert.match(firstLayer(tree),/Ungespeichert/);assert.match(firstLayer(tree),/Speichern schaltet Cloud nicht ein/);
});
test('cloud failures are not buried in a closed provider panel',()=>{
  const tree=render(()=>CloudAccess(),[{storage_available:false,providers:[provider]},true,{},null,{ok:false,text:'Speichern fehlgeschlagen'}]);
  assert.match(firstLayer(tree),/Speichern fehlgeschlagen/);assert.match(firstLayer(tree),/nicht verfügbar/);assert.match(firstLayer(tree),/nicht geladen/);
});
test('optional ChatGPT sign-in starts closed, but restored flow and errors remain visible',()=>{
  const tree=render(()=>ChatGPTAccess(),[{connected:false,accounts:[],secure_storage:true},[],'',false,{session_id:'test',url:'https://auth.openai.com/test'},false,'','Anmeldung fehlgeschlagen','','']);
  const login=nodes(tree,n=>n.type==='details'&&text(n).includes('Mit deinem ChatGPT-Konto verbinden'))[0];assert.ok(login);assert.equal(Boolean(login.props.open),false);
  assert.match(firstLayer(tree),/Anmeldung läuft im Browser/);assert.match(firstLayer(tree),/Anmeldung fehlgeschlagen/);
  assert.match(text(login),/außerhalb der EU/);assert.equal(nodes(login,n=>n.type==='button'&&text(n)==='Mit ChatGPT anmelden')[0].props.disabled,true);
});
test('cloud memory pause and errors remain visible before optional explanations',()=>{
  const job={id:'test',state:'paused',selected:100,position:20,completed:20,failed:0,requests:20,request_limit:100,model:'test',stop_reason:'Pausiert durch dich',issues:[]};
  const tree=render(()=>CloudMemory({model:'test',connected:true}),[job,null,false,false,'Quelle nicht erreichbar']);
  assert.match(firstLayer(tree),/Einordnung pausiert/);assert.match(firstLayer(tree),/20 von 100/);assert.match(firstLayer(tree),/Quelle nicht erreichbar/);
  assert.ok(nodes(tree,n=>n.type==='button'&&text(n)==='Dieses Paket fortsetzen').length);
  assert.ok(nodes(tree,n=>n.type==='details'&&text(n).includes('Ergebnisse bleiben Quellenbefunde')).length,'explanation stays reachable');
});

test('missing ChatGPT credential storage remains visible with its sign-in panel closed',()=>{
  const tree=render(()=>ChatGPTAccess(),[{connected:false,accounts:[],secure_storage:false}]);
  assert.match(firstLayer(tree),/geschützte Zugangsspeicher fehlt/);
});

test('compact Google login keeps restored progress, calendar confirmation and failures outside its disclosure',()=>{
  const base=[{configured:true,secure_storage:true},{session_id:'test',url:'https://accounts.google.com/test'},null,[],false,''];
  const props={compact:true,kind:'calendar',active:true,onConnected(){}};
  let tree=render(()=>GoogleSignIn(props),base);
  assert.equal(Boolean(nodes(tree,n=>n.type==='details')[0].props.open),false);
  assert.match(firstLayer(tree),/Wir warten auf deine Anmeldung/);
  const ready=[...base];ready[2]={status:'ready',email:'test@example.invalid',calendars:[{id:'calendar-test',name:'Testkalender'}]};ready[3]=['calendar-test'];
  tree=render(()=>GoogleSignIn(props),ready);
  assert.match(firstLayer(tree),/Testkalender/);assert.match(firstLayer(tree),/Verbindung bestätigen/);
  assert.equal(nodes(tree,n=>n.type==='button'&&text(n)==='Ausgewählte Kalender verbinden')[0].props.disabled,false);
  const failed=[...base];failed[0]={configured:true,secure_storage:false};failed[2]={status:'failed'};
  tree=render(()=>GoogleSignIn(props),failed);assert.match(firstLayer(tree),/geschützte Speicher/);assert.match(firstLayer(tree),/nicht abgeschlossen/);
});

test('model downloads and their errors are visible while the model catalogue is collapsed',()=>{
  let tree=render(()=>ModelRecommendation({compact:true}),[null,false,null,{rolle:'antwort',titel:'Antwortmodell',state:{phase:'laedt',fortschritt:0.5}},null]);
  assert.match(firstLayer(tree),/Antwortmodell/);assert.match(firstLayer(tree),/50 %/);
  assert.equal(Boolean(nodes(tree,n=>n.type==='details')[0].props.open),false);
  tree=render(()=>ModelRecommendation({compact:true}),[null,false,null,{rolle:'antwort',titel:'Antwortmodell',state:{phase:'fehler',fehler:{grund:'Ollama fehlt.',naechster_schritt:'Ollama starten.'}}},null]);
  assert.match(firstLayer(tree),/Ollama fehlt/);assert.ok(nodes(tree,n=>n.props?.role==='alert').length);
  tree=render(()=>ModelRecommendation({compact:true}),[null,true,null,null,{ok:true,text:'Eingerichtet und geprüft.'}]);
  assert.match(firstLayer(tree),/Eingerichtet und geprüft/);assert.match(firstLayer(tree),/konnte nicht geladen/);
});

const news={aktiv:true,feeds:[{id:'feed-test',label:'Testzeitung',enabled:true,fehler:'Abruf fehlgeschlagen'}],weltquellen:[],vorschlaege:[],vorschlaege_stand:{stand:'2026-09-30',abgerufen:null},abbestellt:[],modell:false};
test('news source choices start closed, with current selection and source failures still visible',()=>{
  const state=[news,'https://draft.invalid/feed','Entwurf',false,'',''];
  let tree=render(()=>Nachrichten(),state);
  const choices=nodes(tree,n=>n.type==='details'&&text(n).includes('Quellen ändern'))[0];assert.ok(choices);assert.equal(Boolean(choices.props.open),false);
  assert.match(firstLayer(tree),/Testzeitung/);assert.match(firstLayer(tree),/Abruf fehlgeschlagen/);assert.doesNotMatch(firstLayer(tree),/Eigene Quelle: Adresse/);
  assert.equal(nodes(tree,n=>n.type==='input'&&n.props.id==='welt-feed-url')[0].props.value,'https://draft.invalid/feed');
  tree=render(()=>Nachrichten(),[null,'','',false,'Einstellung nicht erreichbar','']);assert.match(firstLayer(tree),/Einstellung nicht erreichbar/);
});

const pausedWork={pausiert:true,zustand:'pausiert',grund:'Pausiert. Kingfisher lernt weiter, wenn du „Weiter“ wählst.',fortschritt:{fertig:329,gesamt:347,offen:18}};
const workRows=[{id:'einordnen',fertig:329,gesamt:347,text:'329 von 347 Quellen, pausiert'},
  {id:'mail',fertig:1587,gesamt:122399,text:'Postfach Test: Einlesen pausiert. Bereits 1.587 von 122.399 Mails gelesen.'}];
test('paused work starts with a single source progress and moves mail details and explanations behind Details',()=>{
  const tree=render(()=>KingfisherLernt({}),[workRows,pausedWork,false,'',false,0]);
  const details=nodes(tree,n=>n.type==='details')[0];assert.ok(details);assert.equal(Boolean(details.props.open),false);
  assert.match(firstLayer(tree),/Verarbeitung pausiert/);assert.match(firstLayer(tree),/329 von 347 Quellen/);assert.match(firstLayer(tree),/Weiter/);
  assert.doesNotMatch(firstLayer(tree),/Postfach Test|1\.587|Du kannst Kingfisher|lernt weiter/);
  assert.match(text(details),/Postfach Test/);assert.match(text(details),/Pausiert\. Kingfisher lernt weiter/);
  const summary=nodes(details,n=>n.type==='summary')[0];assert.equal(nodes(summary,n=>n.type==='progress').length,1);assert.equal(nodes(summary,n=>n.type==='progress')[0].props.value,94);
  assert.equal(nodes(details,n=>n.type==='button'&&text(n)==='Weiter').length,0,'resume remains outside disclosure');
});
test('mail-only work shows its own unit and never combines it with source counts',()=>{
  const tree=render(()=>KingfisherLernt({kompakt:true}),[[workRows[1]],{...pausedWork,pausiert:false,zustand:'ohne_modell',grund:null},false,'',false,0]);
  assert.match(firstLayer(tree),/1\.587 von 122\.399 Mails/);assert.doesNotMatch(firstLayer(tree),/347 Quellen|Postfach Test/);
  assert.ok(nodes(tree,n=>n.type==='button'&&text(n)==='Pausieren').length);
});
test('unknown mail totals remain unknown and never acquire a percentage',()=>{
  const tree=render(()=>KingfisherLernt({}),[[{...workRows[1],gesamt:null}],pausedWork,false,'',false,0]);
  assert.match(firstLayer(tree),/1\.587 Mails bisher gelesen/);
  const summary=nodes(tree,n=>n.type==='summary')[0];assert.equal(nodes(summary,n=>n.type==='progress').length,0);
});
test('mail failures, retry controls and failed pause actions stay outside the closed work details',()=>{
  const row={id:'mail_fehler',text:'Testpostfach ist nicht erreichbar.',konto:'test-account',fertig:null,gesamt:null};
  const tree=render(()=>KingfisherLernt({}),[[...workRows,row],pausedWork,false,'Änderung fehlgeschlagen',false,0]);
  assert.match(firstLayer(tree),/Testpostfach ist nicht erreichbar/);assert.match(firstLayer(tree),/Änderung fehlgeschlagen/);
  const details=nodes(tree,n=>n.type==='details')[0];assert.equal(nodes(details,n=>n.type?.name==='MailErneut').length,0);
  assert.equal(nodes(tree,n=>n.type?.name==='MailErneut').length,1);
});

test('explicit pause keeps known source coverage visible even when automatic classification is disabled',()=>{
  const tree=render(()=>KingfisherLernt({}),[[],{...pausedWork,zustand:'aus'},false,'',false,0]);
  assert.match(firstLayer(tree),/329 von 347 Quellen/);assert.match(firstLayer(tree),/Weiter/);
  assert.doesNotMatch(firstLayer(tree),/nicht verfügbar|fertig etwa/);
});

test('a mail failure alone never claims ongoing classification from inactive coverage counts',()=>{
  const row={id:'mail_fehler',text:'Testpostfach ist nicht erreichbar.',konto:'test-account',fertig:null,gesamt:null};
  const tree=render(()=>KingfisherLernt({}),[[row],{...pausedWork,pausiert:false,zustand:'aus',grund:null},false,'',false,0]);
  assert.match(firstLayer(tree),/Verarbeitung braucht Aufmerksamkeit/);assert.match(firstLayer(tree),/Testpostfach ist nicht erreichbar/);
  assert.doesNotMatch(firstLayer(tree),/Kingfisher lernt gerade|329 von 347/);
});

test('Anthropic import has separate provider consent and cost limits without claiming quality approval',()=>{
  const preview={preview_id:'synthetic',provider:'anthropic',purpose:'pilot',count:2,sources:[],next_cursor:null};
  const access={storage_available:true,providers:[{id:'anthropic',label:'Anthropic',key_present:true,import_available:true,model:'claude-synthetic'}]};
  const seeds=[null,preview,false,false,'',undefined,'anthropic',access];
  const tree=render(()=>CloudMemory({model:'subscription-model',connected:false}),seeds);
  assert.match(text(tree),/an Anthropic/);
  assert.match(text(tree),/keine garantierte Euro/);
  assert.doesNotMatch(text(tree),/an OpenAI zu senden/);
  const consent=nodes(tree,n=>n.type==='input'&&n.props.type==='checkbox')[0];
  assert.equal(consent.props.checked,false);
  const start=nodes(tree,n=>n.type==='button'&&text(n).includes('mit Claude API auswerten'))[0];
  assert.ok(start);assert.equal(start.props.disabled,true);
  consent.props.onChange({target:{checked:true}});
  const approved=render(()=>CloudMemory({model:'subscription-model',connected:false}),seeds);
  assert.equal(nodes(approved,n=>n.type==='button'&&text(n).includes('mit Claude API auswerten'))[0].props.disabled,false);
  assert.match(text(tree),/fachliche Qualität/);
});

test('paused Anthropic job lets the user select its original provider to resume after restart',()=>{
  const job={id:'synthetic',state:'paused',provider:'anthropic',selected:2,position:1,completed:1,failed:0,requests:2,request_limit:8,model:'claude-synthetic',stop_reason:'App-Neustart',issues:[]};
  const tree=render(()=>CloudMemory({model:'subscription-model',connected:true}),[job,null,false,false,'']);
  const provider=nodes(tree,n=>n.type==='select')[0];
  assert.equal(provider.props.disabled,false);
});
