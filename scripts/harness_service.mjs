// Read-only worker service. It has no source store, provider key or application token.
import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

function removeOwnedTree(owned){
  // Children have exited. Restore directory traversal only inside this owned
  // tree; lstat avoids changing permissions through an external symlink.
  const pending=[owned];let entries=0;
  while(pending.length){
    const directory=pending.pop();
    if(!fs.lstatSync(directory).isDirectory())continue;
    fs.chmodSync(directory,0o700);
    for(const item of fs.readdirSync(directory,{withFileTypes:true})){
      if(++entries>20000)throw new Error('cleanup bound');
      if(item.isDirectory())pending.push(path.join(directory,item.name));
    }
  }
  fs.rmSync(owned,{recursive:true,force:true});
}

export function runChild(config,signal,{timeout=110000,entry=fileURLToPath(new URL('./harness_worker.mjs',import.meta.url))}={}){
  if(signal?.aborted) return Promise.reject(new Error('cancelled'));
  const owned=fs.mkdtempSync(path.join(config.scratch,'kf-job-'));fs.chmodSync(owned,0o700);
  return new Promise((resolve,reject)=>{
    const env={PATH:path.dirname(process.execPath)+':/usr/bin:/bin',TMPDIR:owned,DSH_TELEMETRY_MODE:'DISABLED'};
    let child,timer,error,finished=false,output=[],outBytes=0,errBytes=0;
    const stop=reason=>{
      error??=reason;
      if(child?.pid){try{process.kill(-child.pid,'SIGKILL');}catch(e){if(e.code!=='ESRCH')error=new Error('termination failed');}}
    };
    const abort=()=>stop(new Error('cancelled'));
    const done=code=>{
      if(finished)return;finished=true;clearTimeout(timer);signal?.removeEventListener('abort',abort);
      stop(error);
      try{removeOwnedTree(owned);}catch(_error){
        const failure=new Error('worker cleanup required');failure.code='WorkerCleanupRequired';
        reject(failure);return;
      }
      if(error||code!==0){reject(new Error('worker failed'));return;}
      try{
        const result=JSON.parse(Buffer.concat(output).toString('utf8'));
        if(result?.status!=='complete'||typeof result.text!=='string'||!result.text.trim()||result.text.length>32000)throw new Error('result');
        resolve(result);
      }catch(_error){reject(new Error('worker result invalid'));}
    };
    try{
      child=spawn(process.execPath,[entry],{env,detached:true,stdio:['pipe','pipe','pipe']});
      child.once('error',()=>{error=new Error('worker startup failed');done(1);});
      child.once('close',done);
      child.stdin.on('error',()=>stop(new Error('input failed')));
      child.stdout.on('data',chunk=>{outBytes+=chunk.length;if(outBytes>65536)stop(new Error('output bound'));else output.push(chunk);});
      child.stderr.on('data',chunk=>{errBytes+=chunk.length;if(errBytes>65536)stop(new Error('diagnostic bound'));});
      signal?.addEventListener('abort',abort,{once:true});
      timer=setTimeout(()=>stop(new Error('deadline')),Math.min(timeout,110000));
      child.stdin.end(JSON.stringify({...config,scratch:owned}));
    }catch(_error){error=new Error('worker startup failed');done(1);}
  });
}

