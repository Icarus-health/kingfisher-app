import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
import {testCache} from './testcache.mjs';
const server=await createServer({cacheDir:testCache('conversation-handoff.test'),root:fileURLToPath(new URL('..',import.meta.url)),server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {runConversationHandoff}=await server.ssrLoadModule('/src/conversationDraftHandoff.ts');
const handoff=id=>({id,text:'Meine erste Frage',state:'ready'});
function transport(claimed=true){let posts=[],finishes=[],started=false;return{posts,finishes,
  start:async(id,body)=>{const first=claimed&&!started;started=true;return{conversation_id:id,instance_id:body.instance_id,claimed:first,handoff:{...handoff(body.handoff_id),state:'started'}};},
  send:async(...args)=>{posts.push(args);return{conversation:{id:args[0]},messages:[]};},
  finish:async(id,body)=>{finishes.push([id,body]);return{conversation_id:id,instance_id:body.instance_id,handoff:{id:body.handoff_id,text:'',state:'accepted'}};}};}
test('only claimed first start posts once with instance binding, then acknowledges without another message',async()=>{const t=transport();const results=await Promise.all([runConversationHandoff('c',handoff('h-one'),'i',t),runConversationHandoff('c',handoff('h-one'),'i',t)]);assert.equal(results[0].state,'accepted');assert.equal(t.posts.length,1);assert.deepEqual(t.posts[0],['c','Meine erste Frage','i']);assert.equal(t.finishes.length,1);assert.equal((await runConversationHandoff('c',handoff('h-one'),'i',t)).state,'uncertain','settled payload must not remain cached');assert.equal(t.posts.length,1);});
test('an already started or uncertain start never retries the message',async()=>{const t=transport(false);assert.equal((await runConversationHandoff('c',handoff('h-two'),'i',t)).state,'uncertain');assert.equal(t.posts.length,0);t.start=async()=>{throw Error('response lost');};assert.equal((await runConversationHandoff('c',handoff('h-three'),'i',t)).state,'uncertain');assert.equal(t.posts.length,0);});
test('failed message or cleanup stays uncertain without second POST; successful payload remains available',async()=>{const t=transport();t.send=async(...args)=>{t.posts.push(args);throw Error('lost response');};assert.equal((await runConversationHandoff('c',handoff('h-four'),'i',t)).state,'uncertain');assert.equal(t.posts.length,1);assert.equal(t.finishes.length,0);const u=transport();u.finish=async()=>{throw Error('disk full');};const result=await runConversationHandoff('c',handoff('h-five'),'i',u);assert.equal(result.state,'finish_failed');assert.equal(result.payload.conversation.id,'c');assert.equal(u.posts.length,1);});
