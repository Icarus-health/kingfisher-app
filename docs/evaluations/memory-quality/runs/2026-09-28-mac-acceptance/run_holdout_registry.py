from pathlib import Path
import os,json,time,hashlib,argparse,tempfile,urllib.request
from datetime import datetime
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend,SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeStore
from icarus_memory.proposals import ProposalStore
from icarus_memory.policy import Policy
from icarus_memory.providers import OpenAICompatible
from icarus_memory.server import create_app,_wire_scheduler,Summarizer
from icarus_memory.connectors.mail import Message
from icarus_memory.connectors.collections import MailCollection,NamedMail
from icarus_memory.working_memory_store import WorkingMemoryStore
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--semantic',action='store_true');a=p.parse_args()
raw=(R/'holdout.json').read_bytes();cases=json.loads(raw)['cases']
out=R/('holdout-registry-'+a.model.replace(':','-')+('-semantic' if a.semantic else '')+'.json')
assert not out.exists()
os.environ['ICARUS_MEMORY_SEMANTIC']='1' if a.semantic else ''
provider=OpenAICompatible(a.model,base_url='http://127.0.0.1:11434/v1')
tags=json.load(urllib.request.urlopen('http://127.0.0.1:11434/api/tags'))
weights=next(x['digest'] for x in tags['models'] if x['name']==a.model)
result={'commit':'49a77e964f0a6b83f76ea0837b405246e934a63d','cases_sha256':hashlib.sha256(raw).hexdigest(),'model':a.model,'weights':weights,'semantic':a.semantic,'synthetic_only':True,'cases':[]}
def save():out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
current=None
for method in ['complete','complete_json']:
 original=getattr(provider,method)
 def wrap(*args,_original=original,_method=method,**kwargs):
  start=time.perf_counter();response=_original(*args,**kwargs)
  current['model_calls'].append({'method':_method,'seconds':round(time.perf_counter()-start,3),'input':args[0],'output':response.text})
  save();return response
 setattr(provider,method,wrap)
class Box:
 def __init__(self,sources):
  self.items={str(i+1):Message(uid=str(i+1),subject=s.get('subject','Test'),sender=s['sender'],date=None,preview=s['text'],unread=False,body=s['text'],message_id=f'<holdout-{i}@example.invalid>',reply_to='') for i,s in enumerate(sources) if 'sender' in s}
 def message(self,uid):return self.items[uid]
 def inbox(self,**kwargs):return list(self.items.values())
 def send(self,*args,**kwargs):raise AssertionError('Sending forbidden in acceptance')
