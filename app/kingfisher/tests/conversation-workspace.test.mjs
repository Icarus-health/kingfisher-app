import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';
const server=await createServer({cacheDir:testCache('conversation-workspace.test'),root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{
  name:'conversation-workspace-hooks',enforce:'pre',resolveId(id){if(id==='virtual:chat-hooks')return '\0'+id;},
  load(id){if(id==='\0virtual:chat-hooks')return `export const useState=(...a)=>globalThis.__chatDriver.state(...a);export const useRef=(...a)=>globalThis.__chatDriver.ref(...a);export const useEffect=(...a)=>globalThis.__chatDriver.effect(...a);export const useMemo=f=>f();`;},
  transform(code,id){if(['/src/ConversationNavigation.tsx','/src/App.tsx','/src/ConversationVoice.tsx'].some(p=>id.endsWith(p)))return code.replace(/from (["'])react\1/,'from "virtual:chat-hooks"')+(id.endsWith('/src/App.tsx')?'\nexport {Conversation, ConversationHistory};':'');}
}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
function nodes(node,predicate,out=[]){if(!node||typeof node!=='object')return out;if(predicate(node))out.push(node);for(const child of [node.props?.children].flat(10))nodes(child,predicate,out);return out;}
const text=node=>node==null?'':typeof node==='object'?[node.props?.children].flat(10).map(text).join(''):String(node);
const button=(tree,label)=>nodes(tree,n=>n.type==='button'&&text(n)===label)[0];
function driver(Component,props){const states=[],refs=[],effects=[],pending=[];let s=0,r=0,e=0;
 const d={props,state(v){const i=s++;if(!(i in states))states[i]=typeof v==='function'?v():v;return[states[i],n=>states[i]=typeof n==='function'?n(states[i]):n];},ref(v){return refs[r++]??={current:v};},effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},render(){s=r=e=0;globalThis.__chatDriver=d;return Component(d.props);},runEffects(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(x=>x.cleanup?.());delete globalThis.__chatDriver;}};return d;}
const tick=async()=>{for(let i=0;i<4;i++)await new Promise(setImmediate);};

test('navigation searches message bodies via server pages, appends pages, and ignores stale queries',async()=>{
 const {ConversationNavigation}=await server.ssrLoadModule('/src/ConversationNavigation.tsx');
 const {api}=await server.ssrLoadModule('/src/api.ts');let calls=[],oldPage=api.conversationPage;
 let resolveOld;
 api.conversationPage=async(q='',cursor)=>{calls.push([q,cursor]);if(q==='alte Anfrage')return new Promise(r=>resolveOld=r);return{conversations:[{id:cursor?'c2':'c1',title:q||'Anfang',updated_at:'2026-10-14',message_count:1,preview:'Text'}],next_cursor:cursor?null:'next',total:2};};
 const d=driver(ConversationNavigation,{onSelect(){},onCreate:async()=>{},revision:0});
 try{d.render();d.runEffects();await tick();let tree=d.render();assert.ok(button(tree,'Weitere Gespräche'));
   await button(tree,'Weitere Gespräche').props.onClick();await tick();tree=d.render();assert.equal(nodes(tree,n=>n.type==='button'&&n.props.className?.includes('conversation-nav-item')).length,2);
   nodes(tree,n=>n.type==='input')[0].props.onChange({target:{value:'alte Anfrage'}});d.render();d.runEffects();await new Promise(r=>setTimeout(r,250));
   nodes(d.render(),n=>n.type==='input')[0].props.onChange({target:{value:'älterer Text'}});d.render();d.runEffects();await new Promise(r=>setTimeout(r,250));
   resolveOld({conversations:[{id:'old',title:'stale'}],next_cursor:null,total:1});await tick();tree=d.render();
   assert.match(text(tree),/älterer Text/);assert.doesNotMatch(text(tree),/stale/);
   assert.ok(calls.some(([q])=>q==='älterer Text'));
 }finally{d.close();api.conversationPage=oldPage;}
});

test('selecting the open conversation closes the drawer without navigating or losing keyboard focus',async()=>{
 const {Conversation}=await server.ssrLoadModule('/src/App.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 const oldWindow=globalThis.window,oldDocument=globalThis.document,oldGet=api.getConversation;
 const pushed=[];let reads=0,focused=0;
 globalThis.window={location:{hash:''},history:{pushState(_s,_t,path){pushed.push(path);}},dispatchEvent(){},addEventListener(){},removeEventListener(){}};
 globalThis.document={getElementById(){return null;}};
 globalThis.PopStateEvent??=class{constructor(type){this.type=type;}};
 api.getConversation=async id=>{reads++;return{conversation:{id,title:'Aktuelles Gespräch'},messages:[],context:{items:[]},memory_candidates:[]};};
 const d=driver(Conversation,{id:'current',recentConversation:'current',rememberConversation(){},chatAvailable:true});
 const toggle=tree=>nodes(tree,n=>n.type==='button'&&n.props['aria-label']==='Gespräche')[0];
 try{d.render();d.runEffects();await tick();let tree=d.render();toggle(tree).props.onClick();tree=d.render();
  assert.equal(toggle(tree).props['aria-expanded'],true);
  if(toggle(tree).props.ref)toggle(tree).props.ref.current={focus(){focused++;}};
  const nav=nodes(tree,n=>n.type?.name==='ConversationNavigation')[0];nav.props.onSelect('current');tree=d.render();
  assert.equal(toggle(tree).props['aria-expanded'],false,'the selected chat must reveal its content even when its id did not change');
  assert.equal(focused,1,'keyboard focus returns to the visible navigation toggle');
  assert.deepEqual(pushed,[],'selecting the open chat must not add a duplicate history entry');
  assert.equal(reads,1,'the existing conversation remains mounted');
  assert.equal(nodes(tree,n=>n.type?.name==='CommandBar')[0].props.conversationId,'current');
  toggle(tree).props.onClick();tree=d.render();nodes(tree,n=>n.type?.name==='ConversationNavigation')[0].props.onSelect('other');tree=d.render();
  assert.equal(toggle(tree).props['aria-expanded'],false);assert.deepEqual(pushed,['/conversations/other']);
 }finally{d.close();api.getConversation=oldGet;globalThis.window=oldWindow;globalThis.document=oldDocument;}
});

test('safe message formatting renders paragraphs lists strong and code while escaping raw HTML',async()=>{
 const {MessageText}=await server.ssrLoadModule('/src/MessageText.tsx');
 const html=renderToStaticMarkup(createElement(MessageText,{content:'Erster Absatz\n\n**Wichtig** und `code`\n\n- Eins\n- Zwei\n\n1. Schritt\n2. Weiter\n\n```js\n<script>danger()</script>\n```\n\n<img src=x onerror=alert(1)>'}));
 assert.match(html,/<strong>Wichtig<\/strong>/);assert.match(html,/<code>code<\/code>/);assert.match(html,/<ul>/);assert.match(html,/<ol>/);assert.match(html,/<pre><code>/);
 assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<script>|<img/);
});

test('old send cannot replace a new conversation and sources stay behind the explicit toggle',async()=>{
 const {Conversation}=await server.ssrLoadModule('/src/App.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 const oldWindow=globalThis.window,oldDocument=globalThis.document;
 globalThis.window={location:{hash:''},addEventListener(){},removeEventListener(){}};
 globalThis.document={getElementById(){return null;}};
 const old={getConversation:api.getConversation,sendMessage:api.sendMessage};
 const payload=id=>({conversation:{id,title:id},messages:[],context:{items:[{statement:'private source context'}]},memory_candidates:[]});
 let resolve;api.getConversation=async id=>payload(id);api.sendMessage=()=>new Promise(r=>resolve=r);
 const props=id=>({id,recentConversation:null,rememberConversation(){},chatAvailable:true});
 const a=driver(Conversation,props('first'));
 try{a.render();a.runEffects();await tick();let tree=a.render();assert.doesNotMatch(text(tree),/private source context/);
   const toolbar=nodes(tree,n=>n.props?.className==='thread-command')[0];
   const keys=[toolbar.props.children].flat(10).filter(n=>n&&typeof n==='object'&&n.key!=null).map(n=>n.key);
   assert.equal(new Set(keys).size,keys.length,'siblings must not duplicate React keys after replies');
   const control=nodes(tree,n=>n.type?.name==='CommandBar')[0];assert.equal(control.props.conversationId,'first');const sent=control.props.onSubmit('send');
   a.close();const b=driver(Conversation,props('second'));try{b.render();b.runEffects();await tick();
     resolve({...payload('first'),messages:[{id:'old',role:'assistant',content:'obsolete response'}]});await sent;tree=b.render();
     assert.doesNotMatch(text(tree),/obsolete response/);assert.match(text(tree),/second/);
     button(tree,'Verwendete Quellen').props.onClick();assert.match(text(b.render()),/private source context/);
   }finally{b.close();}
 }finally{a.close();Object.assign(api,old);globalThis.window=oldWindow;globalThis.document=oldDocument;}
});

test('thread follows the final answer near the bottom and respects reading older messages',async()=>{
 const {Conversation}=await server.ssrLoadModule('/src/App.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 const oldWindow=globalThis.window,oldDocument=globalThis.document,old={getConversation:api.getConversation,sendMessage:api.sendMessage};
 globalThis.window={location:{hash:''},addEventListener(){},removeEventListener(){}};globalThis.document={getElementById(){return null;}};
 const payload=n=>({conversation:{id:'scroll',title:'Scroll'},messages:Array.from({length:n},(_,i)=>({id:'m'+i,role:'user',content:'Text',status:'complete'})),context:{items:[]},memory_candidates:[]});
 api.getConversation=async()=>payload(1);api.sendMessage=async()=>payload(2);
 const d=driver(Conversation,{id:'scroll',recentConversation:null,rememberConversation(){},chatAvailable:true});
 const element={scrollTop:0,scrollHeight:900,clientHeight:300};
 try{let tree=d.render();nodes(tree,n=>n.props?.className==='messages')[0].props.ref.current=element;d.runEffects();await tick();d.render();d.runEffects();assert.equal(element.scrollTop,900);
   tree=d.render();element.scrollTop=100;nodes(tree,n=>n.props?.className==='messages')[0].props.onScroll({currentTarget:element});
   await nodes(tree,n=>n.type?.name==='CommandBar')[0].props.onSubmit('question');element.scrollHeight=1200;d.render();d.runEffects();assert.equal(element.scrollTop,100);
   tree=d.render();element.scrollTop=900;nodes(tree,n=>n.props?.className==='messages')[0].props.onScroll({currentTarget:element});
   api.sendMessage=async()=>payload(3);await nodes(tree,n=>n.type?.name==='CommandBar')[0].props.onSubmit('next');element.scrollHeight=1500;d.render();d.runEffects();assert.equal(element.scrollTop,1500);
 }finally{d.close();Object.assign(api,old);globalThis.window=oldWindow;globalThis.document=oldDocument;}
});


test('start workspace shows the input at once and creates the conversation only with the first question',async()=>{
 const {ConversationHistory}=await server.ssrLoadModule('/src/App.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 const old={createConversation:api.createConversation,sendMessage:api.sendMessage};const oldWindow=globalThis.window,oldDocument=globalThis.document;
 const pushed=[];globalThis.window={location:{hash:''},history:{pushState(_s,_t,path){pushed.push(path);}},dispatchEvent(){},addEventListener(){},removeEventListener(){}};
 globalThis.PopStateEvent??=class{constructor(type){this.type=type;}};
 let focused=0;globalThis.document={querySelector(){return{focus(){focused++;}};}};
 let creates=0,sends=[],failSend=true;
 api.createConversation=async()=>{creates++;return{conversation:{id:'neu'}};};
 api.sendMessage=async(id,message)=>{sends.push([id,message]);if(failSend)throw Error('offline');return{};};
 const d=driver(ConversationHistory,{recentConversation:null,rememberConversation(){},chatAvailable:true});
 try{let tree=d.render();d.runEffects();
   assert.equal(button(tree,'Neues Gespräch beginnen'),undefined,'kein zweiter Knopf in der Mitte');
   const bar=nodes(tree,n=>n.type?.name==='CommandBar')[0];assert.ok(bar,'die Mitte ist gleich das Eingabefeld');assert.equal(bar.props.disabled,false);
   await tick();tree=d.render();assert.equal(creates,0,'Öffnen legt kein Gespräch an');
   const nav=nodes(tree,n=>n.type?.name==='ConversationNavigation')[0];await nav.props.onCreate();assert.equal(creates,0,'„Neues Gespräch“ legt nichts an');assert.equal(focused,1,'sondern führt ins Eingabefeld');
   await assert.rejects(bar.props.onSubmit('Wann ist der Fachtag?'));tree=d.render();
   assert.equal(creates,1);assert.equal(nodes(tree,n=>n.type?.name==='MessageText')[0].props.content,'Wann ist der Fachtag?','die Frage bleibt stehen');assert.match(text(tree),/konnte nicht gesendet werden/);
   failSend=false;await nodes(d.render(),n=>n.type?.name==='CommandBar')[0].props.onSubmit('Wann ist der Fachtag?');
   assert.equal(creates,1,'der zweite Versuch nimmt dasselbe Gespräch');assert.deepEqual(sends.map(x=>x[0]),['neu','neu']);assert.deepEqual(pushed,['/conversations/neu']);
 }finally{d.close();Object.assign(api,old);globalThis.window=oldWindow;globalThis.document=oldDocument;}
});

test('without a known chat status the start input stays disabled and says why',async()=>{
 const {ConversationHistory}=await server.ssrLoadModule('/src/App.tsx');
 const d=driver(ConversationHistory,{recentConversation:null,rememberConversation(){},chatAvailable:false,chatPlaceholder:'Kingfisher wird verbunden …'});
 try{const bar=nodes(d.render(),n=>n.type?.name==='CommandBar')[0];assert.equal(bar.props.disabled,true);assert.equal(bar.props.placeholder,'Kingfisher wird verbunden …');}finally{d.close();}
});

test('review button opens the exact procedure id through an encoded settings link',async()=>{
 const {Conversation}=await server.ssrLoadModule('/src/App.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 const oldWindow=globalThis.window,oldDocument=globalThis.document,oldGet=api.getConversation;
 const pushed=[];globalThis.window={location:{hash:''},history:{pushState(_s,_t,path){pushed.push(path);}},dispatchEvent(){},addEventListener(){},removeEventListener(){}};
 globalThis.PopStateEvent??=class{constructor(type){this.type=type;}};
 globalThis.document={getElementById(){return null;}};
 const id='proc/special?ä&other';
 api.getConversation=async()=>({conversation:{id:'review',title:'Test'},context:{items:[]},memory_candidates:[],messages:[{
  id:'m1',role:'assistant',content:'Ein Ablauf liegt zur Prüfung bereit.',status:'complete',
  metadata:{context:{procedure_proposal:{id,title:'Zielablauf',state:'pending'}}}}]});
 const d=driver(Conversation,{id:'review',recentConversation:null,rememberConversation(){},chatAvailable:true});
 try{d.render();d.runEffects();await tick();const control=button(d.render(),'Ablauf prüfen');assert.ok(control);
  control.props.onClick();assert.deepEqual(pushed,['/settings?ablauf=proc%2Fspecial%3F%C3%A4%26other#ich-ablaeufe']);
 }finally{d.close();api.getConversation=oldGet;globalThis.window=oldWindow;globalThis.document=oldDocument;}
});

test('unverified original fallback keeps the whole source behind a closed accessible disclosure',async()=>{
 const {Conversation}=await server.ssrLoadModule('/src/App.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');
 const oldWindow=globalThis.window,oldDocument=globalThis.document,oldGet=api.getConversation;
 globalThis.window={location:{hash:''},addEventListener(){},removeEventListener(){}};
 globalThis.document={getElementById(){return null;}};
 const original='Die Lieferung erfolgt am 14. November nur nach schriftlicher Freigabe. Kein verbindlicher Termin ohne Bestätigung.';
 try{for(const flag of [true,false,undefined]){
  api.getConversation=async()=>({conversation:{id:'original',title:'Test'},context:{items:[]},memory_candidates:[],messages:[{
   id:'m-original',role:'assistant',content:original,status:'complete',metadata:{context:{original_fallback:flag,source_links:[{episode_id:'e-original',label:'Original öffnen'}]}}}]});
  const d=driver(Conversation,{id:'original',recentConversation:null,rememberConversation(){},chatAvailable:true});
  try{d.render();d.runEffects();await tick();const tree=d.render();
   const disclosure=nodes(tree,n=>n.type==='details'&&nodes(n,c=>c.type==='summary'&&text(c)==='Originalangaben lesen').length)[0];
   if(flag===true){assert.ok(disclosure);assert.notEqual(disclosure.props.open,true);assert.equal(nodes(disclosure,n=>n.type?.name==='MessageText')[0].props.content,original);assert.match(text(tree),/geprüfte Zusammenfassung fehlt/);}
   else{assert.equal(disclosure,undefined);assert.equal(nodes(tree,n=>n.type?.name==='MessageText')[0].props.content,original);}
  }finally{d.close();}
 }}finally{api.getConversation=oldGet;globalThis.window=oldWindow;globalThis.document=oldDocument;}
});
