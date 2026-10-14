import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({cacheDir:`/private/tmp/kingfisher-ui-test-cache-${process.pid}-conversation-workspace.test`,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{
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


test('start workspace keeps creation failure visible and prevents duplicate creation while waiting',async()=>{
 const {ConversationHistory}=await server.ssrLoadModule('/src/App.tsx');const {api}=await server.ssrLoadModule('/src/api.ts');const old=api.createConversation;let reject,creates=0;
 api.createConversation=()=>{creates++;return new Promise((_,r)=>reject=r);};
 const d=driver(ConversationHistory,{recentConversation:null,rememberConversation(){}});
 try{button(d.render(),'Neues Gespräch beginnen').props.onClick();assert.equal(button(d.render(),'Neues Gespräch beginnen').props.disabled,true);
   reject(Error('offline'));await tick();assert.equal(creates,1);assert.match(text(d.render()),/konnte nicht angelegt/);assert.equal(button(d.render(),'Neues Gespräch beginnen').props.disabled,false);
 }finally{d.close();api.createConversation=old;}
});
