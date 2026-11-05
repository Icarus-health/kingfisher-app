"""Frozen synthetic pilot only; reuse the real tested intake/recall diagnostic."""
from pathlib import Path
import hashlib
import json
import sys
import time

REPO=Path('/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/kingfisher-product-readiness-20261105')
sys.path[:0]=[str(REPO/'scripts'),str(REPO/'sidecar'),str(REPO)]
import probe_mail_intake_quality as probe
from probe_intake_precision import _mac_resource_check
from icarus_memory.local_model_guard import verify_local_model

PILOT=REPO/'docs/fixtures/memory-acceptance-20261104/pilot-v2'
CATALOG=PILOT/'catalog.json'
EXPECTED='036fbf45fe33b7329f49c60e6183d13126daa8731bc922545cd7333d2a63f388'
MODEL='kingfisher-qwen3.5:9b-8k'
original_loader=probe.load_catalog

def load_catalog(path=CATALOG):
    catalog=original_loader(path)
    if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=EXPECTED:
        raise ValueError('Frozen synthetic pilot changed; no run permitted')
    if len(catalog['mails'])!=10 or len(catalog['questions'])!=5 or catalog['limits']!={'model_calls':60,'seconds':600}:
        raise ValueError('Pilot boundaries changed')
    return catalog

class GuardedNative(probe.NativeProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.started=time.monotonic()
        self.identity=verify_local_model(self.base,expected_num_ctx=8192)
        if self.identity.digest!='8a5919e3ddda74b7729b65ca0bad9896d36615d872756ca98b17ec8a80374b17':
            raise probe.ProbeLimit('Installed Qwen weights changed before pilot')
    def guard(self):
        _mac_resource_check(self.model)
        reason=probe.stop_reason(time.monotonic()-self.started,probe.resources(),600)
        if reason:self._refuse(probe.ProbeLimit(reason))
    def _call(self,*args,**kwargs):
        self.guard()
        try:return super()._call(*args,**kwargs)
        finally:self.guard()

# Re-applied when multiprocessing imports this module in its own worker.
probe.MODEL=MODEL
probe.CATALOG=CATALOG
probe.load_catalog=load_catalog
probe.NativeProbe=GuardedNative

if __name__=='__main__':
    freeze=json.loads((PILOT/'freeze.json').read_text())
    assert all(hashlib.sha256((PILOT/f).read_bytes()).hexdigest()==h for f,h in freeze['files'].items())
    load_catalog()
    if sys.argv[1:]==['--check']:
        print('Frozen independent pilot verified:10 artificial mails,5 questions;60 calls/600seconds;no provider called.')
    else:
        if len(sys.argv)!=2:raise SystemExit('Expected a new output directory or --check')
        raise SystemExit(probe.run(Path(sys.argv[1])))
