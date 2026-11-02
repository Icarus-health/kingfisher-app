import test from 'node:test';
import assert from 'node:assert/strict';
import {createService,runChild} from './harness_service.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const key='s'.repeat(43), token='t'.repeat(43);
async function setup(run){
  const server=createService({key,run,runtime:'/fixed/runtime',scratch:'/fixed/scratch'});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {url:'http://127.0.0.1:'+server.address().port,server};
}
const headers={Authorization:'Bearer '+key,'content-type':'application/json'};
const data={token,request:'Wo liegt die künstliche Karte?'};

test('service authentication and fixed configuration',async()=>{
  const calls=[];const {url,server}=await setup(async c=>{calls.push(c);return {status:'complete',text:'Künstlich'};});
  try{
    assert.equal((await fetch(url+'/run',{method:'POST',body:JSON.stringify(data)})).status,401);
    assert.equal((await fetch(url+'/run',{method:'POST',headers:{...headers,Authorization:'Bearer wrong'},body:JSON.stringify(data)})).status,401);
    const result=await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)});
    assert.equal(result.status,200);
    assert.equal((await result.json()).text,'Künstlich');
    assert.equal(calls.length,1);
    assert.equal(calls[0].origin,'http://kingfisher-gateway:8890');
    assert.equal(calls[0].runtime,'/fixed/runtime');
    assert.equal(calls[0].syntheticOnly,true);
    assert.ok(!JSON.stringify(calls[0]).includes(key));
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('service rejects arbitrary paths, model routes and malformed bodies',async()=>{
  let calls=0;const {url,server}=await setup(async()=>{calls++;return {};});
  try{
    for(const body of [{...data,runtime:'/Users/private'},{...data,origin:'https://other'},
      {...data,model:'cloud'},{...data,request:'x'.repeat(1201)}, {token:12,request:'text'},
      null,[],{...data,token:'short'}]){
      assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(body)})).status,400);
    }
    assert.equal((await fetch(url+'/run',{method:'POST',headers,body:'x'.repeat(9000)})).status,413);
    assert.equal((await fetch(url+'/shell',{method:'POST',headers,body:'{}'})).status,404);
    assert.equal(calls,0);
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('only one job executes and busy attempts do not start inference',async()=>{
  let entered,release;const started=new Promise(r=>entered=r),finish=new Promise(r=>release=r);
  let calls=0;const {url,server}=await setup(async()=>{calls++;entered();await finish;return {status:'complete',text:'Done'};});
  try{
    const pending=fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)});
    await started;
    assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)})).status,409);
    assert.equal(calls,1);release();assert.equal((await pending).status,200);
  }finally{release();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('client cancellation reaches owned runner before next job',async()=>{
  let entered,cancelled;const start=new Promise(r=>entered=r),stop=new Promise(r=>cancelled=r);
  const {url,server}=await setup(async(_c,signal)=>{
    entered();await new Promise(resolve=>signal.addEventListener('abort',()=>{cancelled();resolve();},{once:true}));
    return {status:'failed'};
  });
  try{
    const controller=new AbortController();
    const pending=fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data),signal:controller.signal}).catch(()=>{});
    await start;controller.abort();await stop;await pending;
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('failed runner never exposes exception details or unlimited output',async()=>{
  const {url,server}=await setup(async()=>{throw new Error('private-key must not leak');});
  try{
    const response=await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)});
    assert.equal(response.status,502);assert.ok(!(await response.text()).includes('private-key'));
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('owned child has clean environment and timeout removes token files',async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'kf-service-test-'));
  const entry=path.join(root,'fake.mjs');
  fs.writeFileSync(entry,`import fs from 'node:fs';import path from 'node:path';
let text='';for await(const c of process.stdin)text+=c;
const data=JSON.parse(text);if(process.env.KF_WORKER_SERVICE_KEY)process.exit(2);
fs.writeFileSync(path.join(data.scratch,'profile.patch.json'),data.token);
setTimeout(()=>{},30000);`);
  process.env.KF_WORKER_SERVICE_KEY=key;
  try{
    await assert.rejects(runChild({scratch:root,token},undefined,{entry,timeout:250}));
    assert.deepEqual(fs.readdirSync(root),['fake.mjs']);
  }finally{delete process.env.KF_WORKER_SERVICE_KEY;fs.rmSync(root,{recursive:true,force:true});}
});

