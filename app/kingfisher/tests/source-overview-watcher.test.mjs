import assert from 'node:assert/strict';
import {test} from 'node:test';
import {watchSourceOverview,adoptSourceResult} from '../src/sourceOverviewWatch.ts';
const tick=()=>new Promise(setImmediate);
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};

test('independent failure retains the previous successful source snapshot while others update',async()=>{
  let state={},fail=false,doc=1;
  const watcher=watchSourceOverview({readers:{mac:async()=>{if(fail)throw Error('synthetic');return {event_count:4};},documents:async()=>({generation:doc})},
    onPart:result=>{state=adoptSourceResult(state,result);},intervalMs:100000});
  try{
    await watcher.refresh();const lastCheck=state.mac.checkedAt;assert.equal(state.mac.data.event_count,4);
    fail=true;doc=2;await watcher.refresh();
    assert.equal(state.mac.failed,true);assert.equal(state.mac.data.event_count,4);assert.equal(state.mac.checkedAt,lastCheck);
    assert.equal(state.documents.failed,false);assert.equal(state.documents.data.generation,2);
    fail=false;await watcher.refresh();assert.equal(state.mac.failed,false);
  }finally{watcher.stop();}
});
test('concurrent refresh requests share one in-flight read',async()=>{
  const wait=deferred();let calls=0;
  const watcher=watchSourceOverview({readers:{mac:async()=>{calls++;await wait.promise;return {status:'granted'};}},onPart:()=>{},intervalMs:100000});
  try{
    const a=watcher.refresh(),b=watcher.refresh();assert.equal(calls,1);
    wait.resolve();await Promise.all([a,b]);assert.equal(calls,1);
  }finally{watcher.stop();}
});
test('hidden view aborts old reads and ignores late results before fetching a fresh visible snapshot',async()=>{
  const wait=deferred(),parts=[];let calls=0,firstSignal;
  const watcher=watchSourceOverview({readers:{mac:async signal=>{calls++;if(calls===1){firstSignal=signal;await wait.promise;return {status:'old'};}return {status:'fresh'};}},
    onPart:r=>parts.push(r),intervalMs:100000});
  try{
    watcher.setVisible(false);assert.equal(firstSignal.aborted,true);
    watcher.setVisible(true);assert.equal(calls,1);wait.resolve();await tick();await tick();
    assert.equal(calls,2);assert.equal(parts.length,1);assert.equal(parts[0].data.status,'fresh');
  }finally{watcher.stop();}
});
test('unmount aborts active work and suppresses late success or failure callbacks',async()=>{
  const wait=deferred(),parts=[];let signal;
  const watcher=watchSourceOverview({readers:{mac:async s=>{signal=s;await wait.promise;throw Error('late');}},onPart:r=>parts.push(r),intervalMs:100000});
  watcher.stop();assert.equal(signal.aborted,true);wait.resolve();await tick();assert.deepEqual(parts,[]);
});
test('bounded request timeout marks only that read failed rather than claiming empty data',async()=>{
  const parts=[];
  const watcher=watchSourceOverview({readers:{mac:signal=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(Error('timeout'))))},
    onPart:r=>parts.push(r),intervalMs:100000,timeoutMs:10});
  try{await watcher.refresh();assert.equal(parts.length,1);assert.equal(parts[0].failed,true);assert.equal(parts[0].data,undefined);}
  finally{watcher.stop();}
});
