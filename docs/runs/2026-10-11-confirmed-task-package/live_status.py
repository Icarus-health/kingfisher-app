import subprocess,json
from pathlib import Path
script='''import os,json,urllib.request,urllib.parse
from datetime import datetime,timedelta,timezone
from icarus_memory.connectors.calendar import Event
from icarus_memory.calendar_window import display_events
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def get(path):
 req=urllib.request.Request('http://127.0.0.1:8890'+path,headers={'X-Icarus-Token':os.environ['ICARUS_SIDECAR_TOKEN']})
 with opener.open(req,timeout=30) as r:return json.load(r)
version=get('/api/v1/fassung')['fassung'];assert version=='1.0.6-preview.a5787c8'
c=get('/api/v1/mac-calendar');intake=get('/api/v1/mail/intake')
start=datetime.now(timezone.utc);end=start+timedelta(days=7)
params=urllib.parse.urlencode({'from':start.isoformat(),'until':end.isoformat(),'tz':'Europe/Berlin'})
view=get('/api/v1/calendar?'+params)
def parse(x):return datetime.fromisoformat(x) if x else None
events=[Event(x['uid'],x['summary'],parse(x.get('start')),parse(x.get('end')),all_day=x.get('all_day',False)) for x in view['items']]
visible,unknown=display_events(events,start,end)
assert visible==events and unknown==0
assert view['errors']==[]
assert c['status']=='granted' and len(c['selected'])==3 and c['memory_allowed'] is False
assert intake['background_paused'] is True
print(json.dumps({'version':version,'calendar_permission':c['status'],'selected_count':len(c['selected']),'calendar_online':c['online'],'calendar_error':bool(c.get('error')),'snapshot_event_count':c.get('event_count'),'snapshot_has_explicit_range':bool(c.get('range_from') and c.get('range_to')),'next_seven_days_count':len(view['items']),'all_displayed_entries_in_requested_window':True,'overview_errors_count':len(view['errors']),'overview_warnings_count':len(view['warnings']),'background_paused':True,'memory_allowed':False,'storage_blocked':intake['storage_blocked'],'native_window_verified':False}))
'''
raw=subprocess.check_output(['/opt/homebrew/bin/docker','exec','-i','kingfisher-kingfisher-1','python','-'],input=script,text=True)
result=json.loads(raw);Path('/private/tmp/kingfisher-task-package-a5787c8/personal-status-after-install.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