test('owned child output is bounded and stderr never escapes',async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'kf-service-test-'));
  const entry=path.join(root,'fake.mjs');
  fs.writeFileSync(entry,`for await(const c of process.stdin){};process.stderr.write('secret');process.stdout.write('x'.repeat(100000));`);
  try{
    await assert.rejects(runChild({scratch:root},undefined,{entry}),e=>!e.message.includes('secret'));
    assert.deepEqual(fs.readdirSync(root),['fake.mjs']);
  }finally{fs.rmSync(root,{recursive:true,force:true});}
});

test('readonly child directories are cleaned without following symlinks',{timeout:2000},async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'kf-service-readonly-'));
  const outside=path.join(root,'untouched');fs.mkdirSync(outside);fs.writeFileSync(path.join(outside,'keep'),'Keep');
  fs.chmodSync(outside,0o500);
  const entry=path.join(root,'fake.mjs');
  fs.writeFileSync(entry,`import fs from 'node:fs';import path from 'node:path';
let text='';for await(const c of process.stdin)text+=c;const c=JSON.parse(text);
const nested=path.join(c.scratch,'locked');fs.mkdirSync(nested);fs.writeFileSync(path.join(nested,'grant'),c.token);
fs.symlinkSync(${JSON.stringify(outside)},path.join(c.scratch,'outside-link'));fs.chmodSync(nested,0o500);
process.stdout.write(JSON.stringify({status:'complete',text:'Done'}));`);
  try{
    const result=await runChild({scratch:root,token},undefined,{entry});
    assert.equal(result.text,'Done');assert.deepEqual(fs.readdirSync(root).sort(),['fake.mjs','untouched']);
    assert.equal(fs.statSync(outside).mode&0o777,0o500);
    assert.equal(fs.readFileSync(path.join(outside,'keep'),'utf8'),'Keep');
  }finally{fs.chmodSync(outside,0o700);fs.rmSync(root,{recursive:true,force:true});}
});

test('unrecoverable cleanup quarantines the service instead of starting another job',async()=>{
  let calls=0;const {url,server}=await setup(async()=>{
    calls++;const error=new Error('private path');error.code='WorkerCleanupRequired';throw error;
  });
  try{
    assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)})).status,502);
    const blocked=await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)});
    assert.equal(blocked.status,503);assert.equal(calls,1);
    assert.equal((await fetch(url+'/health')).status,503);
    assert.ok(!(await blocked.text()).includes('private path'));
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