for case in cases:
 current={'id':case['id'],'model_calls':[],'checks':{},'responses':[]};result['cases'].append(current);save()
 with tempfile.TemporaryDirectory() as folder:
  root=Path(folder);os.environ['ICARUS_DATA_DIR']=str(root/'runtime');os.environ['ICARUS_SIDECAR_TOKEN']='synthetic-holdout'
  stores=[EpisodeStore(root/'episodes.sqlite3'),ClaimStore(root/'claims.sqlite3'),ProposalStore(root/'proposals.sqlite3'),AuditLog(root/'audit.sqlite3')]
  episodes,claims,proposals,audit=stores
  agent=Agent(store=SelfModelStore(MemoryBackend(),subject_id='synthetic'),policy=Policy(),audit=audit,tools={},provider=provider,knowledge=claims,episodes=episodes,max_rounds=4)
  app=create_app(agent._store,agent=agent,audit=audit,proposals=proposals,episodes=episodes,knowledge=claims)
  app.state.mail=MailCollection([NamedMail('work','Synthetic',Box(case['sources']),True,'owner@example.invalid')])
  from icarus_memory.tools import build_registry
  agent._tools=build_registry(app.state.store, mail=app.state.mail, task_store=app.state.tasks, workspace=app.state.workspace, episodes=episodes)
  app.state.summarizer=Summarizer(episodes,provider=provider);_wire_scheduler(app)
  client=TestClient(app,headers={'X-Icarus-Token':'synthetic-holdout'})
  ids=[]
  def request(method,url,payload=None):
   response=client.request(method,url,**({'json':payload} if payload is not None else {}))
   assert response.is_success,(url,response.status_code,response.text)
   return response.json()
  def ask():
   cid=request('POST','/api/v1/conversations',{})['conversation']['id']
   message=request('POST',f'/api/v1/conversations/{cid}/messages',{'message':case['question'],'answer_mode':'auto'})['messages'][-1]
   current['responses'].append(message);save();return cid,message
  try:
   for i,s in enumerate(case['sources']):
    if 'sender' in s:eid=request('POST',f'/api/v1/messages/work:{i+1}/remember')['episode']['id']
    else:eid=request('POST','/api/v1/sources/documents',{'filename':f'holdout-{i}.txt','body':s['text']})['id']
    ids.append(eid)
    job=app.state.scheduler._run_working_memory(True,source_ids=[eid])
    current.setdefault('ingestion',[]).append({'id':eid,'detail':job.detail,'stored_exact':episodes.get(eid).body==s['text']})
   cid,msg=ask();ctx=msg.get('metadata',{}).get('context',{});text=msg['content'];answer=ctx.get('working_answer',{})
   selected={r['episode_id'] for r in answer.get('refs',[])}
   checks=current['checks'];checks['source_selection']=selected=={ids[i] for i in case['expected']}
   checks['status']=ctx.get('answer_contract',{}).get('status') in case['status']
   checks['content']=all(s.casefold() in text.casefold() for s in case.get('contains',[])) and all(s.casefold() not in text.casefold() for s in case.get('excludes',[]))
   checks['originals_preserved']=all(x['stored_exact'] for x in current['ingestion'])
   if case.get('requires_unknown_source_time'):checks['time_uncertainty']='Quellenzeit: unbekannt' in text or 'Zeitbezug ist unklar' in text
   if 'correction' in case:
    state=request('GET',f'/api/v1/memory/working/{ids[0]}/correction')
    corrected=request('POST',f'/api/v1/memory/working/{ids[0]}/correction',{'fingerprint':state['fingerprint'],'body':case['correction']})['episode_id']
    old=request('GET',f'/api/v1/conversations/{cid}')['messages'][-1]
    checks['old_answer_invalidated']=case['sources'][0]['text'] not in old['content']
    cc,new=ask();checks['corrected_content']=all(t in new['content'] for t in case['corrected_contains'])
    newrefs=new.get('metadata',{}).get('context',{}).get('working_answer',{}).get('refs',[])
    checks['corrected_source_selected']={r['episode_id'] for r in newrefs}=={corrected}
    request('POST',f'/api/v1/episodes/{corrected}/ignore')
    withdrawn=request('GET',f'/api/v1/conversations/{cc}')['messages'][-1];checks['withdrawn_history_hidden']=case['correction'] not in withdrawn['content']
    reopened=EpisodeStore(root/'episodes.sqlite3')
    try:checks['withdrawn_after_reopen']=not WorkingMemoryStore(reopened).search('Schließanlage Kiefernwald')['refs']
    finally:reopened.close()
    current['withdrawal_projection']=withdrawn
   current['passed']=all(checks.values())
  except Exception as exc:current['error']=type(exc).__name__+': '+str(exc);current['passed']=False
  finally:
   client.close();app.state.scheduler.stop()
   for name in ['audit','tasks','workspace','episodes','proposals','conversations','claims','regeln']:
    close=getattr(getattr(app.state,name,None),'close',None)
    if callable(close):close()
   save()
 print(a.model,case['id'],current['passed'],current.get('checks'),flush=True)
result['weights_unchanged']=next(x['digest'] for x in json.load(urllib.request.urlopen('http://127.0.0.1:11434/api/tags'))['models'] if x['name']==a.model)==weights
save()
