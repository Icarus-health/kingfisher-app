import test from 'node:test';
import assert from 'node:assert/strict';
import {createService,runChild} from './harness_service.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {runHarness} from './harness_run.mjs';

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

const controlledMode='controlled-local-readonly-v1';
const fixedModel='kingfisher-qwen3.5:9b-8k';
async function controlledService(run){
  const server=createService({mode:controlledMode,run,runtime:'/fixed/runtime',scratch:'/fixed/scratch'});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {server,url:'http://127.0.0.1:'+server.address().port};
}
const controlledReply={status:'complete',text:'Artificial draft',mode:controlledMode,
  model:fixedModel,syntheticOnly:false,osIsolationVerified:false};

test('controlled daemon pairs exactly once and only its trusted setup selects fixed runtime mode',async()=>{
  const calls=[];const {server,url}=await controlledService(async c=>{calls.push(c);return controlledReply;});
  try{
    assert.equal((await fetch(url+'/health')).status,200);
    assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)})).status,503);
    for(const body of [{key},{key,mode:'synthetic'},{key,mode:controlledMode,instance:'a'}]){
      assert.equal((await fetch(url+'/init',{method:'POST',body:JSON.stringify(body)})).status,400);
    }
    const response=await fetch(url+'/init',{method:'POST',body:JSON.stringify({key,mode:controlledMode})});
    assert.equal(response.status,200);
    const initialized=await response.json();
    assert.equal(initialized.status,'initialized');assert.equal(initialized.mode,controlledMode);
    assert.equal(initialized.model,fixedModel);assert.equal(initialized.syntheticOnly,false);
    assert.equal(initialized.osIsolationVerified,false);assert.match(initialized.instance,/^[a-f0-9]{64}$/);
    const health=await (await fetch(url+'/health')).json();
    assert.deepEqual(health,{...initialized,status:'ok'});
    for(const override of [{mode:controlledMode},{syntheticOnly:false},{model:fixedModel},{origin:'http://127.0.0.1:8890'},{instance:initialized.instance}]){
      assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify({...data,...override})})).status,400);
    }
    const result=await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)});
    assert.equal(result.status,200);
    assert.deepEqual(await result.json(),{...controlledReply,instance:initialized.instance});
    assert.equal(calls.length,1);
    assert.deepEqual(calls[0],{mode:controlledMode,syntheticOnly:false,request:data.request,token,
      model:fixedModel,origin:'http://kingfisher-gateway:8890',runtime:'/fixed/runtime',scratch:'/fixed/scratch'});
    assert.equal((await fetch(url+'/init',{method:'POST',body:JSON.stringify({key,mode:controlledMode})})).status,409);
    assert.ok(!JSON.stringify(initialized).includes(key));
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('controlled worker generation changes after restart and mismatched child result quarantines it',async()=>{
  let calls=0;const servers=[];const instances=[];
  try{
    for(let i=0;i<2;i++){
      const {server,url}=await controlledService(async()=>{calls++;return {...controlledReply,syntheticOnly:true};});servers.push(server);
      const init=await (await fetch(url+'/init',{method:'POST',body:JSON.stringify({key,mode:controlledMode})})).json();
      instances.push(init.instance);
      assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)})).status,502);
      assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)})).status,503);
      assert.equal((await fetch(url+'/health')).status,503);
    }
    assert.match(instances[0],/^[a-f0-9]{64}$/);assert.notEqual(instances[0],instances[1]);assert.equal(calls,2);
  }finally{for(const server of servers){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}}
});

