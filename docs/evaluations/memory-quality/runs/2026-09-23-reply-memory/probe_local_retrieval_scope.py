"""One synthetic current-mail flow against actual local classification/selection/drafting."""
import json, os, tempfile, time
from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from test_mail_conversation_flow import mail_app
from icarus_memory.providers import OpenAICompatible
from icarus_memory.working_memory_analysis import interpret
from icarus_memory.working_memory_store import WorkingMemoryStore

HERE=Path(__file__).parent
EXPECTED=json.loads((HERE/'expected.json').read_text())
OUT=HERE/'local-results-retrieval-scope.json'
assert not OUT.exists(), 'Preserve first-run evidence'
result={'model':EXPECTED['model'],'started_at':datetime.now(timezone.utc).isoformat(),'calls':[]}
def save():OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
with tempfile.TemporaryDirectory(prefix='kingfisher-reply-qualification-') as folder:
 os.environ['ICARUS_DATA_DIR']=folder
 os.environ.pop('ICARUS_SIDECAR_TOKEN',None)
 app, other, mailbox=mail_app()
 prior=replace(mailbox.item,uid='1',sender='Mara Kranz <mara@example.test>',subject='Projekt Sturmvogel: Entwurf',body=EXPECTED['source'],preview=EXPECTED['source'],message_id='<sturm-prior@example.test>',reply_to='mara@example.test',date=datetime(2026,9,22,10,tzinfo=timezone.utc))
 current=replace(prior,uid='2',body=EXPECTED['incoming'],preview=EXPECTED['incoming'],message_id='<sturm-current@example.test>')
 mailbox.message=lambda uid: {'1':prior,'2':current}[uid]
 mailbox.inbox=lambda **kwargs:[current]
 real=OpenAICompatible(EXPECTED['model'],base_url='http://127.0.0.1:11434/v1')
 original=real.complete_json
 def capture(messages,**kwargs):
  start=time.perf_counter();reply=original(messages,**kwargs)
  data=json.loads(messages[-1]['content'])
  kind='classification' if 'blocks' in data else 'selection' if 'sources' in data else 'draft'
  result['calls'].append({'kind':kind,'seconds':round(time.perf_counter()-start,3),'text':reply.text});save()
  return reply
 real.complete_json=capture
 app.state.agent._provider=real
 with TestClient(app) as client:
  remembered=client.post('/api/v1/messages/work:1/remember');remembered.raise_for_status()
  eid=remembered.json()['episode']['id'];ep=app.state.episodes.get(eid)
  items=interpret(real,ep)
  assert WorkingMemoryStore(app.state.episodes).commit(app.state.episodes.support_snapshot(eid),items,model=real.model)
  response=client.post('/api/v1/messages/work:2/reply-suggestion',json={'instruction':EXPECTED['instruction']})
  result['suggestion_status']=response.status_code
  response.raise_for_status();suggestion=response.json()
  result['draft']=suggestion['body'];result['source_status']=suggestion['source_status']
  result['expected_source_attached']=suggestion['sources']==[{'episode_id':eid,'title':ep.title}]
  result['token_present']=bool(suggestion['context_token'])
  if result['token_present']:
   prepared=client.post('/api/v1/messages/work:2/reply',json={'body':suggestion['body']+' Viele Grüße.', 'context_token':suggestion['context_token']})
   prepared.raise_for_status();payload=prepared.json();cid=payload['conversation']['id'];action=payload['action_requests'][0]
   client.post(f'/api/v1/episodes/{eid}/ignore').raise_for_status()
   reopened=client.get(f'/api/v1/conversations/{cid}').json()
   result['withdrawal_hides_draft']=suggestion['body'] not in json.dumps(reopened,ensure_ascii=False)
   rejected=client.post(f'/approvals/{action["id"]}',json={'granted':True,'confirmation':'mara@example.test'})
   result['withdrawal_blocks_send']=rejected.status_code==409
  result['no_delivery']=not mailbox.sent and not other.sent
  result['claims_revision']=app.state.claims.revision
  result['finished_at']=datetime.now(timezone.utc).isoformat();save()
print(OUT)
