from pathlib import Path
import subprocess,json,plistlib,hashlib,shutil
root=Path(__file__).parent;app=root/'build/mac-app/Kingfisher.app'
def hashes(base):return {str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(base.rglob('*')) if p.is_file()}
subprocess.run(['/usr/bin/codesign','--verify','--strict','--deep',str(app)],check=True)
assert plistlib.loads((app/'Contents/Info.plist').read_bytes())['CFBundleShortVersionString']=='1.0.6-preview.f858681'
assert subprocess.check_output(['/usr/bin/lipo','-archs',str(app/'Contents/MacOS/Kingfisher')],text=True).strip()=='arm64'
manifest=hashes(app);(root/'mac-app-manifest.json').write_text(json.dumps({'files':manifest},indent=2)+'\n')
raw=subprocess.check_output(['/usr/bin/hdiutil','attach','-readonly','-nobrowse','-plist',str(root/'dist/Kingfisher.dmg')])
state=plistlib.loads(raw);mounts=[x for x in state['system-entities'] if 'mount-point' in x];assert len(mounts)==1
mount=mounts[0]
try:
 mounted=Path(mount['mount-point'])/'Kingfisher.app'
 assert hashes(mounted)==manifest
 subprocess.run(['/usr/bin/codesign','--verify','--strict','--deep',str(mounted)],check=True)
finally:subprocess.run(['/usr/bin/hdiutil','detach',mount['dev-entry']],check=True,capture_output=True)
proof={'version':'1.0.6-preview.f858681','architecture':'arm64','signature':'strict deep ad hoc','notarized':False,'native_files':len(manifest),'read_only_mounted_bundle_matches':True,'detached':True,'dmg_sha256':hashlib.sha256((root/'dist/Kingfisher.dmg').read_bytes()).hexdigest()}
(root/'dmg-verification.json').write_text(json.dumps(proof,indent=2)+'\n')
canonical=Path('/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-11-mail-header-f858681');canonical.mkdir(exist_ok=False)
shutil.copyfile(root/'dist/Kingfisher.dmg',canonical/'Kingfisher.dmg')
assert hashlib.sha256((canonical/'Kingfisher.dmg').read_bytes()).hexdigest()==proof['dmg_sha256']
print(json.dumps(proof))