test('controlled cancellation holds admission until the owned runner has returned',async()=>{
  let entered,aborted,release,calls=0;
  const started=new Promise(r=>entered=r),cancelled=new Promise(r=>aborted=r),finish=new Promise(r=>release=r);
  const {server,url}=await controlledService(async(_config,signal)=>{
    calls++;
    if(calls===1){entered();signal.addEventListener('abort',aborted,{once:true});await finish;}
    return controlledReply;
  });
  try{
    assert.equal((await fetch(url+'/init',{method:'POST',body:JSON.stringify({key,mode:controlledMode})})).status,200);
    const controller=new AbortController();
    const pending=fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data),signal:controller.signal}).catch(()=>{});
    await started;controller.abort();await cancelled;await pending;
    assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)})).status,409);
    assert.equal(calls,1);release();
    // A health round trip lets the released callback settle, without sleeping.
    await fetch(url+'/health');
    assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)})).status,200);
    assert.equal(calls,2);
  }finally{release();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('controlled mode rejects duplicate request members and unsupported setup before any child',async()=>{
  assert.throws(()=>createService({mode:'other'}),/unsupported runtime mode/);
  assert.throws(()=>createService({mode:controlledMode,key}),/initial service credential/);
  let calls=0;const {server,url}=await controlledService(async()=>{calls++;return controlledReply;});
  try{
    assert.equal((await fetch(url+'/init',{method:'POST',body:'{"key":"wrong","key":"'+key+'","mode":"'+controlledMode+'"}'})).status,400);
    assert.equal((await fetch(url+'/init',{method:'POST',body:JSON.stringify({key,mode:controlledMode})})).status,200);
    const raw='{"token":"'+token+'","request":"first","request":"second"}';
    assert.equal((await fetch(url+'/run',{method:'POST',headers,body:raw})).status,400);assert.equal(calls,0);
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('controlled runner only accepts its fixed gateway, model and closed parent configuration',async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'kf-runner-config-'));
  const runtime=path.join(root,'runtime');fs.mkdirSync(runtime);fs.writeFileSync(path.join(runtime,'package.json'),'{}');
  for(const name of ['dsh-sdk-client','dsh-llm-pi-ai','dsh-mcp-client']){
    const directory=path.join(runtime,'node_modules','@deepseek-ai',name);fs.mkdirSync(directory,{recursive:true});
    fs.writeFileSync(path.join(directory,'package.json'),JSON.stringify({type:'module',main:'index.mjs',version:'0.2.2-alpha.2'}));
  }
  const entry=path.join(runtime,'node_modules','@deepseek-ai','dsh-sdk-client','index.mjs');
  fs.writeFileSync(entry,`import fs from 'node:fs';export const seen=[];
export class DeepSeekHarness{constructor(options){this.row={options,patch:JSON.parse(fs.readFileSync(options.patches[0],'utf8'))};seen.push(this.row);}
async run(question){this.row.question=question;return {finalResponse:'Artificial runner draft'};}async close(){this.row.closed=true;}}`);
  const {pathToFileURL}=await import('node:url');const {seen}=await import(pathToFileURL(entry));
  const base={mode:controlledMode,syntheticOnly:false,model:fixedModel,origin:'http://kingfisher-gateway:8890',
    token,request:'Read selected original',runtime,scratch:root};
  try{
    assert.deepEqual(await runHarness(base),{...controlledReply,text:'Artificial runner draft'});
    assert.equal(seen.length,1);assert.equal(seen[0].question,base.request);assert.equal(seen[0].closed,true);
    const options=seen[0].options,patch=seen[0].patch;
    assert.equal(options.model,fixedModel);assert.equal(options.provider,'kingfisher-local');
    assert.equal(options.env.KF_WORKER_GRANT,token);assert.equal(options.env.DSH_TELEMETRY_MODE,'DISABLED');
    assert.deepEqual(Object.keys(options.env).sort(),['DSH_HOME','DSH_TELEMETRY_MODE','KF_WORKER_GRANT','NARB_DISABLE_NATIVE_CACHE','PATH','TMPDIR']);
    for(const id of ['session-log-deepseek','plugin-package-inventory-deepseek','llm-deepseek','persistent-bash',
      'persistent-pwsh','tool-fs','tool-working-directory','llm-retry','compaction-basic','image-offload']){
      assert.equal(patch.find(row=>row.id===id)?.disabled,true);
    }
    const inserted=patch.find(row=>row.insert).insert;
    assert.equal(inserted[0].config.providers['kingfisher-local'].baseURL,'http://kingfisher-gateway:8890/worker/v1');
    assert.equal(inserted[1].config.url,'http://kingfisher-gateway:8890/worker/mcp');
    const prompt=patch.find(row=>row.id==='system-prompt').config.personaPrefix;
    // These are the four public tools exposed by the closed protocol. Assert
    // against the prompt actually delivered to the SDK, not its source text.
    const instructed=[...new Set(prompt.match(/\b[a-z]+(?:_[a-z]+)+\b/g))].sort();
    assert.deepEqual(instructed,['memory_search','selected_original','skills_select','source_excerpt']);
    for(const override of [{origin:'http://127.0.0.1:8890'},{origin:'http://other:8890'},
      {model:'other'},{syntheticOnly:true},{command:'shell'},{mode:'other'}]){
      const result=await runHarness({...base,...override});
      assert.equal(result.status,'failed');assert.ok(!JSON.stringify(result).includes(token));assert.equal(result.syntheticOnly,false);
    }
    assert.equal(seen.length,1,'invalid setup reached the SDK constructor');
    const {mode,...synthetic}=base;
    assert.deepEqual(await runHarness({...synthetic,syntheticOnly:true,origin:'http://127.0.0.1:8890'}),
      {status:'complete',text:'Artificial runner draft',syntheticOnly:true,osIsolationVerified:false});
    assert.deepEqual(fs.readdirSync(root),['runtime']);
  }finally{fs.rmSync(root,{recursive:true,force:true});}
});

test('owned controlled child receives no daemon authority and cannot relabel a synthetic result',async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'kf-controlled-child-'));
  const entry=path.join(root,'fake.mjs');
  const config={scratch:root,mode:controlledMode,syntheticOnly:false,token,model:fixedModel,origin:'http://kingfisher-gateway:8890'};
  process.env.KF_WORKER_SERVICE_KEY=key;process.env.KF_GATEWAY_CONTROL_KEY=key;
  fs.writeFileSync(entry,`let raw='';for await(const c of process.stdin)raw+=c;const c=JSON.parse(raw);
if('KF_WORKER_SERVICE_KEY' in process.env||'KF_GATEWAY_CONTROL_KEY' in process.env||'KF_HARNESS_MODE' in process.env)process.exit(2);
process.stdout.write(JSON.stringify({status:'complete',text:'Done',syntheticOnly:true}));`);
  try{
    await assert.rejects(runChild(config,undefined,{entry}),error=>error.message==='worker result invalid'&&error.code==='WorkerRuntimeMismatch');
    fs.writeFileSync(entry,`let raw='';for await(const c of process.stdin)raw+=c;const c=JSON.parse(raw);
if('KF_WORKER_SERVICE_KEY' in process.env||'KF_GATEWAY_CONTROL_KEY' in process.env||'KF_HARNESS_MODE' in process.env)process.exit(2);
process.stdout.write(JSON.stringify({status:'complete',text:c.mode,mode:c.mode,model:c.model,syntheticOnly:false,osIsolationVerified:false}));`);
    assert.equal((await runChild(config,undefined,{entry})).text,controlledMode);
    assert.deepEqual(fs.readdirSync(root),['fake.mjs']);
  }finally{delete process.env.KF_WORKER_SERVICE_KEY;delete process.env.KF_GATEWAY_CONTROL_KEY;fs.rmSync(root,{recursive:true,force:true});}
});

