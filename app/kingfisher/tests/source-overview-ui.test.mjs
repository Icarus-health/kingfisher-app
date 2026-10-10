import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {SourceOverviewView,sourceMetadataReaders}=await server.ssrLoadModule('/src/SourceOverview.tsx');
const at=Date.parse('2026-10-09T12:00:00Z');
const slot=data=>({data,failed:false,checkedAt:at});
const render=state=>renderToStaticMarkup(createElement(SourceOverviewView,{state,busy:false,onRefresh:()=>{},at}));
test('overview distinguishes loading or failure from a confirmed absence of registered sources',()=>{
  assert.match(render({}),/Informationsquellen/);assert.match(render({}),/wird geladen/);
  const html=render({intake:{failed:true}});assert.match(html,/Quellenstand konnte nicht geladen/);
  assert.doesNotMatch(html,/kein Postfach eingetragen/);
});
test('stale snapshots keep registered source names visible, escaped, and explicitly last known',()=>{
  const html=render({integrations:{...slot({mail_accounts:[],calendar_sources:[{id:'one',label:'<script>Private</script>',enabled:true,configured:true}]}),failed:true}});
  assert.match(html,/&lt;script&gt;Private&lt;\/script&gt;/);assert.match(html,/Letzter bekannter Stand/);
  assert.doesNotMatch(html,/<script>|keine Termine|Zugang eingerichtet/);
});
test('the refresh control actually invokes the supplied read-only refresh handler',()=>{
  let called=0;const tree=SourceOverviewView({state:{},busy:false,onRefresh:()=>called++,at});
  function find(node){if(!node||typeof node!=='object')return;if(node.type==='button')return node;
    for(const child of [node.props?.children].flat(5)){const match=find(child);if(match)return match;}}
  const button=find(tree);assert.ok(button);assert.equal(button.props.disabled,false);button.props.onClick();assert.equal(called,1);
});
test('all six metadata readers use only local authenticated GET endpoints and never calendar-content or model routes',async()=>{
  const previous=globalThis.fetch,calls=[];
  globalThis.fetch=async(path,init)=>{calls.push({path,init});return {ok:true,json:async()=>({})};};
  try{const readers=sourceMetadataReaders();await Promise.all(Object.values(readers).map(read=>read(new AbortController().signal)));
    assert.deepEqual(calls.map(c=>c.path).sort(),['/api/v1/integrations','/api/v1/mail/intake','/api/v1/schedule','/api/v1/mac-calendar','/api/v1/folder-sync?summary=true','/api/v1/transcript-sync?summary=true'].sort());
    assert.equal(calls.length,6);for(const c of calls){assert.ok(c.init.credentials===undefined || c.init.credentials==='same-origin');assert.equal(c.init.body,undefined);assert.ok(!c.init.method||c.init.method==='GET');assert.ok(c.init.signal);}
  }finally{globalThis.fetch=previous;}
});

test('source overview stays accessible even before the separate memory coverage read succeeds',async()=>{
  const {MemoryStatus}=await server.ssrLoadModule('/src/MemoryStatus.tsx');
  const html=renderToStaticMarkup(createElement(MemoryStatus));
  assert.match(html,/Gedächtnisstand wird geladen/);
  assert.match(html,/Deine Informationsquellen/);
});

test('a failed regular mail refresh is visible without expanding details even when intake counts load',()=>{
  const state={intake:slot({accounts:[{account_id:'one',label:'Synthetic mail',connected:true,started:true,paused:false,folders:[],scope:'INBOX'}]}),
    schedule:slot({mail_status:{one:{last_success:'2026-10-08T10:00:00Z',last_failure:'unavailable'}}})};
  const tree=SourceOverviewView({state,busy:false,onRefresh:()=>{},at});
  function visibleText(node){if(node===null||node===undefined)return '';if(typeof node==='string'||typeof node==='number')return String(node);
    if(Array.isArray(node))return node.map(visibleText).join(' ');if(node.type==='details')return '';return visibleText(node.props?.children);}
  assert.match(visibleText(tree),/letzte regelmäßige Abruf ist fehlgeschlagen/);
});
