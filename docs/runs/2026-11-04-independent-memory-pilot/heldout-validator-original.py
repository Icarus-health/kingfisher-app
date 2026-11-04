import argparse,copy,hashlib,json,re
from collections import Counter
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
BASE=Path('/private/tmp/kf-memory-acceptance-20261104');V1=BASE/'heldout';P=BASE/'heldout-v2'
def read(root,name):return json.loads((root/name).read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
old={f:read(V1,f) for f in ['catalog.json','sources.json','reference.json','state-phases.json','freeze.json']}
EXPECTED_PREDECESSOR='99f1a7e11818a737095ff125a91fea156fcf85a51a5902c5275490739e35fb96'
def validate(c,s,r,sp):
 assert digest(V1/'freeze.json')==EXPECTED_PREDECESSOR
 for name,h in old['freeze.json']['files'].items():assert digest(V1/name)==h,('v1 changed',name)
 ids=[m['id'] for m in s['mails']+s['native']];assert len(ids)==len(set(ids))==110
 assert len(c['mails'])==100 and len(c['questions'])==40
 assert c['questions']==old['catalog.json']['questions']
 assert r['questions']==old['reference.json']['questions']
 assert s['mails']==old['sources.json']['mails']
 assert {m['id']: {k:v for k,v in m.items() if k!='expect'} for m in c['mails']}=={m['id']:m for m in s['mails']}
 assert all('expect' not in m for m in s['mails'])
 assert all(not {'tasks','meaning','text_reference','event'} & set(n) for n in s['native'])
 expected_sources=copy.deepcopy(old['sources.json']);expected_sources['suite']=s['suite']
 for n in expected_sources['native']:
  if n['id']=='N03':n['source_at']='2026-11-03T12:00:00+01:00'
 assert s==expected_sources,'unexpected source metadata changes'
 old_mails={m['id']:m for m in old['catalog.json']['mails']}
 for m in c['mails']:
  assert m['body'].encode()==old_mails[m['id']]['body'].encode()
  if m['id']=='E02-03':assert m['expect']==dict(tasks='required',anchor='Werkstatt-Absprachen',person='deniz.alt@werkstatt-rohr.example',due=None)
  else:assert m['expect']==old_mails[m['id']]['expect']
  assert datetime.fromisoformat(m['at'])<=datetime.fromisoformat(c['clock'])
 assert len({m['body'] for m in c['mails']})==100
 source={m['id']:m for m in c['mails']}
 assert len(r['source_annotations'])==100 and len(r['native_annotations'])==10
 rows=[]
 for a in r['source_annotations']:
  m=source[a['source_id']];assert a['original_evidence_quote'].encode()==m['body'].encode()
  assert m['folder']==('Sent' if a['direction']=='sent' else 'INBOX')
  for t in a['tasks']:rows.append((a['source_id'],'mail',t))
 for a in r['native_annotations']:
  for t in a.get('tasks',[]):rows.append((a['id'],'native',t))
 tasks={t['id']:t for _,_,t in rows};assert len(rows)==len(tasks)==48
 assert set(tasks)=={f'T{i:02d}' for i in range(1,49)}
 oldtasks={t['id']:t for a in old['reference.json']['source_annotations']+old['reference.json']['native_annotations'] for t in a.get('tasks',[])}
 for tid,t in oldtasks.items():assert tasks[tid]==t,('existing task changed',tid)
 expected_new={'T45':('E02-03',s['owner']['address']),'T46':('E06-01','evelyn@studio-sedge.example'),'T47':('E06-02','lucie@atelier-roseau.example'),'T48':('E06-03','ines@estudio-junco.example')}
 for tid,(src,owner) in expected_new.items():
  assert next(x[0] for x in rows if x[2]['id']==tid)==src
  assert tasks[tid]['owner']==owner and tasks[tid]['due'] is None
  assert tasks[tid]['evidence_quote'] in source[src]['body']
 assert tasks['T46']['additional_evidence']==['E06-07']
 e607=next(a for a in r['source_annotations'] if a['source_id']=='E06-07')
 assert e607['tasks']==[] and e607['task_evidence']==[dict(task_id='T46',relation='supports_existing_task_not_new_task',quote='you will handle typesetting.')]
 d=r['coverage_denominator'];mailids=sorted(t['id'] for _,scope,t in rows if scope=='mail');nativeids=sorted(t['id'] for _,scope,t in rows if scope=='native')
 assert d['mail_task_ids']==mailids and len(mailids)==39
 assert d['native_task_ids']==nativeids and len(nativeids)==9
 rec=d['current_action_recognition'];recids=sorted(set(tasks)-{'T23','T28'})
 assert rec['all_task_ids']==recids and rec['all_count']==46
 assert rec['mail_task_ids']==sorted(set(mailids)-{'T23','T28'}) and rec['mail_count']==37
 assert rec['native_task_ids']==nativeids and rec['native_count']==9
 assert rec['minimum_correct_mail']==36 and rec['minimum_correct_all']==44 and rec['minimum_fraction']==.95
 assert rec['included_uncertainty_cases']==['T25','T31','T43']
 assert {x['task_id'] for x in d['mandatory_historical_cancelled_gates']}=={'T23','T28'}
 dims={x['task_id']:x for x in r['task_dimensions']};assert len(dims)==len(r['task_dimensions'])==48
 for tid,t in tasks.items():
  a=dims[tid];assert a['action']['expected']==t['action']
  assert a['action']['current_recognition_denominator']==(tid in recids)
  assert set(a['evidence'])<=set(ids)
  assert next(src for src,_,tt in rows if tt['id']==tid) in a['evidence']
  if tid=='T31':assert a['owner']['state']=='source_report_unconfirmed' and a['owner']['reported_value']==s['owner']['address'] and a['owner']['confirmed_value'] is None
  elif tid=='T43':assert a['owner']['state']=='unknown' and a['owner']['value'] is None and a['owner']['alternatives']==['Jona Seidel','Eda Korn']
  else:assert a['owner']['state']=='known_from_source' and a['owner']['value']==t['owner']
  if tid=='T25':assert a['deadline']['state']=='ambiguous' and a['deadline']['value'] is None and a['deadline']['alternatives']==['2026-11-06','2026-11-13']
  else:
   due=t.get('due');assert a['deadline']['value']==due
   assert a['deadline']['state']==('known' if due else 'unknown')
   assert a['deadline']['precision']==(('date' if len(due)==10 else 'datetime') if due else None)
  status={'T23':'historical_unresolved','T28':'cancelled','T27':'open_incomplete','T29':'open_partial','T31':'unconfirmed_proposal','T43':'open_owner_unknown'}.get(tid,'open')
  assert a['status']['expected']==status
 assert 'E06-07' in dims['T46']['evidence']
 assert dims['T25']['owner']['value']==s['owner']['address']
 assert dims['T43']['deadline']==dict(state='known',value='2026-11-29',precision='date')
 deadline=d['deadline_dimension']
 for state,key in [('known','known_due_task_ids'),('unknown','unknown_due_task_ids'),('ambiguous','ambiguous_due_task_ids')]:
  assert deadline[key]==sorted(tid for tid in recids if dims[tid]['deadline']['state']==state)
 assert [len(deadline[k]) for k in ['known_due_task_ids','unknown_due_task_ids','ambiguous_due_task_ids']]==[35,10,1]
 for precision,key in [('date','known_date_only_task_ids'),('datetime','known_datetime_task_ids')]:assert deadline[key]==sorted(tid for tid in recids if dims[tid]['deadline']['state']=='known' and dims[tid]['deadline']['precision']==precision)
 for state,actual in d['owner_dimension']['groups'].items():assert actual==sorted(tid for tid in recids if dims[tid]['owner']['state']==state)
 assert set(r['dimension_scoring_protocol'])=={'action','owner','deadline','status','composite','special_gates'}
 assertions=r['identity_assertions'];assert assertions[0]['evidence']==['E02-01','E02-02','E02-07'];assert assertions[1]['evidence']==['E02-03'];assert assertions[2]['evidence']==['E02-03','E02-05']
 for assertion in assertions:
  combined='\n'.join(source[x]['body']+' '+source[x]['sender']['address'] for x in assertion['evidence'])
  assert all(address in combined for address in assertion['addresses'])
 baseline=r['native_baseline'];assert baseline['id']=='native_baseline_before_N06'
 assert baseline['source_ids']==[f'N{i:02d}' for i in range(1,11) if i!=6]
 assert baseline['held_back_source_ids']==['N06'] and sp['native_baseline']==baseline
 assert len(r['native_questions'])==7
 for q in r['native_questions']:
  assert q['phase']==baseline['id'] and set(q['evidence'])<=set(baseline['source_ids'])
 nq=next(q for q in r['native_questions'] if q['id']=='NQ02')
 assert nq['evidence']==['N02','N05'] and nq['expected'].startswith('Before N06 ingestion:')
 assert 'after N06 visit cancelled' not in nq['expected']
 assert len(sp['phases'])==9 and sum(len(x['questions']) for x in sp['phases'])==11
 phase=next(x for x in sp['phases'] if x['id']=='S09')
 assert phase['baseline']==baseline['id'] and phase['required_source_ids']==['N01','N02','N05']
 assert phase['actions']==[dict(operation='ingest_update_same_calendar_uid',source_id='N06',replaces='N05')]
 assert phase['questions'][0]['id']=='SQ11' and phase['questions'][0]['evidence']==['N06','N02'] and phase['questions'][0]['phase']=='after_N06_ingested'
 for q in c['questions']:
  assert set(q['required']+q['allowed'])<=set(ids)
 for phase in sp['phases']:
  for a in phase['actions']:
   if 'source_id' in a:assert a['source_id'] in ids
   if 'source_ids' in a:assert set(a['source_ids'])<=set(ids)
   if 'task_id' in a:assert a['task_id'] in tasks
  for q in phase['questions']:
   for ev in q['evidence']:
    assert (ev['source_id'] in ids) if isinstance(ev,dict) else (ev in ids or ev.startswith('user_confirmation:'))
 bynative={n['id']:n for n in r['native_annotations']}
 for n in s['native']:
  p=P/n['file'];assert p.read_bytes()==(V1/n['file']).read_bytes(),('native changed',n['id'])
  assert datetime.fromisoformat(n['source_at'])<=datetime.fromisoformat(s['clock'])
  assert n['source_at']==bynative[n['id']]['source_at']
  if p.suffix=='.eml':
   msg=BytesParser(policy=policy.default).parsebytes(p.read_bytes())
   assert parsedate_to_datetime(msg['Date'])==datetime.fromisoformat(n['source_at'])
   attachments=list(msg.iter_attachments());assert len(attachments)==1
   child=next(x for x in s['native'] if x['id']==n['attachments'][0])
   assert attachments[0].get_payload(decode=True)==(P/child['file']).read_bytes()
   assert child['parent_id']==n['id']
  if p.suffix=='.pdf':
   b=p.read_bytes();assert b.startswith(b'%PDF-1.4') and b.endswith(b'%%EOF\n')
   xref=int(b.split(b'startxref\n')[1].splitlines()[0]);assert b[xref:xref+4]==b'xref'
   for off in re.findall(rb'(?m)^([0-9]{10}) 00000 n ',b):assert re.match(rb'[1-5] 0 obj',b[int(off):])
  if p.suffix=='.docx':
   with ZipFile(p) as z:
    assert z.testzip() is None
    for name in z.namelist():ET.fromstring(z.read(name))
  if p.suffix=='.ics':assert p.read_text().startswith('BEGIN:VCALENDAR') and p.read_text().count('BEGIN:VEVENT')==1
 assert r['provenance']['predecessor_freeze_sha256']==EXPECTED_PREDECESSOR and r['provenance']['model_results_used_for_changes'] is False
 return dict(mail_sources=100,native_sources=10,mail_questions=40,native_questions=7,state_phases=9,state_questions=11,logical_mail_tasks=39,logical_native_tasks=9,mail_recognition=37,all_recognition=46,known_deadlines=35,unknown_deadlines=10,ambiguous_deadlines=1,date_only_deadlines=len(deadline['known_date_only_task_ids']),datetime_deadlines=len(deadline['known_datetime_task_ids']),sent_mails=sum(m['folder']=='Sent' for m in c['mails']))
args=argparse.ArgumentParser();args.add_argument('--verify-freeze',action='store_true');opt=args.parse_args()
data=[read(P,n) for n in ['catalog.json','sources.json','reference.json','state-phases.json']]
counts=validate(*data)
faults=[
 ('T25 removed from recognition',lambda x:x[2]['coverage_denominator']['current_action_recognition']['all_task_ids'].remove('T25')),
 ('T31 presented as confirmed owner',lambda x:next(t for t in x[2]['task_dimensions'] if t['task_id']=='T31')['owner'].update(state='known_from_source')),
 ('T43 assigned to Jona',lambda x:next(t for t in x[2]['task_dimensions'] if t['task_id']=='T43')['owner'].update(value=x[1]['owner']['address'])),
 ('T46 duplicate from E06-07',lambda x:next(a for a in x[2]['source_annotations'] if a['source_id']=='E06-07')['tasks'].append(copy.deepcopy(next(t for a in x[2]['source_annotations'] for t in a['tasks'] if t['id']=='T46')))),
 ('T46 lost supporting evidence',lambda x:next(t for a in x[2]['source_annotations'] for t in a['tasks'] if t['id']=='T46').update(additional_evidence=[])),
 ('N03 wrong EML date',lambda x:next(n for n in x[1]['native'] if n['id']=='N03').update(source_at='2026-11-03T11:00:00+01:00')),
 ('NQ02 uses cancelled phase',lambda x:next(q for q in x[2]['native_questions'] if q['id']=='NQ02').update(phase='after_N06_ingested')),
 ('SQ11 missing cancellation evidence',lambda x:next(p for p in x[3]['phases'] if p['id']=='S09')['questions'][0].update(evidence=['N02'])),
 ('Original mail text changed',lambda x:x[1]['mails'][0].update(body='Changed synthetic original')),
 ('T45 invented due',lambda x:next(t for a in x[2]['source_annotations'] for t in a['tasks'] if t['id']=='T45').update(due='2026-11-05')),
]
for label,mutate in faults:
 altered=copy.deepcopy(data);mutate(altered)
 try:validate(*altered)
 except AssertionError:pass
 else:raise AssertionError('Validator accepted fault: '+label)
freeze_verified=False
if opt.verify_freeze:
 mf=read(P,'freeze.json');assert mf['predecessor_freeze_sha256']==EXPECTED_PREDECESSOR
 for f,h in mf['files'].items():assert digest(P/f)==h,f
 assert set(mf['files'])=={str(f.relative_to(P)) for f in P.rglob('*') if f.is_file() and f.name!='freeze.json'}
 freeze_verified=True
report=dict(validation='static_fixture_consistency_only_not_product_acceptance',status='passed',counts=counts,fault_checks_rejected=[label for label,_ in faults],original_mails_byte_preserved=100,native_files_byte_preserved=10,v1_frozen_hashes_verified=len(old['freeze.json']['files']),predecessor_freeze_sha256=EXPECTED_PREDECESSOR,v2_freeze_verified=freeze_verified,evaluation_model_calls=0)
output=BASE/('heldout-v2-static-validation-final.json' if opt.verify_freeze else 'heldout-v2-static-validation-prefreeze.json')
output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