test('known safe controlled child failure is an ordinary run failure for zero and nonzero exits',async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'kf-controlled-failure-'));
  const entry=path.join(root,'fake.mjs');
  const {text,...metadata}=controlledReply;
  const failure={...metadata,status:'failed',error:'HarnessWorkerFailed'};
  try{
    for(const code of [0,1]){
      fs.writeFileSync(entry,`for await(const c of process.stdin){};process.stdout.write(${JSON.stringify(JSON.stringify(failure))});process.exitCode=${code};`);
      await assert.rejects(runChild({scratch:root,mode:controlledMode},undefined,{entry}),
        error=>error.message==='worker failed'&&error.code!== 'WorkerRuntimeMismatch');
      assert.deepEqual(fs.readdirSync(root),['fake.mjs']);
    }
  }finally{fs.rmSync(root,{recursive:true,force:true});}
});

test('controlled child failure still quarantines wrong or extra metadata even with nonzero exit',async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'kf-controlled-invalid-failure-'));
  const entry=path.join(root,'fake.mjs');const {text,...metadata}=controlledReply;
  const failure={...metadata,status:'failed',error:'HarnessWorkerFailed'};
  try{
    for(const change of [{mode:'other'},{model:'cloud'},{syntheticOnly:true},{osIsolationVerified:true},
      {private:'unexpected'},{error:'private diagnostics'}]){
      fs.writeFileSync(entry,`for await(const c of process.stdin){};process.stdout.write(${JSON.stringify(JSON.stringify({...failure,...change}))});process.exitCode=1;`);
      await assert.rejects(runChild({scratch:root,mode:controlledMode},undefined,{entry}),
        error=>error.message==='worker result invalid'&&error.code==='WorkerRuntimeMismatch');
    }
  }finally{fs.rmSync(root,{recursive:true,force:true});}
});

