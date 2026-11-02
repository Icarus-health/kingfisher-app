"""Actual local Qwen through the isolated managed module; artificial sources only.

This is a bounded integration probe, not personal-memory or bulk-import approval.
It never pulls an image, changes the installed app or reads its configuration.
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

from probe_intake_precision import _mac_resource_check

MODEL = 'kingfisher-qwen3.5:9b-8k'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', action='append', choices=[
        'person-task-deadline', 'appointment-versus-deadline', 'ambiguous-name'])
    args = parser.parse_args(argv)
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', args.image):
        raise ValueError('Existing immutable image required')
    _mac_resource_check(MODEL)
    runtime = Path(args.runtime).resolve()
    if hashlib.sha256((runtime / 'package-lock.json').read_bytes()).hexdigest() != \
            'b9c37928b69fc90ea9e8d1f76dabe0696f14c000e36ec54d814e278709ded294':
        raise ValueError('Pinned public runtime required')
    root = Path(__file__).resolve().parents[1]
    report = dict(status='running', artificial_only=True, personal_store_opened=False,
        paid_calls=0, injected_model_only=False, model=MODEL, cases=[], cleanup_verified=False)
    output = Path(args.output)
    with output.open('x') as stream:
        json.dump(report, stream)
    def save():
        temporary = output.with_suffix(output.suffix + '.partial')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        os.replace(temporary, output)
    def docker(*arguments, timeout=30):
        result = subprocess.run(['docker', *arguments], capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError('Artificial Docker operation failed: ' + arguments[0])
        return result.stdout.strip()
    def pressure():
        return int(subprocess.check_output(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'],
            text=True)) if os.uname().sysname == 'Darwin' else 1
    containers, networks, levels = [], [], []
    nonce = secrets.token_hex(6)
    label = 'kingfisher.artificial-local=' + nonce
    stop = threading.Event()
    monitor = None
    def own(identifier):
        value = json.loads(docker('inspect', identifier))[0]
        if value['Config']['Labels'].get('kingfisher.artificial-local') != nonce:
            raise RuntimeError('Artificial ownership changed')
    def call(path, body=None, method='GET'):
        code = """import httpx,json,os
with httpx.Client(timeout=15,trust_env=False,follow_redirects=False) as c:
 r=c.request(%r,'http://127.0.0.1:8890'+%r,json=%r,headers={'x-icarus-token':os.environ['ICARUS_SIDECAR_TOKEN']})
 print(json.dumps({'status':r.status_code,'body':r.json()}))