// Removing one-time initialization, or accepting key material in the initial
// environment again, must fail these observable service/entry checks.
test('uninitialized service cannot run and initializes exactly once in memory',async()=>{
  let calls=0;
  const server=createService({run:async()=>{calls++;return {status:'complete',text:'Done'};}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url='http://127.0.0.1:'+server.address().port;
  try{
    const health=await fetch(url+'/health');
    assert.deepEqual(await health.json(),{status:'awaiting_controller'});
    assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)})).status,503);
    for(const body of [null,[],{}, {key:'short'}, {key:key+'x'}, {key,token}, {key:'!'.repeat(43)}]){
      const response=await fetch(url+'/init',{method:'POST',body:JSON.stringify(body)});
      assert.equal(response.status,400);assert.ok(!(await response.text()).includes(key));
    }
    assert.equal((await fetch(url+'/init',{method:'POST',body:'x'.repeat(129)})).status,413);
    assert.equal((await fetch(url+'/init?key='+key,{method:'POST',body:JSON.stringify({key})})).status,404);
    assert.equal((await fetch(url+'/init')).status,404);
    assert.equal(calls,0);
    const initialized=await fetch(url+'/init',{method:'POST',body:JSON.stringify({key})});
    assert.equal(initialized.status,200);assert.deepEqual(await initialized.json(),{status:'initialized'});
    for(const other of [key,'z'.repeat(43)]){
      const repeated=await fetch(url+'/init',{method:'POST',body:JSON.stringify({key:other})});
      assert.equal(repeated.status,409);assert.ok(!(await repeated.text()).includes(other));
    }
    assert.deepEqual(await (await fetch(url+'/health')).json(),{status:'ok'});
    assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)})).status,200);
    assert.equal(calls,1);
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('concurrent initialization reserves its one-time slot before body reading',async()=>{
  const http=await import('node:http');
  const server=createService({run:async()=>({status:'complete',text:'Done'})});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url='http://127.0.0.1:'+server.address().port;
  let first;
  try{
    first=http.request(url+'/init',{method:'POST',headers:{'Content-Length':53}});
    first.on('error',()=>{});first.write('{');
    // An HTTP response to health means the earlier request headers were handled.
    await fetch(url+'/health');
    assert.equal((await fetch(url+'/init',{method:'POST',body:JSON.stringify({key})})).status,409);
    first.end('"key":"'+key+'"}');
    const status=await new Promise(resolve=>first.once('response',r=>{r.resume();resolve(r.statusCode);}));
    assert.equal(status,200);
  }finally{first?.destroy();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('production entry rejects accidental initial service credential without echoing it',async()=>{
  const {spawn}=await import('node:child_process');
  const {fileURLToPath}=await import('node:url');
  const child=spawn(process.execPath,[fileURLToPath(new URL('./harness_service.mjs',import.meta.url))],
    {env:{PATH:process.env.PATH,KF_WORKER_SERVICE_KEY:key}});
  let output='';child.stdout.on('data',c=>output+=c);child.stderr.on('data',c=>output+=c);
  const result=await Promise.race([new Promise(resolve=>child.once('close',resolve)),
    new Promise(resolve=>{const timer=setTimeout(()=>{child.kill();resolve('timeout');},2000);timer.unref();})]);
  assert.notEqual(result,'timeout');assert.notEqual(result,0);
  assert.ok(output.includes('initial service credential is forbidden'));assert.ok(!output.includes(key));
});

test('same-UID child cannot find initialized service credential in parent initial environment',
  {skip:process.platform!=='linux'},async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'kf-service-initial-env-'));
  const entry=path.join(root,'fake.mjs');
  fs.writeFileSync(entry,`import fs from 'node:fs';for await(const c of process.stdin){};
const initial=fs.readFileSync('/proc/'+process.ppid+'/environ','utf8');
const uid=fs.statSync('/proc/'+process.ppid).uid;
process.stdout.write(JSON.stringify({status:'complete',text:JSON.stringify({sameUid:uid===process.getuid(),
  parentKeyPresent:initial.includes('KF_WORKER_SERVICE_KEY='),ownKeyPresent:'KF_WORKER_SERVICE_KEY' in process.env})}));`);
  const server=createService({scratch:root,run:(config,signal)=>runChild(config,signal,{entry})});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url='http://127.0.0.1:'+server.address().port;
  try{
    assert.equal((await fetch(url+'/init',{method:'POST',body:JSON.stringify({key})})).status,200);
    const response=await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)});
    assert.equal(response.status,200);
    assert.deepEqual(JSON.parse((await response.json()).text),{sameUid:true,parentKeyPresent:false,ownKeyPresent:false});
    assert.deepEqual(fs.readdirSync(root),['fake.mjs']);
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));fs.rmSync(root,{recursive:true,force:true});}
});
