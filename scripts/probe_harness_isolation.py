"""Disposable Colima/Docker proof with public runtime and artificial data only.

Creates/removes only new labelled test containers and networks. Never attaches
the personal volume, application token, cloud key, Docker socket or host port to
the worker. The gateway's temporary control port is loopback-only.
"""
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

import httpx
from probe_intake_precision import _mac_resource_check


NETWORK_CHECK = r"""
import fs from 'node:fs';import net from 'node:net';import dns from 'node:dns/promises';
const tcp=(host,port)=>new Promise(resolve=>{const s=net.connect({host,port});
 s.setTimeout(1200);s.once('connect',()=>{s.destroy();resolve('connected');});
 s.once('error',e=>resolve(e.code));s.once('timeout',()=>{s.destroy();resolve('timeout');});});
const r={uid:process.getuid()};
r.external_ip=await tcp('1.1.1.1',443);r.host_service=await tcp('192.168.5.2',11434);
const resolver=new dns.Resolver({timeout:500,tries:1});
try{r.external_dns=await resolver.resolve4('example.com');}catch(e){r.external_dns=e.code;}
try{r.gateway=(await fetch('http://kingfisher-gateway:8890/health',{signal:AbortSignal.timeout(3000)})).status;}catch(e){r.gateway='unavailable';}
try{fs.writeFileSync('/home/kingfisher/kf-write-probe','test');r.root_write='allowed';}catch(e){r.root_write=e.code;}
try{fs.readdirSync('/data');r.data_read='allowed';}catch(e){r.data_read=e.code;}
const status=fs.readFileSync('/proc/self/status','utf8');
const fields=Object.fromEntries(status.split(String.fromCharCode(10)).filter(l=>l.includes(':'))
 .map(l=>{const colon=l.indexOf(':');return [l.slice(0,colon),l.slice(colon+1).trim()];}));
r.capabilities=fields.CapEff??null;r.no_new_privileges=fields.NoNewPrivs??null;
console.log(JSON.stringify(r));
"""


