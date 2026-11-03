"""Synthetic three-role OS proof; no personal server or model inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time

from probe_harness_isolation import NETWORK_CHECK, isolation_checks

CONTROLLED_MODE='controlled-local-readonly-v1'


def boundary_checks(report):
    """Do not trust a producer's status/claim or a missing OS receipt."""
    try:
        negative=report['negatives']
        cases={row['case']:row for row in report['cases']}
        baseline=cases['baseline']
        exact=lambda values:all(value is True for value in values)
        mode=report.get('runtime_mode','synthetic-only')
        contract=mode=='synthetic-only'
        if mode==CONTROLLED_MODE:
            health=report['controlled_health']
            fields={'status','mode','model','syntheticOnly','osIsolationVerified','instance'}
            contract=(isinstance(health,list) and len(health)==4
                and all(isinstance(row,dict) and set(row)==fields and row['status']=='ok'
                    and row['mode']==CONTROLLED_MODE and row['model']=='kingfisher-qwen3.5:9b-8k'
                    and row['syntheticOnly'] is False and row['osIsolationVerified'] is False
                    and isinstance(row['instance'],str) and re.fullmatch(r'[a-f0-9]{64}',row['instance'])
                    for row in health)
                and len({row['instance'] for row in health})==1)
        return dict(synthetic=(report['synthetic_only'] is True
                    and report['personal_store_opened'] is False
                    and type(report['paid_calls']) is int and report['paid_calls']==0
                    and report['injected_model_only'] is True and report['live_semantic_verified'] is False),
            controls=exact(report['worker_isolation'].values())
                and set(report['worker_isolation'])=={'configured','negative'}
                and exact(report[key] for key in ('topology_verified','no_initial_worker_key',
                                                  'parent_proc_test','ui_bootstrap_baseline')),
            network=negative['main_ip'] in {'ENETUNREACH','timeout','EHOSTUNREACH'}
                and negative['main_dns'] in {'ENOTFOUND','EAI_AGAIN','ESERVFAIL','ECONNREFUSED'}
                and all(negative[key]['status']==404 and negative[key]['cookie'] is False
                    for key in ('gateway_root','gateway_api','gateway_main_port'))
                and negative['controller_without_key']['status']==401
                and negative['controller_without_key']['cookie'] is False,
            baseline=baseline['status']==200 and baseline['model_calls']==2
                and exact(baseline['checks'].get(key) for key in
                    ('complete','scope','actual_search','automatic_skills','originals_unchanged')),
            interruption=len(report['cases'])==3 and set(cases)=={'baseline','cancel','source_revoked'}
                and all(cases[name]['status'] in {401,409,502,503}
                    and cases[name]['model_calls']==1
                    and 0<=cases[name]['coordination']['ui_seconds']<3
                    and exact(cases[name]['checks'].get(key) for key in
                        ('result_withheld','interrupted','ui_responsive','capability_revoked','original_bodies_unchanged'))
                    for name in ('cancel','source_revoked')),
            memory_reserve=type(report['sampled_max_mac_pressure']) is int
                and 0<report['sampled_max_mac_pressure']<=2,
            cleanup=report['cleanup_verified'] is True and not report.get('cleanup_pending'),
            runtime_contract=contract)
    except (KeyError,TypeError,ValueError,AttributeError):
        return dict(complete=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True,help='Existing public Linux Node/SDK directory shared with Colima')
    parser.add_argument('--image',required=True,help='Existing immutable image; no pull or build')
    parser.add_argument('--output',required=True)
    parser.add_argument('--controlled',action='store_true',
        help='Use the fixed controlled daemons with artificial stores and injected inference; no live semantic proof')
    args=parser.parse_args(argv)
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',args.image):raise ValueError('Immutable image required')
    runtime=Path(args.runtime).resolve();root=Path(__file__).resolve().parents[1]
    expected_lock='b9c37928b69fc90ea9e8d1f76dabe0696f14c000e36ec54d814e278709ded294'
    if (hashlib.sha256((runtime/'package-lock.json').read_bytes()).hexdigest()!=expected_lock
            or not (runtime/'bin/node').is_file()
            or not (runtime/'node_modules/@deepseek-ai/dsh-sdk-client/package.json').is_file()):
        raise ValueError('Pinned public runtime missing')
    output=Path(args.output)
    report=dict(status='running',synthetic_only=True,personal_store_opened=False,paid_calls=0,
                injected_model_only=True,live_semantic_verified=False,cases=[],
                runtime_mode=CONTROLLED_MODE if args.controlled else 'synthetic-only')
    mode_args=['--'+CONTROLLED_MODE] if args.controlled else []
    if args.controlled:report['controlled_health']=[]
    with output.open('x') as stream:json.dump(report,stream)
    def save():
        partial=output.with_suffix(output.suffix+'.partial')
        partial.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');os.replace(partial,output)
    nonce=secrets.token_hex(6);label='kingfisher.synthetic='+nonce
    containers=[];networks=[];controller_code=None;started=time.monotonic()
    monitor_stop=threading.Event();monitoring=None;levels=[]
    def docker(*arguments,timeout=30):
        result=subprocess.run(['docker',*arguments],capture_output=True,text=True,timeout=timeout)
        if result.returncode:raise RuntimeError('Docker operation failed: '+arguments[0])
        return result.stdout.strip()
    def details(identifier):return json.loads(docker('inspect',identifier))[0]
    def own(identifier):
        if details(identifier)['Config']['Labels'].get('kingfisher.synthetic')!=nonce:
            raise RuntimeError('Ownership changed')
    def pressure():
        if os.uname().sysname!='Darwin':return 1
        return int(subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True))
    def execute_json(identifier,code,timeout=130):
        return json.loads(docker('exec',identifier,'python','-c',code,timeout=timeout))
    def fixture_call(path,*,method='POST'):
        code="""import httpx,json,os
with httpx.Client(timeout=120,trust_env=False,follow_redirects=False) as c:
 r=c.request(%r,'http://127.0.0.1:8890'+%r,headers={'Authorization':'Bearer '+os.environ['KF_GATEWAY_CONTROL_KEY']});r.raise_for_status();print(json.dumps(r.json()))
""" % (method,path)
        return execute_json(main_id,code)
    try:
        levels.append(pressure())
        if levels[-1]>2:raise RuntimeError('Memory reserve unavailable')
        for name in ('harness_service.mjs','harness_worker.mjs','harness_run.mjs','harness_gateway.py'):
            if (runtime/name).read_bytes() != (root/'scripts'/name).read_bytes():
                raise ValueError('Current reviewed public shim required')
        # The verified runtime is never mutated by this proof. Fixture code is
        # a separate public read-only mount available only to the controller.
        controller_code=runtime.parent/('kf-artificial-controller-'+nonce)
        controller_code.mkdir(mode=0o755)
        shutil.copytree(root/'sidecar/icarus_memory',controller_code/'icarus_memory',
                        dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copy2(root/'integrations/harness/production_boundary_controller.py',controller_code)
        report['code_sha256']={name:hashlib.sha256((runtime/name).read_bytes()).hexdigest()
            for name in ('harness_service.mjs','harness_worker.mjs','harness_run.mjs','harness_gateway.py','package-lock.json')}
        control_net=docker('network','create','--internal','--label',label,'kf-boundary-main-'+nonce);networks.append(control_net)
        worker_net=docker('network','create','--internal','--label',label,'kf-boundary-worker-'+nonce);networks.append(worker_net)
        with tempfile.TemporaryDirectory(prefix='kf-boundary-artificial-env-') as temp:
            environment=Path(temp)/'artificial.env'
            environment.write_text('KF_GATEWAY_CONTROL_KEY='+secrets.token_urlsafe(32)
                +'\nICARUS_SIDECAR_TOKEN='+secrets.token_urlsafe(32)
                +'\nPYTHONPATH=/controller\n')
            environment.chmod(0o600)
            proxy_env=Path(temp)/'proxy.env'
            proxy_env.write_text(environment.read_text().splitlines()[0]+'\n');proxy_env.chmod(0o600)
            common=['--user','1000:1000','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                '--tmpfs','/tmp:rw,noexec,nosuid,size=64m,uid=1000,gid=1000,mode=700',
                '--tmpfs','/data:rw,noexec,nosuid,size=64k,mode=000',
                '--mount','type=bind,source='+str(runtime)+',target=/runtime,readonly','--label',label,'--dns','127.0.0.1']
            main_id=docker('create','--name','kf-boundary-controller-'+nonce,'--network',control_net,
                '--network-alias','kingfisher-controller','--memory','512m','--cpus','0.5','--pids-limit','64',
                '--env-file',str(environment),*common,
                '--mount','type=bind,source='+str(controller_code)+',target=/controller,readonly',
                '--entrypoint','python',args.image,
                '-m','uvicorn','production_boundary_controller:app','--host','0.0.0.0','--port','8890',
                '--lifespan','off','--no-access-log','--log-level','warning');containers.append(main_id)
            proxy_id=docker('create','--name','kf-boundary-proxy-'+nonce,'--network',control_net,
                '--network-alias','kingfisher-gateway-control','--memory','64m','--cpus','0.25','--pids-limit','32',
                '--env-file',str(proxy_env),*common,'--entrypoint','python',args.image,'/runtime/harness_gateway.py',*mode_args);containers.append(proxy_id)
            docker('network','connect','--alias','kingfisher-gateway',worker_net,proxy_id)
            worker_id=docker('create','--name','kf-boundary-worker-'+nonce,'--network',worker_net,
                '--network-alias','kingfisher-worker','--memory','512m','--cpus','0.75','--pids-limit','64',
                *common,'--entrypoint','/runtime/bin/node',args.image,'/runtime/harness_service.mjs',*mode_args);containers.append(worker_id)
            docker('start',main_id,proxy_id,worker_id)
            def monitor():
                while not monitor_stop.wait(2):
                    try:
                        level=pressure();levels.append(level)
                        if level>2:
                            own(worker_id);docker('stop','--time','1',worker_id);return
                    except Exception:
                        levels.append(4);return  # Missing measurement is not a green reserve claim.
            monitoring=threading.Thread(target=monitor,daemon=True);monitoring.start()
            until=time.monotonic()+30
            while True:
                try:
                    if fixture_call('/fixture/readiness',method='GET')['status']=='ok':break
                except Exception:
                    if time.monotonic()>until:raise RuntimeError('Artificial controller did not start')
                    time.sleep(.2)
            mi,pi,wi=(details(i) for i in (main_id,proxy_id,worker_id))
            control_info=json.loads(docker('network','inspect',control_net))[0]
            worker_info=json.loads(docker('network','inspect',worker_net))[0]
            report['topology_verified']=(control_info['Internal'] is True and worker_info['Internal'] is True
                and set(mi['NetworkSettings']['Networks'])=={control_info['Name']}
                and set(pi['NetworkSettings']['Networks'])=={control_info['Name'],worker_info['Name']}
                and set(wi['NetworkSettings']['Networks'])=={worker_info['Name']}
                and all(not any(i['NetworkSettings']['Ports'].values()) for i in (mi,pi,wi))
                and all(i['Image']==args.image for i in (mi,pi,wi)))
            report['no_initial_worker_key']=not any(entry.startswith(('KF_WORKER_SERVICE_KEY=','KF_GATEWAY_CONTROL_KEY=','ICARUS_SIDECAR_TOKEN=')) for entry in wi['Config'].get('Env',[]))
            config=dict(image_id=wi['Image'],uid=wi['Config']['User'],read_only=wi['HostConfig']['ReadonlyRootfs'],
                cap_drop=wi['HostConfig']['CapDrop'],security=wi['HostConfig']['SecurityOpt'],
                memory=wi['HostConfig']['Memory'],nano_cpus=wi['HostConfig']['NanoCpus'],pids=wi['HostConfig']['PidsLimit'],
                dns=wi['HostConfig']['Dns'],tmpfs=wi['HostConfig']['Tmpfs'],
                no_host_ports=not any(wi['NetworkSettings']['Ports'].values()),
                only_internal_network=set(wi['NetworkSettings']['Networks'])=={worker_info['Name']},
                network_internal=worker_info['Internal'],
                public_runtime_only=len(wi['Mounts'])==1 and wi['Mounts'][0]['Source']==str(runtime)
                    and wi['Mounts'][0]['Destination']=='/runtime' and wi['Mounts'][0]['RW'] is False)
            negative=json.loads(docker('exec',worker_id,'/runtime/bin/node','--input-type=module','-e',NETWORK_CHECK))
            report['worker_config']=config;report['negative_network']=negative
            report['worker_isolation']=isolation_checks(config,negative,args.image)
            main_ip=mi['NetworkSettings']['Networks'][control_info['Name']]['IPAddress']
            path_probe=r"""
import net from 'node:net';import dns from 'node:dns/promises';
const r={};const tcp=(host,port)=>new Promise(resolve=>{const s=net.connect({host,port});s.setTimeout(1000);s.once('connect',()=>{s.destroy();resolve('connected')});s.once('error',e=>resolve(e.code));s.once('timeout',()=>{s.destroy();resolve('timeout')})});
r.main_ip=await tcp(MAIN_IP,8890);try{r.main_dns=await dns.resolve4('kingfisher-controller')}catch(e){r.main_dns=e.code}
for(const [name,url] of Object.entries({gateway_root:'http://kingfisher-gateway:8890/',gateway_api:'http://kingfisher-gateway:8890/api/v1/episodes/unknown',gateway_main_port:'http://kingfisher-gateway:8890/fixture/readiness',controller_without_key:'http://kingfisher-gateway:8891/controller/health'})){
 const v=await fetch(url,{redirect:'manual',signal:AbortSignal.timeout(3000)});r[name]={status:v.status,cookie:v.headers.has('set-cookie')};}
console.log(JSON.stringify(r));
""".replace('MAIN_IP',json.dumps(main_ip))
            report['negatives']=json.loads(docker('exec',worker_id,'/runtime/bin/node','--input-type=module','-e',path_probe))
            baseline=r"""import httpx,json
with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as c:
 # The known original endpoint is guarded; no artificial credential is supplied.
 root=c.get('http://127.0.0.1:8890/');cookie='kingfisher_session' in root.cookies
 auth=c.get('http://127.0.0.1:8890/api/v1/task-candidates')
 print(json.dumps({'cookie':cookie,'authorized':auth.status_code==200}))
"""
            baseline_result=execute_json(main_id,baseline)
            report['ui_bootstrap_baseline']=baseline_result=={'cookie':True,'authorized':True}
            parent_probe=r"""
import {createService} from '/runtime/harness_service.mjs';
import {CONTROLLED_MODE} from '/runtime/harness_run.mjs';
import crypto from 'node:crypto';import {spawnSync} from 'node:child_process';
const key=crypto.randomBytes(32).toString('base64url');
const service=createService({mode:CONTROLLED_MODE,runtime:'/runtime',scratch:'/tmp'});
await new Promise(resolve=>service.listen(0,'127.0.0.1',resolve));
let result={passed:false};
try {
 const response=await fetch('http://127.0.0.1:'+service.address().port+'/init',{method:'POST',body:JSON.stringify({key,mode:CONTROLLED_MODE})});
 await response.text();
 const child=spawnSync(process.execPath,['--input-type=module','-e',"import fs from 'node:fs';process.stdout.write(fs.readFileSync('/proc/'+process.ppid+'/environ'));"],{env:{PATH:'/usr/bin:/bin'},timeout:3000,maxBuffer:65536});
 const initial=child.stdout?.toString()??'';
 result={passed:response.status===200&&child.status===0&&!initial.includes(key)&&!initial.includes('KF_WORKER_SERVICE_KEY=')&&!initial.includes('KF_GATEWAY_CONTROL_KEY=')&&!initial.includes('ICARUS_SIDECAR_TOKEN=')};
} finally {service.closeAllConnections();await new Promise(resolve=>service.close(resolve));}
console.log(JSON.stringify(result));
"""
            proc_test=json.loads(docker('exec',worker_id,'/runtime/bin/node','--input-type=module','-e',parent_probe))
            report['parent_proc_receipt']=proc_test
            report['parent_proc_test']=proc_test=={'passed':True}
            initialize=r"""import httpx,json,os
with httpx.Client(timeout=10,trust_env=False,follow_redirects=False) as c:
 r=c.post('http://kingfisher-gateway-control:8891/controller/initialize',json={},headers={'Authorization':'Bearer '+os.environ['KF_GATEWAY_CONTROL_KEY']});r.raise_for_status();print(json.dumps(r.json()))
"""
            report['initialize']=execute_json(main_id,initialize)
            health=r"""import httpx,json,os
with httpx.Client(timeout=10,trust_env=False,follow_redirects=False) as c:
 r=c.get('http://kingfisher-gateway-control:8891/controller/health',headers={'Authorization':'Bearer '+os.environ['KF_GATEWAY_CONTROL_KEY']});r.raise_for_status();print(json.dumps(r.json()))
"""
            if args.controlled:report['controlled_health'].append(execute_json(main_id,health))
            for case in ('baseline','cancel','source_revoked'):
                levels.append(pressure())
                if levels[-1]>2:raise RuntimeError('Memory pressure increased')
                report['cases'].append(fixture_call('/fixture/pilot?case='+case))
                if args.controlled:report['controlled_health'].append(execute_json(main_id,health))
                save()
    except KeyboardInterrupt:report.update(error='KeyboardInterrupt')
    except Exception as exc:report.update(error=type(exc).__name__,operation=str(exc)[:100])
    finally:
        monitor_stop.set()
        if monitoring is not None:monitoring.join(3)
        report['sampled_max_mac_pressure']=max(levels,default=4)
        for identifier in reversed(containers):
            try:
                own(identifier);docker('rm','-f','-v',identifier)
                if docker('ps','-aq','--filter','id='+identifier):raise RuntimeError('Container remains')
            except Exception:report.setdefault('cleanup_pending',[]).append(identifier)
        for identifier in reversed(networks):
            try:
                info=json.loads(docker('network','inspect',identifier))[0]
                if info['Labels'].get('kingfisher.synthetic')!=nonce:raise RuntimeError('Network ownership changed')
                docker('network','rm',identifier)
                if docker('network','ls','-q','--filter','id='+identifier):raise RuntimeError('Network remains')
            except Exception:report.setdefault('cleanup_pending',[]).append(identifier)
        if controller_code is not None:
            try:shutil.rmtree(controller_code)
            except Exception:report.setdefault('cleanup_pending',[]).append('artificial_controller_code')
        report['cleanup_verified']=not report.get('cleanup_pending')
        report['checks']=boundary_checks(report)
        report['status']='passed' if all(report['checks'].values()) else 'failed'
        report['seconds']=round(time.monotonic()-started,3);save()
    print(json.dumps({key:report[key] for key in ('status','seconds','error','operation','cleanup_pending') if key in report}))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
