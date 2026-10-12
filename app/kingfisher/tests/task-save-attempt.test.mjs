import assert from 'node:assert/strict';
import {test} from 'node:test';
import {TaskSaveAttempt, newTaskRequestId} from '../src/taskSaveAttempt.ts';

test('uncertain response retains one identity and changed input cannot invent a fresh request',async()=>{
 let nonce=0;const attempt=new TaskSaveAttempt(()=>`synthetic-${++nonce}`),sent=[];
 await assert.rejects(attempt.save({title:'first'},async value=>{sent.push(value);throw Error('response lost')}));
 assert.equal(await attempt.save({title:'edited'},async value=>{sent.push(value);return 'saved'}),'saved');
 assert.equal(sent[0].request_id,sent[1].request_id);assert.equal(nonce,1);
 assert.equal(await attempt.save({title:'first'},async()=>assert.fail('Already confirmed save repeated')),null);
});
test('one synchronous in-flight guard blocks double submission',async()=>{
 const attempt=new TaskSaveAttempt(()=> 'synthetic'),sent=[];let resolve;
 const first=attempt.save({title:'one'},async p=>{sent.push(p);return new Promise(r=>{resolve=r})});
 assert.equal(attempt.inFlight,true);
 assert.equal(await attempt.save({title:'one'},async()=>assert.fail('Double save')),null);
 resolve('saved');assert.equal(await first,'saved');assert.equal(sent.length,1);
 assert.equal(attempt.inFlight,false);assert.equal(attempt.succeeded,true);
});
test('native WebKit without randomUUID uses random bytes with valid UUID version and variant',()=>{
 const id=newTaskRequestId({getRandomValues:bytes=>{bytes.fill(255);return bytes;}});
 assert.match(id,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});
test('unavailable random identity fails before any task is sent',async()=>{
 const attempt=new TaskSaveAttempt(()=>{throw Error('Random generator unavailable');});
 await assert.rejects(attempt.save({title:'one'},async()=>assert.fail('No identity, no send')));
 assert.equal(attempt.inFlight,false);assert.equal(attempt.succeeded,false);
});
test('a deliberately new draft permits identical content as a distinct task',async()=>{
 let n=0;const ids=[];for(let i=0;i<2;i++)await new TaskSaveAttempt(()=>String(++n)).save({title:'same'},async p=>{ids.push(p.request_id);return p});
 assert.notEqual(ids[0],ids[1]);
});
