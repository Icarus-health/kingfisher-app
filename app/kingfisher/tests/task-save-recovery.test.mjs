import assert from 'node:assert/strict';
import {test} from 'node:test';
import {TaskSaveAttempt} from '../src/taskSaveAttempt.ts';
const id1='00000000-0000-4000-8000-000000000001',id2='00000000-0000-4000-8000-000000000002';
const key='synthetic:manual-task';
function storage() {const values=new Map();return {getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k),values};}

test('reopening after a lost acknowledgement reuses the durable opaque request and clears only on confirmation',async()=>{
 const store=storage(),sent=[];
 const first=new TaskSaveAttempt(()=>id1,key,()=>store);
 await assert.rejects(first.save({title:'Private title',notes:'Private notes'},async p=>{sent.push(p);throw Error('Response lost');}));
 assert.deepEqual([...store.values.entries()],[[key,id1]]);
 const reopened=new TaskSaveAttempt(()=>id2,key,()=>store);
 await reopened.save({title:'Private title',notes:'Private notes'},async p=>{sent.push(p);return {id:'same-task'};});
 assert.equal(sent[0].request_id,sent[1].request_id);
 assert.equal(store.getItem(key),null);
});

test('unavailable durable storage fails before sending, and recovery retains the same identity',async()=>{
 const store=storage();let fail=true,sent=0;
 const wrapped={...store,setItem:(k,v)=>{if(fail)throw Error('Storage unavailable');store.setItem(k,v);}};
 const attempt=new TaskSaveAttempt(()=>id1,key,()=>wrapped);
 await assert.rejects(attempt.save({title:'One'},async()=>{sent++;}));assert.equal(sent,0);assert.equal(attempt.inFlight,false);
 fail=false;await attempt.save({title:'One'},async p=>{sent++;assert.equal(p.request_id,id1);return 'confirmed';});assert.equal(sent,1);
});

test('malformed stored identity fails closed without replacing the unresolved request',async()=>{
 const store=storage();store.setItem(key,'malformed');
 const attempt=new TaskSaveAttempt(()=>id1,key,()=>store);let sent=0;
 await assert.rejects(attempt.save({title:'One'},async()=>{sent++;return 'unexpected';}),/kennung/i);
 assert.equal(sent,0);assert.equal(store.getItem(key),'malformed');
});

test('confirmed save remains confirmed when durable cleanup fails and reopening replays safely',async()=>{
 const store=storage(),wrapped={...store,removeItem:()=>{throw Error('Cleanup unavailable');}};
 const attempt=new TaskSaveAttempt(()=>id1,key,()=>wrapped);
 assert.equal(await attempt.save({title:'One'},async()=> 'confirmed'),'confirmed');assert.equal(attempt.succeeded,true);
 const reopened=new TaskSaveAttempt(()=>id2,key,()=>store);
 await reopened.save({title:'One'},async p=>{assert.equal(p.request_id,id1);return 'same task';});
});

test('an identity established by another draft cannot be overwritten by an uncertain retry',async()=>{
 const store=storage();const attempt=new TaskSaveAttempt(()=>id1,key,()=>store);
 await assert.rejects(attempt.save({title:'One'},async()=>{throw Error('Lost');}));
 store.setItem(key,id2);let sent=0;
 await assert.rejects(attempt.save({title:'One'},async()=>{sent++;return 'unexpected';}),/anderer/);assert.equal(sent,0);
 assert.equal(store.getItem(key),id2);
});

test('an explicit reviewed reset releases only this request and does not send a task',async()=>{
 const store=storage();const attempt=new TaskSaveAttempt(()=>id1,key,()=>store);
 await assert.rejects(attempt.save({title:'One'},async()=>{throw Error('Lost');}));
 attempt.resetAfterReview();assert.equal(store.getItem(key),null);
 const next=new TaskSaveAttempt(()=>id2,key,()=>store);
 await next.save({title:'One'},async p=>{assert.equal(p.request_id,id2);return 'new task';});
});

test('manual and different goal requests have distinct durable scopes',async()=>{
 const store=storage();
 for(const [scope,id] of [[key,id1],['synthetic:goal:a',id2]])await assert.rejects(new TaskSaveAttempt(()=>id,scope,()=>store).save({title:'One'},async()=>{throw Error('Lost');}));
 assert.deepEqual([...store.values.entries()],[[key,id1],['synthetic:goal:a',id2]]);
});

test('reviewed reset after failed restore cannot clear a later unrelated request',()=>{
 const store=storage();store.setItem(key,'malformed');const first=new TaskSaveAttempt(()=>id1,key,()=>store);
 assert.throws(()=>first.restore());store.setItem(key,id2);
 assert.throws(()=>first.resetAfterReview());assert.equal(store.getItem(key),id2);
});

test('unobserved storage after a read failure cannot be reset without reopening',()=>{
 const store=storage();let fail=true;
 const wrapped={...store,getItem:k=>{if(fail)throw Error('Read unavailable');return store.getItem(k);}};
 const first=new TaskSaveAttempt(()=>id1,key,()=>wrapped);assert.throws(()=>first.restore());
 fail=false;store.setItem(key,id2);assert.throws(()=>first.resetAfterReview());assert.equal(store.getItem(key),id2);
});

test('confirmation cannot remove a different request installed while awaiting the response',async()=>{
 const store=storage(),attempt=new TaskSaveAttempt(()=>id1,key,()=>store);
 await attempt.save({title:'One'},async()=>{store.setItem(key,id2);return 'confirmed';});
 assert.equal(store.getItem(key),id2);
});