test('ordinary controlled child failure keeps its paired service healthy for the next run',async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'kf-controlled-service-failure-'));
  const entry=path.join(root,'fake.mjs');const {text,...metadata}=controlledReply;
  const failure={...metadata,status:'failed',error:'HarnessWorkerFailed'};
  fs.writeFileSync(entry,`for await(const c of process.stdin){};process.stdout.write(${JSON.stringify(JSON.stringify(failure))});`);
  const server=createService({mode:controlledMode,runtime:root,scratch:root,run:(c,signal)=>runChild(c,signal,{entry})});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const url='http://127.0.0.1:'+server.address().port;
  try{
    const init=await (await fetch(url+'/init',{method:'POST',body:JSON.stringify({key,mode:controlledMode})})).json();
    assert.equal((await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)})).status,502);
    const health=await fetch(url+'/health');assert.equal(health.status,200);
    assert.deepEqual(await health.json(),{...init,status:'ok'});
    fs.writeFileSync(entry,`for await(const c of process.stdin){};process.stdout.write(${JSON.stringify(JSON.stringify(controlledReply))});`);
    const next=await fetch(url+'/run',{method:'POST',headers,body:JSON.stringify(data)});
    assert.equal(next.status,200);assert.deepEqual(await next.json(),{...controlledReply,instance:init.instance});
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));fs.rmSync(root,{recursive:true,force:true});}
});

test('daemon entry accepts no arbitrary setup arguments',async()=>{
  const {spawn}=await import('node:child_process');const {fileURLToPath}=await import('node:url');
  for(const args of [['--model','cloud'],['--controlled-local-readonly-v1','--origin','http://other']]){
    const child=spawn(process.execPath,[fileURLToPath(new URL('./harness_service.mjs',import.meta.url)),...args],{env:{PATH:process.env.PATH}});
    let output='';child.stdout.on('data',c=>output+=c);child.stderr.on('data',c=>output+=c);
    const result=await Promise.race([new Promise(resolve=>child.once('close',resolve)),
      new Promise(resolve=>{const timer=setTimeout(()=>{child.kill();resolve('timeout');},1000);timer.unref();})]);
    assert.notEqual(result,'timeout');assert.notEqual(result,0);assert.ok(output.includes('unsupported runtime mode'));
  }
});