export function createService({key,run=runChild,runtime='/runtime',scratch='/tmp'}={}){
  const validKey=value=>typeof value==='string'&&/^[-\w]{43}$/.test(value);
  if(key!==undefined&&!validKey(key))throw new Error('service credential invalid');
  let busy=false,tainted=false,initializing=false;
  async function readBody(req,limit){
    let size=0;const chunks=[];
    for await(const chunk of req){size+=chunk.length;if(size>limit)return {tooLarge:true};chunks.push(chunk);}
    try{return {data:JSON.parse(Buffer.concat(chunks).toString('utf8'))};}
    catch(_error){return {};}
  }
  return http.createServer({headersTimeout:5000,requestTimeout:10000,keepAliveTimeout:1000,
    connectionsCheckingInterval:1000,maxHeaderSize:8192},async(req,res)=>{
    const reply=(status,value)=>{
      if(!res.destroyed){res.writeHead(status,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify(value));}
    };
    if(req.url==='/health'&&req.method==='GET'){
      reply(tainted?503:200,{status:tainted?'restart_required':key===undefined?'awaiting_controller':'ok'});return;
    }
    if(req.url==='/init'&&req.method==='POST'){
      if(key!==undefined||initializing){reply(409,{error:'AlreadyInitialized'});return;}
      // Reserve before awaiting a body. This port is reachable only by the trusted gateway.
      initializing=true;
      try{
        const body=await readBody(req,128);
        if(body.tooLarge){reply(413,{error:'InputTooLarge'});return;}
        const value=body.data;
        if(!value||Array.isArray(value)||typeof value!=='object'
            ||Object.keys(value).join()!=='key'||!validKey(value.key)){
          reply(400,{error:'InvalidRequest'});return;
        }
        key=value.key;reply(200,{status:'initialized'});
      }catch(_error){reply(400,{error:'InvalidRequest'});}
      finally{initializing=false;}
      return;
    }
    if(req.url!=='/run'||req.method!=='POST'){reply(404,{error:'UnknownOperation'});return;}
    if(key===undefined){reply(503,{error:'AwaitingController'});return;}
    const supplied=req.headers.authorization??'',wanted='Bearer '+key;
    if(typeof supplied!=='string'||Buffer.byteLength(supplied)!==Buffer.byteLength(wanted)
        ||!crypto.timingSafeEqual(Buffer.from(supplied),Buffer.from(wanted))){reply(401,{error:'Unauthorized'});return;}
    if(tainted){reply(503,{error:'WorkerNeedsRestart'});return;}
    if(busy){reply(409,{error:'WorkerBusy'});return;}
    // Reserve before reading: concurrent slow bodies cannot each start a job.
    busy=true;
    const controller=new AbortController();let complete=false;
    res.once('close',()=>{if(!complete)controller.abort();});
    try{
      let size=0;const chunks=[];
      for await(const chunk of req){size+=chunk.length;if(size>8192){reply(413,{error:'InputTooLarge'});return;}chunks.push(chunk);}
      let data;
      try{data=JSON.parse(Buffer.concat(chunks).toString('utf8'));}catch(_error){reply(400,{error:'InvalidRequest'});return;}
      if(!data||Array.isArray(data)||typeof data!=='object'||Object.keys(data).sort().join()!=='request,token'
          ||typeof data.request!=='string'||!data.request.trim()||data.request.length>1200
          ||typeof data.token!=='string'||!/^[-\w]{43}$/.test(data.token)){
        reply(400,{error:'InvalidRequest'});return;
      }
      const result=await run({syntheticOnly:true,request:data.request,token:data.token,
        model:'kingfisher-qwen3.5:9b-8k',origin:'http://kingfisher-gateway:8890',runtime,scratch},controller.signal);
      if(result?.status!=='complete'||typeof result.text!=='string'||!result.text.trim()||result.text.length>32000){
        reply(502,{error:'WorkerFailed'});return;
      }
      reply(200,{status:'complete',text:result.text,syntheticOnly:true});
    }catch(error){if(error?.code==='WorkerCleanupRequired')tainted=true;reply(502,{error:'WorkerFailed'});}
    finally{complete=true;busy=false;}
  });
}

if(process.argv[1]===fileURLToPath(import.meta.url)){
  // Never load service authority from initial environment: a same-UID child can
  // read those original bytes through /proc even after process.env deletion.
  if(Object.hasOwn(process.env,'KF_WORKER_SERVICE_KEY')){
    process.stderr.write('initial service credential is forbidden\n');process.exitCode=1;
  }else{
    // Internal worker-only network; trusted gateway initializes before any job.
    createService().listen(3001,'0.0.0.0');
  }
}
