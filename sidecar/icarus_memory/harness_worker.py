"""Bounded launcher for the artificial-only SDK compatibility runner.

It deliberately cannot enable personal-data execution. A verified OS boundary
and distribution package are still required before production registration.
"""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import tempfile
import time

from .harness_broker import BridgeError


def run_synthetic_worker(*, node, runtime, origin, token, request, scratch, timeout=110):
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'harness_worker.mjs'
    if not script.is_file():
        raise BridgeError('Der getrennte Prüflauf ist nicht installiert.')
    # Only this directory belongs to us; parent cleanup also runs after SIGKILL.
    with tempfile.TemporaryDirectory(prefix='kf-launcher-',dir=scratch) as owned:
        return _run(node,runtime,origin,token,request,owned,timeout,script)


def _run(node,runtime,origin,token,request,scratch,timeout,script):
    config = dict(syntheticOnly=True,runtime=str(Path(runtime).resolve()),origin=origin,
        token=token,request=request,scratch=str(Path(scratch).resolve()),model='kingfisher-qwen3.5:9b-8k')
    env = {'PATH':str(Path(node).resolve().parent)+':/usr/bin:/bin','TMPDIR':config['scratch'],
           'DSH_TELEMETRY_MODE':'DISABLED'}
    process = subprocess.Popen([str(node),str(script)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,env=env,start_new_session=True)
    output, errors = bytearray(), bytearray()
    deadline = time.monotonic()+min(timeout,110)
    try:
        process.stdin.write(json.dumps(config,ensure_ascii=False).encode())
        process.stdin.close()
        with selectors.DefaultSelector() as selector:
            for pipe in (process.stdout,process.stderr):
                os.set_blocking(pipe.fileno(),False)
                selector.register(pipe,selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise BridgeError('Der getrennte Prüflauf wurde wegen Zeitüberschreitung beendet.')
                for key,_ in selector.select(min(.1,max(0,deadline-time.monotonic()))):
                    chunk = os.read(key.fileobj.fileno(),8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    target = output if key.fileobj is process.stdout else errors
                    target.extend(chunk)
                    if len(target)>65536:
                        raise BridgeError('Der getrennte Prüflauf hat seine Ausgabegrenze erreicht.')
        process.wait(timeout=max(.01,deadline-time.monotonic()))
        try: result = json.loads(output)
        except (ValueError,UnicodeError): raise BridgeError('Ungültiges Ergebnis des getrennten Prüflaufs.') from None
        if process.returncode or result.get('status')!='complete' or result.get('syntheticOnly') is not True:
            raise BridgeError('Der getrennte Prüflauf konnte nicht abgeschlossen werden.')
        return result
    finally:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait()
        for pipe in (process.stdout,process.stderr): pipe.close()