""" % (method, path, body)
        return json.loads(docker('exec', main_id, 'python', '-c', code, timeout=20))
    started = time.monotonic()
    try:
        for name in ('harness_service.mjs', 'harness_worker.mjs', 'harness_run.mjs', 'harness_gateway.py'):
            shutil.copy2(root / 'scripts' / name, runtime / name)
        shutil.copytree(root / 'sidecar/icarus_memory', runtime / 'gateway/icarus_memory',
            dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copy2(root / 'integrations/harness/local_source_model_controller.py', runtime / 'gateway')
        report['code_sha256'] = {name: hashlib.sha256((runtime / name).read_bytes()).hexdigest()
            for name in ('harness_service.mjs', 'harness_worker.mjs', 'harness_run.mjs', 'harness_gateway.py')}
        control = docker('network', 'create', '--internal', '--label', label,
                         'kf-artificial-control-' + nonce); networks.append(control)
        worker = docker('network', 'create', '--internal', '--label', label,
                        'kf-artificial-worker-' + nonce); networks.append(worker)
        outbound = docker('network', 'create', '--label', label,
                          'kf-artificial-model-' + nonce); networks.append(outbound)
        with tempfile.TemporaryDirectory(prefix='kf-artificial-module-env-') as temporary:
            key, token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            environment = Path(temporary) / 'artificial.env'
            environment.write_text('KF_GATEWAY_CONTROL_KEY=' + key + '\nICARUS_SIDECAR_TOKEN=' + token
                + '\nPYTHONPATH=/runtime/gateway\nICARUS_OLLAMA_8K_PROFILE=' + MODEL + '\n')
            environment.chmod(0o600)
            proxy = Path(temporary) / 'proxy.env'
            proxy.write_text('KF_GATEWAY_CONTROL_KEY=' + key + '\n'); proxy.chmod(0o600)
            common = ['--user', '1000:1000', '--read-only', '--cap-drop', 'ALL', '--security-opt',
                'no-new-privileges', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m,uid=1000,gid=1000,mode=700',
                '--tmpfs', '/data:rw,noexec,nosuid,size=64k,mode=000', '--label', label,
                '--mount', 'type=bind,source=' + str(runtime) + ',target=/runtime,readonly']
            main_id = docker('create', '--name', 'kf-artificial-main-' + nonce,
                '--network', control, '--network-alias', 'kingfisher-controller',
                '--add-host', 'host.docker.internal:host-gateway', '--memory', '768m', '--cpus', '.5',
                '--pids-limit', '64', '--env-file', str(environment), *common, '--entrypoint', 'python',
                args.image, '-m', 'uvicorn', 'local_source_model_controller:app', '--host', '0.0.0.0',
                '--port', '8890', '--lifespan', 'off', '--no-access-log', '--log-level', 'warning')
            containers.append(main_id)
            docker('network', 'connect', outbound, main_id)
            gateway_id = docker('create', '--name', 'kf-artificial-gateway-' + nonce,
                '--network', control, '--network-alias', 'kingfisher-gateway-control',
                '--memory', '96m', '--cpus', '.25', '--pids-limit', '32', '--dns', '127.0.0.1',
                '--env-file', str(proxy), *common, '--entrypoint', 'python', args.image,
                '/runtime/harness_gateway.py', '--controlled-local-readonly-v1')
            containers.append(gateway_id)
            docker('network', 'connect', '--alias', 'kingfisher-gateway', worker, gateway_id)
            worker_id = docker('create', '--name', 'kf-artificial-worker-' + nonce, '--network', worker,
                '--network-alias', 'kingfisher-worker', '--memory', '512m', '--cpus', '.75',
                '--pids-limit', '64', '--dns', '127.0.0.1', *common, '--entrypoint', '/runtime/bin/node',
                args.image, '/runtime/harness_service.mjs', '--controlled-local-readonly-v1')
            containers.append(worker_id)
            levels.append(pressure())
            if levels[-1] > 2:
                raise RuntimeError('Mac memory reserve unavailable')
            docker('start', *containers)
            def watch():
                while not stop.wait(2):
                    try:
                        levels.append(pressure())
                        if levels[-1] > 2:
                            for identifier in (worker_id, main_id):
                                own(identifier); docker('stop', '--time', '1', identifier)
                            return
                    except Exception:
                        levels.append(4); return
            monitor = threading.Thread(target=watch, daemon=True); monitor.start()
            deadline = time.monotonic() + 30
            while True:
                try:
                    ready = call('/fixture/readiness')
                    if ready['status'] == 200: break
                except Exception:
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Artificial controller unavailable')
                time.sleep(.2)
            initialized = call('/api/v1/modules/local-source/runtime/initialize', {}, 'POST')
            report['initialized'] = initialized
            if initialized['status'] != 200 or initialized['body'].get('paired') is not True:
                raise RuntimeError('Managed runtime pairing failed')
            selected = [case for case in ready['body']['cases'] if not args.case or case['id'] in args.case]
            report['selected_cases'] = [case['id'] for case in selected]
            for case in selected:
                _mac_resource_check(MODEL)
                tick = time.monotonic()
                prepared = call('/api/v1/modules/local-source/prepare',
                    dict(source_id=case['source_id'], question=case['question']), 'POST')
                row = dict(case=case['id'], original=case['original'], question=case['question'], prepare=prepared)
                report['cases'].append(row); save()
                if prepared['status'] != 200:
                    break
                review = prepared['body']
                admitted = call('/api/v1/modules/local-source/start', dict(source_id=case['source_id'],
                    question=case['question'], source_fingerprint=review['source']['fingerprint'],
                    review_binding=review['review_binding'], consent=True, idempotency_key=secrets.token_hex(16)), 'POST')
                row['start_status'] = admitted['status']
                if admitted['status'] != 200:
                    row['result'] = admitted; break
                run_id = admitted['body']['id']
                until = time.monotonic() + 125
                while True:
                    state = call('/api/v1/modules/local-source/runs/' + run_id)
                    if state['status'] != 200 or (state['body'].get('status') != 'running'
                            and state['body'].get('execution_pending') is False):
                        row['result'] = state; break
                    if time.monotonic() > until:
                        call('/api/v1/modules/local-source/runs/' + run_id + '/cancel', {}, 'POST')
                        raise RuntimeError('Artificial source deadline exceeded')
                    time.sleep(.5)
                row['seconds'] = round(time.monotonic() - tick, 3)
                save()
                if row['result']['status'] != 200 or row['result']['body'].get('status') != 'completed':
                    break
            report['receipt'] = call('/fixture/receipt')
            report['shutdown'] = call('/api/v1/modules/local-source/runtime/shutdown', {}, 'POST')
            transport_complete = len(report['cases']) == len(selected) and all(
                row.get('result', {}).get('status') == 200 and
                row['result']['body'].get('status') == 'completed' for row in report['cases'])
            receipt = report['receipt']
            report['status'] = ('completed_for_review' if transport_complete and
                receipt['status'] == 200 and receipt['body']['originals_unchanged'] is True else 'failed')
    except Exception as error:
        report.update(status='failed', error=type(error).__name__)
    finally:
        stop.set()
        if monitor: monitor.join(3)
        for identifier in reversed(containers):
            try: own(identifier); docker('rm', '--force', identifier)
            except Exception: report.setdefault('cleanup_pending', []).append('container')
        for identifier in reversed(networks):
            try: docker('network', 'rm', identifier)
            except Exception: report.setdefault('cleanup_pending', []).append('network')
        try:
            remaining = docker('ps', '-a', '-q', '--filter', 'label=' + label)
            remaining_networks = docker('network', 'ls', '-q', '--filter', 'label=' + label)
            report['cleanup_verified'] = not remaining and not remaining_networks and not report.get('cleanup_pending')
        except Exception:
            report['cleanup_verified'] = False
        report['sampled_max_mac_pressure'] = max(levels) if levels else None
        report['seconds'] = round(time.monotonic() - started, 3)
        save()
    return 0 if report['status'] == 'completed_for_review' and report['cleanup_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