def isolation_checks(config, negative, image):
    """Missing or malformed receipts never become a green isolation claim."""
    try:
        tmpfs=config['tmpfs']
        if not isinstance(tmpfs,dict) or set(tmpfs)!={'/tmp','/data'}:
            raise ValueError('Incomplete temporary filesystem receipt')
        def options(text):
            if not isinstance(text,str): raise ValueError('Invalid mount options')
            result={}
            for entry in text.split(','):
                key,_,value=entry.partition('=')
                if key in result: raise ValueError('Duplicate mount option')
                result[key]=value or True
            return result
        protected=(options(tmpfs['/tmp'])==dict(rw=True,noexec=True,nosuid=True,size='64m',uid='1000',gid='1000',mode='700')
            and options(tmpfs['/data'])==dict(rw=True,noexec=True,nosuid=True,size='64k',mode='000'))
        return dict(configured=config['image_id']==image and config['uid']=='1000:1000'
            and config['read_only'] is True and config['public_runtime_only'] is True
            and config['no_host_ports'] is True and config['only_internal_network'] is True
            and config['network_internal'] is True and config['dns']==['127.0.0.1']
            and config['cap_drop']==['ALL'] and isinstance(config['security'],list)
            and 'no-new-privileges' in config['security']
            and config['memory']==512*1024**2 and config['nano_cpus']==750000000 and config['pids']==64
            and protected,
            negative=negative['uid']==1000 and negative['external_ip']=='ENETUNREACH'
                and negative['host_service']=='ENETUNREACH'
                and negative['external_dns'] in {'ESERVFAIL','ECONNREFUSED','ENOTFOUND'}
                and negative['gateway']==200 and negative['root_write']=='EROFS'
                and negative['data_read']=='EACCES' and isinstance(negative['capabilities'],str)
                and int(negative['capabilities'],16)==0 and negative['no_new_privileges']=='1')
    except (KeyError,ValueError,TypeError):
        return dict(configured=False,negative=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True,help='Public code/SDK/Linux Node directory shared with Colima')
    parser.add_argument('--image',required=True,help='Existing immutable sha256 image ID with Python dependencies')
    parser.add_argument('--output',required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch('sha256:[0-9a-f]{64}',args.image): raise ValueError('Exact image ID required')
    root = Path(__file__).resolve().parents[1]
    runtime = Path(args.runtime).resolve()
    if not (runtime/'node_modules/@deepseek-ai/dsh-sdk-client/package.json').is_file():
        raise ValueError('Pinned public runtime missing')
    report = dict(status='started',synthetic_only=True,personal_store_opened=False,paid_calls=0)
    output = Path(args.output)
    with output.open('x') as stream: json.dump(report,stream)
    def save():
        temporary = output.with_suffix(output.suffix+'.partial')
        temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        os.replace(temporary,output)
    def docker(*argv,timeout=30):
        result = subprocess.run(['docker',*argv],capture_output=True,text=True,timeout=timeout)
        if result.returncode: raise RuntimeError('DockerOperationFailed:'+argv[0])
        return result.stdout.strip()
    nonce = secrets.token_hex(5)
    label = 'kingfisher.synthetic='+nonce
    containers, networks = [], []
    started = time.monotonic()
    monitor_stop = threading.Event()
    try:
        _mac_resource_check('kingfisher-qwen3.5:9b-8k')
        # Only public source goes into this read-only mount. No profiles/env/session files.
        gateway_code = runtime/'gateway'
        gateway_code.mkdir(exist_ok=True,mode=0o755)
        shutil.copytree(root/'sidecar/icarus_memory',gateway_code/'icarus_memory',dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copy2(root/'integrations/harness/synthetic_gateway.py',gateway_code/'synthetic_gateway.py')
        for name in ('harness_worker.mjs','harness_run.mjs','harness_service.mjs'):
            shutil.copy2(root/'scripts'/name,runtime/name)
        report['public_code_hashes'] = {name:hashlib.sha256((runtime/name).read_bytes()).hexdigest()
            for name in ('harness_worker.mjs','harness_run.mjs','harness_service.mjs','package-lock.json')}
        internal = docker('network','create','--internal','--label',label,'kf-internal-'+nonce)
        networks.append(internal)
        outbound = docker('network','create','--label',label,'kf-gateway-'+nonce)
        networks.append(outbound)
        key,control = secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        with tempfile.TemporaryDirectory(prefix='kf-isolation-control-') as private:
            env = Path(private)/'gateway.env'
            env.write_text('KF_WORKER_SERVICE_KEY='+key+'\nKF_GATEWAY_CONTROL_KEY='+control+'\nPYTHONPATH=/runtime/gateway\n')
            env.chmod(0o600)
            common = ['--read-only','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges',
                '--pids-limit','64','--tmpfs','/tmp:rw,noexec,nosuid,size=64m,uid=1000,gid=1000,mode=700',
                '--tmpfs','/data:rw,noexec,nosuid,size=64k,mode=000',
                '--mount','type=bind,source='+str(runtime)+',target=/runtime,readonly','--label',label]
            gateway = docker('create','--name','kf-gateway-'+nonce,'--network',outbound,
                '--memory','256m','--cpus','0.5','--env-file',str(env),'-p','127.0.0.1::8890',
                *common,'--entrypoint','python',args.image,'-m','uvicorn','synthetic_gateway:app',
                '--host','0.0.0.0','--port','8890','--no-access-log')
            containers.append(gateway)
            docker('network','connect','--alias','kingfisher-gateway',internal,gateway)
            worker = docker('create','--name','kf-worker-'+nonce,'--network',internal,
                '--network-alias','kingfisher-worker','--dns','127.0.0.1','--memory','512m','--cpus','0.75',
                *common,'--entrypoint','/runtime/bin/node',args.image,
                '/runtime/harness_service.mjs')
            containers.append(worker)
            docker('start',gateway,worker)
            port = int(docker('port',gateway,'8890/tcp').rsplit(':',1)[1])
            origin = 'http://127.0.0.1:'+str(port)
            with httpx.Client(timeout=2,trust_env=False,follow_redirects=False) as client:
                until=time.monotonic()+20
                while True:
                    try:
                        if client.get(origin+'/health').status_code==200: break
                    except httpx.HTTPError: pass
                    if time.monotonic()>=until: raise RuntimeError('SyntheticGatewayUnavailable')
                    time.sleep(.1)
            worker_info = json.loads(docker('inspect',worker))[0]
            network_info = json.loads(docker('network','inspect',internal))[0]
            mounts = worker_info['Mounts']
            report['configuration'] = dict(image_id=worker_info['Image'],uid=worker_info['Config']['User'],
                read_only=worker_info['HostConfig']['ReadonlyRootfs'],
                cap_drop=worker_info['HostConfig']['CapDrop'],security=worker_info['HostConfig']['SecurityOpt'],
                memory=worker_info['HostConfig']['Memory'],nano_cpus=worker_info['HostConfig']['NanoCpus'],
                pids=worker_info['HostConfig']['PidsLimit'],dns=worker_info['HostConfig']['Dns'],
                tmpfs=worker_info['HostConfig']['Tmpfs'],
                no_host_ports=not any(worker_info['NetworkSettings']['Ports'].values()),
                only_internal_network=list(worker_info['NetworkSettings']['Networks'])==[network_info['Name']],
                network_internal=network_info['Internal'],
                public_runtime_only=len(mounts)==1 and mounts[0].get('Type')=='bind' and mounts[0]['Destination']=='/runtime'
                    and mounts[0]['Source']==str(runtime) and mounts[0]['RW'] is False)
            report['negative_probes']=json.loads(docker('exec',worker,'/runtime/bin/node','--input-type=module','-e',NETWORK_CHECK))
            negative=report['negative_probes'];config=report['configuration']
            checks=isolation_checks(config,negative,args.image)
            report['isolation_checks']=checks
            save()
            if not all(checks.values()): raise RuntimeError('IsolationCheckFailed')
            _mac_resource_check('kingfisher-qwen3.5:9b-8k')
            def monitor():
                levels=[]
                while not monitor_stop.wait(1):
                    level=int(subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True))
                    levels.append(level)
                    if level>2:
                        docker('stop','--time','1',worker)
                        break
                report['max_mac_pressure']=max(levels,default=1)
            monitoring=threading.Thread(target=monitor,daemon=True)
            monitoring.start()
            try:
                with httpx.Client(timeout=120,trust_env=False,follow_redirects=False) as client:
                    response=client.post(origin+'/control/pilot',headers={'Authorization':'Bearer '+control})
                    response.raise_for_status()
                    report['live_pilot']=response.json()
            finally:
                monitor_stop.set();monitoring.join(3)
            report['status']='passed' if report['live_pilot']['status']=='passed' and report.get('max_mac_pressure',99)<=2 else 'failed'
    except KeyboardInterrupt: report.update(status='interrupted',error='KeyboardInterrupt')
    except Exception as exc: report.update(status='failed',error=type(exc).__name__,operation=str(exc)[:80])
    finally:
        monitor_stop.set()
        for identifier in reversed(containers):
            try:
                details=json.loads(docker('inspect',identifier))[0]
                if details['Config']['Labels'].get('kingfisher.synthetic')==nonce:
                    docker('rm','-f','-v',identifier)
                    if docker('ps','-aq','--filter','id='+identifier):
                        raise RuntimeError('Owned container remains')
                else: raise RuntimeError('Ownership label changed; do not remove')
            except Exception: report.setdefault('cleanup_pending',[]).append(identifier)
        for identifier in reversed(networks):
            try:
                docker('network','rm',identifier)
                if docker('network','ls','-q','--filter','id='+identifier):
                    raise RuntimeError('Owned network remains')
            except Exception: report.setdefault('cleanup_pending',[]).append(identifier)
        if report.get('cleanup_pending'): report['status']='failed'
        report['seconds']=round(time.monotonic()-started,3)
        save()
    print(json.dumps({k:report[k] for k in ('status','seconds','error','operation','cleanup_pending') if k in report}))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__': raise SystemExit(main())
