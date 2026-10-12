import json,subprocess,runpy
from pathlib import Path
D='/opt/homebrew/bin/docker';app=Path('/Users/sorenkube/Applications/Kingfisher.app');repo=Path('/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923')
probe_path=app/'Contents/Resources/update-storage-probe.py';probe=probe_path.read_text()
policy=runpy.run_path(str(probe_path));assert probe==(repo/'scripts/kingfisher_update_storage.py').read_text()
measurement=json.loads(subprocess.check_output([D,'exec','-i','kingfisher-kingfisher-1','python','-'],input=probe,text=True))
before=policy['evaluate_status'](measurement,True);after=policy['evaluate_status'](measurement,False)
query='''import os,json,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def get(path):
 req=urllib.request.Request('http://127.0.0.1:8890'+path,headers={'X-Icarus-Token':os.environ['ICARUS_SIDECAR_TOKEN']})
 with opener.open(req,timeout=5) as r:return json.load(r)
c=get('/api/v1/mac-calendar')
print(json.dumps({'version':get('/api/v1/fassung')['fassung'],'background_paused':get('/api/v1/mail/intake')['background_paused'],'calendar_status':c['status'],'calendar_enabled':c['enabled'],'calendar_online':c['online'],'calendar_has_error':bool(c['error']),'selected_count':len(c['selected']),'memory_allowed':c['memory_allowed']}))
'''
status=json.loads(subprocess.check_output([D,'exec','-i','kingfisher-kingfisher-1','python','-'],input=query,text=True))
result={'measurement':measurement,'installed_probe_and_policy_match_repository':True,'before_backup_policy_result':before,'after_backup_policy_result':after,'before_backup_capacity_passed':before is None,'after_backup_capacity_passed':after is None,'fresh_status':status,'large_import_or_full_day_qualified':False}
p=Path('/private/tmp/kingfisher-storage-reserve-20261011/postcleanup-status.json');p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
assert before is None and after is None and status['background_paused']
