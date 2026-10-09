#!/usr/bin/env python3
"""Plan/apply removal of exactly three already-host-verified old snapshots."""
import argparse, hashlib, json, os, shutil
from pathlib import Path
TARGETS = ('vor-update-20261007T101543Z','vor-update-20261007T102335Z','vor-update-20261008T104710Z')
KEEP = 'vor-update-20261009T022544Z'
def canonical(obj): return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()
def tree(root, names=TARGETS, require_keep=True):
    root=Path(root); result={}
    if root.is_symlink() or not root.is_dir(): raise ValueError('unsafe root')
    keep=root/KEEP
    if require_keep and (keep.is_symlink() or not keep.is_dir()): raise ValueError('current snapshot missing or unsafe')
    for name in names:
        if name not in TARGETS: raise ValueError('unexpected target')
        top=root/name
        if top.is_symlink() or not top.is_dir(): raise ValueError('missing or symlink target')
        rows=[]
        for base, dirs, files in os.walk(top, followlinks=False):
            base=Path(base)
            for d in list(dirs):
                p=base/d
                if p.is_symlink(): raise ValueError('directory symlink')
                rows.append(['dir',p.relative_to(top).as_posix()])
            for f in files:
                p=base/f
                if p.is_symlink() or not p.is_file(): raise ValueError('non-regular file')
                raw=p.read_bytes(); rows.append(['file',p.relative_to(top).as_posix(),len(raw),hashlib.sha256(raw).hexdigest()])
        result[name]=sorted(rows)
    return result
def scan(root): return {'targets':tree(root)}
def make_plan(host, live):
    h=tree(host,require_keep=False); l=live['targets']
    if set(l)!=set(TARGETS) or h!=l: raise ValueError('host/live trees differ')
    return {'version':1,'targets':list(TARGETS),'trees':l}
def apply(root, raw, expected):
    if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError('plan sha mismatch')
    plan=json.loads(raw)
    if plan.get('version')!=1 or plan.get('targets')!=list(TARGETS): raise ValueError('target set mismatch')
    expected=plan.get('trees')
    if not isinstance(expected,dict) or set(expected)!=set(TARGETS) or tree(root)!=expected: raise ValueError('live tree changed; nothing removed')
    base=Path(root).resolve()
    for name in TARGETS:
        if tree(root,(name,))!={name:expected[name]}: raise ValueError('live tree changed; archive retained')
        p=Path(root)/name
        if p.parent.resolve()!=base or p.name not in TARGETS or p.is_symlink(): raise ValueError('unsafe delete path')
        shutil.rmtree(p)
def main():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('scan'); q.add_argument('--root',required=True)
    q=s.add_parser('plan'); q.add_argument('--host-root',required=True); q.add_argument('--live-scan',required=True); q.add_argument('--out',required=True)
    q=s.add_parser('apply'); q.add_argument('--root',required=True); q.add_argument('--plan',required=True); q.add_argument('--sha256',required=True)
    a=p.parse_args()
    if a.cmd=='scan': print(canonical(scan(a.root)).decode())
    elif a.cmd=='plan':
        raw=Path(a.live_scan).read_bytes(); obj=make_plan(a.host_root,json.loads(raw)); out=canonical(obj); Path(a.out).write_bytes(out); print(hashlib.sha256(out).hexdigest())
    else: apply(a.root,Path(a.plan).read_bytes(),a.sha256); print('removed exactly three verified snapshots; current snapshot retained')
if __name__=='__main__': main()
